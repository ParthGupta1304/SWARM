# AI efficiency implementation sequence

The owner approved the written design on 2026-10-31. The referenced writing-plans
skill is not installed; this explicit sequence follows the approved specification.

1. Add deterministic bounded context, recent complete tool turns, scoped facts,
   read-idle controls and per-round local snapshots. Preserve full raw events.
2. Integrate cache usage validation, conservative budget admission, optional cached
   pricing, rate-header feedback and dispatch cancellation. Reuse for the judge.
3. Connect runtime telemetry, verified finding notices, configuration and console
   metrics. Keep isolated state separate and benchmark fingerprints current.
4. Update the scripted provider for bounded histories. Check context semantics,
   repeated writes, cache costs/limits and determinism, then run existing full
   scripted integration and clean-copy startup checks. Measure prompt bytes on
   identical transcripts; do not claim live token/recall gains without an A/B run.
5. Document measured results and limitations; commit the implementation locally.
