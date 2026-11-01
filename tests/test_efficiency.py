"""Behavior checks for context fidelity, conservative accounting and live actions."""

import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import openai
from openai.types.chat import ChatCompletion

from adapters.openapi import OpenAPIAdapter
from bench.judge import judge_findings
from bench.metrics import BenchmarkRun
from detect.contracts import Finding, ReplayAction, ReplayPlan, ReplayStep, Request
from detect.store import SQLiteEventStore
from swarm.agent import AgentLoop, Decision
from swarm.budget import BudgetAccountingError, BudgetExhausted, TokenBudget
from swarm.context import CompactContext, ContextPolicy, bounded_value, stable_json
from swarm.events import RunEvents
from swarm.provider import ProviderPacer, _duration

ROOT = Path(__file__).resolve().parents[1]


def usage(prompt=100, completion=10, cached=None):
    details = None if cached is None else SimpleNamespace(cached_tokens=cached)
    return SimpleNamespace(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=prompt + completion,
        prompt_tokens_details=details,
    )


def model_response(tool="list_items", arguments=None, cached=None):
    data = {
        "id": "fixture-call",
        "object": "chat.completion",
        "created": 1,
        "model": "openai/gpt-oss-120b",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "unused reasoning " * 100,
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {"name": tool, "arguments": json.dumps(arguments or {})},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
    }
    if cached is not None:
        data["usage"]["prompt_tokens_details"] = {"cached_tokens": cached}
    return data


class EfficiencyChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteEventStore(Path(self.tmp.name) / "events.sqlite3")
        self.addCleanup(self.store.close)
        self.adapter = OpenAPIAdapter(ROOT / "apps/bazaar/openapi.json", "http://fixture")
        self.events = RunEvents(self.store, "efficiency-check", 1)

    def actor(self, account=2, policy=None, agent_id="a"):
        actor = AgentLoop(
            agent_id,
            "casual_buyer",
            "Explore",
            "points",
            "https://api.groq.com/openai/v1",
            "openai/gpt-oss-120b",
            "fixture",
            "http://fixture",
            "efficiency-check",
            1,
            adapter=self.adapter,
            events=self.events,
            seeded_user_id=account,
            tool_definitions=self.adapter.get_tool_definitions(["list_items", "add_to_cart"]),
            budget=TokenBudget(
                100000, input_price=0.15, output_price=0.6, cached_input_price=0.075
            ),
            completion_tool=None,
            context_policy=policy,
        )
        self.addCleanup(actor.close)
        return actor

    def execute(self, actor, tool, args, body, status=200):
        message = ChatCompletion.model_validate(model_response(tool, args)).choices[0].message
        request = self.adapter.prepare_request(tool, args)
        slot = self.events.reserve(actor.step, [actor.agent_id])[0]
        with patch.object(self.adapter, "execute_request", return_value=(status, body, 1)) as live:
            event = actor.execute(Decision(tool, args, request, 0, message), slot)
        live.assert_called_once()
        return event

    def test_compaction_keeps_complete_pairs_and_raw_evidence(self):
        actor = self.actor()
        body = json.dumps(
            [{"id": i, "stock": 10, "description": "long text " * 80} for i in range(1, 15)]
        )
        events = [self.execute(actor, "list_items", {"q": str(i)}, body) for i in range(12)]
        self.assertEqual(len(actor.context.turns), 2)
        self.assertEqual(actor.context.compactions, 10)
        self.assertLessEqual(len(stable_json(actor.context.snapshot()).encode()), 6144)
        messages = actor.messages()
        for index, message in enumerate(messages):
            if message.get("tool_calls"):
                following = messages[index + 1]
                self.assertEqual(following["tool_call_id"], message["tool_calls"][0]["id"])
                self.assertIsNone(message["content"])
                result = json.loads(following["content"])
                self.assertIn("1", stable_json(result))
                self.assertLessEqual(len(following["content"].encode()), 2048)
        self.assertNotIn("unused reasoning", stable_json(messages))
        self.assertEqual(len(self.store.events("efficiency-check")), 12)
        self.assertEqual(events[-1].response_json, json.loads(body))
        actor.context.save(Path(self.tmp.name) / "memory", "a", 11, 12)
        saved = json.loads(next((Path(self.tmp.name) / "memory").rglob("*.json")).read_text())
        self.assertEqual(saved["completed_actions"], 12)
        self.assertEqual(len(saved["recent_turns"]), 2)

    def test_dynamic_ids_and_changed_observations_survive(self):
        context = CompactContext(ContextPolicy())
        request = Request(method="POST", path="/api/checkout", json_body={"user_id": 2})
        context.action("checkout", request, 200, '{"order_id":987}', [])
        for i in range(4):
            context.action(
                "read",
                request.model_copy(update={"method": "GET", "path": f"/read/{i}"}),
                200,
                "{}",
                [],
            )
        self.assertIn("987", stable_json(context.snapshot()))
        for stock in (4, 3, 3):
            context.observe(
                {
                    "operation": "list_items",
                    "request": {"item_id": 1},
                    "result": {"id": 1, "stock": stock},
                }
            )
        observations = context.snapshot()["observations"]
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0]["value"]["result"]["stock"], 3)
        self.assertEqual(observations[0]["count"], 2)
        self.assertLessEqual(len(stable_json(bounded_value('\\"🔥' * 10000, 256)).encode()), 256)

    def test_idle_reads_stop_without_model_call_but_writes_repeat_live(self):
        actor = self.actor()
        for _ in range(4):
            self.execute(actor, "list_items", {}, '[{"id":1,"stock":2}]')
        with patch.object(actor, "_model_call", side_effect=AssertionError("wasted model call")):
            self.assertIsNone(actor.decide())
        self.assertEqual(actor.stop_reason, "unchanged_reads")
        other = self.actor()
        for _ in range(6):
            self.execute(other, "add_to_cart", {"user_id": 2, "item_id": 1, "quantity": 1}, "{}")
        self.assertEqual(other.context.read_count, 0)
        self.assertEqual(other.step, 6)
        for _ in range(3):
            self.execute(
                other,
                "add_to_cart",
                {"user_id": 2, "item_id": 1, "quantity": 1},
                '{"detail":"unchanged conflict"}',
                status=409,
            )
        self.assertEqual(other.step, 9)
        self.assertIn("failed identically", other.context.hint)
        self.assertFalse(other.stopped)

        other.context.read_count = 3
        other.context.reset_idle()  # Coordinator applies this after a peer's successful write.
        self.assertEqual(other.context.read_count, 0)

    def test_prefix_is_stable_and_private_observations_do_not_leak(self):
        actor, other = self.actor(), self.actor(3, agent_id="b")
        self.assertEqual(actor.messages()[0], other.messages()[0])
        self.assertNotEqual(actor.messages()[1], other.messages()[1])
        event = self.execute(
            actor, "add_to_cart", {"user_id": 2, "item_id": 1, "quantity": 1}, "{}"
        )
        other.observe([event])
        self.assertFalse(other.context.observations)

    def test_only_verified_own_operations_become_notices(self):
        actor = self.actor()
        finding = Finding(
            run_id="efficiency-check",
            title="Private oracle title",
            severity="high",
            type="emergent",
            evidence_events=["one", "two"],
            involved_agents=["a", "b"],
            oracle_triggered="private-oracle",
            mapped_bug_id="E1",
            minimal_repro_sequence=ReplayPlan(
                seed=1,
                steps=[
                    ReplayStep(
                        actions=[
                            ReplayAction(
                                event_id="one",
                                agent_id="a",
                                expected_status=200,
                                request=Request(
                                    method="POST",
                                    path="/api/checkout",
                                    json_body={"user_id": 2, "item_id": 1},
                                ),
                            ),
                            ReplayAction(
                                event_id="two",
                                agent_id="b",
                                expected_status=200,
                                request=Request(method="POST", path="/private-peer/555"),
                            ),
                        ]
                    )
                ],
            ),
        )
        actor.known_finding(finding)
        self.assertFalse(actor.context.notices)
        actor.known_finding(finding.model_copy(update={"verified": True}))
        snapshot = stable_json(actor.context.snapshot())
        self.assertIn("/api/checkout", snapshot)
        self.assertIn('"item_id":1', snapshot)
        self.assertNotIn("E1", snapshot)
        self.assertNotIn("private", snapshot)

    def test_sdk_cache_usage_cost_and_provider_refund(self):
        actor = self.actor()
        actor.client.close()
        captured = []

        def respond(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200, json=model_response(cached=60))

        actor.client = openai.OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key="fixture",
            http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        )
        actor.pacer = ProviderPacer(100000, 100000)
        with patch.object(actor.pacer, "finish", wraps=actor.pacer.finish) as refund:
            decision = actor.decide()
        self.assertIsNotNone(decision)
        self.assertEqual(refund.call_args.args[1], 50)  # 100 + 10 - 60 confirmed cached tokens.
        self.assertEqual(actor.budget.used, 110)  # Token budget still counts cached input.
        self.assertAlmostEqual(actor.budget.cost_usd, 0.0000165)
        self.assertEqual(actor.budget.summary()["cache_reporting"], "reported")
        self.assertEqual(captured[0]["reasoning_effort"], "low")
        self.assertNotIn("tools", captured[0])
        self.assertNotIn("response_format", captured[0])
        self.assertFalse(captured[0]["include_reasoning"])

    def test_invalid_decisions_stop_after_three_and_cannot_execute(self):
        actor = self.actor()
        response = ChatCompletion.model_validate(model_response("forbidden"))
        with patch.object(actor, "_model_call", return_value=(response, 110)) as model:
            for _ in range(5):
                self.assertIsNone(actor.decide())
        self.assertEqual(model.call_count, 3)
        self.assertEqual(actor.stop_reason, "invalid_decisions")
        self.assertEqual(self.store.events("efficiency-check"), [])

    def test_conservative_budgets_and_malformed_usage_fail_closed(self):
        root = TokenBudget(100000, input_price=1, output_price=2, cached_input_price=0.5)
        actor = TokenBudget(100000, parent=root)
        reservation, _ = actor.reserve([], None, 512)
        actor.finish(reservation, usage(cached=80))
        self.assertEqual(root.cached_prompt_tokens, 80)
        self.assertEqual(root.used, 110)
        self.assertAlmostEqual(root.cost_usd, 0.00008)
        reservation, _ = actor.reserve([], None, 512)
        with self.assertRaises(BudgetAccountingError):
            actor.finish(reservation, usage(cached=101))
        self.assertTrue(root.uncertain)
        self.assertEqual(root._reserved, 0)
        for bad in (None, usage(cached=-1), usage(cached=True)):
            budget = TokenBudget(10000)
            reservation, _ = budget.reserve([], None, 512)
            with self.assertRaises(BudgetAccountingError):
                budget.finish(reservation, bad)
        budget = TokenBudget(
            10000, input_price=1, output_price=2, cached_input_price=0, max_dollars=0.0001
        )
        with self.assertRaises(BudgetExhausted):
            budget.reserve([], None, 512)  # Cannot assume a cache hit during admission.
        budget = TokenBudget(10000, input_price=1, output_price=2)
        reservation, _ = budget.reserve([], None, 512)
        budget.finish(reservation, usage())
        self.assertEqual(budget.summary()["cache_reporting"], "unreported")
        self.assertAlmostEqual(budget.cost_usd, 0.00012)

    def test_judge_uses_confirmed_cache_usage_and_separate_budget(self):
        finding = Finding(
            run_id="judge",
            title="Empty checkout crash",
            severity="high",
            type="single-user",
            evidence_events=["one"],
            involved_agents=["a"],
            oracle_triggered="empty",
            mapped_bug_id="S1",
            verified=True,
            minimal_repro_sequence=ReplayPlan(
                seed=1,
                steps=[
                    ReplayStep(
                        actions=[
                            ReplayAction(
                                event_id="one",
                                agent_id="a",
                                expected_status=500,
                                request=Request(method="POST", path="/api/checkout"),
                            )
                        ]
                    )
                ],
            ),
        )
        run = BenchmarkRun(
            run_id="judge",
            condition="isolated",
            seed=1,
            model="fixture",
            token_budget=1000,
            tokens_used=0,
            cost_usd=0,
            elapsed_s=1,
            findings=[finding],
        )
        data = model_response(cached=60)
        data["choices"][0]["message"] = {
            "role": "assistant",
            "content": json.dumps(
                {"bug_id": "S1", "valid_finding": True, "reason": "Fixture evidence"}
            ),
        }
        data["choices"][0]["finish_reason"] = "stop"
        client = openai.OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key="fixture",
            http_client=httpx.Client(
                transport=httpx.MockTransport(lambda request: httpx.Response(200, json=data))
            ),
        )
        config = SimpleNamespace(
            model="openai/gpt-oss-120b",
            max_dollars=1,
            input_cost_per_million=0.15,
            output_cost_per_million=0.6,
            cached_input_cost_per_million=0.075,
            requests_per_minute=100000,
            tokens_per_minute=100000,
            seed=1,
            provider_base_url="https://api.groq.com/openai/v1",
        )
        with patch("bench.judge.openai.OpenAI", return_value=client):
            result = judge_findings([run], {"S1": "single-user"}, config, "fixture")
        self.assertEqual(result["tokens_used"], 110)
        self.assertAlmostEqual(result["cost_usd"], 0.0000165)
        self.assertEqual(result["efficiency"]["model_calls"], 1)
        self.assertEqual(run.tokens_used, 0)  # Exploration budget remains separate.
        with patch("bench.judge.openai.OpenAI", return_value=client):
            with self.assertRaises(BudgetExhausted):
                judge_findings(
                    [run], {"S1": "single-user"}, config, "fixture", cancelled=lambda: True
                )

    def test_rate_feedback_never_increases_capacity_and_stop_is_responsive(self):
        pacer = ProviderPacer(24, 7000)
        pacer.observe({"X-RateLimit-Limit-Tokens": "999999", "X-RateLimit-Limit-Requests": "14400"})
        self.assertEqual(pacer.tokens_per_minute, 7000)
        self.assertEqual(pacer.requests_per_minute, 24)
        pacer.observe(
            {
                "x-ratelimit-limit-tokens": "3000",
                "x-ratelimit-remaining-tokens": "100",
                "Retry-After": "30",
            }
        )
        self.assertLessEqual(pacer.tokens, 100)
        self.assertGreater(pacer.blocked_until, time.monotonic() + 29)
        before = time.monotonic()
        with self.assertRaises(BudgetExhausted):
            pacer.wait(500, 100, lambda: True)
        self.assertLess(time.monotonic() - before, 0.1)
        with self.assertRaises(BudgetExhausted):
            pacer.wait(3001, 1)
        self.assertEqual(_duration("2m59.56s"), 179.56)
        self.assertEqual(_duration("10ms"), 0.01)


if __name__ == "__main__":
    unittest.main()
