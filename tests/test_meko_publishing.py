"""Publishing must run after local export and never claim failed uploads succeeded."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import httpx
import requests

from dashboard.server import create_app
from detect.contracts import Finding, ReplayAction, ReplayPlan, ReplayStep, Request
from detect.report import write_report
from memory.meko import MekoClient
from memory.publish import FindingsPublishError, publish_run_findings
from memory.store import LocalMemoryStore, MekoMemoryStore
from swarm.cli import main
from swarm.provider import load_config
from swarm.runtime import RunResult

ROOT = Path(__file__).resolve().parents[1]


def finding():
    return Finding(
        run_id=str(uuid4()),
        title="Fixture finding",
        severity="high",
        type="single-user",
        verified=True,
        evidence_events=["e"],
        involved_agents=["a"],
        oracle_triggered="fixture",
        minimal_repro_sequence=ReplayPlan(
            seed=1,
            steps=[
                ReplayStep(
                    actions=[
                        ReplayAction(
                            event_id="e",
                            agent_id="a",
                            request=Request(method="GET", path="/api/items"),
                        )
                    ]
                )
            ],
        ),
    )


class PublishingChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.config = load_config(ROOT / "swarmtest.yaml")
        self.client = Mock()
        self.finding = finding()

    def store(self, *args):
        return MekoMemoryStore(LocalMemoryStore(self.directory / "findings.sqlite3"), self.client)

    def test_failed_publish_is_visible_locally_and_retry_skips_successes(self):
        with patch("memory.publish.create_memory_store", side_effect=self.store):
            self.client.publish_finding.side_effect = RuntimeError("private provider details")
            with self.assertRaises(FindingsPublishError):
                publish_run_findings(self.config, [self.finding], self.directory)
            receipt = json.loads((self.directory / "findings-sync.json").read_text())
            self.assertEqual(receipt["status"], "pending")
            self.assertNotIn("private", json.dumps(receipt))
            with LocalMemoryStore(self.directory / "findings.sqlite3") as local:
                self.assertEqual(local.recall_findings(self.config.project)[0].id, self.finding.id)
            self.client.publish_finding.side_effect = None
            receipt = publish_run_findings(self.config, [self.finding], self.directory)
            self.assertEqual(receipt["status"], "complete")
            publish_run_findings(self.config, [self.finding], self.directory)
            self.assertEqual(self.client.publish_finding.call_count, 2)

    def test_missing_credentials_never_claims_remote_success(self):
        with patch(
            "memory.publish.create_memory_store",
            side_effect=lambda *args: LocalMemoryStore(self.directory / "findings.sqlite3"),
        ):
            with self.assertRaises(FindingsPublishError):
                publish_run_findings(self.config, [self.finding], self.directory)
        receipt = json.loads((self.directory / "findings-sync.json").read_text())
        self.assertEqual(receipt["findings"][self.finding.id]["status"], "pending")

    def test_cli_publish_uses_saved_report_without_model_calls(self):
        write_report([self.finding], self.directory)
        with (
            patch(
                "sys.argv",
                [
                    "swarmtest",
                    "publish",
                    "--config",
                    str(ROOT / "swarmtest.yaml"),
                    "--output",
                    str(self.directory),
                ],
            ),
            patch("memory.publish.create_memory_store", side_effect=self.store),
            patch("swarm.cli.credential", side_effect=AssertionError("Must not call Groq")),
            patch("builtins.print"),
        ):
            main()
            main()
        self.client.publish_finding.assert_called_once()

    def test_json_and_sse_mcp_responses_and_tool_errors(self):
        client = MekoClient(api_key="test-key", datapack_id="fixture")
        for mime, body in [
            ("application/json", '{"result":{"content":[{"type":"text","text":"{}"}]}}'),
            ("text/event-stream", 'data: {"result":{"content":[{"type":"text","text":"{}"}]}}\n\n'),
        ]:
            response = requests.Response()
            response.status_code = 200
            response.headers["Content-Type"] = mime
            response._content = body.encode()
            with patch("memory.meko.requests.post", return_value=response):
                self.assertEqual(client.call_tool("fixture", {}), {})
        response._content = b'{"result":{"isError":true,"content":[]}}'
        response.headers["Content-Type"] = "application/json"
        with patch("memory.meko.requests.post", return_value=response):
            with self.assertRaises(RuntimeError):
                client.call_tool("fixture", {})

    def test_upload_waits_for_indexing_and_accepts_s3_201(self):
        client = MekoClient(api_key="test-key", datapack_id="fixture")
        client._conversation_id = "fixture-conversation"
        with (
            patch.object(
                client,
                "call_tool",
                side_effect=[
                    {"url": "https://upload.invalid", "fields": {"key": "x"}, "key": "doc"},
                    {"state": "processing"},
                    {"state": "indexed"},
                ],
            ),
            patch("memory.meko.requests.post", return_value=SimpleNamespace(status_code=201)),
            patch("memory.meko.time.sleep"),
        ):
            result = client.upload_knowledgebase_document("finding.md", "fixture")
            self.assertEqual(result["indexing_state"], "indexed")


class DashboardPublishingChecks(unittest.IsolatedAsyncioTestCase):
    async def test_completed_run_exports_before_publishing_and_exposes_upload_failure(self):
        config = load_config(ROOT / "swarmtest.yaml")
        saved = finding()

        class Runner:
            def __init__(self, *args, **kwargs):
                pass

            async def run(self, condition):
                return RunResult(
                    saved.run_id, condition, 1, "fixture", 1000, 0, 0, 0.1, [], findings=[saved]
                )

        def publish(config, findings, directory):
            self.assertTrue((directory / "report.json").exists())
            self.assertTrue((directory / "run.json").exists())
            self.assertEqual(findings, [saved])
            raise FindingsPublishError()

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("dashboard.server.RunCoordinator", Runner),
            patch("dashboard.server.make_hooks", return_value=None),
            patch("dashboard.server.credential", return_value="fixture"),
            patch("dashboard.server.publish_run_findings", side_effect=publish) as publisher,
        ):
            app = create_app(
                config, SimpleNamespace(live=SimpleNamespace(url="http://fixture")), Path(tmp)
            )
            async with (
                app.router.lifespan_context(app),
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://console"
                ) as client,
            ):
                self.assertEqual((await client.post("/api/start", json={})).status_code, 200)
                for _ in range(100):
                    state = (await client.get("/api/workspace")).json()
                    if state["error"]:
                        break
                    await asyncio.sleep(0.01)
                self.assertIn("Meko publishing is incomplete", state["error"])
                publisher.assert_called_once()
                self.assertTrue((Path(tmp) / saved.run_id / "report.json").exists())


if __name__ == "__main__":
    unittest.main()
