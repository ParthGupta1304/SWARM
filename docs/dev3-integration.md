# Dev3 integration and handoff

## Implemented scope

- `detect/contracts.py`: version 1 Event, Request, Finding and Replay wire models.
- `detect/store.py`: append-only SQLite/Postgres event stores and JSONL interchange.
- `detect/invariants.py`: read-only SQL invariant evaluation and SQL file parser.
- `detect/findings.py`: invariant findings, 5xx/transport capture and replay construction.
- `verify/replay.py`: isolated actor sessions, seeded resets, concurrency groups,
  repeated replay, oracle-gated verification and whole-step reproducer reduction.
- `detect/report.py`: severity-ranked JSON and Markdown reports.
- `bench/metrics.py`: two-condition/three-seed harness, metrics, JSON/CSV and recall chart.
- `memory/store.py`: local verified-finding and agent memory, traces and regression rechecks.

## Dev2: event integration

```python
from detect import Event, PostgresEventStore, Request

store = PostgresEventStore(event_database_dsn)
store.append(
    Event(
        run_id="run-001",
        seed=1,
        round=0,
        sequence=0,
        agent_id="buyer-01",
        role="casual_buyer",
        tool="checkout",
        request=Request(method="POST", path="/checkout", json_body={"item_id": 1}),
        response_status=200,
        tokens_used=125,
        latency_ms=42,
        concurrency_group="round-0-checkout-1",
    )
)
```

`Event.sequence` is a unique, zero-based, increasing integer per run. Allocate
sequence numbers before dispatching a burst; completion order may differ.
All members of a concurrency group occupy a contiguous sequence range, belong
to the same round and use distinct actor IDs. Never reuse a group ID in a run.
The append API is synchronous: use `await asyncio.to_thread(store.append, event)`
from the async runtime to avoid blocking the agent event loop.

The caller supplies each event's UUID or accepts the generated one. Repeated
event IDs or `(run_id, sequence)` pairs raise `DuplicateEventError`; append
never replaces a record. Resume by reading `events(run_id, after_sequence=N)`.
Postgres storage uses `swarmtest_events.events`; no Bazaar schema is changed.
`SQLiteEventStore(path)` offers the same append/read interface for local runs.

Request paths are origin-relative and parameters live in `Request.query`.
Store the request inputs needed for replay, plus response hashes as evidence.
Do not record Authorization/Cookie/API-key headers; the schema rejects those.
Redact any sensitive values in bodies or custom headers before logging and
replace them from fixture/auth bindings when needed. Do not upload raw events
or credentials to Meko. The caller remains responsible for app-specific redaction.

## Dev1: SQL invariant contract

An invariant query returns **one or more violation rows** when broken and zero
rows when healthy. Returning `SELECT count(*)` always produces a row, so filter
the aggregation with `HAVING` or select offending records instead.

```sql
-- invariant: inventory | high | Inventory cannot be negative
SELECT id, stock FROM inventory WHERE stock < 0;

-- invariant: refunds | critical | Refund must not exceed payment
SELECT order_id, SUM(amount) AS refunded
FROM refunds
GROUP BY order_id
HAVING SUM(amount) > MAX(payment_amount);
```

These are format examples: Dev1 supplies queries for the real Bazaar schema.
Load a file with `load_invariants(path)`, then use
`SQLInvariantRunner.postgres(readonly_dsn)` or `.sqlite(path)`. Query errors
raise `InvariantExecutionError`; they never count as a healthy result.
The generic connection factory must return a fresh read-only DB-API connection.
Evidence is capped at 100 rows per check; order SQL results if stable evidence
ordering matters. Use a least-privilege database role in integration.

## Detection and replay

```python
from detect.findings import finding_from_violation
from detect.invariants import SQLInvariantRunner
from verify import HTTPReplayTarget, ReplayVerifier, apply_verification

violation = SQLInvariantRunner.postgres(target_readonly_dsn).check(invariant)
if violation is not None:
    finding = finding_from_violation(violation, causal_events)
    target = HTTPReplayTarget(
        verifier_base_url,
        reset_snapshot=reset_disposable_snapshot,  # async (seed: int) -> None
        check_oracle=check_original_oracle,  # async (oracle_id, results) -> bool
        agent_headers=fixture_auth_headers,  # credentials supplied at runtime
    )
    try:
        result = await ReplayVerifier(target, attempts=3).verify(finding)
        finding = apply_verification(finding, result)
    finally:
        await target.aclose()
```

The reset callback restores the verifier's **own disposable target**, seeded
accounts, stable object IDs and feature flags. It must never reset the live
swarm target or event store. Fresh per-agent HTTP clients prevent cookie
sharing and are cleared between attempts. Redirects are not followed.

Actions in a step start at an asyncio barrier; each step finishes before the
next begins. This preserves concurrency intent, not a guaranteed database
interleaving. Run repeated attempts and report measured reproducibility. A
single verifier serializes resets; separate verifier instances need separate
targets or a caller-owned shared lock. Invariants are evaluated on completed
event windows or rounds so partial transactions are not mistaken for violations.

