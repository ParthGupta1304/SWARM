"""Run-scoped sequencing and Dev3 event persistence shared by every actor."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from detect.contracts import Event, Request
from detect.store import EventStore, SQLiteEventStore


@dataclass(frozen=True)
class EventSlot:
    sequence: int
    round: int
    agent_id: str
    concurrency_group: str | None


class RunEvents:
    """One instance per run; reserve the whole burst before dispatching actions."""

    def __init__(
        self, store: EventStore, run_id: str, seed: int, jsonl_path: str | Path | None = None
    ):
        self.store, self.run_id, self.seed = store, run_id, seed
        self.jsonl_path = Path(jsonl_path) if jsonl_path is not None else None
        self._lock = RLock()
        existing = store.events(run_id)
        if any(event.seed != seed for event in existing):
            raise ValueError("cannot resume a run with a different seed")
        self._next = max((e.sequence for e in existing), default=-1) + 1

    def reserve(
        self, round_num: int, agent_ids: list[str], *, concurrent: bool = False
    ) -> list[EventSlot]:
        if len(set(agent_ids)) != len(agent_ids):
            raise ValueError("a burst requires distinct actors")
        with self._lock:
            group = (
                f"{self.run_id}:burst:{self._next}" if concurrent and len(agent_ids) > 1 else None
            )
            slots = [
                EventSlot(self._next + i, round_num, actor, group)
                for i, actor in enumerate(agent_ids)
            ]
            self._next += len(slots)
            return slots

    def record(
        self,
        slot: EventSlot,
        *,
        role: str,
        tool: str,
        request: Request,
        response_status: int | None,
        response_body: str,
        latency_ms: float,
        tokens_used: int,
        error: str | None = None,
    ) -> Event:
        event = Event(
            run_id=self.run_id,
            seed=self.seed,
            round=slot.round,
            sequence=slot.sequence,
            agent_id=slot.agent_id,
            role=role,
            tool=tool,
            request=request,
            response_status=response_status,
            response_body_hash=hashlib.sha256(response_body.encode()).hexdigest(),
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            concurrency_group=slot.concurrency_group,
            error=error,
        )
        with self._lock:
            self.store.append(event)
            if self.jsonl_path is not None:
                self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
                with self.jsonl_path.open("a", encoding="utf-8") as output:
                    output.write(event.model_dump_json() + "\n")
        return event


_DEFAULTS: dict[str, RunEvents] = {}
_DEFAULT_LOCK = RLock()


def default_events(run_id: str, seed: int) -> RunEvents:
    with _DEFAULT_LOCK:
        if run_id not in _DEFAULTS:
            _DEFAULTS[run_id] = RunEvents(
                SQLiteEventStore(os.environ.get("SWARMTEST_EVENTS_DB", "swarmtest_events.sqlite3")),
                run_id,
                seed,
                os.environ.get("SWARMTEST_EVENTS_FILE", "swarmtest_events.jsonl"),
            )
        events = _DEFAULTS[run_id]
        if events.seed != seed:
            raise ValueError("run seed changed")
        return events


def log_event(
    run_id: str,
    seed: int,
    round_num: int,
    agent_id: str,
    role: str,
    tool: str,
    request: Request | dict,
    response_status: int | None,
    response_body: str,
    latency_ms: float,
    tokens_used: int,
) -> dict:
    """Serial compatibility entry point; request must be a Dev3 Request, not tool args."""
    request = request if isinstance(request, Request) else Request.model_validate(request)
    recorder = default_events(run_id, seed)
    slot = recorder.reserve(round_num, [agent_id])[0]
    return recorder.record(
        slot,
        role=role,
        tool=tool,
        request=request,
        response_status=response_status,
        response_body=response_body,
        latency_ms=latency_ms,
        tokens_used=tokens_used,
        error="transport failure" if response_status is None else None,
    ).model_dump(mode="json")
