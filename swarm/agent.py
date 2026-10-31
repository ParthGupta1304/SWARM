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
from swarm.context import CompactContext, ContextPolicy, bounded_value, stable_json
from swarm.events import EventSlot, RunEvents, default_events
from swarm.provider import completion_with_headers, is_groq_cache


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
        context_policy: ContextPolicy | None = None,
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

        def compact_schema(value):
            if isinstance(value, dict):
                return {
                    k: compact_schema(v)
                    for k, v in value.items()
                    if not (k == "title" and isinstance(v, str))
                }
            if isinstance(value, list):
                return [compact_schema(v) for v in value]
            return value

        self.tool_defs = compact_schema(self.tool_defs)
        for tool in self.tool_defs:
            function = tool["function"]
            if (
                function.get("description", "").strip().lower().replace(" ", "_")
                == function["name"]
            ):
                function.pop("description", None)
        self.tool_defs.sort(key=lambda tool: tool["function"]["name"])
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
        self.context = CompactContext(context_policy or ContextPolicy())
        self.step = self.tokens_used = self.score = 0
        self.total_tool_calls = self.invalid_tool_calls = 0
        self.used_fallback = self.done = self.stopped = False
        self.error: str | None = None
        self._invalid_streak = 0
        self.stop_reason: str | None = None
        self.prompt_bytes = self.max_prompt_bytes = 0
        self.pacer = None
        self.score_unit = "objective points"
        self.provider_receipts = []
        self.cancelled = None

    def _system_prompt(self) -> str:
        return (
            "Test this authorized local Bazaar sandbox; account setup is complete. "
            "Call exactly ONE tool per turn. Use observed results; omitted data is unknown. "
            "Explore beyond known findings. "
            'Without native tools return {"tool":"name","arguments":{}}. '
            f"Role: {self.role}."
        )

    def messages(self) -> list[dict]:
        return [
            {"role": "system", "content": self._system_prompt()},
            {
                "role": "user",
                "content": "Actor state: "
                + stable_json(
                    {
                        "account_id": self.seeded_user_id,
                        "completed_actions": self.step,
                        "objective": self.objective,
                        "score": self.score_desc,
                    }
                ),
            },
            *self.history,
        ]

    def _cancelled(self):
        return bool(
            (self.cancelled and self.cancelled())
            or self.budget.uncertain
            or (self.budget.parent and self.budget.parent.uncertain)
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
        size = len(stable_json({"messages": messages, "tools": tools}).encode())
        self.prompt_bytes = size
        self.max_prompt_bytes = max(size, self.max_prompt_bytes)
        kwargs = {"model": self.model, "messages": messages, "max_tokens": cap, "seed": self.seed}
        if tools:
            kwargs.update(tools=tools, tool_choice="auto", parallel_tool_calls=False)
        groq_cache = is_groq_cache(self.client.base_url, self.model)
        if groq_cache:
            kwargs["extra_body"] = {"reasoning_effort": "low"}
            if tools:
                kwargs["extra_body"]["disable_tool_validation"] = True
        if self.pacer:
            # Rough tokenizer estimate is for rate pacing only, never cost admission.
            estimate = len(json.dumps(messages + (tools or [])).encode()) // 3 + 128
            try:
                rate_reservation = self.pacer.wait(estimate, cap, self._cancelled)
            except BudgetExhausted:
                self.budget.release(reservation)
                raise
        if self._cancelled():
            self.budget.release(reservation)
            if self.pacer:
                self.pacer.finish(rate_reservation, 0)
            raise BudgetExhausted("Run stopped before provider dispatch")
        try:
            response, headers = completion_with_headers(self.client, kwargs)
        except Exception as exc:
            self.budget.fail(reservation)
            if self.pacer:
                self.pacer.observe(getattr(getattr(exc, "response", None), "headers", {}))
            body = getattr(exc, "body", {})
            details = body.get("error", body) if isinstance(body, dict) else {}
            code = (
                str(details.get("code", "unspecified"))
                if isinstance(details, dict)
                else "unspecified"
            )
            code = code if code.replace("_", "").isalnum() else "unspecified"
            raise BudgetAccountingError(
                f"Provider {type(exc).__name__} "
                f"HTTP {getattr(exc, 'status_code', 'unknown')} ({code}); "
                "usage is unknown"
            ) from None
        tokens = self.budget.finish(reservation, response.usage)
        if self.pacer:
            from swarm.budget import usage_counts

            cached = usage_counts(response.usage).cached if groq_cache else 0
            self.pacer.finish(rate_reservation, tokens - cached)
            self.pacer.observe(headers)
        self.provider_receipts.append(
            {
                "id": response.id,
                "model": response.model,
                "tokens": tokens,
                "system_fingerprint": response.system_fingerprint,
            }
        )
        self.tokens_used += tokens
        return response, tokens

    def _append_turn(self, messages: list[dict]) -> None:
        self.history.extend(messages)

    def reset_idle(self):
        self.context.reset_idle()
        if self.context.policy.enabled:
            self.history = self.context.messages()

    def observe(self, events) -> None:
        """Share account-local observations and public marketplace notices only."""
        observations = []
        for event in events:
            if event.agent_id == self.agent_id:
                continue
            body = event.request.json_body if isinstance(event.request.json_body, dict) else {}
            same_account = body.get("user_id") == self.seeded_user_id
            blocked = event.tool == "block_user" and body.get("blocked_id") == self.seeded_user_id
            if same_account or blocked or event.tool == "create_listing":
                observations.append(
                    {
                        "operation": event.tool,
                        "request": body,
                        "status": event.response_status,
                        "result": event.response_json,
                    }
                )
            elif event.tool == "checkout" and "list_sales" in self.tool_names:
                observations.append(
                    {"notice": "A purchase completed; inspect your sales for orders to fulfil."}
                )
        if observations:
            if self.context.policy.enabled:
                for observation in observations:
                    self.context.observe(observation)
                self.history = self.context.messages()
                return
            self._append_turn(
                [
                    {
                        "role": "user",
                        "content": "Recent marketplace observations: "
                        + json.dumps(observations[-8:]),
                    }
                ]
            )

    def known_finding(self, finding) -> None:
        if not self.context.policy.enabled or not finding.verified:
            return
        operations = []
        for step in finding.minimal_repro_sequence.steps:
            for action in step.actions:
                if action.agent_id != self.agent_id:
                    continue
                body = action.request.json_body
                resources = (
                    {key: value for key, value in body.items() if key.endswith("_id")}
                    if isinstance(body, dict)
                    else {}
                )
                operation = {
                    "method": action.request.method,
                    "path": action.request.path,
                    "resources": resources,
                }
                if operation not in operations:
                    operations.append(operation)
        if operations:
            self.context.notice(
                {
                    "verified_operations": operations[:4],
                    "hint": "Already reproduced; explore another scenario.",
                }
            )
            self.history = self.context.messages()

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
        policy = self.context.policy
        if policy.idle_read_limit and self.context.read_count >= policy.idle_read_limit:
            self.stopped, self.stop_reason = True, "unchanged_reads"
            return None
        try:
            response, tokens = self._model_call(self.messages())
        except BudgetExhausted as exc:
            self.stopped, self.stop_reason = True, str(exc)
            return None
        except BudgetAccountingError as exc:
            self.error, self.stopped, self.stop_reason = str(exc), True, "unknown_usage"
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
                self._invalid_streak = 0
                return Decision(*action, request, tokens, response.choices[0].message)
            except (ValueError, TypeError, KeyError, ValidationError):
                self.invalid_tool_calls += 1
        self._invalid_streak += 1
        if policy.invalid_decision_limit and self._invalid_streak >= policy.invalid_decision_limit:
            self.stopped, self.stop_reason = True, "invalid_decisions"
        correction = [
            {"role": "assistant", "content": "Invalid tool decision."},
            {
                "role": "user",
                "content": "Call exactly one permitted tool with valid arguments.",
            },
        ]
        if policy.enabled:
            self.history = [*self.context.messages(), *correction]
        else:
            self._append_turn(correction)
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
        visible_body = body
        if self.context.policy.enabled:
            try:
                result = json.loads(body)
            except (ValueError, TypeError):
                result = body
            visible_body = stable_json(bounded_value(result, self.context.policy.result_bytes))
        if message.tool_calls:
            call = message.tool_calls[0]
            turn = [
                {
                    "role": "assistant",
                    "content": None if self.context.policy.enabled else message.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": stable_json(
                                    bounded_value(
                                        json.loads(call.function.arguments),
                                        self.context.policy.result_bytes,
                                    )
                                )
                                if self.context.policy.enabled
                                else call.function.arguments,
                            },
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": call.id, "content": visible_body},
            ]
        else:
            turn = [
                {
                    "role": "assistant",
                    "content": stable_json(
                        {
                            "tool": decision.tool,
                            "arguments": bounded_value(
                                decision.arguments, self.context.policy.result_bytes
                            ),
                        }
                    )
                    if self.context.policy.enabled
                    else message.content,
                },
                {"role": "user", "content": f"HTTP {status}: {visible_body}"},
            ]
        if self.context.policy.enabled:
            self.context.action(decision.tool, request, status, body, turn)
            self.history = self.context.messages()
        else:
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
            "score_unit": self.score_unit,
            "done": self.done,
            "total_tool_calls": self.total_tool_calls,
            "invalid_tool_calls": self.invalid_tool_calls,
            "invalid_rate": self.invalid_tool_calls / self.total_tool_calls
            if self.total_tool_calls
            else 0.0,
            "used_json_fallback": self.used_fallback,
            "error": self.error,
            "stop_reason": self.stop_reason,
            "efficiency": {
                **(self.budget.summary() if self.budget else {}),
                "context_bytes": len(stable_json(self.history).encode()),
                "last_prompt_bytes": self.prompt_bytes,
                "max_prompt_bytes": self.max_prompt_bytes,
                "compactions": self.context.compactions,
                "repeat_redirections": self.context.redirections,
            },
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
