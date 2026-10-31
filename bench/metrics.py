"""Score measured runs against a frozen, benchmark-only ground-truth manifest."""

from __future__ import annotations

import csv
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from statistics import mean
from typing import Literal

from pydantic import Field, model_validator

from detect.contracts import Contract, Finding, Nonempty


class BenchmarkRun(Contract):
    run_id: Nonempty
    condition: Literal["isolated", "swarm"]
    seed: int = Field(ge=0)
    model: Nonempty
    token_budget: int = Field(gt=0)
    tokens_used: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    elapsed_s: float = Field(ge=0)
    findings: list[Finding] = Field(default_factory=list)
    finding_times_s: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_run(self) -> BenchmarkRun:
        if self.tokens_used > self.token_budget:
            raise ValueError("run exceeded its token budget")
        if any(f.run_id != self.run_id for f in self.findings):
            raise ValueError("all findings must belong to this run")
        if any(f.minimal_repro_sequence.seed != self.seed for f in self.findings):
            raise ValueError("finding replay seeds must match the benchmark run seed")
        ids = {f.id for f in self.findings}
        if len(ids) != len(self.findings):
            raise ValueError("duplicate finding IDs")
        if set(self.finding_times_s) - ids:
            raise ValueError("finding times reference an unknown finding")
        if any(not 0 <= t <= self.elapsed_s for t in self.finding_times_s.values()):
            raise ValueError("finding times must lie within the run")
        return self


def score_run(run: BenchmarkRun, truth: dict[str, str]) -> dict:
    if not truth or any(kind not in {"single-user", "emergent"} for kind in truth.values()):
        raise ValueError("ground truth must map bug IDs to single-user or emergent")
    verified = [f for f in run.findings if f.verified]
    matched = [f for f in verified if f.mapped_bug_id in truth]
    found = {f.mapped_bug_id for f in matched}
    times = [run.finding_times_s[f.id] for f in matched if f.id in run.finding_times_s]
    all_times_present = all(f.id in run.finding_times_s for f in matched)

    def recall(kind: str) -> float | None:
        expected = {bug for bug, value in truth.items() if value == kind}
        return len(found & expected) / len(expected) if expected else None

    first_per_bug = (
        {
            bug: min(run.finding_times_s[f.id] for f in matched if f.mapped_bug_id == bug)
            for bug in found
        }
        if all_times_present
        else {}
    )
    return {
        "run_id": run.run_id,
        "condition": run.condition,
        "seed": run.seed,
        "recall": len(found) / len(truth),
        "emergent_recall": recall("emergent"),
        "single_user_recall": recall("single-user"),
        "precision_before_verifier": (
            sum(f.mapped_bug_id in truth for f in run.findings) / len(run.findings)
            if run.findings
            else None
        ),
        "precision_after_verifier": len(matched) / len(verified) if verified else None,
        "verified_findings": len(verified),
        "unverified_findings": len(run.findings) - len(verified),
        "found_bug_ids": sorted(found),
        "time_to_first_find_s": min(times) if times and all_times_present else None,
        "time_to_all_finds_s": max(first_per_bug.values())
        if found == set(truth) and first_per_bug
        else None,
        "tokens_used": run.tokens_used,
        "cost_usd": run.cost_usd,
        "cost_per_verified_bug_usd": run.cost_usd / len(found) if found else None,
        "elapsed_s": run.elapsed_s,
    }


def summarize(runs: Sequence[BenchmarkRun], truth: dict[str, str], *, dev_seed: int) -> dict:
    """Enforce the PRD's two conditions and three matching held-out seeds."""
    if len(runs) != 6:
        raise ValueError("benchmark requires two conditions across three held-out seeds")
    run_ids = {run.run_id for run in runs}
    pairs = {(run.condition, run.seed) for run in runs}
    if len(run_ids) != len(runs) or len(pairs) != len(runs):
        raise ValueError("run IDs and condition/seed pairs must be unique")
    seeds = {
        condition: {r.seed for r in runs if r.condition == condition}
        for condition in ("isolated", "swarm")
    }
    if len(seeds["isolated"]) != 3 or seeds["isolated"] != seeds["swarm"]:
        raise ValueError("both conditions must use the same three held-out seeds")
    if dev_seed in seeds["swarm"]:
        raise ValueError("the prompt-development seed cannot be used for evaluation")
    if len({(r.model, r.token_budget) for r in runs}) != 1:
        raise ValueError("conditions must use the same model and token budget")
    scores = [score_run(run, truth) for run in runs]
    conditions = {}
    for condition in ("isolated", "swarm"):
        selected = [row for row in scores if row["condition"] == condition]
        metrics = {}
        for name in [
            "recall",
            "emergent_recall",
            "single_user_recall",
            "precision_before_verifier",
            "precision_after_verifier",
            "cost_usd",
            "tokens_used",
            "time_to_first_find_s",
            "time_to_all_finds_s",
        ]:
            values = [row[name] for row in selected if row[name] is not None]
            metrics[name] = {
                "mean": mean(values) if values else None,
                "min": min(values) if values else None,
                "max": max(values) if values else None,
                "measured_runs": len(values),
            }
        conditions[condition] = {
            "metrics": metrics,
            "repeatability": {
                bug: sum(bug in row["found_bug_ids"] for row in selected) / len(selected)
                for bug in sorted(truth)
            },
        }
    return {
        "schema_version": 1,
        "dev_seed": dev_seed,
        "held_out_seeds": sorted(seeds["swarm"]),
        "conditions": conditions,
        "runs": scores,
    }


def run_benchmark(
    run_condition: Callable[[str, int, int], BenchmarkRun],
    *,
    seeds: Sequence[int],
    token_budget: int,
    dev_seed: int,
    truth: dict[str, str],
) -> dict:
    """Dev2 supplies a callback that resets and runs an isolated/swarm experiment."""
    if len(seeds) != 3 or len(set(seeds)) != 3 or dev_seed in seeds or token_budget <= 0:
        raise ValueError("provide three unique held-out seeds and a positive budget")
    runs = []
    for condition in ("isolated", "swarm"):
        for seed in seeds:
            run = run_condition(condition, seed, token_budget)
            if (run.condition, run.seed, run.token_budget) != (condition, seed, token_budget):
                raise ValueError("runtime returned a different condition, seed or token budget")
            runs.append(run)
    return summarize(runs, truth, dev_seed=dev_seed)


def write_benchmark(report: dict, directory: str | Path, *, chart: bool = False) -> None:
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    (path / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    rows = [{**r, "found_bug_ids": ",".join(r["found_bug_ids"])} for r in report["runs"]]
    if rows:
        with (path / "runs.csv").open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    if chart:
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import pyplot as plt

        names = ["isolated", "swarm"]
        values = [report["conditions"][name]["metrics"]["recall"] for name in names]
        fig, ax = plt.subplots(figsize=(6, 4))
        heights = [value["mean"] for value in values]
        ax.bar(names, heights, color=["#64748b", "#0f766e"])
        ax.errorbar(
            names,
            heights,
            yerr=[
                [v["mean"] - v["min"] for v in values],
                [v["max"] - v["mean"] for v in values],
            ],
            fmt="none",
            color="black",
            capsize=5,
        )
        ax.set(
            ylim=(0, 1.05),
            ylabel="Verified bug recall",
            title="Three held-out seeds: mean and range",
        )
        fig.tight_layout()
        fig.savefig(path / "recall.png", dpi=160)
        plt.close(fig)
