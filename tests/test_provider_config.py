"""The shipped configs must survive runtime validation and dashboard export."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from pydantic import ValidationError

from dashboard.presentation import export_config
from memory.store import LocalMemoryStore, create_memory_store
from swarm.provider import load_config
from swarm.runtime import FindingsStoreConfig, RunConfig

ROOT = Path(__file__).resolve().parents[1]


class ProviderConfigChecks(unittest.TestCase):
    def test_shipped_configs_and_export_round_trip(self):
        for name, backend in (("swarmtest.yaml", "meko"), ("configs/bazaar.yaml", "local")):
            with self.subTest(config=name):
                config = load_config(ROOT / name)
                self.assertEqual(config.findings_store.type, backend)
                restored = RunConfig.model_validate(yaml.safe_load(export_config(config)))
                self.assertEqual(restored.findings_store, config.findings_store)

    def test_store_settings_reject_unknown_options(self):
        for values in ({"type": "typo"}, {"fallback": "typo"}, {"api_key": "secret"}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                FindingsStoreConfig.model_validate(values)

    def test_validated_meko_config_falls_back_without_credentials(self):
        config = load_config(ROOT / "swarmtest.yaml")
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict("os.environ", {}, clear=True),
            patch("memory.store.find_dotenv", return_value=""),
        ):
            with create_memory_store(config.model_dump(), Path(tmp) / "memory.sqlite3") as store:
                self.assertIsInstance(store, LocalMemoryStore)
                self.assertEqual(store.recall_findings(config.project), [])


if __name__ == "__main__":
    unittest.main()
