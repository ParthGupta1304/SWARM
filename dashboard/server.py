"""Local marketplace and operations console for owned disposable targets."""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from bench.gate import evaluate_phase1
from bench.judge import judge_findings
from bench.metrics import BenchmarkRun, run_benchmark, summarize, write_benchmark
from bench.review import record_review
from dashboard.presentation import (
    RunArchive,
    RunOptions,
    as_benchmark,
    export_config,
    public_config,
    selected_config,
)
from dashboard.reset import cleanup_plan, clear_artifacts
from detect.contracts import Finding
from detect.report import write_report
from detect.store import SQLiteEventStore, export_jsonl
from swarm.bazaar import make_hooks, make_verifier
from swarm.provider import credential
from swarm.runtime import RunCoordinator

STATIC = Path(__file__).parent
MARKET = STATIC.parent / "apps" / "bazaar" / "static"
SITE = STATIC / "site"
ALLOWED = re.compile(
    r"api/(?:users(?:/\d+/(?:orders|messages))?|items(?:/\d+(?:/(?:questions|reviews|reports))?)?|sellers/\d+/orders|cart/(?:items(?:/\d+/remove)?|\d+)|coupons/apply|checkout|orders/\d+/(?:refund|disputes|fulfil)|blocks|messages)"
)


class Start(BaseModel):
    condition: Literal["swarm", "isolated", "benchmark"] = "swarm"
    options: RunOptions | None = None


class Review(BaseModel):
    run_id: UUID | None = None
    finding_id: str
    correct: bool
    reviewer: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=3, max_length=2000)


class Recheck(BaseModel):
    run_id: UUID
    finding_id: UUID


