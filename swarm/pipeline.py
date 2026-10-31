"""Connect completed runtime windows to Dev3 detection and independent replay."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence

from detect.contracts import Finding
from detect.findings import build_replay, capture_errors, finding_from_violation
from detect.invariants import SQLInvariant, SQLInvariantRunner, Violation
from swarm.runtime import RoundWindow
from verify import ReplayVerifier, apply_verification


class DetectionPipeline:
    def __init__(
        self,
        *,
        verifier: ReplayVerifier,
        live_base_url: str,
        runner: SQLInvariantRunner | None = None,
        invariants: Sequence[SQLInvariant] = (),
        bug_mapping: dict[str, str] | None = None,
        python_checks: Sequence[Callable[[RoundWindow], list[Violation]]] = (),
    ):
        replay_url = getattr(verifier.target, "base_url", None)
        if replay_url is None or replay_url.rstrip("/") == live_base_url.rstrip("/"):
            raise ValueError("pipeline requires a separate HTTP verifier target")
        if invariants and runner is None:
            raise ValueError("SQL invariants require a read-only runner")
        self.verifier, self.runner, self.invariants = verifier, runner, invariants
        self.bug_mapping = bug_mapping or {}
        self.python_checks = python_checks
        self._seen: set[tuple] = set()

    async def __call__(self, window: RoundWindow) -> list[Finding]:
        candidates = []
        if self.runner is not None:
            violations = await asyncio.to_thread(self.runner.scan, self.invariants)
            candidates.extend(finding_from_violation(v, window.events) for v in violations)
        for check in self.python_checks:
            violations = await asyncio.to_thread(check, window)
            candidates.extend(finding_from_violation(v, window.events) for v in violations)
        logged_keys = {
            row.get("action_key")
            for candidate in candidates
            if candidate.oracle_triggered.startswith("log:")
            for row in candidate.evidence
        }
        for error in capture_errors(window.latest):
            source = next(
                event for event in window.latest if event.event_id == error.evidence_events[0]
            )
            if source.request.headers.get("X-Swarm-Action") in logged_keys:
                continue
            # Error replay also needs prior setup actions, not just the final request.
            end = next(e.sequence for e in window.latest if e.event_id == error.evidence_events[0])
            # Keep the whole completed concurrent burst when it contains the failure.
            last = next(e for e in window.latest if e.sequence == end)
            causal = [
                e
                for e in window.events
                if e.sequence <= end
                or (last.concurrency_group and e.concurrency_group == last.concurrency_group)
            ]
            plan = build_replay(causal)
            data = error.model_dump()
            data.update(
                minimal_repro_sequence=plan,
                evidence_events=[a.event_id for s in plan.steps for a in s.actions],
                involved_agents=sorted({e.agent_id for e in causal}),
            )
            candidates.append(Finding.model_validate(data))
        results = []
        for finding in candidates:
            key = (finding.oracle_triggered, tuple(sorted(finding.involved_agents)))
            if key in self._seen:
                continue
            result = await self.verifier.verify(finding)
            finding = apply_verification(finding, result)
            if finding.verified:
                self._seen.add(key)
            if finding.oracle_triggered in self.bug_mapping:
                finding = finding.model_copy(
                    update={"mapped_bug_id": self.bug_mapping[finding.oracle_triggered]}
                )
            results.append(finding)
        return results
