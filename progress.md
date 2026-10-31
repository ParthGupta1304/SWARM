# Workspace reset — 2026-11-01

- Added a confirmed Reset workspace control to the console. It drains active
  model/API/replay/benchmark work, blocks overlapping operations, resets both
  seeded targets (including findings/telemetry), clears generated run data,
  comparisons/reviews/memory and replaces the event database.
- Added workspace generations, stale-response/cursor protection, browser-state
  clearing and cross-tab Bazaar refresh. Browser HTTP-cache clearing is requested;
  provider-managed Groq caching/account quotas remain outside the local scope.
- Source, credentials, settings, unrelated files/experiments and external saved
  results are protected. Read-only result views disable Reset; failures block
  new work until retry succeeds. No reset was executed on the owner's data.
- Checks: 18 Python checks and the offline frontend behavior check pass. Real
  disposable SQLite/scripted integration passes all eight planted cases, six
  comparison runs, idle/active reset, reseeding and reuse. Frontends/package build
  pass. The idle launcher was reloaded and the live Reset control/API and Bazaar
  assets verified without resetting owner data. This work stays on the local
  `codex/ai-efficiency` branch.
- See `docs/workspace-reset.md` for scope and API/validation details.

---

# Run length update — 2026-11-01

- Owner requested six rounds. Regular dashboard and config-only CLI runs now
  use `max_rounds: 6`; the three-round-per-condition benchmark stays unchanged.
- Latest completed real Groq run `74825234-0830-4b36-9b4e-56fd28bfa737`
  used the prior eight-round limit and verified E2, E7 and S2. It executed 55
  actions from 74 model decisions; 19 decisions were invalid. Four actors hit
  the three-consecutive-invalid-decision cutoff. This limits exploration and
  needs attention before attributing lower recall solely to chance or savings.
- This update does not change validation or suppression policies. No new paid
  run is needed to apply the round limit. Historical eight-round measurements
  remain labelled as such.

---

# AI efficiency — latest implementation

Updated: 2026-11-01. The owner approved the written efficiency specification.

- Implemented bounded deterministic JSON context, two recent complete tool turns,
  relevant observation deduplication, stable role/tool prefixes, removal of
  redundant tool descriptions/reasoning, and atomic local snapshots each round.
- Added idle-read/invalid-decision stopping and scoped verified-finding hints.
  All HTTP actions remain live; concurrent writes and independent replay remain.
- Added actual cached-input accounting, optional cached pricing, conservative
  admission, rate-header/Retry-After feedback and console/run efficiency metrics.
  Independent judge accounting uses the same primitives with a separate budget.
- Ten focused checks pass. Final scripted integration verified all eight
  planted IDs, six comparison runs, telemetry, memory snapshots and stop. Both
  frontend builds, wheel/sdist, lint/format, compilation and startup from a
  clean committed copy passed.
- Offline prompt-payload comparison: 4.87% fewer bytes on 60 recorded three-round
  actor traces; 25.18% fewer bytes over an eight-round repeated-trace scenario.
  These are not measured tokenizer counts, billed savings or live recall results.
- Model, 10-agent population and round counts are retained. No Miko/Meko export,
  paid A/B experiment or new credential is required. Implementation commit:
  `392c0d9` on `codex/ai-efficiency` (local; not pushed). See `docs/ai-efficiency.md`.

---

# Phase 1 PRD completion — latest pass

Updated: 2026-10-31. User approved the written addendum, changing the population
from 20 to **10 agents** and replacing local Qwen with **Groq** from local `.env`.

- Implemented: React/Vite Bazaar storefront at `/bazaar/`; missing marketplace
  operations; ten sessions/six roles; measured objective scores; shared account
  observations; token/dollar caps and provider pacing; same-operation bursts;
  config-only CLI with owned targets/fixture/SQL binding; checkpointed benchmark
  resume; individual-action/actor replay reduction, causal checks and response-ID
  rebinding; full verification evidence; SSE, activity graph and human review UI;
  saved-result inspection and an explicitly labelled offline scripted fallback.
