"""Frontend data bindings preserve real counts, caps and artifact ownership."""

import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

import yaml

from bench.review import record_review
from dashboard.presentation import (
    RunArchive,
    RunOptions,
    as_benchmark,
    export_config,
    public_config,
    selected_config,
)
from detect.contracts import Finding, ReplayAction, ReplayPlan, ReplayStep, Request
from detect.report import write_report
from swarm.provider import load_config
from swarm.runtime import RunConfig

ROOT = Path(__file__).resolve().parents[1]


class PresentationChecks(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT / "configs/bazaar.yaml")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name)
        self.archive = RunArchive(self.output)

    def test_public_config_has_real_limits_and_no_provider_credentials(self):
        config = self.config.model_copy(
            update={"provider_base_url": "https://private-key@provider.invalid/v1"}
        )
        data = public_config(config, {"E1": "emergent", "S1": "single-user"})
        self.assertNotIn("private-key", json.dumps(data))
        self.assertNotIn("private-key", export_config(config))
        self.assertEqual(data["population_cap"], 10)
        self.assertEqual(data["normal_agents"] + data["adversary_agents"], 10)
        self.assertEqual(data["max_rounds"], 6)
        self.assertEqual(data["benchmark_rounds"], 3)

    def test_population_totals_and_default_sessions_are_preserved(self):
        options = RunOptions(normal_agents=2, adversary_agents=8, max_dollars=0.5, seed=1)
        config = selected_config(self.config, options)
        self.assertEqual(config.personas, self.config.personas)
        config = selected_config(
            self.config, options.model_copy(update={"normal_agents": 3, "adversary_agents": 7})
        )
        self.assertEqual(len(config.personas), 10)
        self.assertEqual(len({p.agent_id for p in config.personas}), 10)
        self.assertEqual(sum(p.role == "casual_buyer" for p in config.personas), 3)
        self.assertEqual(len({p.role for p in config.personas}), 6)
        for update in ({"normal_agents": 3}, {"max_dollars": 0.6}, {"seed": 11}):
            with self.assertRaises(ValueError):
                selected_config(self.config, options.model_copy(update=update))
        exported = yaml.safe_load(export_config(config))
        validated = RunConfig.model_validate(exported)
        self.assertEqual(len(validated.personas), 10)
        self.assertEqual(exported["spec"], "apps/bazaar/openapi.json")
        self.assertNotIn("api_key", exported)

    def saved(self):
        run_id = str(uuid4())
        folder = self.output / run_id
        folder.mkdir()
        finding = Finding(
            run_id=run_id,
            title="Fixture proof",
            severity="high",
            type="single-user",
            verified=True,
            mapped_bug_id="S2",
            involved_agents=["a"],
            evidence_events=["e"],
            oracle_triggered="S2",
            minimal_repro_sequence=ReplayPlan(
                seed=1,
                steps=[
                    ReplayStep(
                        actions=[
                            ReplayAction(
                                event_id="e",
                                agent_id="a",
                                expected_status=200,
                                request=Request(
                                    method="POST",
                                    path="/api/cart/items",
                                    json_body={"quantity": -1},
                                ),
                            )
                        ]
                    )
                ],
            ),
        )
        run = {
            "run_id": run_id,
            "condition": "swarm",
            "seed": 1,
            "model": "fixture",
            "token_budget": 1000,
            "tokens_used": 10,
            "cost_usd": 0.001,
            "elapsed_s": 1,
            "agents": [],
            "provenance": {"source": "unattested", "provider_origin": "https://secret@localhost"},
            "stopped": False,
        }
        (folder / "run.json").write_text(json.dumps(run))
        write_report([finding], folder)
        return folder, finding

    def test_saved_details_reviews_and_rechecks_keep_original_proof(self):
        folder, finding = self.saved()
        original = (folder / "report.json").read_bytes()
        run = self.archive.detail(folder.name)
        self.assertEqual(run["findings"][0]["mapped_bug_id"], "S2")
        self.assertNotIn("secret", json.dumps(run))
        measured = as_benchmark(run)
        record_review(
            folder,
            [measured],
            finding.id,
            True,
            "Fixture reviewer",
            "Inspected controlled evidence",
        )
        (folder / "rechecks.json").write_text(
            json.dumps([{"finding_id": finding.id, "status": "completed"}])
        )
        reviewed = self.archive.detail(folder.name)
        self.assertTrue(reviewed["assessments"][finding.id])
        self.assertEqual(len(reviewed["rechecks"]), 1)
        self.assertEqual((folder / "report.json").read_bytes(), original)
        self.assertEqual(self.archive.list()[0]["verified_ids"], ["S2"])

    def test_archive_rejects_traversal_symlinks_and_skips_corrupt_rows(self):
        with self.assertRaises(ValueError):
            self.archive.detail("../outside")
        folder, _ = self.saved()
        folder.rename(self.output / "outside")
        folder.symlink_to(self.output / "outside", target_is_directory=True)
        with self.assertRaises(ValueError):
            self.archive.detail(folder.name)
        self.assertEqual(self.archive.list(), [])


if __name__ == "__main__":
    unittest.main()
