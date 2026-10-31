"""Read-only SQL oracles: a query returns zero rows when the invariant holds."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from detect.contracts import JsonValue, Severity


@dataclass(frozen=True)
class SQLInvariant:
    id: str
    title: str
    query: str
    severity: Severity = "high"

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.title.strip() or not self.query.strip():
            raise ValueError("invariant id, title and query are required")


@dataclass(frozen=True)
class Violation:
    invariant: SQLInvariant
    rows: list[dict[str, JsonValue]]


class InvariantExecutionError(RuntimeError):
    pass


def load_invariants(path: str | Path) -> list[SQLInvariant]:
    """Read Dev1's SQL blocks headed by '-- invariant: ID | severity | title'."""
    checks = []
    header: tuple[str, str, str] | None = None
    lines: list[str] = []

    def finish() -> None:
        if header is not None:
            identifier, severity, title = header
            if severity not in {"critical", "high", "medium", "low", "info"}:
                raise ValueError(f"invalid severity for {identifier}: {severity}")
            checks.append(SQLInvariant(identifier, title, "\n".join(lines).strip(), severity))

    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("-- invariant:"):
            finish()
            fields = line.strip().removeprefix("-- invariant:").strip().split("|", 2)
            if len(fields) != 3:
                raise ValueError("invariant header must contain ID | severity | title")
            header = tuple(part.strip() for part in fields)
            lines = []
        elif header is not None:
            lines.append(line)
        elif line.strip() and not line.strip().startswith("--"):
            raise ValueError("SQL must follow an invariant header")
    finish()
    if not checks or len({c.id for c in checks}) != len(checks):
        raise ValueError("invariant file must contain checks with unique IDs")
    return checks


class SQLInvariantRunner:
    """Connection factory MUST return a fresh read-only DB-API connection.

    Each check gets its own connection, so one failed query cannot poison later
    transactions. Query errors raise; they never count as passing checks.
    """

    def __init__(self, connect_readonly: Callable[[], Any], *, max_rows: int = 100):
        if max_rows < 1:
            raise ValueError("max_rows must be positive")
        self._connect = connect_readonly
        self._max_rows = max_rows

    @classmethod
    def sqlite(cls, path: str | Path) -> SQLInvariantRunner:
        uri = Path(path).resolve().as_uri() + "?mode=ro"

        def connect() -> sqlite3.Connection:
            db = sqlite3.connect(uri, uri=True)
            db.execute("PRAGMA query_only=ON")
            return db

        return cls(connect)

    @classmethod
    def postgres(cls, dsn: str) -> SQLInvariantRunner:
        import psycopg

        def connect() -> Any:
            db = psycopg.connect(dsn, options="-c default_transaction_read_only=on")
            return db

        return cls(connect)

    def check(self, invariant: SQLInvariant) -> Violation | None:
        db = None
        try:
            db = self._connect()
            cursor = db.cursor()
            cursor.execute(invariant.query)
            if cursor.description is None:
                raise ValueError("an invariant must return rows, not modify the application")
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchmany(self._max_rows)
            evidence = [dict(zip(columns, row, strict=True)) for row in rows]
            # DB drivers may return Decimal, UUID, datetime, etc. Keep evidence JSON-safe.
            evidence = json.loads(json.dumps(evidence, default=str))
            return Violation(invariant, evidence) if evidence else None
        except Exception as exc:
            raise InvariantExecutionError(
                f"invariant {invariant.id} could not be evaluated"
            ) from exc
        finally:
            if db is not None:
                db.close()

    def scan(self, invariants: Sequence[SQLInvariant]) -> list[Violation]:
        return [violation for check in invariants if (violation := self.check(check)) is not None]
