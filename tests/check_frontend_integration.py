"""Scripted-provider console check; deliberately cannot pass real-model gate."""

# This standalone check adds the repository root before importing local packages.
# ruff: noqa: E402

import asyncio
import json
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx
import uvicorn
import yaml

from dashboard.server import create_app
from swarm.runtime import RunConfig
from swarm.targets import BazaarEnvironment

WORKSPACE = tempfile.TemporaryDirectory(prefix="swarm-frontend-check-")
OUT = Path(WORKSPACE.name)
from swarm.demo_fixture import app as provider


def launch(app):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    th = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    th.start()
    for _ in range(100):
        if server.started:
            return server, th, sock, f"http://127.0.0.1:{port}"
        time.sleep(0.05)
    raise RuntimeError("startup timeout")


async def verify(app, env):
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://console"
        ) as client:
            for route in ["/", "/dashboard", "/console", "/bazaar/"]:
                assert (await client.get(route)).status_code == 200, route
            metadata = (await client.get("/api/config")).json()
            assert metadata["max_rounds"] == 6 and metadata["population_cap"] == 10
            assert "provider_base_url" not in metadata
            options = {"normal_agents": 2, "adversary_agents": 8, "max_dollars": 0.5, "seed": 1}
            exported = await client.post("/api/config/export", json=options)
            assert exported.status_code == 200
            assert len(RunConfig.model_validate(yaml.safe_load(exported.text)).personas) == 10
            for update in [{"normal_agents": 3}, {"max_dollars": 1}, {"seed": 11}]:
                assert (
                    await client.post("/api/config/export", json={**options, **update})
                ).status_code == 422
            assert (await client.get("/api/history/not-a-uuid")).status_code == 422
            assert (await client.post("/api/start", json={"condition": "swarm"})).status_code == 200
            assert (await client.post("/api/start", json={"condition": "swarm"})).status_code == 409
            for _ in range(1200):
                response = await client.get("/api/state")
                assert response.status_code == 200
                state = response.json()
                if not state["busy"]:
                    break
                await asyncio.sleep(0.1)
            assert not state["error"], state["error"]
            assert state["runs"][-1]["efficiency"]["model_calls"] > 0
            assert state["runs"][-1]["efficiency"]["cache_reporting"] == "unreported"
            assert state["actions"] and all(
                "user_id" in e["request"]["json_body"]
                for e in state["actions"]
                if e["tool"] == "add_to_cart"
            )
            bugids = {f["mapped_bug_id"] for f in state["findings"] if f["verified"]}
            assert {"E1", "E2", "E5", "E7", "S1", "S4", "S2"} <= bugids, bugids
            assert (
                next(r for r in state["runs"] if r["run_id"] == state["actions"][0]["run_id"])[
                    "tokens_used"
                ]
                == 10 * 6 * 30
            )
            assert all(
                f["type"] == "single-user"
                for f in state["findings"]
                if f["mapped_bug_id"] in ["S1", "S2", "S4"]
            ), [(f["mapped_bug_id"], f["type"]) for f in state["findings"]]
            assert all(
                len(f["involved_agents"]) <= 2 for f in state["findings"] if f["verified"]
            ), [(f["mapped_bug_id"], f["involved_agents"]) for f in state["findings"]]
            # Typed history, downloads, real replay and evidence-bound review.
            history = (await client.get("/api/history")).json()
            completed = next(row for row in history if row["status"] == "completed")
            run_id = completed["run_id"]
            saved = (await client.get("/api/history/" + run_id)).json()
            assert set(completed["verified_ids"]) == bugids
            finding = next(f for f in saved["findings"] if f["verified"])
            original = (OUT / run_id / "report.json").read_bytes()
            for kind in ["json", "markdown", "events"]:
                response = await client.get(f"/api/history/{run_id}/download/{kind}")
                assert (
                    response.status_code == 200
                    and "attachment" in response.headers["content-disposition"]
                )
            assert (
                await client.post(
                    "/api/recheck", json={"run_id": run_id, "finding_id": finding["id"]}
                )
            ).status_code == 202
            assert (await client.post("/api/start", json={"condition": "swarm"})).status_code == 409
            for _ in range(600):
                state = (await client.get("/api/state")).json()
                if not state["busy"]:
                    break
                await asyncio.sleep(0.05)
            assert state["recheck"]["status"] == "completed", state["recheck"]
            assert state["recheck"]["result"]["status"] == "verified", state["recheck"]
            assert (OUT / run_id / "report.json").read_bytes() == original
            response = await client.post(
                "/api/review",
                json={
                    "run_id": run_id,
                    "finding_id": finding["id"],
                    "correct": True,
                    "reviewer": "Scripted UI check",
                    "note": "Independent replay confirmed this fixture finding.",
                },
            )
            assert response.status_code == 200, response.text
            reviewed = (await client.get("/api/history/" + run_id)).json()
            assert reviewed["assessments"][finding["id"]] is True
            assert reviewed["rechecks"][-1]["status"] == "completed"
            # Six actual coordinator runs, explicitly labelled fixture evidence.
            assert (
                await client.post("/api/start", json={"condition": "benchmark"})
            ).status_code == 200
            for _ in range(2400):
                state = (await client.get("/api/state")).json()
                if not state["busy"]:
                    break
                await asyncio.sleep(0.1)
            assert not state["error"], state["error"]
            assert state["runs"][-1]["efficiency"]["model_calls"] > 0
            assert state["runs"][-1]["efficiency"]["cache_reporting"] == "unreported"
            assert state["benchmark"] and len(state["benchmark"]["runs"]) == 6
            assert state["gate"]["source"] == "scripted-fixture" and not state["gate"]["complete"]
            assert {"E1", "E2", "E7"} <= set(state["gate"]["verified_emergent_bug_ids"])
            # Stop cooperatively, retain usage and events without scoring an incomplete run.
            await client.post("/api/start", json={"condition": "swarm"})
            await asyncio.sleep(0.2)
            await client.post("/api/stop")
            for _ in range(300):
                stopped = (await client.get("/api/state")).json()
                if not stopped["busy"]:
                    break
                await asyncio.sleep(0.1)
            assert not stopped["busy"]
            snapshots = list((OUT / "memory").rglob("*.json"))
            assert snapshots
            assert all(len(json.loads(p.read_text())["recent_turns"]) <= 2 for p in snapshots)
            generation = (await client.get("/api/workspace")).json()["generation"]
            (OUT / "notes.txt").write_text("preserve user notes")
            reset = await client.post("/api/reset", json={"confirmed": True})
            assert reset.status_code == 202
            for _ in range(600):
                workspace = (await client.get("/api/workspace")).json()
                if not workspace["resetting"]:
                    break
                await asyncio.sleep(0.05)
            assert not workspace["reset_failed"], workspace
            assert workspace["generation"] != generation
            cleared = (await client.get("/api/state")).json()
            for key in ["runs", "actions", "events", "findings"]:
                assert cleared[key] == [], (key, cleared[key])
            assert cleared["benchmark"] is None and cleared["gate"] is None
            assert not (OUT / "memory").exists() and not (OUT / "benchmark").exists()
            assert (OUT / "notes.txt").read_text() == "preserve user notes"
            import sqlite3

            with sqlite3.connect(OUT / "events.sqlite3") as database:
                assert database.execute("select count(*) from events").fetchone()[0] == 0
            for target in [env.live, env.replay]:
                assert target.rows("select count(*) as n from orders")[0]["n"] == 0
                assert target.rows("select count(*) as n from wire_findings")[0]["n"] == 0
                assert target.rows("select count(*) as n from run_telemetry")[0]["n"] == 0
                assert all(
                    row["inventory"] == row["initial_inventory"]
                    for row in target.rows("select inventory,initial_inventory from items")
                )
            # A new real coordinator starts after reset; reset drains its model/action work.
            assert (await client.post("/api/start", json={"condition": "swarm"})).status_code == 200
            await asyncio.sleep(0.2)
            assert (await client.post("/api/reset", json={"confirmed": True})).status_code == 202
            for _ in range(1200):
                workspace = (await client.get("/api/workspace")).json()
                if not workspace["resetting"]:
                    break
                await asyncio.sleep(0.05)
            assert not workspace["reset_failed"], workspace
            assert not (await client.get("/api/state")).json()["findings"]
            assert not (OUT / "memory").exists()
            print(
                "PASS real SQLite replay/review/history/config, six fixture comparisons, "
                "stop, idle/active reset and post-reset reuse"
            )
            print(
                json.dumps(
                    {
                        "console": "pass",
                        "scripted_swarm_verified_ids": sorted(bugids),
                        "benchmark_runs": 6,
                        "gate": state["gate"],
                        "stop": "pass",
                    },
                    indent=2,
                )
            )
            (OUT / "console-results.json").write_text(json.dumps(state["gate"], indent=2))


import os

os.environ["SWARMTEST_RUN_SOURCE"] = "scripted-fixture"
os.environ["SWARMTEST_FIXTURE_KEY"] = "fixture"
server, thread, sock, url = launch(provider)
try:
    with BazaarEnvironment(OUT) as env:
        config = RunConfig.model_validate(
            yaml.safe_load((ROOT / "configs/bazaar.yaml").read_text())
        )
        config = config.model_copy(
            update={
                "spec": str(ROOT / "apps/bazaar/openapi.json"),
                "invariants": str(ROOT / "apps/bazaar/invariants.sql"),
                "app_base_url": env.live.url,
                "provider_base_url": url + "/v1",
                "model": "scripted-fixture",
                "api_key_env": "SWARMTEST_FIXTURE_KEY",
                "max_rounds": 6,
                "requests_per_minute": 1000000,
                "tokens_per_minute": 100000000,
                "input_cost_per_million": 0,
                "output_cost_per_million": 0,
            }
        )
        app = create_app(config, env, OUT)
        asyncio.run(verify(app, env))
finally:
    server.should_exit = True
    thread.join(timeout=10)
    sock.close()
    WORKSPACE.cleanup()
