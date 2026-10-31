"""Explicit Phase 1 acceptance evidence; fixture runs cannot pass the AI gate."""

from collections.abc import Sequence

from bench.metrics import BenchmarkRun, summarize


def evaluate_phase1(
    runs: Sequence[BenchmarkRun],
    truth: dict[str, str],
    *,
    dev_seed: int,
    source: str,
    judge: dict | None = None,
) -> dict:
    report = summarize(runs, truth, dev_seed=dev_seed)
    emergent = {
        finding.mapped_bug_id
        for run in runs
        for finding in run.findings
        if run.condition == "swarm"
        and finding.verified
        and finding.type == "emergent"
        and truth.get(finding.mapped_bug_id) == "emergent"
    }
    pending = []
    if source != "real-model":
        pending.append("Real model-driven discovery and held-out benchmark required")
    if source == "real-model":
        agreed = {
            row["oracle_bug_id"]
            for row in (judge or {}).get("judgements", [])
            if row.get("agrees_with_reviewed_oracle")
        }
        if not judge or judge.get("status") != "complete":
            pending.append("Independent LLM matching against the reviewed catalog required")
        elif not emergent <= agreed:
            pending.append("Review judge/oracle disagreements before accepting the gate")
    if len(emergent) < 3:
        pending.append(f"Need three distinct verified emergent bugs; observed {len(emergent)}")
    return {
        "complete": not pending,
        "source": source,
        "verified_emergent_bug_ids": sorted(emergent),
        "pending": pending,
        "judge": judge,
        "benchmark": report,
    }
