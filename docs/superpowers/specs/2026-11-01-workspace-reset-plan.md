# Workspace reset implementation sequence

The owner approved the written design on 2026-11-01. The writing-plans skill
is unavailable locally; this sequence follows the approved specification.

1. Add a scoped generated-artifact cleanup helper with preflight/path protection.
   Extend owned target reseeding with explicit report clearing and log reset.
2. Add serialized reset/start/write/review operations, cooperative draining,
   reset progress/failure state and workspace generations. Replace event storage
   only after all active work and readers have finished.
3. Add the confirmed Reset button and generation-based console/Bazaar refresh.
   Clear app-owned browser state and request browser HTTP-cache clearing.
4. Check idle/active/benchmark reset, failures/retries, protected paths, saved
   results and post-reset reuse using disposable data and scripted providers.
5. Rebuild assets, run focused checks, document results, commit and reload the
   idle live launcher. Do not click Reset on the owner's saved workspace.