class Reset(BaseModel):
    confirmed: Literal[True]


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
        "reset_task": None,
        "resetting": False,
        "reset_failed": False,
        "generation": uuid4().hex,
        "recheck": None,
    }
    truth = json.loads((STATIC.parent / "configs" / "bazaar-truth.json").read_text())

    operations = asyncio.Lock()
    archive = RunArchive(output)
    state["benchmark_seed"] = (state["benchmark"] or {}).get("dev_seed", config.seed)

    @asynccontextmanager
    async def lifespan(_):
        yield
        state["stop_requested"] = True
        if state["coordinator"]:
            state["coordinator"].stop()
        if state["task"]:
            await state["task"]
        if state["reset_task"]:
            await state["reset_task"]
        store.close()

    app = FastAPI(title="Swarmtest console", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    if MARKET.exists():
        app.mount("/bazaar", StaticFiles(directory=MARKET, html=True), name="bazaar")

    for name in ("assets", "images"):
        if (SITE / name).exists():
            app.mount("/" + name, StaticFiles(directory=SITE / name), name="site-" + name)

    @app.get("/")
    @app.get("/dashboard")
    def index():
        if (SITE / "index.html").exists():
            return FileResponse(SITE / "index.html")
        return legacy_index()

    @app.get("/console")
    def legacy_index():
        page = (
            STATIC / "console.html" if (STATIC / "console.html").exists() else STATIC / "index.html"
        )
        return FileResponse(page)

    def busy():
        return state["task"] is not None and not state["task"].done()

    def check_reset():
        if state["resetting"] or state["reset_failed"]:
            raise HTTPException(409, "Workspace is resetting or needs a reset retry")

    @app.api_route("/market/{path:path}", methods=["GET", "POST"])
    async def market(path: str, request: Request):
        check_reset()
        async with operations:
            check_reset()
            return await forward_market(path, request)

    async def forward_market(path: str, request: Request):
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
            dev_seed=state["benchmark_seed"],
            source=source,
            judge=judge,
            manual_review=reviews,
        )
        state["gate"] = {k: v for k, v in gate.items() if k != "benchmark"}
        state["benchmark"] = summarize(state["runs"], truth, dev_seed=state["benchmark_seed"])
        benchdir.mkdir(parents=True, exist_ok=True)
        write_benchmark(state["benchmark"], benchdir, chart=True)
        (benchdir / "phase1-gate.json").write_text(json.dumps(gate, indent=2))
        (benchdir / "measured-runs.json").write_text(
            json.dumps([r.model_dump(mode="json") for r in state["runs"]], indent=2)
        )

    async def work(condition, selected):
        try:
            if condition != "benchmark":
                await measured(condition, selected)
            else:
                state["benchmark_seed"] = selected.seed
                measured_runs = []

                def callback(condition, seed, budget):
                    if state["stop_requested"]:
                        raise RuntimeError("Benchmark stopped")
                    experiment = selected.model_copy(update={"seed": seed, "token_budget": budget})
                    result = asyncio.run(measured(condition, experiment))
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
                    token_budget=selected.token_budget,
                    dev_seed=selected.seed,
                    truth=truth,
                )
                state["runs"] = measured_runs
                if state["stop_requested"]:
                    raise RuntimeError("Benchmark stopped before evaluation")
                judge = None
                if all(r.provenance.get("source") == "real-model" for r in measured_runs):
                    try:
                        judge = await asyncio.to_thread(
                            judge_findings,
                            measured_runs,
                            truth,
                            config,
                            credential(config),
                            cancelled=lambda: state["stop_requested"],
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
        async with operations:
            check_reset()
            return start_run(payload)

    def start_run(payload):
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
        try:
            selected = selected_config(config, payload.options)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        if payload.condition == "benchmark":
            if selected.seed in {11, 22, 33}:
                raise HTTPException(422, "Development seed must differ from benchmark seeds")
            selected = selected.model_copy(update={"max_rounds": min(3, selected.max_rounds)})
        state["error"], state["stop_requested"], state["recheck"] = None, False, None
        state["task"] = asyncio.create_task(work(payload.condition, selected))
        return {"status": "started"}

    def wipe():
        nonlocal store
        plan = cleanup_plan(output, environment.directory)
        environment.reset_workspace(config.seed)
        store.close()
        clear_artifacts(plan)
        store = SQLiteEventStore(output / "events.sqlite3")

    async def reset_workspace():
        try:
            if state["task"]:
                # Wait for benchmark workers and all replay/API writes before deleting.
                await asyncio.shield(state["task"])
            async with operations:
                await asyncio.to_thread(wipe)
                state.update(
                    task=None,
                    coordinator=None,
                    error=None,
                    stop_requested=False,
                    benchmark=None,
                    gate=None,
                    runs=[],
                    reset_failed=False,
                    generation=uuid4().hex,
                    recheck=None,
                )
        except Exception as exc:
            state["reset_failed"] = True
            state["error"] = (
                f"Reset failed ({type(exc).__name__}). Retry Reset workspace; new runs are blocked."
            )
        finally:
            state["resetting"] = False

    @app.post("/api/reset", status_code=202)
    async def reset(payload: Reset):
        if results is not None:
            raise HTTPException(
                409, "Saved-results mode is read-only; open a live workspace to reset"
            )
        async with operations:
            if not state["resetting"]:
                state.update(resetting=True, reset_failed=False, error=None, stop_requested=True)
                if state["coordinator"]:
                    state["coordinator"].stop()
                state["reset_task"] = asyncio.create_task(reset_workspace())
        return JSONResponse(
            {"status": "resetting"},
            status_code=202,
            headers={"Cache-Control": "no-store", "Clear-Site-Data": '"cache"'},
        )

    def workspace_state():
        return {
            "generation": state["generation"],
            "resetting": state["resetting"],
            "reset_failed": state["reset_failed"],
            "reset_allowed": results is None,
            "error": state["error"],
            "recheck": state["recheck"],
        }

    @app.get("/api/workspace")
    async def workspace(previous: str | None = None):
        headers = {"Cache-Control": "no-store"}
        if previous is not None and previous != state["generation"]:
            headers["Clear-Site-Data"] = '"cache"'
        return JSONResponse(workspace_state(), headers=headers)

    @app.get("/api/config")
    async def configuration():
        return public_config(config, truth)

    @app.post("/api/config/export")
    async def configuration_export(options: RunOptions):
        try:
            selected = selected_config(config, options)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return Response(
            export_config(selected),
            media_type="application/yaml",
            headers={"Content-Disposition": 'attachment; filename="swarmtest.yaml"'},
        )

    @app.get("/api/history")
    async def history():
        async with operations:
            check_reset()
            return await asyncio.to_thread(archive.list)

    async def archive_run(run_id):
        try:
            run = await asyncio.to_thread(archive.detail, str(run_id))
            measured = next((r for r in state["runs"] if r.run_id == str(run_id)), None)
            if measured:
                originals = {f.id: f.model_dump(mode="json") for f in measured.findings}
                run["assessments"] = {
                    **run.get("assessments", {}),
                    **{
                        f["id"]: measured.assessments[f["id"]]
                        for f in run["findings"]
                        if f["id"] in measured.assessments and originals.get(f["id"]) == f
                    },
                }
            return run
        except (OSError, ValueError, KeyError, TypeError):
            raise HTTPException(404, "Saved run unavailable") from None

    @app.get("/api/history/{run_id}")
    async def historical_run(run_id: UUID):
        async with operations:
            check_reset()
            return await archive_run(run_id)

    @app.get("/api/history/{run_id}/download/{kind}")
    async def download(run_id: UUID, kind: Literal["json", "markdown", "events"]):
        async with operations:
            check_reset()
            if kind == "json":
                return JSONResponse(
                    await archive_run(run_id),
                    headers={"Content-Disposition": f'attachment; filename="{run_id}.json"'},
                )
            try:
                path = archive.path(
                    str(run_id), "report.md" if kind == "markdown" else "events.jsonl"
                )
                if not path.is_file():
                    raise FileNotFoundError()
            except (ValueError, OSError):
                raise HTTPException(404, "Export unavailable") from None
            content = await asyncio.to_thread(path.read_bytes)
            extension = "md" if kind == "markdown" else "jsonl"
            return Response(
                content,
                media_type="text/plain",
                headers={"Content-Disposition": f'attachment; filename="{run_id}.{extension}"'},
            )

    async def recheck_work(finding):
        selected = config.model_copy(update={"app_base_url": environment.live.url})
        verifier = None
        try:
            verifier = make_verifier(
                selected, environment, cancelled=lambda: state["stop_requested"]
            )
            result = await verifier.verify(finding)
            record = {
                "finding_id": finding.id,
                "run_id": finding.run_id,
                "status": "stopped" if state["stop_requested"] else "completed",
                "target_version": config.bazaar_version,
                "seed": finding.minimal_repro_sequence.seed,
                "result": result.model_dump(mode="json"),
            }
            path = archive.path(finding.run_id, "rechecks.json")
            checks = json.loads(path.read_text()) if path.exists() else []
            path.write_text(json.dumps([*checks, record], indent=2))
            state["recheck"] = record
        except Exception as exc:
            state["recheck"] = {
                "finding_id": finding.id,
                "run_id": finding.run_id,
                "status": "error",
                "error": type(exc).__name__,
            }
        finally:
            if verifier is not None:
                await verifier.target.aclose()

    @app.post("/api/recheck", status_code=202)
    async def recheck(payload: Recheck):
        async with operations:
            check_reset()
            if busy():
                raise HTTPException(409, "Stop the active run before replaying")
            run = await archive_run(payload.run_id)
            finding = next((f for f in run["findings"] if f["id"] == str(payload.finding_id)), None)
            if finding is None:
                raise HTTPException(404, "Finding unavailable in this run")
            state["stop_requested"], state["error"] = False, None
            state["recheck"] = {
                "run_id": str(payload.run_id),
                "finding_id": str(payload.finding_id),
                "status": "running",
            }
            state["task"] = asyncio.create_task(recheck_work(Finding.model_validate(finding)))
        return {"status": "started"}

    @app.post("/api/stop")
    async def stop():
        state["stop_requested"] = True
        if state["coordinator"]:
            state["coordinator"].stop()
        return {"status": "stopping"}

    @app.post("/api/review")
    async def review(payload: Review):
        async with operations:
            check_reset()
            if payload.run_id is not None:
                if busy():
                    raise HTTPException(409, "Wait until active work completes")
                run = await archive_run(payload.run_id)
                if run.get("stopped"):
                    raise HTTPException(409, "Stopped runs cannot complete acceptance review")
                measured = as_benchmark(run)
                try:
                    record_review(
                        archive.path(str(payload.run_id), "run.json").parent,
                        [measured],
                        **payload.model_dump(exclude={"run_id"}),
                    )
                except ValueError as exc:
                    raise HTTPException(422, str(exc)) from None
                return {"status": "recorded"}
            return review_finding(payload)

    def review_finding(payload):
        if busy():
            raise HTTPException(409, "Wait until the benchmark completes")
        if not state["runs"]:
            raise HTTPException(409, "Complete a benchmark first")
        try:
            record_review(benchdir, state["runs"], **payload.model_dump(exclude={"run_id"}))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        refresh_gate()
        return {"status": "recorded", "gate": state["gate"]}

    @app.get("/api/review")
    async def review_state():
        async with operations:
            check_reset()
            return review_snapshot()

    def review_snapshot():
        return {
            "reviews": read("manual-review.json", []),
            "judge": read("judge.json", None),
            "findings": [f.model_dump(mode="json") for r in state["runs"] for f in r.findings],
        }

    @app.get("/api/state")
    async def snapshot(after_id: int = 0):
        async with operations:
            base = {
                "busy": busy() or state["resetting"],
                **workspace_state(),
                "model": config.model,
                "token_budget": config.token_budget,
                "max_rounds": config.max_rounds,
            }
            if state["resetting"] or state["reset_failed"]:
                return {
                    **base,
                    "actions": [],
                    "runs": [],
                    "findings": [],
                    "events": [],
                    "benchmark": None,
                    "gate": None,
                }
            return {**(await live_snapshot(after_id)), **base}

    async def live_snapshot(after_id):
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
            generation = None
            while not await request.is_disconnected():
                try:
                    data = await snapshot(cursor)
                    if data["generation"] != generation:
                        generation, run_id, cursor = data["generation"], None, 0
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
                    yield f"id: {generation}:{cursor}\ndata: {json.dumps(data)}\n\n"
                except HTTPException:
                    yield "event: unavailable\ndata: {}\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(
            generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )

    return app
