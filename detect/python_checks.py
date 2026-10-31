"""Python response checks and sanitized exception-log evidence."""

from collections.abc import Sequence

from detect.contracts import Event
from detect.invariants import SQLInvariant, Violation


def check_response_contract(events: Sequence[Event]) -> list[Violation]:
    """A redirect from an API write must not masquerade as a successful action."""
    rows = [
        {"event_id": e.event_id, "status": e.response_status, "path": e.request.path}
        for e in events
        if e.request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and e.response_status is not None
        and 300 <= e.response_status < 400
    ]
    if not rows:
        return []
    return [
        Violation(
            SQLInvariant(
                "python:write_redirect",
                "API write unexpectedly redirects",
                "-- Python response contract",
                "medium",
            ),
            rows,
        )
    ]


def check_exception_logs(events: Sequence[Event], read_logs) -> list[Violation]:
    """Correlate exception metadata with this exact completed action window."""
    keys = {e.request.headers.get("X-Swarm-Action") for e in events}
    rows = [row for row in read_logs() if row["action_key"] in keys]
    groups: dict[str, list[dict]] = {}
    for row in rows:
        oracle = f"log:{row['error_class']}:{row['method']}:{row['path']}"
        groups.setdefault(oracle, []).append(row)
    return [
        Violation(
            SQLInvariant(
                key,
                "Application exception: " + values[0]["error_class"],
                "-- Python exception log correlation",
                "high",
            ),
            values,
        )
        for key, values in groups.items()
    ]
