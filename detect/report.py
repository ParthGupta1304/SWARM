"""Stable machine-readable reports and a small human-readable evidence report."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from detect.contracts import Finding

SEVERITY_ORDER = {
    name: index for index, name in enumerate(["critical", "high", "medium", "low", "info"])
}


def write_report(findings: Sequence[Finding], directory: str | Path) -> tuple[Path, Path]:
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    ordered = sorted(findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.id))
    if len({f.id for f in ordered}) != len(ordered):
        raise ValueError("finding IDs must be unique within a report")
    output = {
        "schema_version": 1,
        "summary": {
            "total": len(ordered),
            "verified": sum(f.verified for f in ordered),
            "unverified": sum(not f.verified for f in ordered),
        },
        "findings": [f.model_dump(mode="json") for f in ordered],
    }
    json_path, markdown_path = path / "report.json", path / "report.md"
    json_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Swarmtest findings",
        "",
        (
            f"{output['summary']['verified']} verified; "
            f"{output['summary']['unverified']} unverified."
        ),
        "",
    ]
    for finding in ordered:
        title = finding.title.replace("\n", " ").replace("\r", " ")
        lines.extend(
            [
                f"## {title}",
                "",
                f"Status: **{'VERIFIED' if finding.verified else 'UNVERIFIED'}**",
                "",
                f"Severity: {finding.severity}; type: {finding.type}; "
                f"oracle: {finding.oracle_triggered}",
                "",
                "Agents: " + ", ".join(finding.involved_agents),
                "",
                "Evidence events: " + ", ".join(finding.evidence_events),
                "",
                "Replay:",
                "",
            ]
        )
        for index, step in enumerate(finding.minimal_repro_sequence.steps, 1):
            label = "concurrent" if len(step.actions) > 1 else "sequential"
            actions = "; ".join(
                f"{a.agent_id}: {a.request.method} {a.request.path}" for a in step.actions
            )
            lines.append(f"{index}. {label}: {actions}")
        if finding.suggested_fix:
            lines.extend(["", "Suggested fix: " + finding.suggested_fix])
        lines.append("")
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, markdown_path
