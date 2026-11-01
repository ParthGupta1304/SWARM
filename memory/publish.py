"""Publish completed-run findings, retaining local evidence and upload receipts."""

import hashlib
import json
import os
from pathlib import Path

from dotenv import dotenv_values, find_dotenv

from memory.store import MekoMemoryStore, create_memory_store


class FindingsPublishError(RuntimeError):
    @property
    def user_message(self):
        return (
            "Findings were saved locally, but Meko publishing is incomplete. "
            "Check findings-sync.json in the run directory and retry publishing."
        )


def publish_run_findings(config, findings, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    settings = config.findings_store
    path = find_dotenv()
    values = dotenv_values(path) if path else {}
    name = settings.datapack_id_env
    datapack = values.get(name) if name in values else os.getenv(name)
    # Receipts apply only to the same destination and unchanged finding payload.
    target = hashlib.sha256(f"{settings.type}:{settings.mcp_url}:{datapack}".encode()).hexdigest()
    manifest_path = directory / "findings-sync.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    receipts = previous.get("findings", {}) if previous.get("target") == target else {}
    manifest = {"backend": settings.type, "target": target, "status": "pending", "findings": {}}

    def save_manifest():
        temporary = manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(manifest, indent=2) + "\n")
        temporary.replace(manifest_path)

    save_manifest()
    failed = False
    with create_memory_store(config.model_dump(), directory / "findings.sqlite3") as store:
        for finding in findings:
            if not finding.verified:
                manifest["findings"][finding.id] = {"status": "unverified"}
                continue
            digest = hashlib.sha256(finding.model_dump_json().encode()).hexdigest()
            receipt = {"sha256": digest, "status": "local"}
            if receipts.get(finding.id) == {"sha256": digest, "status": "published"}:
                receipt["status"] = "published"
            else:
                store.save_finding(config.project, finding)
                if settings.type == "meko":
                    if not isinstance(store, MekoMemoryStore):
                        receipt.update(status="pending", error="MekoNotConfigured")
                    elif finding.id in store.publication_errors:
                        receipt.update(status="pending", error=store.publication_errors[finding.id])
                    else:
                        receipt["status"] = "published"
            failed |= receipt["status"] == "pending"
            manifest["findings"][finding.id] = receipt
            save_manifest()
    manifest["status"] = (
        "pending" if failed else ("complete" if settings.type == "meko" else "local")
    )
    save_manifest()
    if failed:
        raise FindingsPublishError()
    return manifest
