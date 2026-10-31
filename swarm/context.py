"""Bounded, deterministic model context; raw requests/results remain in events."""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ContextPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    recent_turns: int = Field(default=2, ge=1, le=8)
    memory_bytes: int = Field(default=6144, ge=512, le=65536)
    result_bytes: int = Field(default=2048, ge=256, le=16384)
    idle_read_limit: int = Field(default=4, ge=0)
    invalid_decision_limit: int = Field(default=3, ge=0)
    failure_hints: bool = True


def stable_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(value) -> str:
    return hashlib.sha256(stable_json(value).encode()).hexdigest()


_IMPORTANT = {
    "id",
    "order_id",
    "item_id",
    "buyer_id",
    "seller_id",
    "user_id",
    "author_id",
    "blocked_id",
    "blocker_id",
    "status",
    "error",
    "detail",
    "quantity",
    "stock",
    "price",
    "total",
    "balance",
    "rating",
    "fulfilled",
    "refund",
    "discount",
    "code",
}


def _project(value, depth=0):
    if depth > 5:
        return "[omitted: nesting]"
    if isinstance(value, dict):
        keys = sorted(value, key=lambda key: (key not in _IMPORTANT, key))
        result = {key: _project(value[key], depth + 1) for key in keys[:24]}
        if len(keys) > 24:
            result["_omitted_fields"] = len(keys) - 24
        return result
    if isinstance(value, list):
        result = [_project(item, depth + 1) for item in value[:12]]
        if len(value) > 12:
            result.append({"_omitted_items": len(value) - 12})
        return result
    if isinstance(value, str) and len(value) > 192:
        return value[:192] + "[omitted]"
    return value


def bounded_value(value, limit: int):
    """Keep JSON valid and omissions explicit, including for unusual response shapes."""
    if len(stable_json(value).encode()) <= limit:
        return value
    result = _project(value)
    # Prefer complete newest resource rows over an invalid sliced JSON document.
    if isinstance(result, list):
        kept = []
        for item in result:
            trial = {"items": [*kept, item], "_omitted": True}
            if len(stable_json(trial).encode()) > limit:
                break
            kept.append(item)
        if kept:
            return {"items": kept, "_omitted": True}
    if isinstance(result, dict):
        kept = {"_omitted": True}
        for key in sorted(result, key=lambda key: (key not in _IMPORTANT, key)):
            trial = {**kept, key: result[key]}
            if len(stable_json(trial).encode()) <= limit:
                kept = trial
        if len(kept) > 1:
            return kept
    # JSON escaping may expand a string; size the fallback by serialized bytes.
    preview = stable_json(result)
    while len(stable_json({"_omitted": True, "preview": preview}).encode()) > limit:
        preview = preview[: len(preview) // 2]
    return {"_omitted": True, "preview": preview}


class CompactContext:
    def __init__(self, policy: ContextPolicy):
        self.policy = policy
        self.turns: list[tuple[str, list[dict]]] = []
        self.facts: OrderedDict[str, dict] = OrderedDict()
        self.compactions = 0
        self.observations: OrderedDict[str, dict] = OrderedDict()
        self.notices: OrderedDict[str, dict] = OrderedDict()
        self.read_key = None
        self.read_count = 0
        self.failure_key = None
        self.failure_count = 0
        self.redirections = 0
        self.hint = ""

    def _remember(self, store, key, value):
        previous = store.pop(key, None)
        if previous and previous.get("value") == value:
            count = min(previous["count"] + 1, 999)
        else:
            count = 1
        store[key] = {"count": count, "value": value}
        while len(stable_json(list(store.values())).encode()) > self.policy.memory_bytes:
            store.popitem(last=False)

    def action(self, tool, request, status, body, turn):
        key = fingerprint([tool, request.method, request.path, request.query, request.json_body])
        try:
            result = json.loads(body)
        except (ValueError, TypeError):
            result = body
        value = bounded_value(
            {
                "operation": tool,
                "path": request.path,
                "arguments": request.json_body,
                "query": request.query,
                "status": status,
                "result": bounded_value(result, self.policy.result_bytes // 2),
            },
            self.policy.result_bytes,
        )
        self._remember(self.facts, key, value)
        self.turns.append((key, turn))
        if len(self.turns) > self.policy.recent_turns:
            self.turns.pop(0)
            self.compactions += 1
        if request.method in {"GET", "HEAD"}:
            self.failure_key, self.failure_count = None, 0
            read_key = fingerprint([key, status, body])
            self.read_count = self.read_count + 1 if read_key == self.read_key else 1
            self.read_key = read_key
            if self.policy.idle_read_limit and self.read_count == 2:
                self.redirections += 1
                self.hint = "This read is unchanged. Try another resource or an unexplored action."
        else:
            failure_key = fingerprint([key, status, body])
            previous = self.failure_count if failure_key == self.failure_key else 0
            self.reset_idle()
            if self.policy.failure_hints and status is not None and status >= 400:
                self.failure_key, self.failure_count = failure_key, previous + 1
                if self.failure_count >= 2:
                    if self.failure_count == 2:
                        self.redirections += 1
                    self.hint = (
                        "This request failed identically again. Try another resource/input "
                        "or coordinate a state change. Race-sensitive retries remain allowed."
                    )

    def reset_idle(self):
        self.read_key, self.read_count, self.hint = None, 0, ""
        self.failure_key, self.failure_count = None, 0

    def observe(self, observation):
        # Replace older state for the same operation/resource instead of growing history.
        request = observation.get("request", {})
        scope = {k: v for k, v in request.items() if k.endswith("_id") or k in {"id", "code"}}
        key = fingerprint([observation.get("operation"), scope, observation.get("notice")])
        self._remember(self.observations, key, bounded_value(observation, self.policy.result_bytes))

    def notice(self, notice):
        self._remember(self.notices, fingerprint(notice), notice)

    def snapshot(self):
        recent = {key for key, _ in self.turns}
        result = {
            "facts": [v for k, v in self.facts.items() if k not in recent],
            "observations": list(self.observations.values()),
            "verified_findings": list(self.notices.values()),
        }
        # Three independently bounded stores must also fit one combined memory bound.
        for name in ("facts", "observations", "verified_findings"):
            while len(stable_json(result).encode()) > self.policy.memory_bytes and result[name]:
                result[name].pop(0)
        return result

    def messages(self):
        snapshot = self.snapshot()
        result = []
        if any(snapshot.values()):
            result.append({"role": "user", "content": "Local memory: " + stable_json(snapshot)})
        if self.hint:
            result.append({"role": "user", "content": self.hint})
        return [*result, *[message for _, turn in self.turns for message in turn]]

    def save(self, directory: Path, agent_id: str, round_num: int, completed_actions: int):
        directory = directory / f"round-{round_num:04d}"
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"{fingerprint(agent_id)[:24]}.json"
        payload = {
            "agent_id": agent_id,
            "round": round_num,
            "completed_actions": completed_actions,
            "memory": self.snapshot(),
            "recent_turns": [turn for _, turn in self.turns],
        }
        temp = destination.with_suffix(".tmp")
        temp.write_text(stable_json(payload), encoding="utf-8")
        temp.replace(destination)
