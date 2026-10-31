# Dev2 implementation and integration handoff

- Updated: 2026-10-31 (Asia/Kolkata).
- Original implementation author: Dev2, source commits `42d285a`, `59055b1`.
- Integration author: Codex, explicitly authorized by the project owner to
  finish the missing runtime and check Dev2/Dev3 compatibility.
- Integration branch: `codex/dev2-dev3-integration`; exact delivery SHA is
  available in Git and recorded in the Meko handoff after commit.
- Status: M1/M2 integrated; runtime coordination and benchmark bridge completed
  and checked against mock/controlled HTTP targets. Real Bazaar/live-model
  integration remains dependent on Dev1's fixtures and selected provider.

## What Dev2 supplied

A single-agent loop with native tool calls/JSON fallback and rolling memory;
OpenAPI tools; M1/M2 example entry points; an in-memory mock app and example
spec. The teammate merge preserved Dev3's packages but had not replaced its
original JSONL logger with the actual v1 Event contract. It had no async
coordinator, barrier grouping, shared budget or benchmark callback.

## Integration completed

- `adapters/openapi.py`: shared request preparation, schema validation, actual
  path/query/header/body capture and transport errors with no fabricated status.
- `swarm/events.py`: RunEvents, reserved sequences, groups, canonical Events,
  durable store and optional JSONL. Credentials are injected only at execution.
- `swarm/agent.py`: decisions separated from execution, tool-scope enforcement,
  valid history, complete model-usage accounting and isolated account setup.
- `swarm/budget.py`: shared/per-actor reservation and actual usage reconciliation.
- `swarm/runtime.py`: concurrent rounds, baseline resets, actor limits, seeds,
  kill switch, optional local memory and measured benchmark callback.
- `swarm/pipeline.py`: completed-window detection and separate-target replay.
- `swarm/personas.py`: six PRD role objectives; real tool bindings are explicit.
- CLI/config: `swarm/cli.py`, `swarm/__main__.py`, `configs/mock.yaml`, `main.py`.
- Shared package metadata and `uv.lock` now install the actual dependencies.

## Compatibility and decisions

The authoritative Dev3 Event/Finding/Replay schemas are unchanged. All actors
in a run share one event context and one aggregate budget. Actor caps apply
in addition. Reserved sequence order is independent of HTTP completion order.
Blocking HTTP/store/model operations run in worker threads; round detection
waits for all event writes. Baseline resets never touch the event database.

Decision: integrate through existing Python contracts rather than introducing
a competing event schema or orchestration framework. Reason: preserve Dev3's
verified pipeline while completing Dev2's missing responsibilities. Trade-off:
threaded synchronous model/HTTP clients retain the teammate's provider approach;
barriers preserve action intent without promising deterministic DB scheduling.
Alternative considered: retain standalone M1/M2 and only document the gap.
Impact: Dev1 supplies the real callbacks and consumes the unchanged Finding JSON.

All model calls, invalid decisions and rolling summaries count toward budgets.
Missing usage and uncertain failed calls abort rather than invent measurements.
The conservative byte-based prompt admission assumes a byte-token provider and
can stop early; see the runtime guide for provider and billing limitations.
An unsupported OpenAPI body/serialization fails explicitly rather than silently
producing incomplete replay evidence. Auth setup remains a runtime prerequisite,
not stored credential-bearing actions.

## Actual direct checks

- Two buyers against the actual teammate mock completed browse/add/checkout.
- Six canonical events round-tripped through Dev3 JSONL and built three replay
  steps. Single-agent M1 flow, M2 dynamic-tool generation and config CLI worked.
- Separate live/verifier race fixtures reproduced and verified one controlled
  oversell; a verified finding was saved in local memory and reports exported.
- Six controlled benchmark runs completed over seeds 11/22/33, with nine resets
  enforcing isolated actor targets. Only the swarm reproduced the fixture bug.
- Shared/actor budgets, step caps, usage failure, tool scope, multiple calls,
  fallback parsing, summary accounting, transport errors and stopping checked.
- Reports, benchmark JSON/CSV/chart and result summaries are in the ignored
  `artifacts/dev2-dev3-integration/` directory.

The model responses in these checks came from a deterministic localhost
fixture, not a live LLM. No real Bazaar benchmark or three-bug core gate is
claimed. No written test suite was added, per the owner's established workflow.

## Remaining tasks

1. Dev1 supplies real Bazaar, OpenAPI, invariant SQL, stable fixtures and separate
   disposable verifier reset/oracles; confirm `/register`/`/login` token behavior.
2. Bind the six roles to those real operations and configure the actual provider.
   Check all role scenarios, which the small teammate mock does not implement.
3. Reproduce at least three verified emergent Bazaar bugs and run the real
   equal-budget, two-condition, three-held-out-seed benchmark.
4. Integrate dashboard/SSE with Dev1. Dynamic response-ID bindings and product
   Meko adapter remain deferred; shared development context already uses Meko.

Dev2's previously reported Meko client problem is still undiagnosed. This
handoff is attributed from inspected code and integration checks; it does not
invent a Dev2 report about his client, checks or decisions.
