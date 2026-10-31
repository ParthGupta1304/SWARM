"""Same-origin console for an owned disposable Bazaar environment."""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from bench.gate import evaluate_phase1
from bench.judge import judge_findings
from bench.metrics import run_benchmark, write_benchmark
from detect.report import write_report
from detect.store import SQLiteEventStore, export_jsonl
from swarm.bazaar import make_hooks
from swarm.runtime import RunCoordinator

STATIC = Path(__file__).parent


class Start(BaseModel):
    condition: Literal["swarm", "isolated", "benchmark"] = "swarm"


def create_app(config, environment, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    store = SQLiteEventStore(output / "events.sqlite3")
    state = {
        "task": None,
        "coordinator": None,
        "error": None,
        "benchmark": None,
        "stop_requested": False,
    }

    @asynccontextmanager
    async def lifespan(_):
        yield
        state["stop_requested"] = True
        if state["coordinator"]:
            state["coordinator"].stop()
        if state["task"]:
            await state["task"]
        store.close()

    app = FastAPI(title="Swarmtest console", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/")
    def index():
        page = STATIC / "console.html" if (STATIC / "console.html").exists() else STATIC / "index.html"
        return FileResponse(page)

    def busy():
        return state["task"] is not None and not state["task"].done()

    def coordinator(selected):
        value = RunCoordinator(
            selected,
            store,
            api_key=os.getenv(selected.api_key_env, "ollama"),
            hooks=make_hooks(selected, environment),
        )
        state["coordinator"] = value
        if state["stop_requested"]:
            value.stop()
        return value

    async def measured(condition, selected=config):
        runner = coordinator(selected)
        result = await runner.run(condition)
        directory = output / result.run_id
        directory.mkdir(parents=True, exist_ok=True)
        export_jsonl(store, result.run_id, directory / "events.jsonl")
        write_report(result.findings, directory)
        (directory / "run.json").write_text(
            json.dumps({k: v for k, v in vars(result).items() if k != "findings"}, indent=2)
        )
        return result

    async def work(condition):
        try:
            if condition != "benchmark":
                await measured(condition)
            else:
                measured_runs = []

                def callback(condition, seed, budget):
                    if state["stop_requested"]:
                        raise RuntimeError("benchmark stopped before next run")
                    selected = config.model_copy(update={"seed": seed, "token_budget": budget})
                    result = asyncio.run(measured(condition, selected))
                    run = result.benchmark_run()
                    measured_runs.append(run)
                    (output / result.run_id / "measured.json").write_text(
                        run.model_dump_json(indent=2)
                    )
                    return run

                truth = json.loads((STATIC.parent / "configs" / "bazaar-truth.json").read_text())
                report = await asyncio.to_thread(
                    run_benchmark,
                    callback,
                    seeds=[11, 22, 33],
                    token_budget=config.token_budget,
                    dev_seed=config.seed,
                    truth=truth,
                )
                write_benchmark(report, output / "benchmark", chart=True)
                source = os.getenv("SWARMTEST_RUN_SOURCE", "real-model")
                judge = None
                if source == "real-model":
                    try:
                        judge = await asyncio.to_thread(
                            judge_findings,
                            measured_runs,
                            truth,
                            config,
                            os.getenv(config.api_key_env, "ollama"),
                        )
                    except Exception as exc:
                        judge = {"status": "error", "error_class": type(exc).__name__}
                    (output / "benchmark" / "judge.json").write_text(json.dumps(judge, indent=2))
                gate = evaluate_phase1(
                    measured_runs,
                    truth,
                    dev_seed=config.seed,
                    source=source,
                    judge=judge,
                )
                (output / "benchmark" / "phase1-gate.json").write_text(json.dumps(gate, indent=2))
                state["gate"] = {key: value for key, value in gate.items() if key != "benchmark"}
                state["benchmark"] = report
        except Exception as exc:
            # Provider response bodies and credentials stay out of the browser.
            state["error"] = (
                f"{type(exc).__name__}: run failed; inspect local server logs/configuration."
            )
        finally:
            state["coordinator"] = None

    @app.post("/api/start")
    async def start(payload: Start):
        if busy():
            raise HTTPException(409, "A run is already active")
        state["error"], state["stop_requested"] = None, False
        state["task"] = asyncio.create_task(work(payload.condition))
        return {"status": "started"}

    @app.post("/api/stop")
    async def stop():
        state["stop_requested"] = True
        if state["coordinator"]:
            state["coordinator"].stop()
        return {"status": "stopping"}

    @app.get("/api/state")
    async def snapshot(after_id: int = 0):
        try:
            async with httpx.AsyncClient(base_url=environment.live.url, timeout=5) as client:
                responses = await asyncio.gather(
                    client.get("/api/runs"),
                    client.get("/api/findings"),
                    client.get("/api/events", params={"after_id": max(0, after_id), "limit": 100}),
                )
                for response in responses:
                    response.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(
                503, "Target temporarily unavailable; retry state snapshot"
            ) from None
        runs = responses[0].json()
        current = next(
            (run for run in runs if run.get("status") == "running"), runs[-1] if runs else None
        )
        actions = await asyncio.to_thread(store.events, current["run_id"]) if current else []
        return {
            "busy": busy(),
            "error": state["error"],
            "actions": [event.model_dump(mode="json") for event in actions],
            "runs": responses[0].json(),
            "findings": responses[1].json(),
            "events": responses[2].json(),
            "benchmark": state["benchmark"],
            "gate": state.get("gate"),
            "model": config.model,
            "token_budget": config.token_budget,
        }

    return app