- E5 now requires a purchase, separate seller fulfilment and buyer review. E7
  records whether the sender was blocked at submission, eliminating false
  timestamp-ordering matches. The frozen catalog has 3 single-user/5 emergent IDs.
- Direct checks: all eight cases pass SQLite/Postgres; fixed race paths pass;
  six scripted benchmark runs pass with correct one-actor versus two-actor
  attribution. Dollar/usage/cancellation/ID-binding/review-hash checks pass.
- Real Groq: connection/tool preflight passed; a development run found E1/E7.
  An early held-out comparison was stopped for an oracle correction; a later
  comparison completed one baseline then failed on Groq HTTP400 without usage.
  These are retained as partial evidence, never scored as complete benchmarks.
- Groq compatibility now uses documented provider validation settings while
  retaining strict local tool/argument validation. A token bucket refunds known
  unused reservations. The six-run, three-round Groq comparison completed. E1/E2/E7 were independently
  replay-verified; the judge assessed every candidate, and the owner explicitly
  accepted the E7 moderation-bypass spot-check. **The approved core gate passed.**
  Completed exploration used 109,096 tokens (~$0.02017 estimated); judging used
  5,361 tokens (~$0.00117). Results: `docs/results/phase1-groq-summary.json`.
- Marketplace browser purchase/coupon/checkout/fulfilment passed. The locked environment and wheel/sdist build pass with storefront assets
  included and credentials/node_modules excluded. The two-minute captured-state fallback is in `docs/demo/phase1-fallback.mp4`;
  source labels distinguish manual, scripted and real Groq sections. The latest teammate React dashboard is merged alongside the full run console;
  its event and finding field mappings are compatible with the canonical API.
  Merged verification passed: six scripted comparison runs, all eight planted
  cases, cooperative stop, clean-copy startup, both frontend builds, locked
  Python setup, lint/format/compilation and package asset checks. `main` is the
  supported pull/run branch for this delivery. Further edge-case work is deferred
  per owner request.
- Docker daemon unavailable; native execution is the verified path. No Meko
  handoff export was performed. See `docs/phase1.md` for current instructions.

---

# SWARM progress

Updated: 2026-10-31 (Asia/Kolkata)

## Earlier Phase 1 completion work — historical

- Branch: `codex/phase1-completion`, starting from Dev1 `75a312d`.
- Status: implementation integrated and directly checked; **Phase 1 acceptance
  is not yet complete** because the real model provider/AI benchmark is pending.
- User approved the design and written spec, then authorized changing planted
  scenarios to match the PRD rather than misclassifying single-user failures.
- Delivered: seeded-user runtime identities; fixed model-controlled identity
  fields; stable real tool IDs; canonical Finding ingestion; valid SSE;
  correlated sanitized exception capture and Python response checks; owned
  disposable live/replay targets; atomic seeded resets; full SQL/log replay
  hooks; live round timeline, findings, usage/cost, stop and comparison console;
  complete model/fixture provenance gate and independent evaluator LLM matching.
- Real config includes six roles across eight sessions, with extra sessions for
  shared-account races. E2 and E4 now reject sequential duplicates and expose
  check/write races only under overlap. E1/E2/E4/E7 are interaction-dependent;
  same-owner E5 remains independently single-user in the seeded fixture.
- Direct evidence: all eight bug paths independently replay-verified on SQLite
  and on a temporary Postgres16 cluster (stopped afterward). Seeded startup,
  fixed arguments, wire findings, exception correlation, telemetry and SSE pass.
- Fixed flag evidence: v2 prevents overselling and coupon duplication; the
  payout override prevents double payment; sequential coupon reuse returns409.
- Full console check: concurrent scripted provider run, six measured fixture
  callbacks across held-out seeds, report/event exports, stop and overlapping-run
  rejection passed. The fixture produced three verified emergent IDs but its
  gate correctly remained incomplete, requiring real-model evidence.
