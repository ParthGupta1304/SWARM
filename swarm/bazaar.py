"""Real Bazaar reset, detection, replay and telemetry integration."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from detect.invariants import load_invariants
from detect.python_checks import check_exception_logs, check_response_contract
from swarm.pipeline import DetectionPipeline
from swarm.runtime import RunConfig, RuntimeHooks
from swarm.targets import BazaarEnvironment
from verify import HTTPReplayTarget, ReplayVerifier

BAZAAR_ROOT = Path(__file__).resolve().parent.parent / "apps" / "bazaar"


def make_hooks(config: RunConfig, environment: BazaarEnvironment) -> RuntimeHooks:
    live, replay = environment.live, environment.replay
    if config.app_base_url != live.url:
        raise ValueError("runtime must use this environment's owned live target")
    invariants = load_invariants(BAZAAR_ROOT / "invariants.sql")
    by_id = {inv.id: inv for inv in invariants}
    replay_runner = replay.invariant_runner()
    client = httpx.AsyncClient(base_url=live.url, timeout=10)

    async def reset_live(seed):
        await asyncio.to_thread(live.reset, seed)

    async def post(path, payload):
        response = await client.post(path, json=payload)
        response.raise_for_status()

    async def reset_replay(seed):
        await asyncio.to_thread(replay.reset, seed)

    async def oracle(name, results):
        if name in by_id:
            return await asyncio.to_thread(replay_runner.check, by_id[name]) is not None
        if name.startswith("http:"):
            return any(result.status_code == int(name.split(":")[1]) for result in results)
        if name.startswith("log:"):
            _, cls, method, path = name.split(":", 3)
            rows = replay.rows("SELECT error_class, method, path FROM request_errors")
            return any(row == {"error_class": cls, "method": method, "path": path} for row in rows)
        if name == "python:write_redirect":
            return any(300 <= result.status_code < 400 for result in results)
        raise RuntimeError("oracle unavailable")

    target = HTTPReplayTarget(replay.url, reset_snapshot=reset_replay, check_oracle=oracle)
    mapping = {inv.id: inv.id for inv in invariants}
    mapping.update(
        {"log:RuntimeError:GET:/api/items": "S4", "log:RuntimeError:POST:/api/checkout": "S1"}
    )

    def python_checks(window):
        return check_response_contract(window.latest) + check_exception_logs(
            window.latest,
            lambda: live.rows("SELECT action_key, method, path, error_class FROM request_errors"),
        )

    pipeline = DetectionPipeline(
        verifier=ReplayVerifier(target),
        live_base_url=live.url,
        runner=live.invariant_runner(),
        invariants=invariants,
        bug_mapping=mapping,
        python_checks=[python_checks],
    )

    async def detect(window):
        findings = await pipeline(window)
        for index, finding in enumerate(findings):
            # Reduce whole setup steps; this improves actor attribution and preserves bursts.
            if finding.verified:
                finding = await pipeline.verifier.minimize(finding)
                findings[index] = finding
            await post("/api/findings", finding.model_dump(mode="json"))
        return findings

    async def close():
        await target.aclose()
        await client.aclose()

    return RuntimeHooks(
        reset=reset_live,
        detect=detect,
        close=close,
        progress=lambda payload: post("/api/runs/telemetry", payload),
    )
