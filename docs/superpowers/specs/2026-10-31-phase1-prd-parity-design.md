# Phase 1 PRD completion addendum

Status: proposed for user review, 2026-10-31. This extends the previously approved
Phase 1 design and resolves the gaps in `docs/prd-audit-2026-10-31.md`.

## Scope and approach

Complete Phase 1 P0/P1 requirements and its demo delivery. Phase 2 and Phase 1
stretch features remain outside this implementation. Preserve the existing
Python contracts, async runtime, independent replay environment and OpenAPI
adapter. Keep the user's Qwen/OpenAI-compatible provider choice; do not spend
the configured paid API key to substitute for friend-machine Qwen testing.

Recommended approach: add a React/Vite Bazaar storefront built into static
assets served by the current Python launcher; extend existing modules rather
than replacing them. This follows the PRD frontend choice while retaining one
local command and origin for the finished demo.

Alternative: build the storefront entirely in plain browser JavaScript, matching
the existing console. That reduces tooling, but departs from the PRD stack and
makes complex cart, orders and seller views harder to maintain. A separate
always-running frontend service is another option, but introduces a second
startup and cross-origin configuration without improving this local demo.

## 1. Visible Bazaar marketplace

Expose the storefront at `/bazaar/` and retain the Swarmtest console at `/`.
Provide navigation between them. All storefront actions reach the same live
Bazaar target that agents explore; verifier targets stay separate and hidden
from storefront controls. Forward a defined allowlist of marketplace API routes
through the console origin, preserving API status codes and excluding arbitrary
upstream URLs, evaluator APIs and provider secrets.

The marketplace includes product browsing/search, item details and questions,
account selection/registration for synthetic demo users, carts and coupons,
checkout, order history, refunds/disputes, reviews, seller listings/fulfilment,
direct messages, blocking and benign listing reports. Complete the missing API
operations as OpenAPI-described business tools. Show actual server results,
stock, totals and useful error messages; no simulated successful checkout.

This is a disposable demo application, not production authentication or hosting.
Explicit synthetic account switching supports manual multi-user demonstrations.
Normal controls do not disclose planted IDs or oracle answers to agents.

Use a recognizable marketplace layout: restrained blue/white surfaces, dark
ink text, a prominent Bazaar wordmark, product imagery/illustrations, search,
stock labels and a persistent cart affordance. Keep the testing console's round
timeline as its signature. Responsive layouts, keyboard focus, accessible
labels, reduced motion, escaped user content and clear empty/error states are
required. Product artwork should be local and work without an external CDN.

## 2. Twenty actors and measurable objectives

Ship the PRD's 20-agent population: six casual buyers, four bargain hunters,
four impatient clickers, two fraudsters, two sock-puppet actors and two trolls.
Seed sufficient synthetic users while preserving existing fixture IDs where
practical. Shared-account sessions are explicit for coupon/refund races; they
must not be described as distinct account owners. Every actor has a unique ID,
fixed permitted account identity, step/token budget and tool allowlist.

Compute role scores from observed business results/state: completed purchases
for buyers; realized savings for bargain hunters; successful purchases under
retries for impatient buyers; compensation beyond purchase value for fraud;
same-owner purchase/reputation outcomes for sock puppets; successful contact
after blocking for trolls. Display score units and explanations. Scores guide
objectives and never replace detector/replay evidence.

Retain round barriers and add an explicit same-operation burst selection path
for eligible pending actions. Bound model-call concurrency and request rate
through config; preserve fairness and equal aggregate exploration budgets in
the isolated/swarm comparison. Add a monetary admission cap using conservative
reserved input/output cost alongside token reservations. Local inference with
zero configured prices incurs zero modeled dollars. Stop cooperatively and
retain all known usage if calls fail or usage is uncertain.

## 3. Faithful planted cases and causal verification

Keep the eight frozen PRD IDs: S1/S2/S4 and E1/E2/E4/E5/E7. Preserve E1/E2/E4
interaction-dependent races and E7 block bypass. Restore a genuinely interacting
E5 flow: a different same-owner account purchases an item, the seller fulfils
it, and the purchasing account reviews the completed purchase. A direct
same-account seller review is rejected; review eligibility requires a fulfilled
purchase. In v1 the same-owner check is missing, permitting the sock account to
inflate reputation. Disabling the E5 flag rejects that same-owner purchase
review. Fixed actor identities require separate seller and buyer actions; a
seeded single-actor shortcut must not satisfy its oracle.

Make the invariant describe the actual completed self-dealing flow. Freeze the
resulting 3-single/5-emergent catalog before held-out model evaluation. Verify
every planted path and each fixed flag directly on owned targets.

