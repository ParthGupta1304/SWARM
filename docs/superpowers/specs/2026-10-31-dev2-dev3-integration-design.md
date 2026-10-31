# Dev2/Dev3 integration completion

Approved by the user on 2026-10-31: complete the missing runtime as well as repair
M1/M2 compatibility. Source inspected: teammate merge `59055b1` on main.

## Design

Preserve Dev3's v1 contracts. OpenAPIAdapter prepares one credential-free
Request for both execution and event persistence. Transport failures have no
HTTP status. A shared run context reserves sequence numbers before dispatch and
writes validated Event records to the existing SQLite/Postgres store. JSONL is
an export, using the same schema. Credentials are injected only for execution;
registration/login inputs are not persisted as replay actions.

Separate the agent's model decision from HTTP execution. The coordinator runs
one decision and action per active actor per round. Reserve a contiguous range
and unique group ID for each concurrent burst; use a barrier before dispatch.
An isolated condition resets the disposable target before each actor and never
shares actor state. The event store is independent of those resets.

Every model call, including summaries, consumes a shared budget. Reserve input
and output capacity before calls; refuse when insufficient, reconcile actual
provider usage, and stop on absent or impossible usage. Disable SDK retries to
avoid unaccounted extra calls. Record model tokens separately from event tokens
so invalid decisions and summaries are counted.

A benchmark callback supplies measured runtime/cost plus caller-owned target
reset, detection and verifier hooks. Detect after completed rounds; verify on a
separate target. Preserve unverified findings. Local memory remains available;
the product Meko adapter stays deferred until the real core-demo gate passes.

## Validation and boundaries

Use direct checks, not a written test suite. Exercise the real HTTP mock app
and a deterministic local model-provider fixture; validate events through
Dev3's reader, replay builder and replay verifier. Check concurrency groups,
actor isolation, token limits, failures, six benchmark runs and reports. These
checks establish integration behavior, not real LLM discovery or Bazaar recall.

Dev1 still supplies the actual Bazaar app, invariants, frozen ground truth,
stable fixtures, disposable verifier reset and dashboard. No mock implementation
is presented as completion of those deliverables.

## Implementation sequence

1. Repair OpenAPI request preparation and event persistence.
2. Split agent decisions/actions; validate tool scope and account for budgets.
3. Add round coordinator, configuration CLI and benchmark callback.
4. Run direct integration checks and fix observed failures.
5. Update progress, handoff and usage docs with actual evidence.
