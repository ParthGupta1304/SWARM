"""Budgeted evaluator-only LLM matching, separate from exploration costs."""

import json
from collections.abc import Sequence

import openai

from bench.metrics import BenchmarkRun
from swarm.budget import TokenBudget, usage_counts
from swarm.context import stable_json
from swarm.provider import ProviderPacer, completion_with_headers, is_groq_cache

DESCRIPTIONS = {
    "E1": "Concurrent buyers purchase more units than initial stock",
    "E2": "Concurrent sessions redeem the same account coupon twice",
    "E4": "Overlapping refund and dispute requests pay the same order twice",
    "E5": "Seller or same-owner account reviews its listing",
    "E7": "Blocked account contacts seller using item questions",
    "S1": "Empty-cart checkout crashes",
    "S2": "Nonpositive cart quantity accepted",
    "S4": "Special-character search crashes",
}


def judge_findings(
    runs: Sequence[BenchmarkRun],
    truth: dict[str, str],
    config,
    api_key: str,
    *,
    token_budget: int = 20000,
) -> dict:
    budget = TokenBudget(
        token_budget,
        max_dollars=config.max_dollars,
        input_price=config.input_cost_per_million,
        output_price=config.output_cost_per_million,
        cached_input_price=config.cached_input_cost_per_million,
    )
    pacer = ProviderPacer(config.requests_per_minute, config.tokens_per_minute)
    judgements = []
    unique = {finding.id: finding for run in runs for finding in run.findings}
    with openai.OpenAI(
        base_url=config.provider_base_url, api_key=api_key, max_retries=0, timeout=30
    ) as client:
        for finding in unique.values():
            messages = [
                {
                    "role": "system",
                    "content": "You are an independent evaluation judge. Match the finding "
                    "to an ID in the supplied frozen catalog, or null if unsupported. Return "
                    "JSON with bug_id (catalog string ID or JSON null), valid_finding "
                    "(boolean: does the evidence support a real application failure?), "
                    "and a short reason. An unsupported candidate is false even if its "
                    "title resembles a catalog entry.",
                },
                {
                    "role": "user",
                    "content": stable_json(
                        {
                            "catalog": {
                                bug: {"type": kind, "description": DESCRIPTIONS[bug]}
                                for bug, kind in truth.items()
                            },
                            "title": finding.title,
                            "verified_by_oracle_replay": finding.verified,
                            "verification": finding.verification,
                            "causality": finding.causality,
                            "evidence": [
                                {k: v for k, v in row.items() if k != "bug_id"}
                                for row in finding.evidence[:3]
                            ],
                            "replay": [
                                [
                                    [
                                        action.agent_id,
                                        action.request.method,
                                        action.request.path,
                                        action.request.query,
                                        action.request.json_body,
                                    ]
                                    for action in step.actions
                                ]
                                for step in finding.minimal_repro_sequence.steps
                            ],
                        }
                    ),
                },
            ]
            reservation, cap = budget.reserve(messages, None, 512)
            rate_reservation = pacer.wait(len(json.dumps(messages).encode()) // 3 + 128, cap)
            try:
                response, headers = completion_with_headers(
                    client,
                    dict(
                        model=config.model,
                        messages=messages,
                        max_tokens=cap,
                        seed=config.seed,
                        **(
                            {"extra_body": {"reasoning_effort": "low"}}
                            if is_groq_cache(config.provider_base_url, config.model)
                            else {}
                        ),
                    ),
                )
            except Exception as exc:
                budget.fail(reservation)
                pacer.observe(getattr(getattr(exc, "response", None), "headers", {}))
                raise RuntimeError("evaluation judge usage is unknown") from None
            tokens = budget.finish(reservation, response.usage)
            cached = (
                usage_counts(response.usage).cached
                if is_groq_cache(config.provider_base_url, config.model)
                else 0
            )
            pacer.finish(rate_reservation, tokens - cached)
            pacer.observe(headers)
            content = response.choices[0].message.content or ""
            try:
                data = json.loads(
                    content.strip().removeprefix("```json").removesuffix("```").strip()
                )
            except (ValueError, TypeError):
                raise RuntimeError("evaluation judge returned invalid JSON") from None
            guessed = data.get("bug_id")
            if not isinstance(data.get("valid_finding"), bool):
                raise RuntimeError("evaluation judge omitted the correctness assessment")
            if guessed is not None and guessed not in truth:
                raise RuntimeError("evaluation judge returned an unknown bug ID")
            judgements.append(
                {
                    "finding_id": finding.id,
                    "oracle_bug_id": finding.mapped_bug_id,
                    "judge_bug_id": guessed,
                    "agrees_with_reviewed_oracle": guessed == finding.mapped_bug_id,
                    "correct": data["valid_finding"],
                    "reason": str(data.get("reason", ""))[:1000],
                }
            )
    cost = budget.cost_usd
    return {
        "status": "complete",
        "model": config.model,
        "tokens_used": budget.used,
        "token_budget": token_budget,
        "cost_usd": cost,
        "judgements": judgements,
        "accounting": "Evaluator overhead, excluded from equal exploration budgets",
        "efficiency": {**budget.summary(), "pacing_wait_s": pacer.wait_seconds},
    }
