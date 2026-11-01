"""Groq decision formatting, credential rotation and safe failure propagation."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import openai

from adapters.openapi import OpenAPIAdapter
from dashboard.server import create_app
from detect.store import SQLiteEventStore
from swarm.agent import AgentLoop
from swarm.budget import BudgetAccountingError, ProviderCallError, TokenBudget
from swarm.events import RunEvents
from swarm.provider import credential, load_config

ROOT = Path(__file__).resolve().parents[1]


class GroqActionChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteEventStore(Path(self.tmp.name) / "events.sqlite3")
        self.addCleanup(self.store.close)
        self.root_budget = TokenBudget(100000)
        self.requests = []

    def actor(self, handler):
        adapter = OpenAPIAdapter(ROOT / "apps/bazaar/openapi.json", "http://fixture")
        actor = AgentLoop(
            "buyer",
            "casual_buyer",
            "Browse listings",
            "purchases",
            "https://api.groq.com/openai/v1",
            "openai/gpt-oss-120b",
            "fixture",
            "http://fixture",
            "check",
            1,
            adapter=adapter,
            events=RunEvents(self.store, "check", 1),
            seeded_user_id=2,
            fixed_arguments={"user_id": 2},
            completion_tool=None,
            tool_definitions=adapter.get_tool_definitions(["list_items", "add_to_cart"]),
            budget=TokenBudget(30000, parent=self.root_budget),
        )
        actor.client.close()

        def respond(request):
            self.requests.append(json.loads(request.content))
            return handler(request)

        actor.client = openai.OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key="fixture",
            http_client=httpx.Client(transport=httpx.MockTransport(respond)),
            max_retries=0,
        )
        self.addCleanup(actor.close)
        return actor

    def test_json_actions_are_validated_and_bad_decisions_cannot_execute(self):
        actions = iter(
            [
                {"tool": "forbidden", "arguments": {}},
                {"tool": "list_items", "arguments": {}},
            ]
        )

        def reply(_):
            return httpx.Response(
                200,
                json={
                    "id": "test",
                    "object": "chat.completion",
                    "created": 1,
                    "model": "openai/gpt-oss-120b",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(next(actions)),
                            },
                        }
                    ],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
                },
            )

        actor = self.actor(reply)
        self.assertIsNone(actor.decide())
        decision = actor.decide()
        self.assertEqual(decision.tool, "list_items")
        self.assertEqual(actor.invalid_tool_calls, 1)
        self.assertEqual(self.root_budget.used, 220)
        self.assertFalse(self.root_budget.uncertain)
        self.assertEqual(self.store.events("check"), [])
        for payload in self.requests:
            self.assertNotIn("tools", payload)
            self.assertNotIn("parallel_tool_calls", payload)
            self.assertNotIn("response_format", payload)
            self.assertFalse(payload["include_reasoning"])
            self.assertEqual(payload["max_tokens"], 2048)
            self.assertIn("Available actions (JSON Schema)", payload["messages"][0]["content"])

    def test_malformed_and_truncated_text_is_accounted_and_never_executed(self):
        for content, finish in [
            ('{"tool":"list_items","arguments":', "stop"),
            ('{"tool":"list_items","arguments":{}}', "length"),
            ('explanation {"tool":"list_items","arguments":{}}', "stop"),
            ('[{"tool":"list_items","arguments":{}}]', "stop"),
            ('{"tool":"add_to_cart","arguments":{"item_id":"invalid"}}', "stop"),
        ]:
            with self.subTest(content=content, finish=finish):
                self.root_budget = TokenBudget(100000)
                actor = self.actor(
                    lambda _, content=content, finish=finish: httpx.Response(
                        200,
                        json={
                            "id": "test",
                            "object": "chat.completion",
                            "created": 1,
                            "model": "openai/gpt-oss-120b",
                            "choices": [
                                {
                                    "index": 0,
                                    "finish_reason": finish,
                                    "message": {"role": "assistant", "content": content},
                                }
                            ],
                            "usage": {
                                "prompt_tokens": 100,
                                "completion_tokens": 10,
                                "total_tokens": 110,
                            },
                        },
                    )
                )
                for _ in range(3):
                    self.assertIsNone(actor.decide())
                self.assertEqual(actor.stop_reason, "invalid_decisions")
                self.assertEqual(actor.invalid_tool_calls, 3)
                self.assertEqual(self.root_budget.used, 330)
                self.assertFalse(self.root_budget.uncertain)
                self.assertEqual(self.store.events("check"), [])

    def test_provider_rejections_keep_the_root_cause_and_do_not_invent_usage(self):
        for status, code, message in [
            (400, "tool_use_failed", "malformed native tool call"),
            (400, "json_validate_failed", "invalid JSON"),
            (401, "invalid_api_key", "rejected the API key"),
            (429, "rate_limit_exceeded", "rate limit or account quota"),
        ]:
            with self.subTest(status=status):
                self.root_budget = TokenBudget(100000)
                actor = self.actor(
                    lambda _, status=status, code=code: httpx.Response(
                        status,
                        json={
                            "error": {
                                "code": code,
                                "message": "secret raw provider details",
                            }
                        },
                    )
                )
                self.assertIsNone(actor.decide())
                error = self.root_budget.failure
                self.assertIsInstance(error, ProviderCallError)
                self.assertIn(message, error.user_message)
                self.assertNotIn("secret", error.user_message)
                self.assertTrue(self.root_budget.uncertain)
                self.assertEqual(self.root_budget.used, 0)
                self.assertEqual(self.root_budget._reserved, 0)
                with self.assertRaises(ProviderCallError) as raised:
                    self.root_budget.reserve([], None, 10)
                self.assertIs(raised.exception, error)
                self.assertEqual(self.store.events("check"), [])

    def test_key_rotation_reads_current_file_without_overwriting_server_environment(self):
        config = load_config(ROOT / "configs/bazaar.yaml")
        env = Path(self.tmp.name) / ".env"
        with (
            patch("swarm.provider.find_dotenv", return_value=str(env)),
            patch.dict("os.environ", {"GROQ_API_KEY": "old-process-key"}),
        ):
            env.write_text("GROQ_API_KEY=first-local-key\n")
            self.assertEqual(credential(config), "first-local-key")
            env.write_text("GROQ_API_KEY=rotated-local-key\n")
            self.assertEqual(credential(config), "rotated-local-key")
            env.write_text("GROQ_API_KEY=\n")
            with self.assertRaises(ValueError):
                credential(config)
            env.unlink()
            self.assertEqual(credential(config), "old-process-key")

    def test_unknown_codes_and_accounting_errors_never_echo_raw_provider_details(self):
        self.assertNotIn("secret", ProviderCallError(400, "secret_key_123").user_message)
        self.assertNotIn("secret", BudgetAccountingError("secret").user_message)


class ProviderErrorDisplayChecks(unittest.IsolatedAsyncioTestCase):
    async def test_dashboard_exposes_actionable_safe_provider_error(self):
        config = load_config(ROOT / "configs/bazaar.yaml")

        class RejectedRunner:
            def __init__(self, *args, **kwargs):
                pass

            async def run(self, condition):
                raise ProviderCallError(400, "tool_use_failed")

            def stop(self):
                pass

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("dashboard.server.RunCoordinator", RejectedRunner),
            patch("dashboard.server.credential", return_value="fixture"),
            patch("dashboard.server.make_hooks", return_value=None),
        ):
            environment = SimpleNamespace(live=SimpleNamespace(url="http://fixture"))
            app = create_app(config, environment, Path(tmp))
            async with (
                app.router.lifespan_context(app),
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://console"
                ) as client,
            ):
                self.assertEqual((await client.post("/api/start", json={})).status_code, 200)
                await asyncio.sleep(0)
                error = (await client.get("/api/workspace")).json()["error"]
                self.assertIn("tool_use_failed", error)
                self.assertIn("HTTP 400", error)
                self.assertNotIn("check provider configuration, limits and local logs", error)


if __name__ == "__main__":
    unittest.main()
