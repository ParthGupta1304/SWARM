"""Replay recorded actions on a disposable seeded target without LLM calls."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Sequence
from hashlib import sha256
from typing import Literal, Protocol
from urllib.parse import urlsplit

import httpx
from pydantic import Field, model_validator

from detect.contracts import Contract, Finding, ReplayAction, ReplayPlan


class ActionResult(Contract):
    event_id: str
    status_code: int = Field(ge=100, le=599)
    response_body_hash: str


class VerificationAttempt(Contract):
    status: Literal["verified", "not_reproduced", "error"]
    results: list[ActionResult] = Field(default_factory=list)
    error: str | None = None


class VerificationResult(Contract):
    finding_id: str
    status: Literal["verified", "not_reproduced", "error"]
    attempts: list[VerificationAttempt] = Field(min_length=1)

    @model_validator(mode="after")
    def consistent_status(self) -> VerificationResult:
        expected = (
            "verified"
            if any(a.status == "verified" for a in self.attempts)
            else ("error" if any(a.status == "error" for a in self.attempts) else "not_reproduced")
        )
        if self.status != expected:
            raise ValueError("verification status must match its attempts")
        return self

    @property
    def verified(self) -> bool:
        return self.status == "verified"


class ReplayTarget(Protocol):
    async def reset(self, seed: int) -> None: ...

    async def execute(self, action: ReplayAction) -> ActionResult: ...

    async def check(self, oracle_id: str, results: Sequence[ActionResult]) -> bool: ...


class HTTPReplayTarget:
    """Dev1 injects reset/oracles; each actor receives an isolated HTTP session.

    reset must reset only the verifier's disposable application snapshot, restore
    stable fixture IDs, and never reset the event store or live swarm target.
    """

    def __init__(
        self,
        base_url: str,
        *,
        reset_snapshot: Callable[[int], Awaitable[None]],
        check_oracle: Callable[[str, Sequence[ActionResult]], Awaitable[bool]],
        agent_headers: dict[str, dict[str, str]] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 10,
    ):
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an HTTP(S) target origin")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("base_url must not embed credentials, a query, or a fragment")
        if parsed.path not in {"", "/"}:
            raise ValueError("base_url must be an origin; put API prefixes in Request.path")
        self.base_url = base_url.rstrip("/")
        self._reset = reset_snapshot
        self._oracle = check_oracle
        self._headers = agent_headers or {}
        self._transport = transport
        self._timeout = timeout
        self._clients: dict[str, httpx.AsyncClient] = {}
        self._responses: dict[str, dict] = {}

    async def aclose(self) -> None:
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()

    async def reset(self, seed: int) -> None:
        await self.aclose()
        self._responses.clear()
        await self._reset(seed)

    async def execute(self, action: ReplayAction) -> ActionResult:
        if action.agent_id not in self._clients:
            self._clients[action.agent_id] = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._headers.get(action.agent_id, {}),
                transport=self._transport,
                timeout=self._timeout,
                follow_redirects=False,
            )
        client = self._clients[action.agent_id]
        data = action.request.model_dump()
        for location, source in action.bindings.items():
            value = self._responses[source["event_id"]][source["key"]]
            area, key = location.split(".", 1)
            if area == "path":
                parts = data["path"].split("/")
                parts[int(key)] = str(value)
                data["path"] = "/".join(parts)
            elif area in {"json_body", "query"}:
                data[area][key] = value
            else:
                raise ValueError("unsupported replay reference location")
        request = type(action.request).model_validate(data)
        # Concatenation keeps the configured origin authoritative (no URL-join redirects).
        response = await client.request(
            request.method,
            self.base_url + request.path,
            params=request.query,
            headers=request.headers,
            json=request.json_body,
        )
        try:
            payload = response.json()
            if isinstance(payload, dict):
                self._responses[action.event_id] = payload
        except (ValueError, json.JSONDecodeError):
            pass
        return ActionResult(
            event_id=action.event_id,
            status_code=response.status_code,
            response_body_hash=sha256(response.content).hexdigest(),
        )

    async def check(self, oracle_id: str, results: Sequence[ActionResult]) -> bool:
        return await self._oracle(oracle_id, results)


class ReplayVerifier:
    def __init__(self, target: ReplayTarget, *, attempts: int = 3, attempt_timeout: float = 30):
        if attempts < 1 or attempt_timeout <= 0:
            raise ValueError("attempts and attempt_timeout must be positive")
        self.target = target
        self.attempts = attempts
        self.attempt_timeout = attempt_timeout
        # Snapshot reset + replay + oracle must never interleave on this target.
        self._lock = asyncio.Lock()

    async def _attempt(self, plan: ReplayPlan, oracle: str) -> VerificationAttempt:
        results: list[ActionResult] = []
        try:
            async with asyncio.timeout(self.attempt_timeout):
                await self.target.reset(plan.seed)
                for step in plan.steps:
                    barrier = asyncio.Barrier(len(step.actions))

                    async def perform(
                        action: ReplayAction, step_barrier: asyncio.Barrier = barrier
                    ) -> ActionResult:
                        await step_barrier.wait()
                        result = await self.target.execute(action)
                        if result.event_id != action.event_id:
                            raise ValueError("executor returned a result for a different event")
                        if action.expected_status is not None:
                            allowed = {action.expected_status, *action.acceptable_statuses}
                            if result.status_code not in allowed:
                                raise ValueError(
                                    "replay response status differs from recorded action"
                                )
                        return result

                    # TaskGroup cancels siblings before returning on an execution failure.
                    async with asyncio.TaskGroup() as tasks:
                        jobs = [tasks.create_task(perform(action)) for action in step.actions]
                    results.extend(job.result() for job in jobs)
                reproduced = await self.target.check(oracle, results)
                if not isinstance(reproduced, bool):
                    raise TypeError("oracle must return bool; query failures must raise")
                return VerificationAttempt(
                    status="verified" if reproduced else "not_reproduced",
                    results=results,
                )
        except Exception as exc:
            # Exceptions can contain credentials or response content. Record only their class.
            return VerificationAttempt(status="error", results=results, error=type(exc).__name__)

    async def verify(self, finding: Finding) -> VerificationResult:
        outcomes = []
        async with self._lock:
            for _ in range(self.attempts):
                outcome = await self._attempt(
                    finding.minimal_repro_sequence, finding.oracle_triggered
                )
                outcomes.append(outcome)
                if outcome.status == "verified":
                    break
        status = (
            "verified"
            if any(a.status == "verified" for a in outcomes)
            else ("error" if any(a.status == "error" for a in outcomes) else "not_reproduced")
        )
        return VerificationResult(finding_id=finding.id, status=status, attempts=outcomes)

    async def minimize(self, finding: Finding) -> Finding:
        """Reduce steps, actors and actions against independent reset/oracle checks."""
        proof = await self.verify(finding)
        if not proof.verified:
            return apply_verification(finding, proof)

        def reduced(steps):
            # Drop actions that depend on removed resource-producing actions.
            available = set()
            clean = []
            for step in steps:
                actions = [
                    a
                    for a in step.actions
                    if all(ref["event_id"] in available for ref in a.bindings.values())
                ]
                if actions:
                    clean.append(
                        type(step)(
                            actions=[
                                a.model_copy(update={"expected_status": None}) for a in actions
                            ]
                        )
                    )
                    available.update(a.event_id for a in actions)
            if not clean:
                return None
            actions = [a for step in clean for a in step.actions]
            agents = sorted({a.agent_id for a in actions})
            return Finding.model_validate(
                {
                    **finding.model_dump(),
                    "evidence_events": [a.event_id for a in actions],
                    "involved_agents": agents,
                    "type": "emergent" if len(agents) > 1 else "single-user",
                    "verified": False,
                    "minimal_repro_sequence": ReplayPlan(
                        seed=finding.minimal_repro_sequence.seed, steps=clean
                    ),
                }
            )

        # Actor removal first removes whole unrelated histories efficiently.
        for actor in list(finding.involved_agents):
            steps = [
                type(step)(actions=actions)
                for step in finding.minimal_repro_sequence.steps
                if (actions := [a for a in step.actions if a.agent_id != actor])
            ]
            candidate = reduced(steps)
            if candidate is not None:
                result = await self.verify(candidate)
                if result.verified:
                    finding, proof = candidate, result
        changed = True
        while changed:
            changed = False
            steps = finding.minimal_repro_sequence.steps
            candidates = [steps[:i] + steps[i + 1 :] for i in range(len(steps))]
            for i, step in enumerate(steps):
                if len(step.actions) > 1:
                    for j in range(len(step.actions)):
                        candidates.append(
                            [
                                *steps[:i],
                                type(step)(actions=step.actions[:j] + step.actions[j + 1 :]),
                                *steps[i + 1 :],
                            ]
                        )
            for candidate_steps in candidates:
                candidate = reduced(candidate_steps)
                if candidate is not None:
                    result = await self.verify(candidate)
                    if result.verified:
                        finding, proof = candidate, result
                        changed = True
                        break
        checks = []
        for actor in finding.involved_agents if len(finding.involved_agents) > 1 else []:
            candidate = reduced(
                [
                    type(step)(actions=actions)
                    for step in finding.minimal_repro_sequence.steps
                    if (actions := [a for a in step.actions if a.agent_id != actor])
                ]
            )
            if candidate is None:
                checks.append({"removed_actor": actor, "status": "not_reproduced"})
                continue
            result = await self.verify(candidate)
            if result.verified:
                return await self.minimize(candidate)
            checks.append({"removed_actor": actor, "status": result.status})
        conclusive = all(check["status"] == "not_reproduced" for check in checks)
        return Finding.model_validate(
            {
                **finding.model_dump(),
                "verified": conclusive,
                "causality": (
                    "single-user"
                    if len(finding.involved_agents) == 1
                    else "interaction-required"
                    if conclusive
                    else "inconclusive"
                ),
                "verification": {**proof.model_dump(mode="json"), "causal_checks": checks},
            }
        )


def apply_verification(finding: Finding, result: VerificationResult) -> Finding:
    if finding.id != result.finding_id:
        raise ValueError("verification belongs to a different finding")
    return Finding.model_validate(
        {
            **finding.model_dump(),
            "verified": result.verified,
            "verification": result.model_dump(mode="json"),
        }
    )
