"""Configuration-based runs and the two-condition, three-seed benchmark."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
from pathlib import Path

import yaml

from bench.metrics import run_benchmark, write_benchmark
from detect.report import write_report
from detect.store import SQLiteEventStore, export_jsonl
from swarm.runtime import RunConfig, RunCoordinator, RuntimeHooks, benchmark_callback


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "benchmark"])
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--events-db", type=Path, default=Path("swarmtest_events.sqlite3"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/swarm"))
    parser.add_argument(
        "--hooks", help="Python module:factory taking RunConfig, returning RuntimeHooks"
    )
    parser.add_argument("--condition", choices=["isolated", "swarm"], default="swarm")
    parser.add_argument("--truth", type=Path, help="Evaluator-only JSON mapping bug IDs to types")
    parser.add_argument("--seeds", nargs=3, type=int, default=[11, 22, 33])
    args = parser.parse_args()
    config = RunConfig.model_validate(yaml.safe_load(args.config.read_text(encoding="utf-8")))
    config = config.model_copy(
        update={
            "spec": str((args.config.resolve().parent / config.spec).resolve()),
            "kill_file": str((args.config.resolve().parent / config.kill_file).resolve())
            if config.kill_file
            else None,
        }
    )
    api_key = os.environ.get(config.api_key_env, "ollama")
    factory = None
    if args.hooks:
        module, separator, name = args.hooks.partition(":")
        if not separator:
            parser.error("--hooks must be module:factory")
        factory = getattr(importlib.import_module(module), name)

    def hooks(selected: RunConfig = config) -> RuntimeHooks:
        value = factory(selected) if factory else RuntimeHooks()
        if not isinstance(value, RuntimeHooks):
            raise TypeError("hook factory must return RuntimeHooks")
        return value

    args.output.mkdir(parents=True, exist_ok=True)
    args.events_db.parent.mkdir(parents=True, exist_ok=True)
    with SQLiteEventStore(args.events_db) as store:
        if args.command == "run":
            result = asyncio.run(
                RunCoordinator(config, store, api_key=api_key, hooks=hooks()).run(args.condition)
            )
            summary = {key: value for key, value in vars(result).items() if key != "findings"}
            (args.output / "run.json").write_text(json.dumps(summary, indent=2) + "\n")
            export_jsonl(store, result.run_id, args.output / "events.jsonl")
            write_report(result.findings, args.output)
            print(json.dumps(summary, indent=2))
        else:
            if not factory or not args.truth:
                parser.error("benchmark requires --hooks and --truth from the evaluator")
            report = run_benchmark(
                benchmark_callback(config, store, hook_factory=hooks, api_key=api_key),
                seeds=args.seeds,
                token_budget=config.token_budget,
                dev_seed=config.seed,
                truth=json.loads(args.truth.read_text(encoding="utf-8")),
            )
            write_benchmark(report, args.output)
            print(f"Six measured runs exported to {args.output}")
