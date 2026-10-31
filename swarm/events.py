"""
events.py — Minimal event logger for Swarmtest.

Appends one JSON line per agent action to swarmtest_events.jsonl.
All field names match the PRD Appendix B 'Event' schema so Dev 3 can
drop in the real event store without changing callers.

Swap guide: replace the body of log_event() with a call to Dev 3's
EventStore.append() — the signature stays the same.
"""

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Written to the current working directory. Override by setting
# SWARMTEST_EVENTS_FILE before importing this module.
import os
_EVENTS_FILE = Path(os.environ.get("SWARMTEST_EVENTS_FILE", "swarmtest_events.jsonl"))


def log_event(
    run_id: str,
    seed: int,
    round_num: int,
    agent_id: str,
    role: str,
    tool: str,
    request: dict[str, Any],
    response_status: int,
    response_body: str,
    latency_ms: float,
    tokens_used: int,
) -> dict:
    """
    Log one agent action. Returns the event dict (useful for unit tests).

    Fields:
      run_id            — unique id for this swarm run
      seed              — RNG seed used for this run
      round_num         — agent step index (0-based)
      agent_id          — unique string id for the agent instance
      role              — persona role name (e.g. 'casual_buyer')
      tool              — tool name called (e.g. 'checkout')
      request           — arguments passed to the tool
      response_status   — HTTP status code returned by the app
      response_body     — raw response text (hashed for storage)
      latency_ms        — round-trip time in milliseconds
      tokens_used       — tokens consumed by this LLM call
    """
    event = {
        "run_id": run_id,
        "seed": seed,
        "round": round_num,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id,
        "role": role,
        "tool": tool,
        "request": request,
        "response_status": response_status,
        "response_body_hash": hashlib.sha256(response_body.encode()).hexdigest()[:16],
        "latency_ms": round(latency_ms, 2),
        "tokens_used": tokens_used,
    }
    with _EVENTS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
    return event

