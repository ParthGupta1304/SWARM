# Bazaar Phase 1 integration handoff

Dev1 source commits through `75a312d` supplied models, routes, eight flags,
fixtures, SQL invariants and OpenAPI. Phase 1 integration continues on
`codex/phase1-completion` with the owner's approved design and authorization to
correct planted scenarios to match the PRD. See `docs/phase1.md` for execution,
independently reviewed classes, actual check evidence and pending AI acceptance.

## Runtime contract

Stable business operation IDs include list_items, add_to_cart, checkout,
apply_coupon, request_refund, open_dispute, block_user, ask_question and
create_review. list_orders exposes real order IDs to owner sessions. Model
schemas exclude health/flags, findings, telemetry and evaluator endpoints.

Bazaar uses seeded users, not mock /register and /login. Persona configuration
sets seeded_user_id and fixed_arguments; the runtime validates the seeded user
and removes those fixed fields from model control. Synthetic owner keys connect
the seller and sock-puppet fixture accounts. This is a local vulnerable target,
not a production authentication implementation.

POST /api/findings accepts the canonical Dev3 Finding payload, preserving it in
wire_findings; legacy FindingRequest remains supported. GET /api/findings serves
stored findings. Runtime aggregates are persisted through /api/runs/telemetry;
/api/runs and correctly framed /api/events/stream feed the console. Sanitized
request_errors metadata is correlated through the X-Swarm-Action header.

## Reset and independent replay

swarm.targets creates owned target processes, separate databases and ports.
seed_database atomically resets business fixtures and exception/activity logs;
reports/telemetry and the independent runtime EventStore survive. The seed
changes item prices reproducibly while fixture identities remain stable.
It resets only an explicitly disposable database; it is not an app HTTP route.
Existing user-managed databases are not migrated or reset by the local launcher.

swarm.bazaar.make_hooks connects live SQL checks and Python/log checks to a
separate HTTPReplayTarget and original-failure oracles. It also publishes
minimized findings. Blocking DB operations and exception logging run in worker
threads so a race or a log write cannot hold the async request loop hostage.
The same checks passed on SQLite/WAL and a temporary Postgres16 cluster.

## Deliberate bug behavior

Sequential duplicate coupon redemption and duplicate compensation return409.
Their v1 defects require overlapping checks from multiple sessions. v2 locks
coupon/inventory state; an individual double_payout override locks the order.
SQLite uses an immediate transaction for fixed paths; Postgres uses row locks.
All delayed write paths commit before releasing their locks.

E5 checks owner equality as well as account identity when fixed. Its seeded
same-owner review is single-actor reproducible, so the evaluator does not count
it toward the three-emergent-bug gate. The exact frozen catalog is in
configs/bazaar-truth.json and is withheld from exploring model prompts.

## Still pending

Configure a real provider locally, tune on development seed1, then run both
conditions on held-out seeds11/22/33. The gate requires three distinct verified
emergent bugs plus independent model matching of the manually reviewed catalog.
Scripted checks are not sufficient. Product Meko memory is Phase2. No push to
main is authorized yet.
