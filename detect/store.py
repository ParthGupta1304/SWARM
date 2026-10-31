"""Durable append-only event storage, independent of the target application's DB."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from threading import RLock
from typing import Protocol

from detect.contracts import Event


class EventStore(Protocol):
    def append(self, event: Event) -> None: ...

    def events(self, run_id: str, *, after_sequence: int = -1) -> list[Event]: ...


class DuplicateEventError(ValueError):
    """An event ID or run sequence was already recorded; records cannot be replaced."""


class SQLiteEventStore:
    def __init__(self, path: str | Path):
        self._lock = RLock()
        self._db = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("""CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, sequence INTEGER NOT NULL,
            payload TEXT NOT NULL, UNIQUE (run_id, sequence))""")
        self._db.commit()

    def append(self, event: Event) -> None:
        with self._lock:
            try:
                with self._db:
                    self._db.execute(
                        "INSERT INTO events VALUES (?, ?, ?, ?)",
                        (event.event_id, event.run_id, event.sequence, event.model_dump_json()),
                    )
            except sqlite3.IntegrityError as exc:
                raise DuplicateEventError("event id or run sequence already exists") from exc

    def events(self, run_id: str, *, after_sequence: int = -1) -> list[Event]:
        with self._lock:
            rows = self._db.execute(
                "SELECT payload FROM events WHERE run_id=? AND sequence>? ORDER BY sequence",
                (run_id, after_sequence),
            ).fetchall()
        return [Event.model_validate_json(row[0]) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def __enter__(self) -> SQLiteEventStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class PostgresEventStore:
    """Uses its own swarmtest_events schema; does not reset or migrate Bazaar."""

    def __init__(self, dsn: str):
        import psycopg

        self._dsn = dsn
        self._driver = psycopg
        with psycopg.connect(dsn) as db:
            db.execute("CREATE SCHEMA IF NOT EXISTS swarmtest_events")
            db.execute("""CREATE TABLE IF NOT EXISTS swarmtest_events.events (
                event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, sequence BIGINT NOT NULL,
                payload JSONB NOT NULL, UNIQUE (run_id, sequence))""")

    def append(self, event: Event) -> None:
        try:
            with self._driver.connect(self._dsn) as db:
                db.execute(
                    "INSERT INTO swarmtest_events.events VALUES (%s, %s, %s, %s::jsonb)",
                    (event.event_id, event.run_id, event.sequence, event.model_dump_json()),
                )
        except self._driver.errors.UniqueViolation as exc:
            raise DuplicateEventError("event id or run sequence already exists") from exc

    def events(self, run_id: str, *, after_sequence: int = -1) -> list[Event]:
        with self._driver.connect(self._dsn) as db:
            rows = db.execute(
                """SELECT payload FROM swarmtest_events.events
                   WHERE run_id=%s AND sequence>%s ORDER BY sequence""",
                (run_id, after_sequence),
            ).fetchall()
        return [Event.model_validate(row[0]) for row in rows]


def export_jsonl(store: EventStore, run_id: str, path: str | Path) -> None:
    with Path(path).open("w", encoding="utf-8") as output:
        for event in store.events(run_id):
            output.write(event.model_dump_json() + "\n")


def read_jsonl(path: str | Path) -> Iterator[Event]:
    with Path(path).open(encoding="utf-8") as source:
        for line in source:
            if line.strip():
                yield Event.model_validate(json.loads(line))