The oracle receives results for the replayed actions and must return whether
the **original failure** occurred. It must raise on inability to evaluate.
For 5xx findings, compare the observed response to the original error. SQL
business findings require checking the actual application state. Transport
failures require a dedicated deterministic oracle; they remain unverified if
the executor cannot complete.

Recorded response statuses are enforced. If a legitimate fix changes a response
(for example 200 to 409), set that ReplayAction's `acceptable_statuses=[409]`
after agreeing the API contract. Unexpected auth/404/setup failures otherwise
remain inconclusive instead of producing a false claim that the bug is fixed.

Initial findings preserve the caller's supplied causal window. Include setup
actions and all dependencies; Dev3 cannot infer missing actions from a hash.
The initial single-user/emergent label is inferred from actors in that window;
it is not proof that every actor was necessary. Review the reduced reproducer
or frozen benchmark ground truth before claiming a failure requires interaction.
`await verifier.minimize(finding)` removes independently dispensable whole
steps while keeping concurrency groups intact. It is greedy reduction, not a
claim of global minimality. Newly created resource IDs must be stable in seeded
fixtures; dynamic response-to-request bindings are not implemented yet.

## Dev1: dashboard and reports

`Finding.model_dump(mode="json")` is the dashboard payload. A finding contains
its run ID, severity, event IDs, involved actors, replay plan, oracle, evidence,
verification flag and optional benchmark bug ID. Only `apply_verification`
should set the verification flag after replay. Benchmark-only planted IDs must
not leak into agent prompts or runtime tools. JSON Schema exports are in
`docs/contracts/`; regenerate them from the authoritative Pydantic models.

`write_report(findings, output_directory)` writes `report.json` and `report.md`.
Unverified findings are explicitly labelled and are not scored as verified finds.
Live SSE delivery belongs to Dev1/Dev2; this module does not start an API server.

## Benchmark interface

Dev2 supplies `run_condition(condition, seed, token_budget) -> BenchmarkRun` to
`run_benchmark(...)`. The callback must reset its target, run the requested
`isolated` or `swarm` condition, verify findings and return measured tokens,
cost, elapsed time and finding discovery times. It must ensure all LLM calls
respect the budget and the baseline isolates actors.

Use exactly three unique held-out seeds, distinct from `dev_seed`. Both
conditions must use the same model and token budget. `truth` maps frozen bug
IDs to `single-user` or `emergent`; the evaluator supplies independently reviewed
bug mappings. No LLM judge is implemented in this phase. Recall deduplicates bug
IDs; precision counts reports, with before/after verification values. Undefined
precision or missing discovery times are null, never invented. Summaries include
mean, min, max, measured-run count and per-bug repeatability. This harness cannot
prove baseline isolation or truthful cost reporting on behalf of the callback.

`write_benchmark(report, directory, chart=True)` exports JSON, per-run CSV and
a static recall chart. Install the `charts` extra for matplotlib.

## Memory and Run 2

`MemoryStore` defines `save_finding`, `recall_findings`, `save_agent_memory`,
`recall_agent_memory` and `record_trace`, all scoped to a project; actor memory
is additionally scoped by actor ID. `LocalMemoryStore(path)` stores data in
SQLite and only accepts verified findings as regression checks. Close stores
or use context managers.

Local `classify(project, finding, result, run_id=...)` records an append-only
check per finding/run: `still_failing`, `fixed`, `regressed` after a recorded fix,
or `inconclusive` on errors. A newly discovered bug is a new finding; it cannot
be called a regression without historical evidence of a passing check. A fixed
classification means not reproduced across the configured completed attempts,
not mathematical proof the race is absent. Errors do not erase a previous fix.
`recheck_saved_findings` performs local checks before new exploration.

Dev2's Phase 2 Meko adapter can implement the five-method MemoryStore interface.
The local history/recheck API is an extension and is not required of that adapter.
Raw event and replay evidence remain in our own database. Meko downtime must not
prevent Phase 1 from running.

## Dev2 integration update — 2026-10-31

The implemented runtime now emits these v1 Events and consumes the replay and
benchmark APIs without contract changes. See `docs/dev2-integration.md` for
`RunEvents`, `RunCoordinator`, `DetectionPipeline`, the CLI and actual direct
check evidence. The teammate mock and controlled race fixtures have been
checked; real Bazaar and live-model results remain pending.

## Pending real-target integration

1. Dev1 supplies the real Bazaar OpenAPI spec, SQL invariants, ground-truth bug
   manifest and seeded reset callback on a separate verifier target.
2. Bind the completed Dev2 runtime, event emitter and benchmark callback to
   Dev1's real fixtures and per-actor verifier credentials; confirm the real
   authentication convention and exercise all six roles with the live model.
3. Jointly confirm the v1 schemas and statuses accepted after fixes. Coordinate
   root packaging/lockfile changes through one integrator.
4. Run the real two-condition, three-seed benchmark and core gate of three
   verified emergent bugs before adding product Meko integration.

The direct smoke-check results validate Dev3's implementation only. They do not
establish detection rates, costs or successful bug discovery in Bazaar.
