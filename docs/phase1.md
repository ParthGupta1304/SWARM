# Phase 1: Bazaar, the swarm and acceptance

The approved scope uses **10 agents** instead of the PRD's 20-agent minimum,
with six roles and **Groq `openai/gpt-oss-120b`** instead of local Qwen. These
changes were explicitly requested by the project owner. Phase 2 Meko memory and
Phase 1 stretch features are separate work.

## Run the application

```sh
uv sync --locked --extra postgres --extra charts
uv run --no-sync python -m swarm.demo
```

- Bazaar marketplace: http://127.0.0.1:8080/bazaar/
- Swarmtest console: http://127.0.0.1:8080/

The launcher owns separate disposable live and verifier Bazaar processes,
databases, and a durable event store. Default storage is SQLite/WAL; Postgres
invariants and replay are directly checked on a temporary Postgres 16 cluster.
Closing the launcher stops its owned processes. No reset endpoint is exposed
on an arbitrary customer target.

The React/Vite storefront includes browsing/search, item details/questions,
synthetic account creation/switching, cart add/remove, coupons, checkout, orders,
seller listings/fulfilment, reviews, direct messages, blocking and listing reports.
It talks to the actual live Bazaar API through an allowlisted same-origin proxy.
Writes are rejected while a test run owns that live target. The independent
verifier never resets the marketplace being explored.

Compiled assets are included, so Node is unnecessary to run the app. To edit
or rebuild the storefront:

```sh
npm ci --prefix apps/bazaar/web
npm run build --prefix apps/bazaar/web
```

## Provider and budgets

Keep credentials in ignored `.env`; do not replace an existing file or commit it.

```dotenv
GROQ_API_KEY=your_key_here
SWARMTEST_PROVIDER_URL=https://api.groq.com/openai/v1
SWARMTEST_MODEL=openai/gpt-oss-120b
```

Python reads the key; the browser only receives the model name and run results.
Groq uses the OpenAI-compatible SDK. For GPT-OSS, low reasoning effort and
Groq's `disable_tool_validation` option avoid provider-side unknown-tool
validation failures. **Local allowlists, exact-one-call validation, JSON Schema
validation and fixed account identities still apply before any HTTP action.**
A malformed model choice consumes measured usage and is rejected locally.

