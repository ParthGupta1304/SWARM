# Swarmtest

Multi-agent testing for failures caused by interacting users. This first slice
implements Dev3's event logging, detection, replay verification, reports,
benchmark utilities and local memory. Bazaar, the swarm runtime and dashboard
are separate teammate deliverables.

## Development

Python 3.11 or later and [uv](https://docs.astral.sh/uv/) are required.

```sh
uv sync --locked --no-dev
uv run --no-sync python -m detect.schemas
uv run --no-sync python -m compileall -q detect verify bench memory
```

Install the optional `postgres` extra for Postgres storage and the `charts`
extra for matplotlib charts. No model API key is required for Dev3's pipeline.
Per the project owner's workflow, delivery uses direct feature smoke checks
rather than a written test suite. Actual checks and their results are recorded
in [progress.md](progress.md).

See [Dev3 integration and handoff](docs/dev3-integration.md) for public contracts,
ownership, runtime integration, reset requirements and pending work. Exported
JSON Schemas are under `docs/contracts/`.

## Ownership

| Owner | Modules and handoffs |
| --- | --- |
| Dev1 | `apps/bazaar/`, `dashboard/`, OpenAPI spec, seed fixtures, invariant SQL and reset fixture |
| Dev2 | `swarm/`, `adapters/`, CLI/config, orchestration, barriers, budgets and the later Meko adapter |
| Dev3 | `detect/`, `verify/`, `bench/`, `memory/` and their interface docs |

Root packaging and dependency lock were bootstrapped by Dev3 while the repo
was empty. Coordinate changes to those shared files instead of independently
replacing them. Python contracts in `detect/contracts.py` are authoritative for
Dev3's v1 interface; affected owners review contract changes.

Search the shared Meko datapack before major tasks. Save decisions, bug fixes
and handoffs with paths, branch and commit SHA. Keep secrets out of shared
memory and Git. Verify retrieved context against the current repository code.

## What is measured

Direct smoke checks use a deliberately controlled two-user oversell fixture to
verify the pipeline. Those results are **not** a Bazaar benchmark. Real benchmark
results require Dev1's planted-bug manifest and Dev2's isolated/swarm runs.

The event/replay store is separate from the target app's disposable database.
Meko holds shared development context now; a product memory adapter can be
added after the core demo works without changing the local MemoryStore API.
