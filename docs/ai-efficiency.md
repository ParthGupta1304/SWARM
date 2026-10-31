# AI context and cost efficiency

The runtime now sends bounded local context, preserves cacheable prompt prefixes,
and reports confirmed cache usage. The provider remains Groq GPT-OSS 120B with
10 actors, six interactive rounds and three rounds in each benchmark condition.
Miko/Meko integration and multiple-model routing are not part of this change.

## Context and memory

Each actor keeps two complete recent action/result turns and up to 6 KiB of older
JSON facts, relevant observations and verified-finding hints. Model-visible tool
results are capped at 2 KiB. Reduction prioritizes resource IDs, status/errors,
quantities, stock, prices and order state, with explicit omission markers.
Redundant tool descriptions and assistant reasoning are removed from retained
context. Compaction is deterministic Python code and makes no model calls.

Common instructions and role-specific tools stay stable; account identity,
objective, action count and changing observations follow them. Only relevant
account observations are shared. Verified notices contain the participating
actor's operations/resources, not planted catalog labels or private peer evidence.
Notices guide discovery but do not prevent a legitimate setup or race attempt.

The CLI and console save snapshots after each completed round under
`<output>/memory/<run-hash>/round-NNNN/<actor-hash>.json`. The file includes the
agent ID, action count, older memory and recent turns. Direct runtime consumers
use `artifacts/context/` by default. These files are ignored by Git, are written
atomically, and are not uploaded. Fresh seeds/conditions do not reload them;
isolated actors get separate state and target resets. The hot context remains
in memory, avoiding disk reads before every decision.

The canonical event evidence is unchanged: full requests, full response hashes,
and parsed JSON within the pre-existing 16,000-character response limit. Prompt
reduction does not replace replay evidence. HTTP results are always fetched live;
marketplace actions and replay/scoring are not cached AI decisions.

## Repetition and capacity

Two identical consecutive reads produce a short redirection hint. Four unchanged
reads stop that actor before another paid decision, provided no successful write
intervenes. A write anywhere in the current target batch resets idle-read state.
Repeated identical write failures produce an advisory exploration hint, while
remaining live and retryable for race testing. Three consecutive invalid model
decisions stop an actor with an explicit reason.
Mutations are never skipped by this policy, including coupon, checkout, refund,
and dispute attempts. Concurrent execution barriers remain in place.

The configured model concurrency remains two. Shared request/token pacing observes
rate headers and Retry-After to reduce capacity or pause dispatch. Server headers
never raise the configured ceiling. Stop remains responsive while waiting. An
unknown-usage provider failure aborts measured execution without automatic retries.
Groq's daily request headers are not interpreted as requests per minute.

## Usage and prices

The console reports model calls, input/output tokens, confirmed cached input,
cache-reporting status, compactions, repetition hints and pacing wait. Actor rows
show stop reasons. Run JSON and measured benchmark runs also retain these metrics.
Independent judging uses the same accounting, with its own budget and counters.

Groq configs set `cached_input_cost_per_million: 0.075`, versus ordinary input
`0.15` and output `0.6`. These are configured estimates, not invoices. Update all
prices when switching provider/model. A missing cached-input price defaults to
the ordinary input price. Missing cache usage receives no discount; malformed
usage fails closed. Dollar admission assumes full uncached cost; token budgets
count cached tokens too. Confirmed Groq cache hits are excluded from subsequent
provider token pacing, never assumed before dispatch.

Groq cache hits depend on exact prefixes and are not guaranteed. See
[Groq prompt caching](https://console.groq.com/docs/prompt-caching) and
[rate limits](https://console.groq.com/docs/rate-limits).

## Configuration

The default policy can be overridden in any run YAML:

```yaml
context:
  enabled: true
  recent_turns: 2
  memory_bytes: 6144
  result_bytes: 2048
  idle_read_limit: 4
  invalid_decision_limit: 3
  failure_hints: true
```

Set either repetition limit to `0` to disable that control. Setting `enabled` to
`false` disables prompt compaction, while repetition limits remain independently
configurable. Neither mode makes an AI summary call. Changes apply equally to
both benchmark conditions. Existing checkpoint fingerprints reject resuming an
older runtime/configuration; use a new output directory for optimized comparisons.
Historical Groq acceptance results were not overwritten or relabelled.

## Verification and measurement

`make check` includes ten focused checks for bounded/valid context, IDs, raw
evidence, observation privacy, live repeated writes, idle/invalid stopping,
cache and judge costs, conservative budgets, pacing and cancellation.
The scripted console integration exercises all eight planted cases, all six
comparison runs, telemetry, memory snapshots and stop. Both frontend builds,
wheel/sdist and clean-copy startup passed. Scripted decisions and
usage are not evidence of live-model discovery or cost savings.

An offline comparison used the same 60 actor traces from the earlier six real
Groq runs, with minimal reconstructed native decisions and identical recorded
results in both arms. Reasoning and peer observations were excluded from both.
Prompt payloads were 4.87% smaller for recorded three-round traces and 25.18%
smaller for an eight-round repeated-trace scenario. The latter repeats recorded
results; it is not an eight-round AI run. These are serialized byte measurements,
not tokenizer counts, actual billed credits or proof of unchanged model recall.
A real Groq A/B comparison remains necessary to measure those effects.

The sanitized result is in `docs/results/ai-efficiency-summary.json`; the detailed
local measurement is `artifacts/ai-efficiency/prompt-size-comparison.json`.
