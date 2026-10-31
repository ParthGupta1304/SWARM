"""One actor's bounded model decisions and replayable HTTP actions."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import openai
import requests
from jsonschema.exceptions import ValidationError

from adapters.openapi import OpenAPIAdapter
from detect.contracts import Event, Request
from swarm.budget import BudgetAccountingError, BudgetExhausted, TokenBudget
from swarm.events import EventSlot, RunEvents, default_events

MEMORY_SUMMARY_INTERVAL = 8
MEMORY_KEEP_RECENT = 4


def _extract_json(text: str) -> dict | None:
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                value, _ = decoder.raw_decode(text[i:])
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                continue
    return None


@dataclass
class Decision:
    tool: str
    arguments: dict[str, Any]
    request: Request
    tokens: int
    message: Any


class AgentLoop:
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
        tool_definitions: list[dict] | None = None,
        adapter: OpenAPIAdapter | None = None,
        events: RunEvents | None = None,
        budget: TokenBudget | None = None,
        completion_tool: str | None = "checkout",
        seeded_user_id: int | None = None,
        fixed_arguments: dict[str, Any] | None = None,
    ):
        self.agent_id, self.role, self.objective = agent_id, role, objective
        self.score_desc, self.app_base_url = score_desc, app_base_url.rstrip("/")
        self.run_id, self.seed, self.model = run_id, seed, model
        self.adapter = adapter or OpenAPIAdapter(
            Path(__file__).parent.parent / "openapi.json", app_base_url
        )
        self.tool_defs = (
            tool_definitions
            if tool_definitions is not None
            else self.adapter.get_tool_definitions(
                sorted(self.adapter.get_tool_names() - {"register", "login", "health"})
            )
        )
        self.seeded_user_id = seeded_user_id
        self.fixed_arguments = fixed_arguments or {}
        for tool in self.tool_defs:
            schema = tool["function"]["parameters"]
            for key in self.fixed_arguments:
                schema.get("properties", {}).pop(key, None)
                if key in schema.get("required", []):
                    schema["required"].remove(key)
        self.tool_names = {tool["function"]["name"] for tool in self.tool_defs}
        if not self.tool_names or not self.tool_names <= self.adapter.get_tool_names():
            raise ValueError("actor tools must be a nonempty subset of adapter operations")
        if self.tool_names & {"register", "login"}:
            raise ValueError("authentication is runtime setup, not a stored model action")
        self.client = openai.OpenAI(
            base_url=provider_base_url, api_key=api_key or "ollama", max_retries=0, timeout=30
        )
        self.events = events or default_events(run_id, seed)
        if (self.events.run_id, self.events.seed) != (run_id, seed):
            raise ValueError("actor and event context run/seed differ")
        self.budget = budget
        self.completion_tool = completion_tool
        self.auth_token: str | None = None
        digest = hashlib.sha256(f"{run_id}:{agent_id}".encode()).hexdigest()[:24]
        self.username, self.password = f"swarm_{digest}", secrets.token_urlsafe(24)
        self.history: list[dict] = []
        self._turns: list[list[dict]] = []
        self.step = self.tokens_used = self.score = 0
        self.total_tool_calls = self.invalid_tool_calls = 0
        self.used_fallback = self.done = self.stopped = False
        self.error: str | None = None
        self._summary_at = -1

    def _system_prompt(self) -> str:
        return (
            f"You are a user of Bazaar. Role: {self.role}. Objective: {self.objective}. "
            f"Score: {self.score_desc}. Call exactly ONE available tool per turn. "
            'If native tools are unavailable, return {"tool":"name","arguments":{}}. '
            "Account setup is already complete. Follow the objective using tool results."
        )

    def _register_account(self) -> bool:
        if self.seeded_user_id is not None:
            try:
                response = requests.get(f"{self.app_base_url}/api/users", timeout=10)
                if response.status_code == 200 and any(
                    user["id"] == self.seeded_user_id for user in response.json()
                ):
                    return True
            except (requests.RequestException, ValueError, TypeError, KeyError):
                pass
            self.error = "seeded actor is missing from the target"
            return False
        if self.auth_token:
            return True
        credentials = {"username": self.username, "password": self.password}
        try:
            register = requests.post(
                f"{self.app_base_url}/register", json=credentials, timeout=10, allow_redirects=False
            )
            if register.status_code not in {200, 201, 409}:
                self.error = f"registration HTTP {register.status_code}"
                return False
            login = requests.post(
                f"{self.app_base_url}/login", json=credentials, timeout=10, allow_redirects=False
            )
            token = login.json().get("token") if login.status_code == 200 else None
            if not isinstance(token, str) or not token:
                self.error = f"login failed (HTTP {login.status_code})"
                return False
            self.auth_token = token
            return True
        except (requests.RequestException, ValueError):
            self.error = "account setup failed"
            return False

    def start(self) -> bool:
        if not self._register_account():
            self.stopped = True
            return False
        if not self.history:
            self.history = [{"role": "user", "content": "Start your objective."}]
        return True

    def _model_call(self, messages: list[dict], *, summary: bool = False):
        if self.budget is None:
            raise RuntimeError("a token budget is required before a model call")
        tools = None if summary else self.tool_defs
        reservation, cap = self.budget.reserve(messages, tools, 120 if summary else 512)
        kwargs = {"model": self.model, "messages": messages, "max_tokens": cap, "seed": self.seed}
        if tools:
            kwargs.update(tools=tools, tool_choice="auto", parallel_tool_calls=False)
        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception:
            self.budget.fail(reservation)
            raise BudgetAccountingError("model call failed; provider usage is unknown") from None
        tokens = self.budget.finish(reservation, response.usage)
        self.tokens_used += tokens
        return response, tokens

    def _append_turn(self, messages: list[dict]) -> None:
        self._turns.append(messages)
        self.history.extend(messages)

    def _maybe_summarise(self) -> None:
        if (
            self.step == 0
            or self.step % MEMORY_SUMMARY_INTERVAL
            or self._summary_at == self.step
            or len(self._turns) <= MEMORY_KEEP_RECENT
        ):
            return
        old = self._turns[:-MEMORY_KEEP_RECENT]
        response, _ = self._model_call(
            [
                {
                    "role": "system",
                    "content": "Summarise earlier actions and results in 3 sentences.",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        self.history[
                            : -sum(len(turn) for turn in self._turns[-MEMORY_KEEP_RECENT:])
                        ]
                    ),
                },
            ],
            summary=True,
        )
        self._turns = self._turns[len(old) :]
        self.history = [
            {
                "role": "user",
                "content": "Earlier actions: " + (response.choices[0].message.content or ""),
            },
            *[message for turn in self._turns for message in turn],
        ]
        self._summary_at = self.step

    def _extract_action(self, response) -> tuple[str, dict] | None:
        message = response.choices[0].message
        self.total_tool_calls += 1
        action = None
        if message.tool_calls:
            if len(message.tool_calls) == 1:
                call = message.tool_calls[0]
                try:
                    action = call.function.name, json.loads(call.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    pass
        elif message.content:
            data = _extract_json(message.content)
            if data:
                action = data.get("tool"), data.get("arguments", {})
                self.used_fallback = True
        if (
            action is None
            or not isinstance(action[0], str)
            or action[0] not in self.tool_names
            or not isinstance(action[1], dict)
        ):
            self.invalid_tool_calls += 1
            return None
        return action

    def decide(self) -> Decision | None:
        if self.done or self.stopped:
            return None
        try:
            self._maybe_summarise()
            response, tokens = self._model_call(
                [{"role": "system", "content": self._system_prompt()}, *self.history]
            )
        except BudgetExhausted:
            self.stopped = True
            return None
        except BudgetAccountingError as exc:
            self.error, self.stopped = str(exc), True
            return None
        action = self._extract_action(response)
        if action is not None:
            try:
                name, arguments = action
                properties = self.adapter.operations[name]["schema"]["properties"]
                arguments = {
                    **arguments,
                    **{
                        key: value
                        for key, value in self.fixed_arguments.items()
                        if key in properties
                    },
                }
                action = name, arguments
                request = self.adapter.prepare_request(*action)
                return Decision(*action, request, tokens, response.choices[0].message)
            except (ValueError, TypeError, KeyError, ValidationError):
                self.invalid_tool_calls += 1
        self._append_turn(
            [
                {"role": "assistant", "content": "Invalid tool decision."},
                {
                    "role": "user",
                    "content": "Call exactly one permitted tool with valid arguments.",
                },
            ]
        )
        return None

    def execute(self, decision: Decision, slot: EventSlot) -> Event:
        headers = {**decision.request.headers, "X-Swarm-Action": f"{self.run_id}:{slot.sequence}"}
        request = decision.request.model_copy(update={"headers": headers})
        status, body, latency = self.adapter.execute_request(request, self.auth_token or "")
        event = self.events.record(
            slot,
            role=self.role,
            tool=decision.tool,
            request=request,
            response_status=status,
            response_body=body,
            latency_ms=latency,
            tokens_used=decision.tokens,
            error="transport failure" if status is None else None,
        )
        message = decision.message
        if message.tool_calls:
            call = message.tool_calls[0]
            turn = [
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments,
                            },
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": call.id, "content": body},
            ]
        else:
            turn = [
                {"role": "assistant", "content": message.content},
                {"role": "user", "content": f"HTTP {status}: {body}"},
            ]
        self._append_turn(turn)
        self.step += 1
        if decision.tool == self.completion_tool and status is not None and 200 <= status < 300:
            self.score, self.done = 1, True
        return event

    def summary(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "steps": self.step,
            "tokens_used": self.tokens_used,
            "score": self.score,
            "done": self.done,
            "total_tool_calls": self.total_tool_calls,
            "invalid_tool_calls": self.invalid_tool_calls,
            "invalid_rate": self.invalid_tool_calls / self.total_tool_calls
            if self.total_tool_calls
            else 0.0,
            "used_json_fallback": self.used_fallback,
            "error": self.error,
        }

    def run(self, max_steps: int = 40, max_tokens: int = 60000) -> dict:
        if max_steps <= 0:
            raise ValueError("max_steps must be positive")
        self.budget = self.budget or TokenBudget(max_tokens)
        if self.start():
            for round_num in range(max_steps):
                if self.done or self.stopped:
                    break
                decision = self.decide()
                if decision is not None:
                    slot = self.events.reserve(round_num, [self.agent_id])[0]
                    self.execute(decision, slot)
        return self.summary()

    def close(self) -> None:
        self.client.close()
