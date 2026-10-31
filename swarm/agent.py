"""
agent.py — Core agent loop for Swarmtest.

One AgentLoop instance = one simulated user persona running against the app.
The loop:
  1. Calls the LLM with the system prompt + conversation history + tool defs.
  2. Extracts a tool call (native function-calling, then JSON fallback).
  3. Executes the tool via HTTP.
  4. Logs the event.
  5. Adds the result to history and repeats.

Rolling memory: every MEMORY_SUMMARY_INTERVAL steps the older portion of
history is compressed into a short summary to keep the prompt small.
"""

import json
import time
import requests
import openai
from typing import Optional, Any, Callable

from swarm.events import log_event
from swarm.tools import TOOL_DEFINITIONS, TOOL_NAMES, execute_tool
from adapters.openapi import OpenAPIAdapter

# How often (in steps) to summarise old history.
MEMORY_SUMMARY_INTERVAL = 8
# How many recent message-pairs to keep verbatim after a summary.
MEMORY_KEEP_RECENT = 4


def _extract_json(text: str) -> Optional[dict]:
    """
    Find and parse the outermost JSON object in a string.
    Handles nested braces correctly.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


class AgentLoop:
    """
    Runs a single agent persona against the target app.

    Parameters
    ----------
    agent_id        : unique string (e.g. 'agent-1-casual-0')
    role            : persona role name (e.g. 'casual_buyer')
    objective       : plain-English task the agent must complete
    score_desc      : how the score is computed (shown in system prompt)
    provider_base_url: OpenAI-compatible endpoint (Ollama or Groq)
    model           : model name to request
    api_key         : API key ('ollama' for local, real key for Groq)
    app_base_url    : base URL of the target app (e.g. 'http://localhost:8001')
    run_id          : shared run identifier (all agents in one run share this)
    seed            : RNG seed for this run
    tool_definitions: list of OpenAI-format tool defs for this persona
    """

    def __init__(
        self,
        agent_id: str,
        role: str,
        objective: str,
        score_desc: str,
        provider_base_url: str,
        model: str,
        api_key: str,
        app_base_url: str,
        run_id: str,
        seed: int,
        tool_definitions: Optional[list[dict]] = None,
        adapter: Optional[OpenAPIAdapter] = None,
    ):
        self.agent_id = agent_id
        self.role = role
        self.objective = objective
        self.score_desc = score_desc
        self.app_base_url = app_base_url
        self.run_id = run_id
        self.seed = seed
        self.model = model
        self.adapter = adapter

        if tool_definitions is not None:
            self.tool_defs = tool_definitions
        elif self.adapter is not None:
            self.tool_defs = self.adapter.get_tool_definitions()
        else:
            self.tool_defs = TOOL_DEFINITIONS

        self.tool_names = {t["function"]["name"] for t in self.tool_defs}

        self.client = openai.OpenAI(
            base_url=provider_base_url,
            api_key=api_key if api_key and api_key != "NONE" else "ollama",
        )

        # State
        self.auth_token: Optional[str] = None
        self.history: list[dict] = []
        self.step: int = 0
        self.tokens_used: int = 0
        self.score: int = 0

        # Diagnostics
        self.total_tool_calls: int = 0
        self.invalid_tool_calls: int = 0
        self.used_fallback: bool = False

    # ── System prompt ─────────────────────────────────────────────────────────

    def _system_prompt(self) -> str:
        tool_names = ", ".join(t["function"]["name"] for t in self.tool_defs)
        return f"""You are a user of an online marketplace called Bazaar.

Role: {self.role}
Objective: {self.objective}
Score: {self.score_desc}

Available tools: {tool_names}

Rules:
- Call ONE tool per turn to make progress toward your objective.
- Observe tool outputs carefully and decide your next action based on the result.
- Conclude when your objective has been accomplished.

