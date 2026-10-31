"""Budgeted evaluator-only LLM matching, separate from exploration costs."""

import json
from collections.abc import Sequence

import openai

from bench.metrics import BenchmarkRun
from swarm.budget import TokenBudget

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
    budget = TokenBudget(token_budget)
    judgements = []
    # One independently reviewed exemplar per mapped bug, plus unknown reports.
    unique = {}
    for run in runs:
        for finding in run.findings:
            if finding.verified:
                unique.setdefault(finding.mapped_bug_id or finding.id, finding)
    with openai.OpenAI(
        base_url=config.provider_base_url, api_key=api_key, max_retries=0, timeout=30
    ) as client:
        for finding in unique.values():
            messages = [
                {
                    "role": "system",
                    "content": "You are an independent evaluation judge. Match the finding "
                    "to an ID in the supplied frozen catalog, or null if unsupported. Return "
                    "JSON with bug_id (catalog string ID or JSON null) and a short reason. ",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "catalog": {
                                bug: {"type": kind, "description": DESCRIPTIONS[bug]}
                                for bug, kind in truth.items()
                            },
                            "title": finding.title,
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
            reservation, cap = budget.reserve(messages, None, 256)
            try:
                response = client.chat.completions.create(
                    model=config.model, messages=messages, max_tokens=cap, seed=config.seed
                )
            except Exception:
                budget.fail(reservation)
                raise RuntimeError("evaluation judge usage is unknown") from None
            budget.finish(reservation, response.usage)
            content = response.choices[0].message.content or ""
            try:
                data = json.loads(
                    content.strip().removeprefix("```json").removesuffix("```").strip()
                )
            except (ValueError, TypeError):
                raise RuntimeError("evaluation judge returned invalid JSON") from None
            guessed = data.get("bug_id")
            if guessed is not None and guessed not in truth:
                raise RuntimeError("evaluation judge returned an unknown bug ID")
            judgements.append(
                {
                    "finding_id": finding.id,
                    "oracle_bug_id": finding.mapped_bug_id,
                    "judge_bug_id": guessed,
                    "agrees_with_reviewed_oracle": guessed == finding.mapped_bug_id,
                }
            )
    cost = (
        budget.prompt_tokens * config.input_cost_per_million
        + budget.completion_tokens * config.output_cost_per_million
    ) / 1e6
    return {
        "status": "complete",
        "model": config.model,
        "tokens_used": budget.used,
        "token_budget": token_budget,
        "cost_usd": cost,
        "judgements": judgements,
        "accounting": "Evaluator overhead, excluded from equal exploration budgets",
    }
