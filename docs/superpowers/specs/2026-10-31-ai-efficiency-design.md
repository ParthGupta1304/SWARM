# AI efficiency improvements

Date: 2026-10-31
Status: Written specification awaiting owner review; implementation has not started.

## Request and chosen approach

The owner requested implementation of five techniques: reduced repeated context,
prompt caching, concurrency within capacity, avoiding unproductive repetition,
and using code instead of AI where practical.

Use deterministic local context management and provider-aware accounting in the
existing runtime. This directly reduces input and auxiliary calls while retaining
live marketplace execution and independent verification.

Alternatives considered: configuration-only reductions are simpler but leave
repeated histories intact; multiple models or an external memory service add
latency, integration work and experimental differences. They are deferred. The
latest request authorizes the five techniques above, not a Miko export. Retain
10 agents, eight interactive rounds and the existing three-round comparison.
The earlier proposed eight-agent/six-round change was discussion, not an
implementation approval. No provider/model changes or new API keys are needed.

## Context and prompts

- Introduce a focused context component used by AgentLoop. Store compact JSON
  facts locally: operation, arguments/resource IDs, HTTP status, selected result
  fields, changed observations and repeated-result counts.
- Keep two recent complete action/result turns plus bounded older facts. Cap
  the older-fact snapshot at 6 KiB and each model-visible tool result at 2 KiB,
  with explicit omission markers. Retain newest resource references first.
  Serialize stable JSON with deterministic field ordering and compact separators.
- Preserve IDs, status/error information and operationally useful quantities,
  prices, stock and order state when reducing responses. Unexpected shapes have
  a bounded, labelled fallback. Do not pretend omitted details were examined.
- Repeated identical observations are represented once with a count. Changed
  values replace stale facts. Account-local/private observation boundaries remain.
- Replace periodic AI-generated history summaries with deterministic summaries;
  compaction and memory snapshots require zero additional model calls.
- Drop assistant reasoning/prose from retained native tool-call turns. Preserve
  tool call IDs, names, arguments and result pairing. Compact JSON-fallback turns
  equivalently. Strict tool validation and fixed account arguments remain.
- Put common instructions and stable per-role tool definitions before changing
  identity, observations and memory. Do not insert run IDs or timestamps into
  the reusable prefix. Reuse deterministic role schemas during a run.
- Save each agent's bounded context snapshot once per completed round as local
  JSON under the run's ignored artifact directory. Isolated actors and benchmark
  runs do not import one another's snapshots. Raw evidence remains in event stores.

## Repetition and verified findings

- Count exact repeated reads only after completed results. After two identical
  read results, provide a short exploration hint. Stop an actor after four
  identical read results with no intervening successful marketplace write.
  A successful write in the current target lifetime clears idle-read counters.
- Stop after three consecutive invalid model decisions; surface the reason.
  These controls are configurable and can be disabled for comparison.
- Never cache or suppress HTTP writes, checkout, coupon/refund/dispute attempts,
  or other mutation operations. Concurrent execution barriers remain intact.
  Read responses also come from the actual API; only their prompt representation
  is deduplicated. Every executed action retains full replay evidence.
- After independent verification, supply a short shared known-finding notice
  scoped to the observed operations/resources. It advises alternative exploration;
  it does not reveal planted catalog IDs, silently mark a bug fixed, or prohibit
  mutations that might expose another bug. Unverified candidates do not enter it.
- In isolated mode, notices and counters reset before each actor's target reset.
  Across seeds/conditions all optimization state starts empty. Both conditions
  use the same policy. Existing benchmark artifacts are historical, not rerun or
  relabelled as evidence for the optimized runtime.

## Provider capacity, cache usage and cost

- Retain the configured concurrency ceiling (currently two) and shared RPM/TPM
  admission. No automatic increase beyond the configured/account capacity.
- Observe rate headers when available to reduce dispatch capacity or wait until
  reset. Treat Retry-After as a dispatch pause, with cancellation support.
  Never perform an automatic retry when the previous call's usage is unknown.
  Unknown usage continues to abort measured execution rather than invent charges.
- Record actual prompt, cached prompt and output tokens from provider usage;
  validate that cached tokens are nonnegative and no greater than prompt tokens.
  If cache details are absent, assume zero cached tokens and label them unreported.
- Add an optional cached-input price. Configure Groq GPT-OSS using its documented
  50% cached-input discount; other providers default to the ordinary input rate.
  Estimate cost from uncached input, cached input and output separately. Keep
  budget admission conservative at the undiscounted price and count all tokens
  against the run token budget. Only confirmed cache hits receive a discount.
- Apply Groq's confirmed cached-token TPM exclusion after the response, never
  before dispatch; do not change request counts or assume a future cache hit.
- Use the same accounting primitives for the independent judge. Judging remains
  separate from exploration, and discovery-time detection/replay/scoring stays
  deterministic. Do not cache judge decisions across different evidence.
- Expose calls, input/output/cached tokens, context size/compactions, repeat
  redirections, stop reasons and pacing wait time in run summaries and the
  existing console. Cost is an estimate from configured prices, not an invoice.

## Validation and acceptance

- Focused checks exercise bounded context, ID retention, tool-pair validity,
  deterministic prefixes, state changes, isolation, read repetition and invalid
  decisions. Exact repeated writes must still execute through a shared barrier.
- Exercise valid/missing/malformed cache usage, conservative budget admission,
  cached/uncached costs, pacing feedback and cancellation with provider fixtures.
- Run the existing scripted console/benchmark integration, all eight planted
  paths and clean-copy startup; rebuild affected frontends and run lint/format.
- Compare optimized and legacy prompt construction on identical recorded
  multi-round transcripts. Report serialized prompt size and summary-call
  reductions as proxies, without presenting bytes as measured model tokens.
- Use fixture token counts only to validate accounting, never to claim real
  token savings or preserved live-model recall. A real Groq A/B benchmark is a
  separate follow-up, not an automatic paid run in this implementation pass.
- Record measured software-check results and limitations in progress/docs.
  No percentage speed/cost improvement is promised before measurement.

## Workflow checklist

- [x] Explore code, recent commits and provider documentation.
- [x] Visual companion assessed: no visual decision requires it.
- [x] Clarify scope from the approved technique table and existing constraints.
- [x] Compare configuration-only, local compaction and external/multi-model paths.
- [x] Present concrete local design and write this specification.
- [x] Self-review scope, consistency and acceptance criteria.
- [ ] Owner reviews this written specification.
- [ ] Produce the implementation sequence, implement and validate.

## Provider references

- https://console.groq.com/docs/prompt-caching
- https://console.groq.com/docs/rate-limits

Cache hits are automatic and not guaranteed. Groq documents a 50% input discount
on successful cache hits and applies rate limits at organization level. Exact
account limits remain authoritative.
