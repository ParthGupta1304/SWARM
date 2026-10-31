# SWARM progress

Updated: 2026-10-31 (Asia/Kolkata)

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
