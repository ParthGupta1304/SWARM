"""Replay recorded actions on a disposable seeded target without LLM calls."""

from __future__ import annotations

import asyncio
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

    async def aclose(self) -> None:
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()

    async def reset(self, seed: int) -> None:
        await self.aclose()
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
        request = action.request
        # Concatenation keeps the configured origin authoritative (no URL-join redirects).
        response = await client.request(
            request.method,
            self.base_url + request.path,
            params=request.query,
            headers=request.headers,
            json=request.json_body,
        )
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
        """Greedy removal of whole steps; concurrent groups always remain intact.

        Each candidate is independently reset and verified. This finds a smaller
        reproducer, not a proof of global minimality. Call after initial verify.
        """
        if not (await self.verify(finding)).verified:
            raise ValueError("only reproducible findings can be minimized")
        steps = list(finding.minimal_repro_sequence.steps)
        index = 0
        while index < len(steps) and len(steps) > 1:
            candidate_steps = steps[:index] + steps[index + 1 :]
            actions = [a for step in candidate_steps for a in step.actions]
            agents = sorted({a.agent_id for a in actions})
            data = finding.model_dump()
            data.update(
                evidence_events=[a.event_id for a in actions],
                involved_agents=agents,
                type="emergent" if len(agents) > 1 else "single-user",
                minimal_repro_sequence=ReplayPlan(
                    seed=finding.minimal_repro_sequence.seed,
                    steps=candidate_steps,
                ),
                verified=False,
            )
            candidate = Finding.model_validate(data)
            if (await self.verify(candidate)).verified:
                steps = candidate_steps
                finding = candidate
                index = 0
            else:
                index += 1
        data = finding.model_dump()
        data["verified"] = True
        return Finding.model_validate(data)


def apply_verification(finding: Finding, result: VerificationResult) -> Finding:
    if finding.id != result.finding_id:
        raise ValueError("verification belongs to a different finding")
    return Finding.model_validate({**finding.model_dump(), "verified": result.verified})
