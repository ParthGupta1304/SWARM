"""Evidence-bound human spot checks; an automated judge cannot sign these."""

import hashlib
import json
from pathlib import Path


def evidence_hash(finding):
    return hashlib.sha256(finding.model_dump_json().encode()).hexdigest()


def catalog_hash(truth):
    return hashlib.sha256(json.dumps(truth, sort_keys=True).encode()).hexdigest()


def record_review(directory, runs, finding_id, correct, reviewer, note):
    reviewer = reviewer.strip()
    if not reviewer or not note.strip():
        raise ValueError("Reviewer name and an evidence-based note are required")
    finding = next((f for r in runs for f in r.findings if f.id == finding_id), None)
    if finding is None:
        raise ValueError("Unknown finding")
    path = Path(directory) / "manual-review.json"
    rows = json.loads(path.read_text()) if path.exists() else []
    rows = [row for row in rows if row["finding_id"] != finding_id]
    rows.append(
        {
            "finding_id": finding_id,
            "correct": correct,
            "reviewer": reviewer,
            "note": note.strip(),
            "evidence_sha256": evidence_hash(finding),
        }
    )
    path.write_text(json.dumps(rows, indent=2) + "\n")
    return rows


def valid_reviews(rows, runs):
    findings = {f.id: f for r in runs for f in r.findings}
    return [
        row
        for row in rows
        if row.get("finding_id") in findings
        and row.get("reviewer")
        and row.get("note")
        and row.get("evidence_sha256") == evidence_hash(findings[row["finding_id"]])
    ]