The shipped prices are uncached-input $0.15 and output $0.60 per million tokens,
verified against [Groq's model documentation](https://console.groq.com/docs/model/openai/gpt-oss-120b).
Displayed dollars are an estimate from reported tokens and configured rates,
not a claim about a provider invoice or free-credit balance. Update the rates
when selecting another model.

Shared/per-actor token budgets and a conservative dollar reservation cap apply
before model calls. Each run has a $0.50 cap. Evaluator overhead has its own
20,000-token budget and dollar cap and is reported separately. Provider usage
must include prompt, completion and total tokens. Missing/inconsistent usage
aborts scoring; no amount is invented for a failed provider call.

Shared request spacing and a token bucket pace all actors. The token bucket
reserves estimated usage and refunds the difference after measured usage is
returned. Default limits are 24 requests/minute and 7,000 tokens/minute, below
the observed account's 8,000-token/minute limit. This limits provider calls;
HTTP business actions still dispatch together at round barriers. Other clients
using the same key can still exhaust account limits. Stop cooperatively through
the console; in-flight calls finish and queued calls can be cancelled.

## Config-only CLI

```sh
uv run --no-sync swarmtest run --config swarmtest.yaml
uv run --no-sync swarmtest run --config swarmtest.yaml --condition isolated
uv run --no-sync swarmtest benchmark --config configs/bazaar-benchmark.yaml --output artifacts/groq-phase1
# After a transient interruption, reuse only matching completed runs:
uv run --no-sync swarmtest benchmark --config configs/bazaar-benchmark.yaml --output artifacts/groq-phase1 --resume
```

`swarmtest.yaml` binds OpenAPI, seed JSON, invariant SQL, personas, model,
budgets and the owned Bazaar target. No Python hook factory is needed for this
built-in target. Custom external targets must explicitly supply disposable
reset/detection hooks; the CLI refuses to silently omit detection.

Interactive runs allow six rounds. The bounded benchmark config allows
three rounds per actor for **both** conditions and uses equal 100,000-token
caps and the same model. This short-horizon experiment fits provider quotas;
it is not a claim of exhaustive exploration or complete recall. Isolated mode
resets the app before each actor and disables cross-run actor memory. Swarm
mode shares the app. Both use the same ten personas and aggregate budget.

Completed benchmark conditions are checkpointed. Resume verifies the config,
seeds, frozen truth, relevant source and provider protocol before reusing a run.
Changed experiments require a new output directory. Failed runs retain partial
events, are labelled unscored and never count as completed conditions. Earlier
four-round experiments interrupted for an oracle correction or provider error
are retained separately; they are not mixed into the final comparison.

An optional `burst_tool: checkout` configuration selects a same-operation cohort
and fires it at its own barrier; other pending actions follow afterward. With
no selection, all ready actions share the round barrier. No model action is
silently invented by the scheduler.

## Objectives and observations

The roster contains two casual buyers, two bargain hunters, one impatient
clicker, two fraudsters, two sock-puppet actors and one troll. Coupon and payout
pairs explicitly share an account; a session is not presented as a separate
human owner. Every actor has a unique ID and fixed permitted identity fields.

Scores are observed business outcomes: completed purchases, realized cents
saved, excess compensation, same-owner reputation gains and successful contact
after blocking. Shared-account sessions see the same account outcome. Scores
are not proof that a bug exists. SQL/Python oracles and independent replay are
the proof mechanism.

Actors observe their own account's recent activity, blocks affecting them and
public listing/sales notices. They do not receive oracle results, planted bug
IDs, verifier state or other accounts' private order details. The rolling
summary is charged to the same budgets as decisions.

## Frozen planted cases

| ID | Scenario | Required classification |
| --- | --- | --- |
| E1 | Buyers purchase more units than the initial stock under overlap | Emergent |
| E2 | Concurrent sessions redeem one account's coupon twice | Emergent |
| E4 | Refund and dispute requests overlap and pay an order twice | Emergent |
| E5 | A same-owner second account buys, the seller fulfils, and the buyer inflates reputation | Emergent |
| E7 | A user who is already blocked posts an item question to the seller | Emergent |
| S1 | Empty-cart checkout crashes | Single-user |
| S2 | Nonpositive quantity accepted in a cart | Single-user |
| S4 | Search for `[` crashes | Single-user |

E5 requires a fulfilled purchase and separate fixed seller/buyer identities;
a direct seller review is rejected. E7 records actual block state at submission,
not a timestamp comparison that can confuse same-second ordering. This internal
oracle metadata is excluded from product responses.

Use one config switch to apply the PRD's two advertised fixes:

```sh
BAZAAR_VERSION=v2 uv run --no-sync python -m swarm.demo
```

v2 fixes E1/E2 while leaving the other planted cases enabled. Individual bug
overrides remain available for focused direct checks. Phase 2's new E3 scenario
is outside this Phase 1 delivery.

## Replay and reporting

Every action is appended to the independent event store with a sequence,
request, response hash/JSON, actor, round, seed, status, latency and usage.
Generated resource IDs can be rebound from earlier replay responses; echoed
fixture IDs are not incorrectly treated as creation dependencies.

Verification resets the independent target and checks the original oracle.
Reduction removes whole steps, unrelated actors and individual unnecessary
actions inside concurrent steps. Counterfactual actor-removal results and
verification attempts are retained. Single-user findings remain single-user
when other agents happened to be active. Errors or uncertain causal checks
cannot pass the emergent gate. Races retain repeated-attempt evidence; barriers
preserve simultaneous intent rather than guaranteeing OS/database scheduling.

The console includes an SSE activity feed with reconnection/cursors, shared
resource graph, scores, usage/cost, stop, replay progress, findings and comparison.
Graph links indicate shared resources, not causality. Completed benchmark
reports can be loaded without another AI run:

```sh
uv run --no-sync python -m swarm.demo --port 8082 --results artifacts/groq-phase1
```

The review screen shows the saved findings and replay evidence. A console opened
with `--results` cannot overwrite that experiment by starting a new benchmark.

## Acceptance and human review

The benchmark gate requires six completed runs (isolated/swarm x seeds
11/22/33), ten actors, matching model/token cap, real provider receipts, the
frozen catalog hash, at least three distinct causally verified emergent bugs,
independent LLM assessment and an evidence-bound **human** spot-check.

Candidates are independently assessed for actual correctness; membership of an
assigned ID in the catalog is not a precision measurement. Precision stays
unassessed until the relevant candidates have correctness labels. Reports
include split recall, before/after precision, timing, tokens, estimated cost,
cost per verified bug, repeatability, mean/range, CSV and chart exports.

Inspect actual requests and evidence before recording a review in the console.
Alternatively:

```sh
uv run --no-sync swarmtest review --config configs/bazaar-benchmark.yaml --output artifacts/groq-phase1 --finding-id FINDING_ID --reviewer YOUR_NAME --decision correct --note 'What I checked in the evidence'
```

Reviews are tied to the exact finding payload hash. Changed evidence invalidates
an old review. The software never signs a human review automatically. A stopped,
failed, scripted or incomplete experiment cannot pass real AI acceptance. The
benchmark gate is separate from the full software/demo checklist in progress.md.

## Offline fallback and verification

```sh
uv run --no-sync python -m swarm.demo --scripted --port 8081
```

This owns a local scripted model-provider fixture and needs no real key. It
executes real marketplace requests and replay. Model choices and token counts
are synthetic and prominently labelled; its results cannot pass AI acceptance.
See [the two-minute demo script](demo-script.md) and
[recorded fallback](demo/phase1-fallback.mp4). The captured-state recording clearly
distinguishes manual actions, scripted integration and actual Groq results.

Direct checks cover all eight cases on SQLite/Postgres, fixed race paths,
three single-user versus five emergent causal reductions, generated-ID replay,
ten actors/scores, money/token caps, pacing/stop, CLI wiring, six-run fixture
comparison, evidence review and browser marketplace flows. No broad new test
suite was added. Evidence is kept under ignored `artifacts/` directories.
Docker definitions exclude `.env`, repository metadata, artifacts and local
virtual environments from image context. Native execution is checked; the
Docker daemon was unavailable, so container execution is not claimed verified.
