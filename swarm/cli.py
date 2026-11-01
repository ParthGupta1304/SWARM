"""Config-only owned Bazaar runs, benchmarking, serving and human review."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import sys
from pathlib import Path
from uuid import uuid4

from bench.gate import evaluate_phase1
from bench.judge import judge_findings
from bench.metrics import BenchmarkRun, run_benchmark, summarize, write_benchmark
from bench.review import record_review, valid_reviews
from detect.contracts import Finding
from detect.report import write_report
from detect.store import SQLiteEventStore, export_jsonl
from memory.publish import publish_run_findings
from swarm.bazaar import make_hooks
from swarm.provider import credential, load_config
from swarm.runtime import RunCoordinator
from swarm.targets import BazaarEnvironment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "benchmark", "serve", "review", "publish"])
    parser.add_argument("--config", type=Path, default=Path("swarmtest.yaml"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/swarm"))
    parser.add_argument("--events-db", type=Path)
    parser.add_argument("--condition", choices=["isolated", "swarm"], default="swarm")
    parser.add_argument("--seeds", nargs=3, type=int, default=[11, 22, 33])
    parser.add_argument("--hooks", help="Optional module:factory for an external disposable target")
    parser.add_argument("--truth", type=Path)
    parser.add_argument("--finding-id")
    parser.add_argument("--reviewer")
    parser.add_argument("--note")
    parser.add_argument("--decision", choices=["correct", "incorrect"])
    parser.add_argument(
        "--resume", action="store_true", help="Resume a matching checkpointed benchmark"
    )
    args = parser.parse_args()
    if args.command == "serve":
        from swarm.demo import main as serve

        sys.argv = [sys.argv[0], "--config", str(args.config), "--output", str(args.output)]
        serve()
        return
    config = load_config(args.config)
    if args.command == "publish":
        reports = (
            [args.output / "report.json"]
            if (args.output / "report.json").exists()
            else sorted(args.output.glob("*/report.json"))
        )
        if not reports:
            parser.error("No saved run reports found under --output")
        for report in reports:
            findings = [
                Finding.model_validate(f) for f in json.loads(report.read_text())["findings"]
            ]
            receipt = publish_run_findings(config, findings, report.parent)
            print(json.dumps({"run": report.parent.name, "publishing": receipt["status"]}))
        return
    truth = json.loads(
        (
            args.truth or Path(__file__).resolve().parent.parent / "configs/bazaar-truth.json"
        ).read_text()
    )
    args.output.mkdir(parents=True, exist_ok=True)
    if args.command == "review":
        if not all([args.finding_id, args.reviewer, args.note, args.decision]):
            parser.error("review needs --finding-id, --reviewer, --note and --decision")
        runs = [
            BenchmarkRun.model_validate(r)
            for r in json.loads((args.output / "measured-runs.json").read_text())
        ]
        reviews = record_review(
            args.output, runs, args.finding_id, args.decision == "correct", args.reviewer, args.note
        )
        judge = json.loads((args.output / "judge.json").read_text())
        labels = {row["finding_id"]: row["correct"] for row in (judge or {}).get("judgements", [])}
        labels.update({row["finding_id"]: row["correct"] for row in valid_reviews(reviews, runs)})
        runs = [
            run.model_copy(
                update={"assessments": {f.id: labels[f.id] for f in run.findings if f.id in labels}}
            )
            for run in runs
        ]
        (args.output / "measured-runs.json").write_text(
            json.dumps([run.model_dump(mode="json") for run in runs], indent=2)
        )
        write_benchmark(summarize(runs, truth, dev_seed=config.seed), args.output, chart=True)
        gate = evaluate_phase1(
            runs,
            truth,
            dev_seed=config.seed,
            source=runs[0].provenance.get("source", "unattested"),
            judge=judge,
            manual_review=reviews,
        )
        (args.output / "phase1-gate.json").write_text(json.dumps(gate, indent=2))
        print("Review recorded; phase1 gate complete:", gate["complete"])
        return
    api_key = credential(config)
    from contextlib import ExitStack

    with ExitStack() as stack:
        env = (
            stack.enter_context(
                BazaarEnvironment(
                    args.output, version=config.bazaar_version, seed_fixture=config.seed_fixture
                )
            )
            if config.target == "bazaar"
            else None
        )
        if env:
            config = config.model_copy(update={"app_base_url": env.live.url})
        factory = None
        if args.hooks:
            module, sep, name = args.hooks.partition(":")
            if not sep:
                parser.error("--hooks must be module:factory")
            factory = getattr(importlib.import_module(module), name)
        if not env and not factory:
            parser.error("external targets require explicit disposable reset/detection hooks")
        event_path = args.events_db or args.output / "events.sqlite3"
        event_path.parent.mkdir(parents=True, exist_ok=True)
        store = stack.enter_context(SQLiteEventStore(event_path))
        measured = []
        settings = config.model_dump(exclude={"app_base_url"})
        source_root = Path(__file__).resolve().parent.parent
        critical = [
            "swarm/agent.py",
            "swarm/runtime.py",
            "swarm/budget.py",
            "swarm/provider.py",
            "swarm/context.py",
            "verify/replay.py",
            "detect/findings.py",
            "swarm/bazaar.py",
            "apps/bazaar/bazaar/main.py",
            "apps/bazaar/bazaar/models.py",
            "apps/bazaar/bazaar/marketplace.py",
            "apps/bazaar/bazaar/seed.py",
            "apps/bazaar/invariants.sql",
            "apps/bazaar/seed_data.json",
        ]
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "protocol": "groq-local-validation-v2",
                    "config": settings,
                    "seeds": args.seeds,
                    "truth": truth,
                    "source": {
                        name: hashlib.sha256((source_root / name).read_bytes()).hexdigest()
                        for name in critical
                    },
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        checkpoint_path = args.output / "checkpoint.json"
        completed = {}
        if args.command == "benchmark" and checkpoint_path.exists():
            if not args.resume:
                parser.error(
                    "Benchmark checkpoint exists; use --resume or a new --output directory"
                )
            checkpoint = json.loads(checkpoint_path.read_text())
            if checkpoint["fingerprint"] != fingerprint:
                parser.error("Checkpoint configuration/source differs; use a new output directory")
            completed = {
                (r.condition, r.seed): r
                for value in checkpoint["runs"]
                if (r := BenchmarkRun.model_validate(value))
            }

        def run(condition, seed, budget):
            if (condition, seed) in completed:
                value = completed[(condition, seed)]
                measured.append(value)
                print(
                    json.dumps(
                        {
                            "resumed": True,
                            "run_id": value.run_id,
                            "condition": condition,
                            "seed": seed,
                        }
                    ),
                    flush=True,
                )
                return value
            selected = config.model_copy(update={"seed": seed, "token_budget": budget})
            hooks = factory(selected) if factory else make_hooks(selected, env)
            run_id = str(uuid4())
            try:
                result = asyncio.run(
                    RunCoordinator(
                        selected,
                        store,
                        api_key=api_key,
                        hooks=hooks,
                        context_dir=args.output / "memory",
                    ).run(condition, run_id=run_id)
                )
            except BaseException as exc:
                directory = args.output / run_id
                directory.mkdir(parents=True, exist_ok=True)
                export_jsonl(store, run_id, directory / "partial-events.jsonl")
                (directory / "failure.json").write_text(
                    json.dumps(
                        {
                            "condition": condition,
                            "seed": seed,
                            "run_id": run_id,
                            "error_class": type(exc).__name__,
                            "scored": False,
                            "note": "Partial events retained; provider usage may be uncertain",
                        },
                        indent=2,
                    )
                )
                raise
            directory = args.output / result.run_id
            directory.mkdir(parents=True, exist_ok=True)
            export_jsonl(store, result.run_id, directory / "events.jsonl")
            write_report(result.findings, directory)
            (directory / "run.json").write_text(
                json.dumps({k: v for k, v in vars(result).items() if k != "findings"}, indent=2)
            )
            publish_run_findings(selected, result.findings, directory)
            if result.stopped:
                raise RuntimeError("Stopped runs are not scored")
            value = result.benchmark_run()
            value = value.model_copy(
                update={"provenance": {**value.provenance, "experiment_sha256": fingerprint}}
            )
            measured.append(value)
            (directory / "measured.json").write_text(value.model_dump_json(indent=2))
            if args.command == "benchmark":
                completed[(condition, seed)] = value
                temporary = checkpoint_path.with_suffix(".tmp")
                temporary.write_text(
                    json.dumps(
                        {
                            "fingerprint": fingerprint,
                            "runs": [r.model_dump(mode="json") for r in completed.values()],
                        },
                        indent=2,
                    )
                )
                temporary.replace(checkpoint_path)
            print(
                json.dumps(
                    {
                        "run_id": value.run_id,
                        "condition": condition,
                        "seed": seed,
                        "tokens": value.tokens_used,
                        "verified": sum(f.verified for f in value.findings),
                    }
                ),
                flush=True,
            )
            return value

        if args.command == "run":
            run(args.condition, config.seed, config.token_budget)
        else:
            run_benchmark(
                run,
                seeds=args.seeds,
                token_budget=config.token_budget,
                dev_seed=config.seed,
                truth=truth,
            )
            (args.output / "measured-runs.json").write_text(
                json.dumps([r.model_dump(mode="json") for r in measured], indent=2)
            )
            judge = None
            if all(r.provenance.get("source") == "real-model" for r in measured):
                try:
                    judge = judge_findings(measured, truth, config, api_key)
                except Exception as exc:
                    judge = {"status": "error", "error_class": type(exc).__name__}
            (args.output / "judge.json").write_text(json.dumps(judge, indent=2))
            labels = {
                row["finding_id"]: row["correct"] for row in (judge or {}).get("judgements", [])
            }
            measured = [
                r.model_copy(
                    update={
                        "assessments": {f.id: labels[f.id] for f in r.findings if f.id in labels}
                    }
                )
                for r in measured
            ]
            write_benchmark(
                summarize(measured, truth, dev_seed=config.seed), args.output, chart=True
            )
            (args.output / "measured-runs.json").write_text(
                json.dumps([r.model_dump(mode="json") for r in measured], indent=2)
            )
            source = (
                "real-model"
                if all(r.provenance.get("source") == "real-model" for r in measured)
                else "scripted-fixture"
            )
            gate = evaluate_phase1(
                measured, truth, dev_seed=config.seed, source=source, judge=judge
            )
            (args.output / "phase1-gate.json").write_text(json.dumps(gate, indent=2))
            print(json.dumps({"complete": gate["complete"], "pending": gate["pending"]}))