- Judge/gate checks: fixture provenance, missing judge and judge disagreement
  cannot pass acceptance; evaluator usage is accounted separately and expected
  oracle IDs are withheld from its matching prompt. No real judge call yet.
- Browser reviewed activity/budget/comparison views. Lint, formatting, Python
  compilation, JS syntax and Git whitespace pass. Native package build passed,
  including the dashboard assets, YAML configuration and Bazaar fixtures. No
  new test suite added.
- Local evidence: `artifacts/phase1-check/` and
  `artifacts/phase1-console-check/`. See `docs/phase1.md` and
  `docs/dev1-context.md`. Provider keys are not included in Git or these reports.
- Nothing from this branch has been pushed to main. The user requested no
  publication without explicit approval. No Meko handoff sync was performed.

## Team context update

- Dev2 reports that Meko MCP is unavailable in his client. The root cause is
  not diagnosed; his client details and redacted error are still needed.
- GitHub fallback is documented in `docs/team-context.md`. Dev2 can commit
  implementation context in `docs/handoffs/dev2.md` on his own feature branch.
- Dev2 implementation is now present: teammate commits `42d285a` and `59055b1`
  were pulled without conflicts. `docs/handoffs/dev2.md` records the inspected
  source and the integration work completed in this workspace.
- A connected agent can explicitly copy committed handoffs into Meko with the
  original author, source branch and exact SHA. No automatic sync is installed.
- Dev3 maintains this overall progress summary; developer-owned handoffs reduce
  conflicting edits to the shared progress file.

## Dev3 — detection and replay feature

- Working branch: `dev3/detection-verification`.
- Status: complete, directly verified, merged and pushed to GitHub `main`.
- Implemented: versioned event/finding/replay models, append-only SQLite and
  Postgres event stores, SQL invariant runner, error capture, finding builder,
  concurrent HTTP replay and oracle gate, reports, benchmark metrics and local memory.
- Documentation: `docs/dev3-integration.md`; public schemas: `docs/contracts/`.
- User workflow: complete a feature, check it directly, then merge/push to main;
  do not write a test suite. Maintain this file and a Meko handoff.

## Dev2 + Dev3 integration completion

- Source: local main fast-forwarded from `3df1bee` to teammate merge `59055b1`.
  There were no Git merge conflicts. Functional incompatibilities were found
  and repaired instead of treating a clean Git merge as proof of compatibility.
- Integration branch: `codex/dev2-dev3-integration`.
- Teammate M1/M2 delivered the single-agent loop, OpenAPI tools and mock Bazaar.
  The old JSONL logger lacked Dev3 Requests, sequences and full response hashes;
  transport errors were incorrectly represented as HTTP 503s. The dependency
  lockfile also omitted teammate dependencies. These issues are corrected.
- Completed runtime: async round coordinator, barrier bursts, shared/per-actor
  token budgets, per-actor decision limits, cooperative kill switch, seeds,
  isolated baseline, six role objectives, config/CLI and benchmark callback.
- Completed bridge: validated Dev3 events, completed-window SQL/error detection,
  independent replay pipeline, reports and optional local actor/finding memory.
- Dev3 v1 public contracts are unchanged. See `docs/dev2-integration.md` for
  usage, hook contracts, limits, checks and remaining Dev1 inputs.

### New direct checks

- Actual teammate mock: two authenticated buyers each completed three actions;
  six Events persisted and three concurrent replay steps were reconstructed.
- M1-style single-agent flow and the config-based CLI completed successfully.
- Separate controlled live/replay targets: two concurrent HTTP actions caused
  an oversell; SQL detection and replay verified one emergent fixture finding.
- Six measured fixture runs completed across seeds 11/22/33. Isolated runs reset
  before every actor (nine total live resets); only swarm reproduced the bug.
  JSON, CSV and PNG benchmark exports were generated.
- Tool allowlists, multiple-call rejection, JSON fallback, missing-usage abort,
  shared/per-actor admission, per-actor step limits, cooperative kill and full
  rolling-summary token accounting passed. Transport errors remained transport
  findings. Local memory isolated actors and saved the verified fixture finding.
