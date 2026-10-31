"""Public UI models and safe access to the console's canonical run artifacts."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

import yaml
from pydantic import BaseModel, ConfigDict, Field

from bench.judge import DESCRIPTIONS
from bench.metrics import BenchmarkRun
from bench.review import valid_reviews
from detect.contracts import Finding
from detect.store import read_jsonl
from swarm.runtime import RunConfig

ROLE_NAMES = {
    "casual_buyer": "Casual buyer",
    "bargain_hunter": "Bargain hunter",
    "impatient_clicker": "Impatient clicker",
    "fraudster": "Fraudster",
    "sock_puppet": "Sock puppet operator",
    "troll": "Troll",
}


class RunOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    normal_agents: int = Field(ge=1)
    adversary_agents: int = Field(ge=5)
    max_dollars: float = Field(gt=0)
    seed: int = Field(ge=0, le=2147483647)


def public_config(config: RunConfig, truth: dict):
    counts = Counter(p.role for p in config.personas)
    return {
        "model": config.model,
        "provider": "Groq" if "api.groq.com" in config.provider_base_url else "Configured provider",
        "normal_agents": counts["casual_buyer"],
        "adversary_agents": len(config.personas) - counts["casual_buyer"],
        "population_cap": len(config.personas),
        "max_dollars": config.max_dollars,
        "max_dollars_cap": config.max_dollars,
        "seed": config.seed,
        "max_rounds": config.max_rounds,
        "benchmark_rounds": min(3, config.max_rounds),
        "token_budget": config.token_budget,
        "roles": [
            {
                "id": role,
                "name": ROLE_NAMES.get(role, role),
                "count": count,
                "objective": next(p.objective for p in config.personas if p.role == role),
            }
            for role, count in counts.items()
        ],
        "bugs": [
            {"id": bug, "type": kind, "description": DESCRIPTIONS[bug]}
            for bug, kind in truth.items()
        ],
    }


def selected_config(config: RunConfig, options: RunOptions | None):
    if options is None:
        return config
    total = options.normal_agents + options.adversary_agents
    if total > len(config.personas) or options.max_dollars > config.max_dollars:
        raise ValueError("Population or dollar cap exceeds the server configuration")
    if options.seed in {11, 22, 33}:
        raise ValueError("Development seed must differ from benchmark seeds 11, 22 and 33")
    normal = [p for p in config.personas if p.role == "casual_buyer"]
    groups = {}
    for p in config.personas:
        if p.role != "casual_buyer":
            groups.setdefault(p.role, []).append(p)
    if not normal or len(groups) > options.adversary_agents:
        raise ValueError("Population must include the supported persona roles")
    if options.normal_agents == len(normal) and options.adversary_agents == sum(
        map(len, groups.values())
    ):
        personas = config.personas
    else:
        allocated = dict.fromkeys(groups, 1)
        for _ in range(options.adversary_agents - len(groups)):
            role = max(groups, key=lambda r: len(groups[r]) / (allocated[r] + 1))
            allocated[role] += 1
        personas = []
        for templates, count in [
            (normal, options.normal_agents),
            *[(groups[r], n) for r, n in allocated.items()],
        ]:
            for i in range(count):
                p = templates[i % len(templates)]
                personas.append(
                    p.model_copy(
                        update={
                            "agent_id": p.agent_id
                            if i < len(templates)
                            else f"{p.agent_id}-{i + 1}"
                        }
                    )
                )
    return RunConfig.model_validate(
        {
            **config.model_dump(),
            "personas": personas,
            "seed": options.seed,
            "max_dollars": options.max_dollars,
        }
    )


def export_config(config: RunConfig):
    values = config.model_dump()
    provider = urlsplit(values["provider_base_url"])
    # Provider authentication belongs in the named server-side environment key.
    values["provider_base_url"] = urlunsplit(
        (provider.scheme, provider.netloc.rsplit("@", 1)[-1], provider.path, "", "")
    )
    # Export a root-level config for the documented repository CLI workflow.
    values.update(
        spec="apps/bazaar/openapi.json",
        seed_fixture="apps/bazaar/seed_data.json",
        invariants="apps/bazaar/invariants.sql",
        app_base_url="http://127.0.0.1:8000",
    )
    return yaml.safe_dump(values, sort_keys=False)


class RunArchive:
    def __init__(self, output: Path):
        self.output = output.resolve()

    def path(self, run_id: str, name: str):
        run_id = str(UUID(run_id))
        path = self.output / run_id / name
        if (
            path.parent.is_symlink()
            or path.is_symlink()
            or not path.resolve().is_relative_to(self.output)
        ):
            raise ValueError("Run artifacts must be inside the active workspace")
        return path

    def detail(self, run_id: str):
        path = self.path(run_id, "run.json")
        run = json.loads(path.read_text())
        report = self.path(run_id, "report.json")
        run["findings"] = (
            [
                Finding.model_validate(f).model_dump(mode="json")
                for f in json.loads(report.read_text())["findings"]
            ]
            if report.exists()
            else []
        )
        events = self.path(run_id, "events.jsonl")
        run["actions"] = (
            [e.model_dump(mode="json") for e in read_jsonl(events)] if events.exists() else []
        )
        checks = self.path(run_id, "rechecks.json")
        run["rechecks"] = json.loads(checks.read_text()) if checks.exists() else []
        run["source"] = run.get("provenance", {}).get("source", "unattested")
        run.get("provenance", {}).pop("provider_origin", None)
        reviews = self.path(run_id, "manual-review.json")
        if reviews.exists():
            measured = as_benchmark(run)
            run["assessments"] = {
                row["finding_id"]: row["correct"]
                for row in valid_reviews(json.loads(reviews.read_text()), [measured])
            }
        run["status"] = "stopped" if run.get("stopped") else "completed"
        run["saved_at"] = path.stat().st_mtime
        return run

    def list(self):
        rows = []
        for folder in self.output.iterdir():
            if not folder.is_dir() or folder.is_symlink():
                continue
            try:
                UUID(folder.name)
                path = self.path(folder.name, "run.json")
                run = json.loads(path.read_text())
                report = self.path(folder.name, "report.json")
                findings = json.loads(report.read_text())["findings"] if report.exists() else []
                rows.append(
                    {
                        k: v
                        for k, v in {
                            **run,
                            "saved_at": path.stat().st_mtime,
                            "verified_ids": sorted(
                                {
                                    f["mapped_bug_id"]
                                    for f in findings
                                    if f.get("verified") and f.get("mapped_bug_id")
                                }
                            ),
                            "status": "stopped" if run.get("stopped") else "completed",
                        }.items()
                        if k not in {"agents", "provenance", "finding_times_s"}
                    }
                )
            except (ValueError, OSError, KeyError, TypeError):
                continue
        return sorted(rows, key=lambda row: row["saved_at"], reverse=True)


def as_benchmark(run):
    values = {k: v for k, v in run.items() if k in BenchmarkRun.model_fields}
    values["actor_count"] = len(run.get("agents", [])) or run.get("actor_count", 0)
    return BenchmarkRun.model_validate(values)
