# Dev2 runtime and Dev3 integration

## Delivered code

The teammate's `42d285a` implemented M1/M2: a single-agent OpenAI-compatible
model loop, OpenAPI-generated tools and an in-memory mock Bazaar. Merge
`59055b1` brought those files together with Dev3, but the old event logger did
not produce Dev3 Events and `uv.lock` did not include the new dependencies.

The integration completion adds:

- `adapters/openapi.py`: one `prepare_request()` used for HTTP execution and
  replay evidence; local references, nested body schemas, inherited parameters,
  encoded path values and scalar query/header parameters. Tool arguments are
  validated. Unknown operations and ambiguous parameter names are rejected.
- `swarm/events.py`: shared `RunEvents` with preallocated run-wide sequences,
  contiguous concurrency groups, full SHA-256 hashes, SQLite/Postgres protocol
  support and optional schema-compatible JSONL mirroring.
- `swarm/agent.py`: separate decisions/actions, actor tool allowlists, one native
  call per turn, robust JSON fallback, rolling summaries, isolated account
  setup and measured usage for all model calls. Retries are disabled.
- `swarm/budget.py`: shared and per-actor admission, reservation and actual
  prompt/completion accounting. Unknown or inconsistent usage aborts the run.
- `swarm/runtime.py`: asynchronous round coordination, barrier dispatch,
  per-actor decision limits, isolated baseline, cooperative kill switch,
  optional local actor memory and measured benchmark callback.
- `swarm/pipeline.py`: checks on completed windows, detection, independent replay,
  preservation of unverified findings, verified-finding deduplication and
  evaluator-only bug mappings.
- `swarm/personas.py`: the six PRD role objectives and `build_roster(tool_sets)`.
  Bind each role to actual operation IDs from Dev1's spec. This does not claim
  that the mock implements coupons, self-dealing or blocking scenarios.
- `swarm/cli.py`, `swarm/__main__.py`, `configs/mock.yaml`: configured runs and
  benchmarks. `main.py` delegates to the CLI. The lockfile includes dependencies.

Dev3's version 1 wire contracts and stores are unchanged.

## Run against the teammate mock

From the repository root, install dependencies and start the target:

```sh
uv sync --locked
uv run --no-sync uvicorn mock_bazaar.server:app --port 8001
```

Start the configured local model provider separately, then run:

```sh
uv run --no-sync python -m swarm run --config configs/mock.yaml
```

The example uses the teammate's Ollama-compatible endpoint and model. Point
`provider_base_url` and `model` at a running OpenAI-compatible provider; set the
API key in the environment variable named by `api_key_env`. The YAML stores
only that variable name. Set the actual input/output prices for paid providers;
zero prices are appropriate for a free local provider. The model must return
prompt, completion and total token usage.

Output: `artifacts/swarm/run.json`, `events.jsonl`, `report.json`, `report.md`.
The SQLite event store defaults to `swarmtest_events.sqlite3`. CLI runs without
hooks execute and log actors only; an empty report does not certify that SQL
invariants were checked. Supply detection hooks for actual finding discovery.

The six roles are casual buyer, bargain hunter, impatient clicker, fraudster,
sock puppet and troll. Configured personas need unique IDs, objectives, tool
allowlists and optionally `completion_tool`, `max_steps` and `token_budget`.
Completion is a flow stop signal, not evidence that a bug occurred. Set
`completion_tool: null` for exploration that should continue until its limits.

`max_rounds` bounds all decisions, including invalid ones. Actor `max_steps`
counts decision attempts, not just successful HTTP actions. Seeds are sent to
the provider and determine actor ordering; a provider or DB may still be
nondeterministic. One ready action per actor is dispatched at the round barrier;
actors choosing the same tool execute a same-action burst. This preserves
simultaneous intent, not a guaranteed network or database interleaving.

## Reset, detection and verification hooks

Create a Python module with a synchronous `create_hooks(config: RunConfig)`
factory returning `RuntimeHooks`. Load it with `--hooks your_module:create_hooks`.
The factory receives the actual condition run's seed and budget in its config.

`RuntimeHooks` contains:

| Hook | Signature | Responsibility |
| --- | --- | --- |
| `reset` | `async (seed: int) -> None` | Reset only the live disposable target and restore stable fixtures. |
| `detect` | `async (window: RoundWindow) -> list[Finding]` | Check completed target windows and independently verify candidates. |
| `close` | `async () -> None` | Close verifier HTTP clients and other hook resources. |

Construct `DetectionPipeline` with a `ReplayVerifier`, the live origin, and
optionally a read-only `SQLInvariantRunner`, SQL invariants and an evaluator bug
mapping. Pass the pipeline as `detect`. Its verifier must use a different HTTP
origin from the live target. Different URLs alone cannot prove separate DBs:
Dev1 must ensure that the targets actually have independent disposable data.

