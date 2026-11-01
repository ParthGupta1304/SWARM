"""Local MemoryStore implementation with Meko Phase 2 adapter."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Literal, Protocol

from dotenv import dotenv_values, find_dotenv
from pydantic import JsonValue

from detect.contracts import Finding
from verify.replay import ReplayVerifier, VerificationResult

logger = logging.getLogger("swarmtest.memory")
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


class MekoMemoryStore:
    """
    Decorator around LocalMemoryStore that publishes verified findings to Meko.
    Local database remains the primary source of truth for replays and regression checks.
    If Meko fails, a warning is logged and execution continues seamlessly.
    """

    def __init__(self, local_store: LocalMemoryStore, meko_client: Any = None):
        self._local = local_store
        self._meko = meko_client
        self.publication_errors: dict[str, str] = {}

    def save_finding(self, project: str, finding: Finding) -> None:
        # Local database is always the source of truth
        self._local.save_finding(project, finding)
        if self._meko:
            try:
                self._meko.publish_finding(finding)
                self.publication_errors.pop(finding.id, None)
                logger.info("Successfully published finding %s to Meko", finding.id)
            except Exception as exc:
                self.publication_errors[finding.id] = type(exc).__name__
                logger.warning(
                    "Meko publish_finding failed for %s (falling back to local): %s",
                    finding.id,
                    exc,
                )

    def recall_findings(self, project: str) -> list[Finding]:
        # Exhaustive recall always comes from local database
        return self._local.recall_findings(project)

    def save_agent_memory(self, project: str, agent_id: str, memory: dict[str, JsonValue]) -> None:
        self._local.save_agent_memory(project, agent_id, memory)

    def recall_agent_memory(self, project: str, agent_id: str) -> dict[str, JsonValue] | None:
        return self._local.recall_agent_memory(project, agent_id)

    def record_trace(self, project: str, trace: dict[str, JsonValue]) -> None:
        self._local.record_trace(project, trace)

    def traces(self, project: str) -> list[dict[str, JsonValue]]:
        return self._local.traces(project)

    def classify(
        self, project: str, finding: Finding, result: VerificationResult, *, run_id: str
    ) -> Classification:
        return self._local.classify(project, finding, result, run_id=run_id)

    def publish_run_summary(self, run_id: str, results: list[dict[str, str]]) -> None:
        if self._meko:
            try:
                self._meko.publish_run_summary(run_id, results)
                logger.info("Successfully published run summary %s to Meko", run_id)
            except Exception as exc:
                logger.warning(
                    "Meko publish_run_summary failed for %s (falling back to local): %s",
                    run_id,
                    exc,
                )

    def close(self) -> None:
        self._local.close()

    def __enter__(self) -> MekoMemoryStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def create_memory_store(
    config: dict[str, Any] | None = None,
    local_db_path: str | Path = "swarmtest_memory.sqlite3",
) -> MemoryStore:
    """
    Factory function returning MekoMemoryStore if configured and valid,
    falling back safely to LocalMemoryStore otherwise.
    """
    local = LocalMemoryStore(local_db_path)
    if not config:
        return local

    store_cfg = config.get("findings_store", {})
    if store_cfg.get("type") != "meko":
        return local

    api_key_env = store_cfg.get("api_key_env", "MEKO_API_KEY")
    datapack_id_env = store_cfg.get("datapack_id_env", "MEKO_DATAPACK_ID")
    mcp_url = store_cfg.get("mcp_url", "https://mcp.mekodata.ai/mcp")

    path = find_dotenv()
    local_values = dotenv_values(path) if path else {}

    def current(name):
        value = local_values.get(name) if name in local_values else os.getenv(name)
        return (value or "").strip()

    api_key = current(api_key_env)
    datapack_id = current(datapack_id_env)

    if not api_key or not datapack_id:
        logger.warning(
            "Meko credentials missing (env %s / %s not set). Falling back to local store.",
            api_key_env,
            datapack_id_env,
        )
        return local

    try:
        from memory.meko import MekoClient

        client = MekoClient(mcp_url=mcp_url, api_key=api_key, datapack_id=datapack_id)
        logger.info("Initialized MekoMemoryStore connected to datapack %s", datapack_id)
        return MekoMemoryStore(local_store=local, meko_client=client)
    except Exception as exc:
        logger.warning("Failed to initialize MekoClient: %s. Falling back to local store.", exc)
        return local


async def recheck_saved_findings(
    store: LocalMemoryStore | MekoMemoryStore,
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

    # Publish run summary to Meko if supported by store
    if hasattr(store, "publish_run_summary"):
        store.publish_run_summary(run_id, outcomes)

    return outcomes
