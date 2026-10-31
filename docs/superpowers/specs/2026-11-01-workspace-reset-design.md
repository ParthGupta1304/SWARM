# Reset workspace and clear local caches

Date: 2026-11-01
Status: Approved by owner (“ok proceed”); implemented and checked on disposable data.

## Requested behavior and approach

Add a Reset button to the existing run console. One confirmed action returns
its active local workspace to a fresh seeded state and clears its stored memory
and results. This is an explicit deletion operation, not a new AI run.

Recommended approach: a full reset of the current console workspace. A
memory-only reset would leave old findings/reports visible. Deleting every
artifact directory in the repository would also remove independent experiments;
that broader operation is outside this button's scope.

## User interaction

- Place “Reset workspace” alongside Start and Stop. Explain that it deletes this
  workspace's run history, findings, reports, comparison/review results and memory,
  and restores the seeded marketplace. Confirm once in the interface before acting.
- Allow the request during a run. Show “Stopping and resetting” while work drains;
  disable Start, repeat Reset and marketplace writes until completion.
- Finish in-flight model/API/replay work cooperatively before clearing data.
  A benchmark must stop before another condition/seed starts. Do not silently
  cancel threads while they can still write files or target databases.
- On completion, show an empty console with zero usage/findings and no old
  benchmark/review evidence. Refresh Bazaar's seeded users/items, cart, orders,
  selected user and other current frontend state, including other open app tabs.
- If a reset fails, show the failure and keep new runs blocked until the workspace
  is consistent or reset is retried; never claim that a partial deletion succeeded.
- In external saved-results review mode (`--results`), disable Reset with an
  explanation. Reviewing a source directory does not grant ownership to delete it.

## Reset scope

Clear from this console's configured output directory:

- Its event database and SQLite sidecars, generated per-run event exports,
  reports, measured runs, run summaries, failed-run traces and snapshots.
- Its `memory/` snapshots, in-memory agent context, known-finding hints,
  repetition counters, model usage/cost counters and previous run errors.
- Its generated benchmark/checkpoint/judge/manual-review results and charts.
- Obsolete owned target directories and their logs. Keep current target backing
  files usable while their databases are reset and reseeded, or replace targets
  only through their existing owned-process lifecycle.

Reset both owned live/replay Bazaar databases to `config.seed` using the existing
fixture/reset code. This clears purchases, carts, coupons, messages, questions,
reviews, telemetry and findings, restoring the original seeded fixtures and bug
configuration. Release old coordinator/pipeline/provider-pacer references so a new
run gets fresh local state. This does not change Groq's account limits.

Clear app-owned browser state such as the `bazaar-user` storage key, frontend
render/review caches and app resource caches where the browser permits. Notify
other open app tabs to refresh. Do not assume an old SSE cursor still applies
when database event IDs restart; reset cursors using a workspace generation ID.

Preserve source, Git history, `.env`/API keys, configuration, planted bug catalog,
committed demo/acceptance evidence, unrelated output directories and external
services. No Miko/Meko deletion or upload is performed. Provider-managed prompt
caching remains under Groq's control; the local reset must not claim to erase it.

## Ownership and concurrency

- Implement reset at the console controller boundary; existing target objects
  remain the authority for disposable database resets.
- Serialize reset with Start, manual marketplace writes and review writes.
  Wait for current work before file deletion or event-store replacement.
- Delete only recognized generated entries within the active output directory.
  Do not recursively erase arbitrary output contents or follow symlinks outside
  the workspace. Reject unsafe paths instead of treating project files as caches.
- Protect active owned target resources during cleanup. Never stop unrelated
  servers or erase other experiment directories.
- Expose reset progress/generation in console state and SSE. Browsers clear
  their old rendering state when the generation changes. Agent/round settings
  remain 10 agents and six regular rounds; benchmark rounds remain three.

## Validation and delivery

- Exercise idle reset with populated events, memory, findings and reports in a
  disposable output directory; verify zero state and freshly seeded targets.
- Exercise reset during scripted activity and benchmark transitions. Prove no
  writes survive after reset and another run can start normally.
- Cover repeated Reset, Start/write/review overlap, protected files/symlinks,
  saved-results mode, deletion failure and SSE cursor/generation handling.
- Check browser-state reset and rebuilt Bazaar assets, console JS syntax,
  Python lint/format and the existing focused/runtime checks.
- Use scripted providers/disposable data; do not clear the owner's actual saved
  workspace or start paid AI work merely to test the button.
- Document scope and limitations, commit locally and reload the idle launcher
  so the button is available. No GitHub push is included in this request.

## Workflow checklist

- [x] Explore local storage, target resets, event store and frontend state.
- [x] Assess visual companion: button scope does not require a visual decision.
- [x] Resolve scope conservatively to the active console workspace.
- [x] Compare memory-only, active-workspace and repository-wide approaches.
- [x] Write the concrete design and self-review scope/concurrency/acceptance.
- [x] Owner approves the written reset scope.
- [x] Write the implementation sequence, implement, validate and reload.