Use `HTTPReplayTarget` with Dev1's async reset callback, original-failure oracle
and per-actor credentials. Credentials are never stored in Event headers. For
changing tokens, initialize `agent_headers` with a nonempty mapping keyed by
actor ID and update its values in the replay reset callback before execution.
Provision the appropriate actor fixtures on every replay reset. Replay setup
must recreate prerequisites omitted from recorded model actions, including
registration and login. Live runtime setup currently expects `/register`,
`/login` and a login response containing `token`, matching the teammate mock;
confirm this convention with Dev1's real app before claiming integration.

Detection runs after the entire HTTP burst and event writes finish. A
`RoundWindow` exposes all causal events in the current target lifetime and the
latest burst. In isolated mode, it never combines evidence across actor resets.
The pipeline retains prior setup actions in error reproducers. Unavailable SQL
checks raise; replay errors remain unverified. Actor-based emergent labels
still need causal review, as described in Dev3's integration guide.

## Baseline and benchmark

Isolated mode requires `reset`. It runs each actor alone, resets the disposable
target before the next actor and keeps the event store. Both conditions share
the same configured aggregate budget, per-actor caps and model.

```sh
uv run --no-sync python -m swarm benchmark --config configs/mock.yaml \
  --hooks your_module:create_hooks --truth path/to/frozen-truth.json \
  --seeds 11 22 33 --output artifacts/bazaar-benchmark
```

The truth JSON maps frozen bug IDs to `single-user` or `emergent`. It and the
pipeline's oracle-to-bug mapping are evaluator inputs, never model tools or
prompts. Benchmark mode requires reset and detection hooks and uses fresh
agents and hook instances for all six runs. Cross-run actor memory is disabled.
The synchronous `benchmark_callback(...)` also plugs into `bench.run_benchmark`.
Hook reset/detection resources must be scoped per run. No real benchmark can be
claimed until Dev1 supplies the actual app, invariants, reset and ground truth.

## Budgets, stopping and memory

Every model call reserves prompt/output capacity before dispatch. A conservative
UTF-8-byte estimate plus framing allowance bounds prompts for byte-token
providers; it can reject calls before a provider's exact tokenizer would.
Provider usage is reconciled on return. Providers using a different tokenization
bound must supply a suitable admission estimator before being used for strict
budget experiments. Missing usage, network failures with unknown usage, or a
provider exceeding its reservation abort the run; they never become fabricated
zero-cost measurements. Configured prices convert reported input/output usage
to cost, rather than claiming an audited billing total.

Set `kill_file` in YAML and create that file to stop, or call
`RunCoordinator.stop()`. Relative config paths resolve beside the YAML. Stops
are cooperative: in-flight calls finish within their configured timeouts, then
no new round dispatches. Stopped runs retain events but cannot be scored as
completed benchmarks. They can include an actor decision that consumed tokens
without dispatching its action; aggregate accounting includes that decision.

Pass a `LocalMemoryStore` to `RunCoordinator` to recall/save actor summaries and
save verified findings. Raw conversations and credentials are not stored there.
Dev3's existing regression recheck API remains available to callers before
exploration. The product Meko adapter remains Phase 2 after the real core gate.
Shared development handoffs in Meko are separate from product runtime memory.

## Direct checks performed

Direct HTTP checks on 2026-10-31 used ephemeral localhost model/app fixtures;
no written test suite was added and no paid model API was called.

- Actual teammate mock: two authenticated buyers each completed browse, add and
  checkout; six persisted Events round-tripped through Dev3 JSONL and replay.
- Direct M1-style single-agent flow and the config-driven CLI completed.
- A separate controlled SQLite-backed race fixture reached two concurrent HTTP
  actions; the invariant found an oversell and a different target verified it.
- Six fixture benchmark runs across seeds 11/22/33 completed: swarm reproduced
  the controlled bug and isolated runs did not. Nine live-target resets
  confirmed per-actor isolation. JSON, CSV and PNG exports were generated.
- Tool-scope violations and multiple native calls dispatched no actions while
  accounting for usage. JSON strings containing braces parsed correctly.
- Tiny shared/per-actor budgets dispatched no model calls. Missing usage aborted.
  A per-actor one-step cap also stopped invalid decisions after one attempt.
- Twelve browsing decisions plus one rolling summary counted all 390
  provider-reported fixture tokens. Kill-switch runs were rejected for scoring.
- Transport failure produced `response_status=None` and a Dev3 transport finding.
- Local actor memory was isolated and the verified fixture finding was saved.

Local evidence: `artifacts/dev2-dev3-integration/check-results.json` and its
report/benchmark subdirectories, ignored by Git. The measured tokens above
belong to the deterministic provider fixture, not live-model inference.

## Remaining external integration

Dev1 must deliver real Bazaar, its OpenAPI, stable seeded fixtures, SQL
invariants, frozen planted-bug mappings and separate verifier reset/oracles.
Then exercise all six real role scenarios with the selected live model, verify
at least three emergent bugs, and run the actual held-out benchmark. Dashboard
and SSE delivery remain outside this runtime. Dynamic response-ID binding and
the product Meko adapter remain deferred as documented by Dev3.
