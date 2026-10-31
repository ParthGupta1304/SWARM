"""Explicit Phase 1 acceptance evidence; fixture runs cannot pass the AI gate."""

from collections.abc import Sequence

from bench.metrics import BenchmarkRun, summarize
from bench.review import catalog_hash, valid_reviews


def evaluate_phase1(
    runs: Sequence[BenchmarkRun],
    truth: dict[str, str],
    *,
    dev_seed: int,
    source: str,
    judge: dict | None = None,
    manual_review: list | None = None,
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
        if any(run.actor_count < 10 for run in runs):
            pending.append("The approved population requires at least 10 actors per condition")
        if any(not run.provenance.get("receipts") for run in runs):
            pending.append("Provider response receipts are missing")
        if any(run.provenance.get("catalog_sha256") != catalog_hash(truth) for run in runs):
            pending.append("Run provenance does not match the frozen evaluation catalog")
        if any(
            len({r.get("agent_id") for r in run.provenance.get("receipts", [])}) < 10
            for run in runs
        ):
            pending.append("Provider receipts must cover the approved 10 actors")
        checks = valid_reviews(manual_review or [], runs)
        if not checks:
            pending.append("A human spot-check of benchmark evidence is required")
        elif any(not row["correct"] for row in checks):
            pending.append("Resolve manually rejected findings before acceptance")
        agreed = {
            row["oracle_bug_id"]
            for row in (judge or {}).get("judgements", [])
            if row.get("agrees_with_reviewed_oracle") and row.get("correct")
        }
        reviewed_ids = {row["finding_id"] for row in checks if row["correct"]}
        agreed.update(
            f.mapped_bug_id
            for run in runs
            for f in run.findings
            if f.id in reviewed_ids and f.mapped_bug_id in truth
        )
        if not judge or judge.get("status") != "complete":
            pending.append("Independent LLM matching against the reviewed catalog required")
        elif not emergent <= agreed:
            pending.append("Review judge/oracle disagreements before accepting the gate")
        required = {f.id for run in runs for f in run.findings}
        judged = {row.get("finding_id") for row in (judge or {}).get("judgements", [])}
        if not required <= judged:
            pending.append("Independent correctness assessment of every candidate required")
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
