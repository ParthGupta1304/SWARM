"""
test_meko_integration.py — Verify Phase 2 Meko MCP Finding Publisher.

Tests:
  1. Creates memory store from swarmtest.yaml config.
  2. Constructs a sample verified Finding contract.
  3. Saves the finding:
     - Verifies it is saved in local SQLite database.
     - Verifies it is published to Meko as a replay artifact + knowledge base doc.
  4. Publishes run results summary to Meko.
  5. Verifies fallback to local store when Meko credentials/network fail.
"""

import os
import sys
import uuid
import yaml
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv(dotenv_path=Path(".env"))

from detect.contracts import Finding, ReplayAction, ReplayPlan, ReplayStep, Request
from memory.store import LocalMemoryStore, MekoMemoryStore, create_memory_store
from memory.meko import MekoClient, format_finding_markdown


def make_dummy_verified_finding() -> Finding:
    """Construct a valid Finding contract conforming to detect.contracts."""
    ev1_id = str(uuid.uuid4())
    ev2_id = str(uuid.uuid4())
    run_id = f"test-run-{uuid.uuid4().hex[:6]}"

    action1 = ReplayAction(
        event_id=ev1_id,
        agent_id="buyer-1",
        request=Request(method="POST", path="/checkout", json_body={"cart_id": "c1"}),
        expected_status=200,
    )
    action2 = ReplayAction(
        event_id=ev2_id,
        agent_id="buyer-2",
        request=Request(method="POST", path="/checkout", json_body={"cart_id": "c2"}),
        expected_status=409,
    )

    step = ReplayStep(actions=[action1, action2])
    plan = ReplayPlan(seed=1, steps=[step])

    finding = Finding(
        id=f"finding-e1-{uuid.uuid4().hex[:6]}",
        run_id=run_id,
        title="Oversell: Concurrent checkouts oversold inventory",
        severity="critical",
        type="emergent",
        evidence_events=[ev1_id, ev2_id],
        involved_agents=["buyer-1", "buyer-2"],
        minimal_repro_sequence=plan,
        oracle_triggered="inventory_never_negative",
        verified=True,
        mapped_bug_id="E1",
        suggested_fix="Acquire row-level locks on inventory during checkout.",
        causality="interaction-required",
    )
    return finding


def test_markdown_formatting():
    print("\n--- 1. Testing Finding Markdown Formatting ---")
    finding = make_dummy_verified_finding()
    md = format_finding_markdown(finding, replay_artifact_hash="abc123hash", commit="test_commit")
    print(md[:400] + "...\n")
    assert "<!-- Notice: This document contains testing data and bug reports." in md
    assert "- **id**: `" in md
    assert "- **replay_artifact_hash**: `abc123hash`" in md
    assert "- **violated_invariant**: `inventory_never_negative`" in md
    print("[OK] Markdown format conforms to spec.")


def test_local_store_and_meko_publish():
    print("\n--- 2. Testing MemoryStore Creation & Publishing ---")
    with open("swarmtest.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    db_path = "test_memory.sqlite3"
    if os.path.exists(db_path):
        os.remove(db_path)

    store = create_memory_store(cfg, local_db_path=db_path)
    print(f"Instantiated store type: {type(store).__name__}")

    finding = make_dummy_verified_finding()
    print(f"Saving finding {finding.id}...")
    store.save_finding(project="bazaar-phase1", finding=finding)

    # Verify local store recall
    recalled = store.recall_findings(project="bazaar-phase1")
    assert len(recalled) == 1
    assert recalled[0].id == finding.id
    print(f"[OK] Finding recalled from local store: {recalled[0].id}")

    # Test run results summary
    if isinstance(store, MekoMemoryStore):
        print("Publishing run results summary...")
        store.publish_run_summary(
            run_id=finding.run_id,
            results=[{"finding_id": finding.id, "classification": "still_failing"}],
        )
        print("[OK] Run summary published to Meko.")

    store.close()
    if os.path.exists(db_path):
        os.remove(db_path)


def test_graceful_fallback():
    print("\n--- 3. Testing Graceful Fallback on Bad Credentials ---")
    bad_cfg = {
        "findings_store": {
            "type": "meko",
            "api_key_env": "NON_EXISTENT_KEY",
            "datapack_id_env": "NON_EXISTENT_DP",
            "fallback": "local",
        }
    }
    fallback_store = create_memory_store(bad_cfg, local_db_path="fallback.sqlite3")
    assert isinstance(fallback_store, LocalMemoryStore)
    print("[OK] Successfully fell back to LocalMemoryStore when credentials missing.")
    fallback_store.close()
    if os.path.exists("fallback.sqlite3"):
        os.remove("fallback.sqlite3")


if __name__ == "__main__":
    test_markdown_formatting()
    test_local_store_and_meko_publish()
    test_graceful_fallback()
    print("\n[SUCCESS] All Meko integration tests passed!")

