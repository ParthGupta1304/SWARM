"""Launch owned Phase 1 targets and the local operations console."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn
import yaml
from dotenv import load_dotenv

from dashboard.server import create_app
from swarm.runtime import RunConfig
from swarm.targets import BazaarEnvironment


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "configs" / "bazaar.yaml",
    )
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", choices=["127.0.0.1", "0.0.0.0"], default="127.0.0.1")
    parser.add_argument("--output", type=Path, default=Path("artifacts/phase1"))
    args = parser.parse_args()
    config = RunConfig.model_validate(yaml.safe_load(args.config.read_text()))
    values = config.model_dump()
    values["spec"] = str((args.config.resolve().parent / config.spec).resolve())
    values["kill_file"] = None
    values["provider_base_url"] = os.getenv("SWARMTEST_PROVIDER_URL", config.provider_base_url)
    values["model"] = os.getenv("SWARMTEST_MODEL", config.model)
    with BazaarEnvironment(args.output) as environment:
        values["app_base_url"] = environment.live.url
        selected = RunConfig.model_validate(values)
        app = create_app(selected, environment, args.output)
        print(f"Swarmtest console: http://127.0.0.1:{args.port}")
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
