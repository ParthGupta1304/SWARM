"""Build conservative, unverified findings from a caller-supplied causal window."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import groupby

from detect.contracts import Event, Finding, ReplayAction, ReplayPlan, ReplayStep
from detect.invariants import Violation


def build_replay(events: Sequence[Event]) -> ReplayPlan:
    if not events:
        raise ValueError("a replay needs at least one event")
    ordered = sorted(events, key=lambda event: event.sequence)
    if len({(e.run_id, e.seed) for e in ordered}) != 1:
        raise ValueError("a causal window must belong to one run and seed")
    if len({e.sequence for e in ordered}) != len(ordered):
        raise ValueError("run sequence numbers must be unique")
    steps = []
    references = {}

    def action_for(e):
        bindings = {}
        for area in ("json_body", "query"):
            value = getattr(e.request, area)
            if isinstance(value, dict):
                for key, literal in value.items():
                    if key.endswith("_id") and (key, str(literal)) in references:
                        bindings[f"{area}.{key}"] = references[(key, str(literal))]
        parts = e.request.path.split("/")
        for index, part in enumerate(parts):
            key = {"orders": "order_id", "items": "item_id", "users": "user_id"}.get(
                parts[index - 1] if index else ""
            )
            if key and (key, part) in references:
                bindings[f"path.{index}"] = references[(key, part)]
        return ReplayAction(
            event_id=e.event_id,
            agent_id=e.agent_id,
            request=e.request,
            expected_status=e.response_status,
            bindings=bindings,
        )

    seen_groups: set[str] = set()
    for group, members in groupby(
        ordered,
        key=lambda e: (
            ("parallel", e.concurrency_group) if e.concurrency_group else ("serial", e.event_id)
        ),
    ):
        batch = list(members)
        if group[0] == "parallel":
            if group[1] in seen_groups:
                raise ValueError("a concurrency group must occupy contiguous run sequence numbers")
            seen_groups.add(group[1])
            if len({e.round for e in batch}) != 1:
                raise ValueError("a concurrency group cannot span rounds")
        steps.append(ReplayStep(actions=[action_for(e) for e in batch]))
        for e in batch:
            if (
                not isinstance(e.response_json, dict)
                or not e.response_status
                or e.response_status >= 300
            ):
                continue
            created_key = {
                "checkout": "order_id",
                "create_review": "review_id",
                "ask_question": "question_id",
            }.get(e.tool)
            for key, value in e.response_json.items():
                # Echoed fixture user/item IDs are not resource creation dependencies.
                if key == created_key:
                    references.setdefault((key, str(value)), {"event_id": e.event_id, "key": key})
            semantic = {"create_listing": "item_id", "create_user": "user_id"}.get(e.tool)
            if semantic and "id" in e.response_json:
                references[(semantic, str(e.response_json["id"]))] = {
                    "event_id": e.event_id,
                    "key": "id",
                }
    return ReplayPlan(seed=ordered[0].seed, steps=steps)


def finding_from_violation(violation: Violation, events: Sequence[Event]) -> Finding:
    plan = build_replay(events)
    agents = sorted({e.agent_id for e in events})
    return Finding(
        run_id=events[0].run_id,
        title=violation.invariant.title,
        severity=violation.invariant.severity,
        type="emergent" if len(agents) > 1 else "single-user",
        evidence_events=[a.event_id for step in plan.steps for a in step.actions],
        involved_agents=agents,
        minimal_repro_sequence=plan,
        oracle_triggered=violation.invariant.id,
        evidence=violation.rows,
    )


def capture_errors(events: Sequence[Event]) -> list[Finding]:
    """Capture observed 5xx and transport failures, pending independent replay."""
    findings = []
    for event in events:
        server_error = event.response_status is not None and event.response_status >= 500
        if not server_error and not event.error:
            continue
        code = f"http:{event.response_status}" if server_error else "transport:error"
        findings.append(
            Finding(
                run_id=event.run_id,
                title=f"{event.tool}: {code}",
                severity="high",
                type="single-user",
                evidence_events=[event.event_id],
                involved_agents=[event.agent_id],
                minimal_repro_sequence=build_replay([event]),
                oracle_triggered=code,
            )
        )
    return findings
