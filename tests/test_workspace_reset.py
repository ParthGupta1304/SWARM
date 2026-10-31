"""Destructive reset checks use isolated temporary workspaces and fake providers."""

import asyncio
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import httpx

from dashboard.reset import cleanup_plan
from dashboard.server import create_app
from detect.contracts import Event, Request
from detect.store import SQLiteEventStore
from swarm.provider import load_config
from swarm.runtime import RunResult

ROOT = Path(__file__).resolve().parents[1]


def event(run_id):
    return Event(
        run_id=run_id,
        seed=1,
        round=0,
        sequence=0,
        agent_id="actor",
        role="fixture",
        tool="list_items",
        request=Request(method="GET", path="/api/items"),
        response_status=200,
        response_json=[],
        latency_ms=0,
        tokens_used=0,
    )


class WorkspaceResetChecks(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = (await asyncio.to_thread(Path(self.tmp.name).resolve)) / "workspace"
        self.root.mkdir()
        self.targets = self.root / "targets-abcdefgh"
        self.targets.mkdir()
        (self.targets / "current.db").write_text("active target backing file")
        self.backend = {"runs": [], "findings": [], "events": []}
        self.after_ids = []
        self.write_started = asyncio.Event()
        self.write_release = asyncio.Event()
        self.hold_write = False
        self.order = []
        self.reset_count = 0
        self.runner_started = threading.Event()
        self.runner_release = threading.Event()
        self.runners = []

        def reseed(seed):
            self.reset_count += 1
            self.order.append("reset")
            self.backend.update(runs=[], findings=[], events=[])

        self.env = SimpleNamespace(
            directory=self.targets,
            live=SimpleNamespace(url="http://bazaar"),
            reset_workspace=Mock(side_effect=reseed),
        )
        self.config = load_config(ROOT / "configs/bazaar.yaml")
        self.app = create_app(self.config, self.env, self.root)
        self.lifecycle = self.app.router.lifespan_context(self.app)
        await self.lifecycle.__aenter__()
        original_client = httpx.AsyncClient
        self.client = original_client(
            transport=httpx.ASGITransport(app=self.app), base_url="http://console"
        )

        async def target(request):
            if request.method == "POST":
                self.write_started.set()
                if self.hold_write:
                    await self.write_release.wait()
                self.backend["events"].append({"id": 1, "event_type": "manual_write"})
                self.order.append("write")
                return httpx.Response(200, json={"ok": True})
            resource = request.url.path.rsplit("/", 1)[-1]
            if resource == "events":
                after = int(request.url.params.get("after_id", 0))
                self.after_ids.append(after)
                return httpx.Response(
                    200, json=[e for e in self.backend["events"] if e["id"] > after]
                )
            return httpx.Response(200, json=self.backend.get(resource, []))

        self.http_patch = patch(
            "dashboard.server.httpx.AsyncClient",
            side_effect=lambda *a, **kw: original_client(
                *a, **kw, transport=httpx.MockTransport(target)
            ),
        )
        self.http_patch.start()
        self.credential_patch = patch("dashboard.server.credential", return_value="fixture")
        self.credential_patch.start()
        self.hooks_patch = patch("dashboard.server.make_hooks", return_value=None)
        self.hooks_patch.start()
        owner = self

        class Runner:
            def __init__(self, config, store, **kwargs):
                self.config, self.store = config, store
                self.stopping = threading.Event()
                owner.runners.append(self)

            def stop(self):
                self.stopping.set()

            async def run(self, condition):
                owner.runner_started.set()
                deadline = time.monotonic() + 5
                while not (self.stopping.is_set() and owner.runner_release.is_set()):
                    if time.monotonic() > deadline:
                        raise RuntimeError("fixture did not receive cooperative stop")
                    await asyncio.sleep(0.005)
                # Simulate a final write after Stop: reset must wait for this and exports.
                run_id = str(uuid4())
                self.store.append(event(run_id))
                memory = owner.root / "memory"
                memory.mkdir(exist_ok=True)
                (memory / "last.json").write_text("{}")
                owner.order.append("run-write")
                return RunResult(run_id, condition, 1, "fixture", 1000, 0, 0, 0.1, [], stopped=True)

        self.runner_patch = patch("dashboard.server.RunCoordinator", Runner)
        self.runner_patch.start()

    async def asyncTearDown(self):
        self.runner_release.set()
        self.write_release.set()
        await self.lifecycle.__aexit__(None, None, None)
        await self.client.aclose()
        self.runner_patch.stop()
        self.hooks_patch.stop()
        self.credential_patch.stop()
        self.http_patch.stop()
        self.tmp.cleanup()

    async def reset(self):
        response = await self.client.post("/api/reset", json={"confirmed": True})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.headers["clear-site-data"], '"cache"')
        return await self.finish_reset()

    async def finish_reset(self):
        for _ in range(500):
            state = (await self.client.get("/api/workspace")).json()
            if not state["resetting"]:
                return state
            await asyncio.sleep(0.005)
        self.fail("Reset did not finish")

    def stored_events(self):
        with sqlite3.connect(self.root / "events.sqlite3") as db:
            return db.execute("SELECT count(*) FROM events").fetchone()[0]

    async def test_idle_reset_clears_generated_state_and_preserves_other_files(self):
        relative = Path(await asyncio.to_thread(os.path.relpath, self.root))
        self.assertNotIn(self.targets, cleanup_plan(relative, self.targets))
        initial = (await self.client.get("/api/workspace")).json()["generation"]
        run_id = str(uuid4())
        store = SQLiteEventStore(self.root / "events.sqlite3")
        store.append(event(run_id))
        store.close()
        for name in ("memory", "benchmark", run_id, "targets-12345678"):
            folder = self.root / name
            folder.mkdir()
            (folder / "data.json").write_text("{}")
        (self.root / "checkpoint.json").write_text("{}")
        (self.root / ".env").write_text("placeholder-only")
        (self.root / "notes.txt").write_text("keep")
        self.backend.update(
            runs=[{"run_id": run_id, "status": "completed"}], findings=[{"id": "finding"}]
        )
        self.assertEqual((await self.client.post("/api/reset", json={})).status_code, 422)
        state = await self.reset()
        self.assertFalse(state["reset_failed"])
        self.assertNotEqual(state["generation"], initial)
        self.assertEqual(self.reset_count, 1)
        self.assertEqual(self.stored_events(), 0)
        for name in ("memory", "benchmark", run_id, "targets-12345678", "checkpoint.json"):
            self.assertFalse((self.root / name).exists(), name)
        self.assertTrue((self.targets / "current.db").exists())
        self.assertEqual((self.root / ".env").read_text(), "placeholder-only")
        self.assertEqual((self.root / "notes.txt").read_text(), "keep")
        snapshot = (await self.client.get("/api/state")).json()
        for key in ("runs", "findings", "events", "actions"):
            self.assertEqual(snapshot[key], [])
        self.assertIsNone(snapshot["benchmark"])
        self.assertIsNone(snapshot["gate"])
        self.assertIsNone(snapshot["error"])

    async def test_reset_drains_active_run_and_rejects_overlapping_operations(self):
        self.assertEqual(
            (await self.client.post("/api/start", json={"condition": "swarm"})).status_code, 200
        )
        self.assertTrue(await asyncio.to_thread(self.runner_started.wait, 2))
        first = await self.client.post("/api/reset", json={"confirmed": True})
        second = await self.client.post("/api/reset", json={"confirmed": True})
        self.assertEqual((first.status_code, second.status_code), (202, 202))
        self.assertEqual(self.reset_count, 0)
        self.assertEqual(
            (await self.client.post("/api/start", json={"condition": "swarm"})).status_code, 409
        )
        self.assertEqual(
            (await self.client.post("/market/api/cart/items", json={})).status_code, 409
        )
        self.assertEqual(
            (
                await self.client.post(
                    "/api/review",
                    json={
                        "finding_id": "x",
                        "correct": True,
                        "reviewer": "test",
                        "note": "fixture",
                    },
                )
            ).status_code,
            409,
        )
        self.assertTrue(self.runners[0].stopping.is_set())
        self.runner_release.set()
        state = await self.finish_reset()
        self.assertFalse(state["reset_failed"])
        self.assertEqual(self.order, ["run-write", "reset"])
        self.assertEqual(self.reset_count, 1)
        self.assertEqual(self.stored_events(), 0)
        self.assertFalse((self.root / "memory").exists())
        await asyncio.sleep(0.025)
        self.assertEqual(self.stored_events(), 0)
        self.runner_started.clear()
        self.assertEqual(
            (await self.client.post("/api/start", json={"condition": "swarm"})).status_code, 200
        )
        self.assertTrue(await asyncio.to_thread(self.runner_started.wait, 2))
        await self.client.post("/api/stop")

    async def test_reset_stops_benchmark_before_another_seed_starts(self):
        self.assertEqual(
            (await self.client.post("/api/start", json={"condition": "benchmark"})).status_code, 200
        )
        self.assertTrue(await asyncio.to_thread(self.runner_started.wait, 2))
        await self.client.post("/api/reset", json={"confirmed": True})
        self.runner_release.set()
        state = await self.finish_reset()
        self.assertFalse(state["reset_failed"])
        self.assertEqual(len(self.runners), 1)
        self.assertEqual(self.stored_events(), 0)
        self.assertFalse((self.root / "benchmark").exists())

    async def test_failure_blocks_new_runs_and_retry_recovers(self):
        generation = (await self.client.get("/api/workspace")).json()["generation"]
        with patch("dashboard.server.clear_artifacts", side_effect=OSError("fixture failure")):
            state = await self.reset()
        self.assertTrue(state["reset_failed"])
        self.assertEqual(state["generation"], generation)
        self.assertIn("Reset failed", state["error"])
        self.assertEqual(
            (await self.client.post("/api/start", json={"condition": "swarm"})).status_code, 409
        )
        self.assertEqual(
            (await self.client.post("/market/api/cart/items", json={})).status_code, 409
        )
        self.assertTrue((await self.client.get("/api/state")).json()["reset_failed"])
        state = await self.reset()
        self.assertFalse(state["reset_failed"])
        self.assertNotEqual(state["generation"], generation)

    async def test_unsafe_symlink_fails_preflight_without_reseeding(self):
        outside = Path(self.tmp.name) / "external"
        outside.mkdir()
        (outside / "keep").write_text("keep")
        (self.root / "memory").symlink_to(outside, target_is_directory=True)
        state = await self.reset()
        self.assertTrue(state["reset_failed"])
        self.assertEqual(self.reset_count, 0)
        self.assertEqual((outside / "keep").read_text(), "keep")
        (self.root / "memory").unlink()
        self.assertFalse((await self.reset())["reset_failed"])
        with self.assertRaises(ValueError):
            cleanup_plan(ROOT, ROOT / "targets-abcdefgh")

    async def test_manual_write_finishes_before_reset(self):
        self.hold_write = True
        write = asyncio.create_task(self.client.post("/market/api/cart/items", json={}))
        await self.write_started.wait()
        reset = asyncio.create_task(self.client.post("/api/reset", json={"confirmed": True}))
        await asyncio.sleep(0.02)
        self.assertEqual(self.reset_count, 0)
        self.write_release.set()
        self.assertEqual((await write).status_code, 200)
        self.assertEqual((await reset).status_code, 202)
        self.assertFalse((await self.finish_reset())["reset_failed"])
        self.assertEqual(self.order, ["write", "reset"])
        self.assertFalse(self.backend["events"])

    async def test_saved_results_are_read_only(self):
        external = Path(self.tmp.name) / "saved"
        external.mkdir()
        (external / "manual-review.json").write_text("[]")
        app = create_app(self.config, self.env, self.root, results=external)
        original_client = self.client.__class__
        async with app.router.lifespan_context(app):
            async with original_client(
                transport=httpx.ASGITransport(app=app), base_url="http://console"
            ) as client:
                self.assertFalse((await client.get("/api/workspace")).json()["reset_allowed"])
                self.assertEqual(
                    (await client.post("/api/reset", json={"confirmed": True})).status_code, 409
                )
        self.assertTrue((external / "manual-review.json").exists())

    async def test_sse_drops_cursor_from_old_generation(self):
        old = (await self.client.get("/api/workspace")).json()["generation"]
        await self.reset()
        self.backend["events"] = [{"id": 1, "event_type": "fresh"}]

        async def disconnected():
            return False

        route = next(
            route for route in self.app.routes if getattr(route, "path", None) == "/api/stream"
        )
        response = await route.endpoint(
            SimpleNamespace(headers={"last-event-id": old + ":999"}, is_disconnected=disconnected)
        )
        try:
            payload = await anext(response.body_iterator)
        finally:
            await response.body_iterator.aclose()
        body = json.loads(payload.split("data: ", 1)[1])
        stale = await self.client.get("/api/workspace", params={"previous": old})
        self.assertEqual(stale.headers["clear-site-data"], '"cache"')
        self.assertNotEqual(body["generation"], old)
        self.assertEqual(body["events"][0]["id"], 1)
        self.assertEqual(self.after_ids[-1], 0)


if __name__ == "__main__":
    unittest.main()