Extend replay reduction to remove individual unnecessary actions inside
concurrent steps, as well as whole steps, with reset/oracle checks for each
candidate. Preserve necessary overlapping actions and serial setup. Derive
attribution from reduced causal actions and counterfactual actor removal; use
unverified/inconclusive labels when causal necessity cannot be established.
Never infer emergent status merely from the number of active agents in a round.

Represent response-created resource references in replay so IDs can be rebound
to replay responses where the fixture cannot guarantee stable IDs. Preserve
backward compatibility for existing literal requests. Persist reduction and
verification attempts for the evidence presentation; do not promise identical
OS/database scheduling for races.

## 4. CLI, reports, provenance and review

Provide root `swarmtest.yaml` and built-in `swarmtest run --config ...`,
`swarmtest benchmark --config ...` and demo/serve workflows. Config binds the
owned target, fixture, invariant file, personas, provider, budgets and seed
without requiring a customer Python hook factory. Existing custom hook support
remains available. Load `.env` server-side and use a harmless local-provider
placeholder when no credential is needed. Reject unsupported reset/target
combinations rather than silently running with detection disabled.

Keep ordinary reports separate from evaluator-only planted mappings. Benchmark
output includes every candidate, independently assessed correctness, verified
status, oracle/judge mapping, timing and actual usage. Assess candidates rather
than counting any known assigned bug ID as a true positive. Report precision
as unavailable until the required independent correctness labels exist.

Evaluate all relevant candidates, not just one example per known ID. Persist
judge decisions and a manual spot-check record tied to finding/evidence IDs.
Expose a local review action or command that records the actual reviewer's
decisions; do not auto-approve manual review. Record config/catalog hashes,
model/provider metadata, run IDs, seeds, population, budgets and evidence source.
Scripted fixtures remain conspicuously labelled. A source label alone is not
presented as proof of a real provider run.

Require six completed runs, equal model/budget, three held-out seeds, at least
three causally verified emergent IDs, 20-actor population, independent matching
and manual review for the real-model benchmark gate. Maintain a separate full
Phase 1 checklist for non-benchmark deliverables. Report mean/range, recall
splits, assessed precision, repeatability, first/all-find timing, tokens,
dollars and cost per verified bug without selecting only favorable runs.

## 5. Demo and acceptance

Connect the live activity/findings view through SSE with reconnection/cursors.
Show actor interactions, score explanations and replay/reduction progress in
the console. Retain baseline/swarm comparison and make benchmark/review errors
actionable. Persist completed comparison output so restarting the console does
not erase the visible last benchmark.

Deliver a two-minute demo script, a repeatable local demonstration command and
a recorded fallback. A recording made with scripted actions must say so and
cannot substitute for real AI discovery evidence. Document native and Docker
startup and exact Qwen environment settings for the friend's machine. Make
the single-launcher path openable and verify it in a browser at desktop/mobile
sizes, including actual marketplace interactions.

Direct checks, consistent with the existing project workflow: all eight bug
paths and fixed variants on SQLite and Postgres; causal single-user versus
multi-user reduction; dynamic replay references; 20-actor concurrency and
scores; budgets/rate/stop; config-only CLI; six-run fixture benchmark; review
and provenance negative controls; storefront flows; packaged assets and
container startup when the daemon is available. Add no broad new test suite.

The friend's real Qwen runs remain the empirical acceptance step. Complete the
software and handoff here; record real-model acceptance as pending until those
runs and manual review actually succeed. Neither a local scripted recording nor
an API connection preflight satisfies the PRD's discovery/benchmark gate.

## Implementation sequence and review tasks

1. Project context: complete; current implementation and actual PRD audited.
2. Visual companion: not needed for the current architecture/scope decision;
   offer only if a later visual choice needs comparison.
3. Clarifications: existing instructions settle Phase 1 scope, Qwen testing on
   the friend's machine, local-only development handoff and direct-check style.
4. Approaches and design: proposed above, awaiting user review.
5. Spec self-review: complete; no placeholders; implementation versus empirical
   acceptance explicitly separated; Phase 2 excluded.
6. Written spec approval: pending. Begin implementation after approval.
7. Implement in bounded steps: causal/report correctness; backend/seed/20-actor
   objectives and budgets; built-in CLI/benchmark review; marketplace; live
   evidence presentation; integration checks, recording and handoff.
8. Update progress/audit with actual evidence and remaining Qwen acceptance;
   publish verified implementation using the user's existing main-push approval
   after integration checks pass, preserving teammate history.

The brainstorming skill references `writing-plans`; no such installed skill
was found in the available local skill roots/plugin cache. The implementation
sequence above supplies the concrete plan without depending on that missing
helper. The available brainstorming written-spec review requirement still
applies.
