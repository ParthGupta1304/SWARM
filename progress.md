# SWARM progress

Updated: 2026-10-31 (Asia/Kolkata)

## Dev3 — detection and replay feature

- Working branch: `dev3/detection-verification`.
- Status: feature complete and directly verified; delivery target is `main`.
- Implemented: versioned event/finding/replay models, append-only SQLite and
  Postgres event stores, SQL invariant runner, error capture, finding builder,
  concurrent HTTP replay and oracle gate, reports, benchmark metrics and local memory.
- Documentation: `docs/dev3-integration.md`; public schemas: `docs/contracts/`.
- User workflow: complete a feature, check it directly, then merge/push to main;
  do not write a test suite. Maintain this file and a Meko handoff.

## Checks

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

Emit `Event` records with unique per-run sequence numbers and contiguous,
distinct-actor concurrency groups. Use `asyncio.to_thread` for synchronous store
calls. Supply actor credentials at runtime, not in stored events. Implement the
isolated/swarm benchmark callback and the later Meko MemoryStore adapter.

## Shared integration and known limits

- Agree contract changes with affected owners. Coordinate root packaging and
  lockfile changes instead of replacing teammates' files.
- Initial finding labels reflect actors in the supplied causal window; verify
  necessary interactions before claiming an emergent bug.
- Race replay preserves simultaneous action intent, not guaranteed DB scheduling.
- Explicitly allow changed response statuses for legitimate API fixes.
- Dynamic response-ID bindings are not implemented; fixtures need stable IDs.
- Controlled fixture checks are not Bazaar detection-rate/benchmark results.
- Live dashboard/SSE, Bazaar and the agent runtime remain Dev1/Dev2 deliverables.

## Delivery

The feature is developed on `dev3/detection-verification` and published to
`main` only after the direct checks above pass. No force push is used.
See [main history](https://github.com/ParthGupta1304/SWARM/commits/main) for the
delivery commit; the exact commit and handoff are also recorded in Meko.
