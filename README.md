# Swarmtest

A community of normal users and adversaries tests a real marketplace, then
replays observed failures on an independent database. The Phase 1 build includes
the Bazaar storefront, ten configurable agents, detection/replay, a live console
and the isolated-versus-swarm benchmark. Product Meko memory is Phase 2.

## Start

```sh
uv sync --locked --extra postgres --extra charts
# Configure GROQ_API_KEY in ignored .env; see .env.example.
uv run --no-sync python -m swarm.demo
```

Open [Bazaar](http://127.0.0.1:8080/bazaar/) to browse and shop, or the
[Swarmtest console](http://127.0.0.1:8080/) to run agents and inspect findings.
The React storefront uses the same live Bazaar instance as the agents.
The launcher owns separate live/replay targets and stops them on exit.

The project owner approved **10 agents and Groq `openai/gpt-oss-120b`**, replacing
the PRD's 20-agent minimum and earlier local-Qwen setup. The API key remains server-side and is
never committed or sent to the browser. Keep `.env` local.

## Run or compare

```sh
uv run --no-sync swarmtest run --config swarmtest.yaml
uv run --no-sync swarmtest benchmark --config configs/bazaar-benchmark.yaml --output artifacts/groq-phase1
# Resume only an identical experiment after a transient interruption:
uv run --no-sync swarmtest benchmark --config configs/bazaar-benchmark.yaml --output artifacts/groq-phase1 --resume
# Review saved comparison/evidence without running the model again:
uv run --no-sync python -m swarm.demo --port 8082 --results artifacts/groq-phase1
```

Interactive runs allow eight rounds; the quota-bounded comparison uses three
rounds in both conditions and three held-out seeds. Token/dollar caps, shared
provider pacing and a cooperative stop apply. Findings include reduced causal
reproductions and independent verification attempts. Human review is an
explicit acceptance step, not an automatically completed checkbox.

For an offline rehearsal, with clear scripted-fixture labels:

```sh
uv run --no-sync python -m swarm.demo --scripted --port 8081
```

The [two-minute fallback](docs/demo/phase1-fallback.mp4) combines captured UI states
with explicit manual/scripted/real-Groq labels.

See [context, caching and cost efficiency](docs/ai-efficiency.md),
[setup, budgets, bug semantics and acceptance](docs/phase1.md),
[demo script](docs/demo-script.md), and [current progress](progress.md).
Direct/scripted checks establish software behavior; real AI results and human
review must establish the benchmark gate. No detection-rate claim should be
inferred from a scripted rehearsal.

## Development

Python 3.11+ and uv are required. Compiled storefront assets are included;
Node is needed only when editing them:

```sh
make frontend
make check
```

The teammate React dashboard source is also preserved in `dashboard/`. The
Python launcher serves the full run console from `dashboard/console.html`.
To develop the separate read-only React viewer, run `npm ci --prefix dashboard`
and `npm run dev --prefix dashboard -- --host 127.0.0.1`; it connects to a
standalone Bazaar API at `http://localhost:8000` by default. Override
`VITE_BAZAAR_API_URL` when using another API address.


| Owner | Modules |
| --- | --- |
| Dev1 | `apps/bazaar/`, `dashboard/`, fixtures, OpenAPI and demo |
| Dev2 | `swarm/`, `adapters/`, CLI/config, scheduling and budgets |
| Dev3 | `detect/`, `verify/`, `bench/`, `memory/` and contracts |

The teams' contributions are integrated. Earlier development handoffs remain
under `docs/`; current behavior is described in `docs/phase1.md`. Public wire
schemas are in `docs/contracts/`. Coordinate shared packaging/lock changes.

Development handoffs stay in Git per the project owner's preference. The
[team context fallback](docs/team-context.md) remains available. A connected
Meko tool used for development notes is separate from the unimplemented Phase 2
product adapter; no Meko sync is required to run Phase 1.
