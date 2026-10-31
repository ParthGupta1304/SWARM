# Swarmtest

Multi-agent testing for failures caused by interacting users. The runtime now
connects OpenAPI-driven actors to Dev3 event logging, detection, independent
replay, reports, benchmark utilities and local memory. A mock Bazaar supports
direct checks; real Bazaar and the dashboard remain Dev1 deliverables.

## Phase 1 console

The real Bazaar app, runtime, independent replay target and local dashboard
are integrated on `codex/phase1-completion`. Run:

```sh
uv sync --locked --extra postgres --extra charts
uv run --no-sync python -m swarm.demo
```

Open [the local console](http://127.0.0.1:8080). Configure the model provider in
ignored `.env` using `.env.example`; do not commit or share its API key.
See [Phase 1 setup and acceptance](docs/phase1.md) for the six-role/eight-session
configuration, frozen bug semantics, provider setup, benchmark and gate.
Direct/scripted checks passed; real-model acceptance remains pending until
provider configuration and the measured AI runs are complete.

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

See [runtime setup and Dev2/Dev3 integration](docs/dev2-integration.md) for
configuration, concurrent/isolated execution, budgets and benchmark hooks.
Run `uv run --no-sync python -m swarm --help` for the CLI.

See [Dev3 integration and handoff](docs/dev3-integration.md) for public contracts,
ownership, runtime integration, reset requirements and pending work. Exported
JSON Schemas are under `docs/contracts/`.

If a teammate cannot use Meko, follow the
[shared context fallback](docs/team-context.md) and maintain a developer-owned
handoff such as [Dev2's handoff](docs/handoffs/dev2.md). Code and committed
context can be shared through GitHub while MCP is unavailable.

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
