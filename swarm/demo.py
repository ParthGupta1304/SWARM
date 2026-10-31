"""Launch owned Phase 1 targets and the local operations console."""

from __future__ import annotations

import argparse
import os
from contextlib import ExitStack
from pathlib import Path

import uvicorn

from dashboard.server import create_app
from swarm.provider import load_config
from swarm.runtime import RunConfig
from swarm.targets import BazaarEnvironment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "configs" / "bazaar.yaml",
    )
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", choices=["127.0.0.1", "0.0.0.0"], default="127.0.0.1")
    parser.add_argument("--output", type=Path, default=Path("artifacts/phase1"))
    parser.add_argument("--results", type=Path, help="Review an existing benchmark directory")
    parser.add_argument(
        "--scripted", action="store_true", help="Explicit offline fixture demo; never AI acceptance"
    )
    args = parser.parse_args()
    config = load_config(args.config)
    values = config.model_dump()
    with ExitStack() as stack:
        if args.scripted:
            from swarm.demo_fixture import ScriptedProvider

            provider = stack.enter_context(ScriptedProvider())
            os.environ["SWARMTEST_FIXTURE_KEY"] = "fixture"
            values.update(
                provider_base_url=provider.url,
                model="scripted-fixture",
                api_key_env="SWARMTEST_FIXTURE_KEY",
                max_rounds=6,
                requests_per_minute=1000000,
                tokens_per_minute=100000000,
                input_cost_per_million=0,
                output_cost_per_million=0,
            )
        environment = stack.enter_context(
            BazaarEnvironment(
                args.output, version=config.bazaar_version, seed_fixture=config.seed_fixture
            )
        )
        values["app_base_url"] = environment.live.url
        selected = RunConfig.model_validate(values)
        app = create_app(selected, environment, args.output, results=args.results)
        print(f"Swarmtest console: http://127.0.0.1:{args.port}")
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
