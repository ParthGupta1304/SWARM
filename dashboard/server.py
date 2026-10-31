"""Local marketplace and operations console for owned disposable targets."""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from bench.gate import evaluate_phase1
from bench.judge import judge_findings
from bench.metrics import BenchmarkRun, run_benchmark, summarize, write_benchmark
from bench.review import record_review
from detect.report import write_report
from detect.store import SQLiteEventStore, export_jsonl
from swarm.bazaar import make_hooks
from swarm.provider import credential
from swarm.runtime import RunCoordinator

STATIC = Path(__file__).parent
MARKET = STATIC.parent / "apps" / "bazaar" / "static"
ALLOWED = re.compile(
    r"api/(?:users(?:/\d+/(?:orders|messages))?|items(?:/\d+(?:/(?:questions|reviews|reports))?)?|sellers/\d+/orders|cart/(?:items(?:/\d+/remove)?|\d+)|coupons/apply|checkout|orders/\d+/(?:refund|disputes|fulfil)|blocks|messages)"
)


class Start(BaseModel):
    condition: Literal["swarm", "isolated", "benchmark"] = "swarm"


class Review(BaseModel):
    finding_id: str
    correct: bool
    reviewer: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=3, max_length=2000)


def create_app(config, environment, output: Path, results: Path | None = None):
    output.mkdir(parents=True, exist_ok=True)
    store = SQLiteEventStore(output / "events.sqlite3")
    benchdir = results or (
        output if (output / "measured-runs.json").exists() else output / "benchmark"
    )

    def read(name, default):
        path = benchdir / name
        return json.loads(path.read_text()) if path.exists() else default

    state = {
        "task": None,
        "coordinator": None,
        "error": None,
        "stop_requested": False,
        "benchmark": read("benchmark.json", None),
        "gate": read("phase1-gate.json", None),
        "runs": [BenchmarkRun.model_validate(r) for r in read("measured-runs.json", [])],
    }
    truth = json.loads((STATIC.parent / "configs" / "bazaar-truth.json").read_text())

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
    if MARKET.exists():
        app.mount("/bazaar", StaticFiles(directory=MARKET, html=True), name="bazaar")

    @app.get("/")
    def index():
        page = (
            STATIC / "console.html" if (STATIC / "console.html").exists() else STATIC / "index.html"
        )
        return FileResponse(page)

    def busy():
        return state["task"] is not None and not state["task"].done()

    @app.api_route("/market/{path:path}", methods=["GET", "POST"])
    async def market(path: str, request: Request):
        if not ALLOWED.fullmatch(path):
            raise HTTPException(404, "Unknown marketplace operation")
        if request.method == "POST" and busy():
            raise HTTPException(
                409, "A test run owns the marketplace. Stop it before making changes."
            )
        async with httpx.AsyncClient(
            base_url=environment.live.url, timeout=15, follow_redirects=False
        ) as client:
            try:
                r = await client.request(
                    request.method,
                    "/" + path,
                    params=request.query_params,
                    content=await request.body(),
                    headers={"Content-Type": "application/json"},
                )
            except httpx.HTTPError:
                raise HTTPException(
                    503, "Marketplace unavailable; restart the local demo"
                ) from None
        return Response(r.content, status_code=r.status_code, media_type="application/json")

    async def measured(condition, selected=config):
        runner = RunCoordinator(
            selected,
            store,
            api_key=credential(selected),
            hooks=make_hooks(selected, environment),
            context_dir=output / "memory",
        )
        state["coordinator"] = runner
        if state["stop_requested"]:
            runner.stop()
        result = await runner.run(condition)
        directory = output / result.run_id
        directory.mkdir(parents=True, exist_ok=True)
        export_jsonl(store, result.run_id, directory / "events.jsonl")
        write_report(result.findings, directory)
        (directory / "run.json").write_text(
            json.dumps({k: v for k, v in vars(result).items() if k != "findings"}, indent=2)
        )
        return result

    def refresh_gate(judge=None):
        runs = state["runs"]
        judge = judge if judge is not None else read("judge.json", None)
        rows = (judge or {}).get("judgements", [])
        assessed = {row["finding_id"]: row["correct"] for row in rows if "correct" in row}
        reviews = read("manual-review.json", [])
        from bench.review import valid_reviews

        assessed.update({row["finding_id"]: row["correct"] for row in valid_reviews(reviews, runs)})
        for i, run in enumerate(runs):
            state["runs"][i] = run.model_copy(
                update={
                    "assessments": {f.id: assessed[f.id] for f in run.findings if f.id in assessed}
                }
            )
        source = (
            "real-model"
            if all(r.provenance.get("source") == "real-model" for r in runs)
            else "scripted-fixture"
        )
        gate = evaluate_phase1(
            state["runs"],
            truth,
            dev_seed=config.seed,
            source=source,
            judge=judge,
            manual_review=reviews,
        )
        state["gate"] = {k: v for k, v in gate.items() if k != "benchmark"}
        state["benchmark"] = summarize(state["runs"], truth, dev_seed=config.seed)
        benchdir.mkdir(parents=True, exist_ok=True)
        write_benchmark(state["benchmark"], benchdir, chart=True)
        (benchdir / "phase1-gate.json").write_text(json.dumps(gate, indent=2))
        (benchdir / "measured-runs.json").write_text(
            json.dumps([r.model_dump(mode="json") for r in state["runs"]], indent=2)
        )

    async def work(condition):
        try:
            if condition != "benchmark":
                await measured(condition)
            else:
                measured_runs = []

                def callback(condition, seed, budget):
                    if state["stop_requested"]:
                        raise RuntimeError("Benchmark stopped")
                    selected = config.model_copy(update={"seed": seed, "token_budget": budget})
                    result = asyncio.run(measured(condition, selected))
                    run = result.benchmark_run()
                    measured_runs.append(run)
                    (output / result.run_id / "measured.json").write_text(
                        run.model_dump_json(indent=2)
                    )
                    return run

                await asyncio.to_thread(
                    run_benchmark,
                    callback,
                    seeds=[11, 22, 33],
                    token_budget=config.token_budget,
                    dev_seed=config.seed,
                    truth=truth,
                )
                state["runs"] = measured_runs
                judge = None
                if all(r.provenance.get("source") == "real-model" for r in measured_runs):
                    try:
                        judge = await asyncio.to_thread(
                            judge_findings, measured_runs, truth, config, credential(config)
                        )
                    except Exception as exc:
                        judge = {"status": "error", "error_class": type(exc).__name__}
                benchdir.mkdir(parents=True, exist_ok=True)
                (benchdir / "judge.json").write_text(json.dumps(judge, indent=2))
                refresh_gate(judge)
        except Exception as exc:
            state["error"] = (
                f"{type(exc).__name__}: run failed; "
                "check provider configuration, limits and local logs."
            )
        finally:
            state["coordinator"] = None

    @app.post("/api/start")
    async def start(payload: Start):
        if busy():
            raise HTTPException(409, "A run is already active")
        if results is not None and payload.condition == "benchmark":
            raise HTTPException(
                409,
                "This console is reviewing saved results. "
                "Start without --results to run a new benchmark.",
            )
        try:
            credential(config)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        state["error"], state["stop_requested"] = None, False
        state["task"] = asyncio.create_task(work(payload.condition))
        return {"status": "started"}

    @app.post("/api/stop")
    async def stop():
        state["stop_requested"] = True
        if state["coordinator"]:
            state["coordinator"].stop()
        return {"status": "stopping"}

    @app.post("/api/review")
    def review(payload: Review):
        if busy():
            raise HTTPException(409, "Wait until the benchmark completes")
        if not state["runs"]:
            raise HTTPException(409, "Complete a benchmark first")
        try:
            record_review(benchdir, state["runs"], **payload.model_dump())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        refresh_gate()
        return {"status": "recorded", "gate": state["gate"]}

    @app.get("/api/review")
    def review_state():
        return {
            "reviews": read("manual-review.json", []),
            "judge": read("judge.json", None),
            "findings": [f.model_dump(mode="json") for r in state["runs"] for f in r.findings],
        }

    @app.get("/api/state")
    async def snapshot(after_id: int = 0):
        try:
            async with httpx.AsyncClient(base_url=environment.live.url, timeout=5) as client:
                responses = await asyncio.gather(
                    client.get("/api/runs"),
                    client.get("/api/findings"),
                    client.get("/api/events", params={"after_id": max(0, after_id), "limit": 100}),
                )
                for r in responses:
                    r.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(503, "Marketplace temporarily unavailable") from None
        runs = responses[0].json()
        current = next(
            (r for r in runs if r.get("status") == "running"), runs[-1] if runs else None
        )
        actions = await asyncio.to_thread(store.events, current["run_id"]) if current else []
        return {
            "busy": busy(),
            "error": state["error"],
            "actions": [e.model_dump(mode="json") for e in actions],
            "runs": runs,
            "findings": responses[1].json(),
            "events": responses[2].json(),
            "benchmark": state["benchmark"],
            "gate": state["gate"],
            "model": config.model,
            "token_budget": config.token_budget,
            "max_rounds": config.max_rounds,
        }

    @app.get("/api/stream")
    async def stream(request: Request):
        async def generate():
            try:
                cursor = max(0, int(request.headers.get("last-event-id", "0").split(":")[-1]))
            except ValueError:
                cursor = 0
            run_id = None
            while not await request.is_disconnected():
                try:
                    data = await snapshot(cursor)
                    current = next(
                        (r for r in data["runs"] if r.get("status") == "running"),
                        data["runs"][-1] if data["runs"] else {},
                    )
                    if current.get("run_id") != run_id:
                        run_id = current.get("run_id")
                        cursor = 0
                        data = await snapshot(cursor)
                    ids = [e["id"] for e in data["events"]]
                    if ids:
                        cursor = max(ids)
                    yield f"id: {cursor}\ndata: {json.dumps(data)}\n\n"
                except HTTPException:
                    yield "event: unavailable\ndata: {}\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(
            generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )

    return app
