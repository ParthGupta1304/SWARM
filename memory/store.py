"""Local MemoryStore implementation; Meko is a pluggable Phase 2 adapter."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Literal, Protocol

from pydantic import JsonValue

from detect.contracts import Finding
from verify.replay import ReplayVerifier, VerificationResult

Classification = Literal["fixed", "still_failing", "regressed", "inconclusive"]


class MemoryStore(Protocol):
    def save_finding(self, project: str, finding: Finding) -> None: ...

    def recall_findings(self, project: str) -> list[Finding]: ...

    def save_agent_memory(
        self, project: str, agent_id: str, memory: dict[str, JsonValue]
    ) -> None: ...

    def recall_agent_memory(self, project: str, agent_id: str) -> dict[str, JsonValue] | None: ...

    def record_trace(self, project: str, trace: dict[str, JsonValue]) -> None: ...


class LocalMemoryStore:
    def __init__(self, path: str | Path):
        self._lock = RLock()
        self._db = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS findings (
                project TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY (project, id));
            CREATE TABLE IF NOT EXISTS agent_memories (
                project TEXT NOT NULL, agent_id TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY (project, agent_id));
            CREATE TABLE IF NOT EXISTS traces (
                id INTEGER PRIMARY KEY, project TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS checks (
                id INTEGER PRIMARY KEY, project TEXT NOT NULL, finding_id TEXT NOT NULL,
                run_id TEXT NOT NULL, classification TEXT NOT NULL, checked_at TEXT NOT NULL,
                UNIQUE (project, finding_id, run_id));
        """)

    def save_finding(self, project: str, finding: Finding) -> None:
        if not finding.verified:
            raise ValueError("only verified findings become saved regression checks")
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO findings VALUES (?, ?, ?) ON CONFLICT(project,id) "
                "DO UPDATE SET payload=excluded.payload",
                (project, finding.id, finding.model_dump_json()),
            )

    def recall_findings(self, project: str) -> list[Finding]:
        with self._lock:
            rows = self._db.execute(
                "SELECT payload FROM findings WHERE project=? ORDER BY id", (project,)
            ).fetchall()
        return [Finding.model_validate_json(row[0]) for row in rows]

    def save_agent_memory(self, project: str, agent_id: str, memory: dict[str, JsonValue]) -> None:
        payload = json.dumps(memory, allow_nan=False)
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO agent_memories VALUES (?, ?, ?) "
                "ON CONFLICT(project,agent_id) DO UPDATE SET payload=excluded.payload",
                (project, agent_id, payload),
            )

    def recall_agent_memory(self, project: str, agent_id: str) -> dict[str, JsonValue] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT payload FROM agent_memories WHERE project=? AND agent_id=?",
                (project, agent_id),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def record_trace(self, project: str, trace: dict[str, JsonValue]) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO traces(project,payload) VALUES (?, ?)",
                (project, json.dumps(trace, allow_nan=False)),
            )

    def traces(self, project: str) -> list[dict[str, JsonValue]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT payload FROM traces WHERE project=? ORDER BY id", (project,)
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def classify(
        self, project: str, finding: Finding, result: VerificationResult, *, run_id: str
    ) -> Classification:
        """A failed oracle/reset/execution is inconclusive, never a claimed fix."""
        if finding.id != result.finding_id:
            raise ValueError("verification belongs to a different finding")
        with self._lock, self._db:
            saved = self._db.execute(
                "SELECT 1 FROM findings WHERE project=? AND id=?", (project, finding.id)
            ).fetchone()
            if not saved:
                raise ValueError("save the original verified finding before classifying")
            previous = self._db.execute(
                "SELECT classification FROM checks WHERE project=? AND finding_id=? "
                "AND classification != 'inconclusive' ORDER BY id DESC LIMIT 1",
                (project, finding.id),
            ).fetchone()
            if result.status == "error":
                classification: Classification = "inconclusive"
            elif result.status == "not_reproduced":
                classification = "fixed"
            else:
                classification = (
                    "regressed"
                    if previous and previous[0] == "fixed"
                    else (
                        "regressed" if previous and previous[0] == "regressed" else "still_failing"
                    )
                )
            self._db.execute(
                "INSERT INTO checks(project,finding_id,run_id,classification,checked_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (project, finding.id, run_id, classification, datetime.now(UTC).isoformat()),
            )
        return classification

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def __enter__(self) -> LocalMemoryStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


async def recheck_saved_findings(
    store: LocalMemoryStore,
    project: str,
    verifier: ReplayVerifier,
    *,
    run_id: str,
) -> Sequence[dict[str, str]]:
    """Run saved checks before Dev2 spends the remaining budget on exploration."""
    outcomes = []
    for finding in store.recall_findings(project):
        result = await verifier.verify(finding)
        classification = store.classify(project, finding, result, run_id=run_id)
        outcomes.append({"finding_id": finding.id, "classification": classification})
    return outcomes