Fallback (only if you cannot call a tool natively):
Respond with EXACTLY this JSON on a single line, no other text:
{{"tool": "<tool_name>", "arguments": {{<key>: <value>}}}}"""

    # ── Registration ──────────────────────────────────────────────────────────

    def _register_account(self) -> bool:
        """Create a unique Bazaar account for this agent and store the token."""
        username = f"{self.role[:8]}_{self.agent_id[-6:]}"
        password = f"pw_{self.agent_id[-8:]}"

        try:
            r = requests.post(
                f"{self.app_base_url}/register",
                json={"username": username, "password": password},
                timeout=10,
            )
            if r.status_code not in (200, 201):
                print(f"[{self.agent_id}] Register failed {r.status_code}: {r.text}")
                return False

            r2 = requests.post(
                f"{self.app_base_url}/login",
                json={"username": username, "password": password},
                timeout=10,
            )
            if r2.status_code != 200:
                print(f"[{self.agent_id}] Login failed {r2.status_code}: {r2.text}")
                return False

            self.auth_token = r2.json().get("token")
            print(f"[{self.agent_id}] Registered as '{username}'")
            return True

        except requests.RequestException as exc:
            print(f"[{self.agent_id}] Registration error: {exc}")
            return False

    # ── Action extraction ─────────────────────────────────────────────────────

    def _extract_action(self, response) -> Optional[tuple[str, dict[str, Any]]]:
        """
        Extract (tool_name, arguments) from an LLM response.

        Path 1 — native tool calling: response.choices[0].message.tool_calls
        Path 2 — JSON fallback: parse {"tool": ..., "arguments": ...} from content

        Increments invalid_tool_calls if neither path yields a valid tool name.
        """
        msg = response.choices[0].message
        self.total_tool_calls += 1

        # Path 1: native tool call
        if msg.tool_calls:
            tc = msg.tool_calls[0]
            try:
                args = json.loads(tc.function.arguments)
                return tc.function.name, args
            except json.JSONDecodeError:
                print(f"[{self.agent_id}] Malformed tool arguments: {tc.function.arguments!r}")
                self.invalid_tool_calls += 1
                return None

        # Path 2: JSON in content
        if msg.content:
            content = msg.content.strip()
            data = _extract_json(content)
            if data:
                tool = data.get("tool")
                args = data.get("arguments", {})
                if isinstance(tool, str) and tool in self.tool_names:
                    if not self.used_fallback:
                        print(f"[{self.agent_id}] [NOTE] Using JSON fallback (model didn't use native tool calling)")
                        self.used_fallback = True
                    return tool, args if isinstance(args, dict) else {}

            print(f"[{self.agent_id}] No valid action in response: {content[:120]!r}")
            self.invalid_tool_calls += 1

        return None

    # ── Rolling memory ────────────────────────────────────────────────────────

    def _maybe_summarise(self):
        """Compress old history into a short summary every MEMORY_SUMMARY_INTERVAL steps."""
        # Keep at least MEMORY_KEEP_RECENT * 2 messages (each step = 2 messages)
        cutoff = MEMORY_KEEP_RECENT * 2
        if len(self.history) <= cutoff:
            return

        to_summarise = self.history[:-cutoff]
        try:
            r = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Summarise the agent's actions below in 2-3 sentences. Focus on what was found and done.",
                    },
                    {"role": "user", "content": json.dumps(to_summarise)},
                ],
                max_tokens=120,
            )
            summary = r.choices[0].message.content or "(no summary)"
        except Exception as exc:
            summary = "(summary failed)"
            print(f"[{self.agent_id}] History summarisation failed: {exc}")

        self.history = [
            {"role": "system", "content": f"[Earlier steps summary]: {summary}"},
            *self.history[-cutoff:],
        ]

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self, max_steps: int = 40, max_tokens: int = 60000) -> dict:
        """
        Run the agent until objective complete, budget exhausted, or repeated failures.
        Returns a summary dict for printing and benchmarking.
        """
        print(f"\n{'='*54}")
        print(f"  Agent : {self.agent_id}")
        print(f"  Role  : {self.role}")
        print(f"  Goal  : {self.objective}")
        print(f"{'='*54}")

        if not self._register_account():
            return {"agent_id": self.agent_id, "error": "registration failed"}

        self.history = [
            {"role": "user", "content": "Start your task. Begin by browsing available items."},
        ]

        done = False
        consecutive_failures = 0

        while self.step < max_steps and self.tokens_used < max_tokens and not done:

            # Summarise old history periodically
            if self.step > 0 and self.step % MEMORY_SUMMARY_INTERVAL == 0:
                self._maybe_summarise()

            messages = [
                {"role": "system", "content": self._system_prompt()},
                *self.history,
            ]

            # ── LLM call ──────────────────────────────────────────────────────
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=self.tool_defs,
                    tool_choice="auto",
                    max_tokens=512,
                )
            except Exception as exc:
                print(f"[{self.agent_id}] LLM error: {exc}")
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    print(f"[{self.agent_id}] 3 consecutive LLM failures — stopping.")
                    break
                time.sleep(1)
                continue

            usage = response.usage
            step_tokens = usage.total_tokens if usage else 0
            self.tokens_used += step_tokens

            # ── Extract action ────────────────────────────────────────────────
            action = self._extract_action(response)
            if action is None:
                consecutive_failures += 1
                # Feed back to model so it knows something went wrong
                raw_content = response.choices[0].message.content or ""
                if raw_content:
                    self.history.append({"role": "assistant", "content": raw_content})
                    self.history.append({
                        "role": "user",
                        "content": "Please call one of the available tools to continue.",
                    })
                if consecutive_failures >= 3:
                    print(f"[{self.agent_id}] 3 consecutive invalid responses — stopping.")
                    break
                continue

            consecutive_failures = 0
            tool_name, tool_args = action
            print(f"[{self.agent_id}] step {self.step+1:02d}  {tool_name}({tool_args})")

            # ── Execute tool ──────────────────────────────────────────────────
            if self.adapter is not None:
                status, body, latency = self.adapter.execute_tool(
                    tool_name, tool_args, self.auth_token or ""
                )
            else:
                status, body, latency = execute_tool(
                    tool_name, tool_args, self.auth_token or "", self.app_base_url
                )

            # ── Log event ─────────────────────────────────────────────────────
            log_event(
                run_id=self.run_id,
                seed=self.seed,
                round_num=self.step,
                agent_id=self.agent_id,
                role=self.role,
                tool=tool_name,
                request=tool_args,
                response_status=status,
                response_body=body,
                latency_ms=latency,
                tokens_used=step_tokens,
            )

            print(f"[{self.agent_id}]          → HTTP {status}  ({latency:.0f} ms)  {body[:80]}")

            # ── Update history ────────────────────────────────────────────────
            asst_msg = response.choices[0].message
            if asst_msg.tool_calls:
                # Native path: record tool_call + tool result
                self.history.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in asst_msg.tool_calls
                    ],
                })
                self.history.append({
                    "role": "tool",
                    "tool_call_id": asst_msg.tool_calls[0].id,
                    "content": body,
                })
            else:
                # Fallback path: plain assistant/user exchange
                self.history.append({"role": "assistant", "content": asst_msg.content})
                self.history.append({"role": "user", "content": f"Tool result (HTTP {status}): {body}"})

            # ── Check completion ──────────────────────────────────────────────
            if tool_name == "checkout" and status == 200:
                print(f"[{self.agent_id}] [OK] Checkout succeeded — objective complete!")
                self.score = 1
                done = True

            self.step += 1

        # ── Summary ───────────────────────────────────────────────────────────
        invalid_rate = (
            self.invalid_tool_calls / self.total_tool_calls
            if self.total_tool_calls > 0
            else 0.0
        )
        summary = {
            "agent_id": self.agent_id,
            "role": self.role,
            "steps": self.step,
            "tokens_used": self.tokens_used,
            "score": self.score,
            "done": done,
            "total_tool_calls": self.total_tool_calls,
            "invalid_tool_calls": self.invalid_tool_calls,
            "invalid_rate": round(invalid_rate, 3),
            "used_json_fallback": self.used_fallback,
        }
        print(f"\n[{self.agent_id}] Run finished → {summary}")
        return summary

