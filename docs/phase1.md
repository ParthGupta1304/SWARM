# Phase 1: local run and acceptance

## Start

```sh
uv sync --locked --extra postgres --extra charts
cp .env.example .env
# Edit .env locally with your provider URL, model and API key.
uv run --no-sync python -m swarm.demo
```

Open http://127.0.0.1:8080. Select a swarm run, isolated users, or the complete
six-run benchmark. Stop cooperatively with the Stop run button. Each launcher
owns two different disposable Bazaar processes/databases, an independent event
store and its output directory. Default storage is SQLite with WAL; Postgres
uses the same target/reset and invariant contracts and is directly verified.
No production target URL has a reset endpoint. Closing the launcher stops its
owned targets; artifacts remain under `artifacts/phase1/` and are Git-ignored.

Provider configuration stays in ignored `.env`:

- `SWARMTEST_PROVIDER_URL`: OpenAI-compatible endpoint ending in `/v1`.
- `SWARMTEST_MODEL`: actual model identifier.
- `SWARMTEST_API_KEY`: credential read only by the Python server.

Set real input/output token prices in `configs/bazaar.yaml` for paid providers.
The provider must return complete prompt/completion/total usage. Missing or
uncertain usage aborts a run. Default prices are zero for local free inference;
they do not represent an estimate of a paid provider's bill. Restart the launcher
after changing provider settings. The browser never receives the key.

Optional container entry point: `docker compose up --build`. It uses the root
repository build context, binds only host localhost:8080 and stores artifacts
under `artifacts/docker-phase1/`. The container definition is supplied; the
local Docker daemon was unavailable, so container execution is not claimed as
verified. Native Python execution is the checked path.

## Integrated behavior

The six PRD roles are configured in YAML. There are eight actor sessions:
extra coupon/refund sessions exercise shared-account races without inventing
an extra role. Seeded identities are checked against the app and fixed request
identity arguments cannot be chosen by the model. The sock-puppet session
controls the seller and a separate same-owner account; ownership is represented
explicitly in the fixture. Tool definitions contain business operations only;
findings, feature flags, telemetry and evaluator ground truth are not model tools.

RunCoordinator preallocates Event sequences and dispatches action bursts at
barriers. Every model decision, invalid action and rolling summary is charged
to shared and per-actor caps. The UI reads persisted usage, actor summaries,
request timelines and findings; it displays connection failures and empty states.
Canonical Dev3 Finding payloads are stored intact and SSE emits real newlines.
Run and benchmark output includes JSON/Markdown reports, canonical events,
measured raw runs, CSV summaries and a recall chart.

`swarm.bazaar.make_hooks` connects atomic fixture resets, SQL/Python/log checks,
independent HTTP replay, greedy whole-step reduction and publication. Error logs
store action correlation, exception class, method and path rather than raw
tracebacks or credentials. Reads see the previous or next reset state, never
missing tables. Published findings/telemetry survive target resets; replay
state and exploration data remain separate. Isolated mode resets app data before
every actor and disables cross-run actor memory in benchmark comparisons.

## Frozen bug semantics

The original implementation let E2 and E4 reproduce sequentially. With the
owner's authorization, these now implement interaction-dependent check/write
races, matching the PRD's concurrent scenarios. No planted ID was renamed.

| ID | Scenario | Independent classification |
| --- | --- | --- |
| E1 | Two buyers purchase the last unit concurrently | Emergent |
| E2 | Two sessions apply a coupon concurrently; sequential reuse returns 409 | Emergent |
| E4 | Refund and dispute checks overlap; sequential repeat compensation returns 409 | Emergent |
| E5 | Seller or same-owner sock account reviews its listing | Single-user in this seeded fixture |
| E7 | A seller blocks a user who then contacts them via item questions | Emergent |
| S1 | Empty-cart checkout throws 500 | Single-user |
| S2 | Cart accepts nonpositive quantity | Single-user |
| S4 | Search crashes on the special character `[` | Single-user |

`configs/bazaar-truth.json` is evaluator-only and frozen before held-out runs.
E5 is classified from its independently executable one-actor reproducer, rather
than repeating the PRD's original emergent assumption. Shared-account E2/E4
involve multiple sessions, not necessarily different human account owners.
`BAZAAR_VERSION=v2` fixes E1/E2. Individual overrides can fix any other planted
scenario. The fixed lock path works on both Postgres and SQLite; blocking DB
work and exception-log persistence run outside the async request loop.

## Acceptance gate

`bench.gate.evaluate_phase1` requires:

1. Six complete measured runs: isolated/swarm × seeds 11, 22, 33, distinct from
   development seed 1, with matching model/budget.
2. At least three distinct verified, ground-truth emergent bugs.
3. Evidence provenance `real-model`. Scripted fixture evidence cannot pass.

The console writes `benchmark/phase1-gate.json`. A failed/incomplete/stopped run
is never presented as a complete benchmark. Successful implementation checks do
not satisfy this gate. Real provider discovery, prompt tuning on the dev seed,
and the held-out benchmark are pending until a provider is configured. An
independent evaluator LLM matches evidence to the manually reviewed frozen
catalog, with expected oracle IDs withheld. Its separate 20,000-token evaluator
budget and measured overhead are recorded in `benchmark/judge.json`, outside
both conditions' equal exploration budgets. Judge errors/disagreements keep the
gate incomplete; they do not overwrite the underlying oracle mapping. Live
model performance remains an empirical outcome.

## Verification evidence

Direct checks are performed rather than adding a new test suite:

- All eight real Bazaar failures detected and independently replay verified on
  owned SQLite targets; E1/E2/E4/E7 preserved multiple necessary sessions.
- The same eight paths verified on a temporary Postgres 16 cluster, stopped
  afterward without touching the pre-existing server.
- Sequential coupon reuse rejected; fixed race paths prevent duplicate coupon
  redemptions, overselling and duplicate payouts.
- Seeded actor startup, fixed identity parameters, full canonical finding
  ingestion, exception-log correlation, SSE framing and telemetry checked.
- Full console path with an explicitly scripted local provider: concurrent run,
  all six benchmark callbacks, persisted events/reports, live metrics, conflict
  rejection for overlapping runs and cooperative stop. Fixture gate remained
  incomplete as designed. Latest source rechecks are recorded in progress.md.
- Browser review: activity view, budget meter, findings and comparison layout.
  Native source lint/format/compilation and JavaScript syntax checks passed.

Evidence directories are local/ignored: `artifacts/phase1-check/` and
`artifacts/phase1-console-check/`. They contain scripted/direct results, not
live-model discovery claims.

## Known practical limits

Barriers preserve simultaneous action intent, not deterministic DB scheduling.
Repeated replay measures reproducibility. Stable seeded IDs are restored on
reset; dynamic generated-ID rebinding is not implemented, so a replay whose
resource IDs change remains inconclusive instead of claiming verification.
The byte-based prompt admission bound assumes byte-token providers and can
stop earlier than an exact tokenizer. Post-demo Meko product memory, autonomous
fix loops, a second-app pack and chaos injection are outside Phase 1.
