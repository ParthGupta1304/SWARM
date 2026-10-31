"""Export the language-neutral contracts for other developers and agents."""

import json
from pathlib import Path

from detect.contracts import Event, Finding, ReplayPlan
from verify.replay import VerificationResult


def export_schemas(directory: str | Path) -> None:
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    for model in (Event, Finding, ReplayPlan, VerificationResult):
        (path / f"{model.__name__}.schema.json").write_text(
            json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    export_schemas(Path(__file__).resolve().parents[1] / "docs" / "contracts")
