# Phase 1 completion design

User approved the design on 2026-10-31. Starting point: Dev1 commit 75a312d,
Dev2/Dev3 integration 949271f. Work on codex/phase1-completion; do not push main.

## Completion criteria

Deliver the PRD's Bazaar app, six configurable personas, API tool loop,
concurrent bursts, budgets, durable events, SQL/Python/log detectors, separate
reset/replay verification, ranked reports, two-condition/three-seed benchmark,
and local live dashboard with findings, agent activity, token/cost meter,
stopping control and baseline/swarm comparison. The completion gate additionally
requires three distinct verified emergent Bazaar bugs discovered by a real
model and a real measured held-out benchmark. Scripted validation is explicitly
labelled and cannot satisfy that gate. Product Meko memory and other stretch
features remain Phase 2, not dependencies of Phase 1.

## Architecture

Keep the Python contracts and services. Extend persona configuration with
seeded user identity and fixed identity arguments; the runtime can select either
existing register/login setup or seeded Bazaar users. Restrict model tools to
business operations, excluding evaluator, settings, reset and findings APIs.
Normalize real operation IDs through the supplied spec and explicit config.
Keep user identity arguments fixed per actor; objectives describe intentions,
not planted IDs or evaluator ground truth.

Provide reusable deterministic seed/reset functions supporting only explicitly
configured disposable targets. A local service launcher owns separate live and
verifier databases, processes and ports, plus the event store. Reset callbacks
operate on those owned databases; they never reset a user-provided production
URL or event database. Frozen truth contains independently reviewed bug classes.
Use the same seed/model/aggregate budget for isolated and swarm conditions;
isolated resets once per actor and does not share actor memory. Persist raw
measured runs and report skipped or unavailable oracles as inconclusive.

Use SQL invariants for business state and Python checks for response correctness.
Capture sanitized application exception metadata correlated with observed
requests. Never put credentials or raw tracebacks in shared memory. Verify
server errors with their original failure oracle. Initial actor-derived
emergent labels need independent causal/manifest review; mappings alone cannot
prove interaction. Preserve causal setup and stable IDs in reproducers.

Accept the canonical Dev3 Finding payload in Bazaar via a validated adapter;
store full payloads while preserving legacy readers. Correct SSE framing and
add run telemetry events that contain actor summaries, aggregate usage and
cost. The dashboard reads persisted state and events, offers an explicit stop
button for the owned run and displays errors/empty states. Server-side model
calls keep provider credentials out of browser code. Controls operate only on
the local coordinator; no secret-bearing config is returned to the browser.

## Dashboard design

Local operational console, served by the Python stack without a second build
service. Cool white #f5f8fc background, ink #142338, blue #2765cf, slate #64758b,
warning amber #b87912 and failure red #b73b49. System sans headings/body and
monospace for requests and budgets. The signature is a round timeline showing
simultaneous actor actions side by side. Activity and verified findings are
primary; benchmark comparison is a separate clear view. Responsive layout,
keyboard focus, reduced-motion support, textContent rendering for untrusted
content, readable empty/loading/error states. No planted answers in agent views.

## Error handling and verification

Fail closed on unknown model usage, invalid targets, detector errors and budget
accounting problems. Stop cooperatively after in-flight operations finish.
Streaming reconnects resume by event cursor. Dashboard reports lost connections
and never displays fabricated live statistics. Replay remains independent of
exploration state and does not call the model.

Direct checks, no new written test suite: run the real Bazaar on independent
SQLite and Postgres fixtures, check all planted paths, seeded actors, canonical
findings, valid SSE, live telemetry and stopping, real invariant detection and
replay, six-condition/seed fixture callback runs, export reports, inspect the
dashboard in a browser, then run the selected real provider and evaluate the
Phase 1 gate. Maintain progress and actual evidence, not claimed results.

## Implementation plan

1. Repair seeded actor/config and findings/SSE integration.
2. Add owned Bazaar target reset/oracle hooks and frozen evaluation inputs.
3. Complete detectors, telemetry and the local dashboard.
4. Add run/benchmark launch commands and repeatable environment instructions.
5. Directly verify the assembled application; fix observed failures.
6. Run real-model discovery/benchmark when a provider is configured. Record the
   gate as incomplete until the required measured evidence exists.