- Checks used a deterministic local model-provider fixture. No paid model API
  was used; this is not evidence of live-model discovery or Bazaar recall.
- Evidence: `artifacts/dev2-dev3-integration/check-results.json` and report/
  benchmark outputs (local and ignored by Git).
- Ruff lint/format, compilation, M2 dynamic-tool acceptance, Dev3 schemas and
  locked dependency installation passed. Inherited path parameters, encoded
  values, header/query capture and nested body constraints also passed.

## Earlier Dev3 direct checks

- Python 3.11 imports: httpx, Pydantic and psycopg work.
- Python source compilation: passed before final integration check.
- Real HTTP + Postgres 16: passed. Two independent buyer HTTP requests triggered
  the controlled oversell; the invariant found it and concurrent replay verified it.
- Postgres event store: two event records survived target resets; SQLite and JSONL
  export/read persisted the same run.
- JSON and Markdown reports: generated with one verified finding.
- Local memory: project isolation and recall worked; repeated checks reported
  `still_failing`, then `fixed`, then `regressed` as the fixture changed.
- Benchmark utility: completed two conditions across three held-out seeds and
  exported six measured fixture runs as JSON/CSV. This is not a Bazaar benchmark.
- Read-only SQL oracle connection: rejected an attempted write.
- Unavailable replay oracle: remained `inconclusive`, without claiming a fix.
- JSON Schema exports: generated successfully for Event, Finding, ReplayPlan and
  VerificationResult.
- Lint, formatting and Python compilation: passed.
- Optional chart export: generated a valid PNG from the measured fixture runs.
- Direct-check artifacts: `artifacts/dev3-smoke/` (local, ignored by Git).
- Docker: allowed, but the local Docker daemon is not running. A disposable
  local Postgres 16 instance is used instead; no existing server is changed.

## Dev1 handoff

Supply Bazaar's actual OpenAPI spec, invariant SQL, frozen planted-bug manifest,
stable seeded fixtures and a separate disposable verifier target/reset callback.
Consume `Finding.model_dump(mode="json")` for the dashboard. Details and examples
are in `docs/dev3-integration.md`.

## Dev2 handoff

The runtime now emits Dev3 Events with preallocated unique sequences and
contiguous distinct-actor bursts through synchronous stores in worker threads.
The isolated/swarm callback and detection/replay bridge are implemented.
Confirm real Bazaar authentication/reset conventions with Dev1, bind all six
roles to the real operation IDs, and run the selected live model. The product
Meko MemoryStore adapter remains deferred until the real core-demo gate.

## Shared integration and known limits

- Agree contract changes with affected owners. Coordinate root packaging and
  lockfile changes instead of replacing teammates' files.
- Initial finding labels reflect actors in the supplied causal window; verify
  necessary interactions before claiming an emergent bug.
- Race replay preserves simultaneous action intent, not guaranteed DB scheduling.
- Explicitly allow changed response statuses for legitimate API fixes.
- Dynamic response-ID bindings are not implemented; fixtures need stable IDs.
- Controlled fixture checks are not Bazaar detection-rate/benchmark results.
- Live dashboard/SSE and real Bazaar remain Dev1 deliverables. The runtime is
  implemented and directly checked against the teammate mock and controlled
  fixtures; its real Bazaar/live-model integration is still outstanding.

## Earlier Dev3 delivery

- Implementation commit: `50c9789`.
- Verified feature merge published to main: `d69ddb5`.
- Both `main` and `dev3/detection-verification` were pushed without force.
- The temporary verification Postgres instance was stopped after the checks.

The original Dev3 feature was developed on `dev3/detection-verification`. The
new integration completion is on `codex/dev2-dev3-integration`; publication is
recorded after its direct checks pass. No force push is used.
See [main history](https://github.com/ParthGupta1304/SWARM/commits/main) for the
delivery commit; the exact commit and handoff are also recorded in Meko.
