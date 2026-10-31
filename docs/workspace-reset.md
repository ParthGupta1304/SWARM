# Reset workspace

Click **Reset workspace** beside Start and Stop in the console, then confirm the
deletion. This restores the current workspace to a fresh seeded marketplace.

The reset stops active work cooperatively and waits for current model calls,
API actions, replay and benchmark workers to finish. Start, manual writes and
review writes are blocked during reset. The status stays “Stopping and resetting”
until cleanup finishes; it can take time if a provider call or replay is active.

## Data cleared

- Current-workspace event database, per-run histories/exports/reports, findings,
  benchmark/checkpoint/judge/review results and saved agent-memory snapshots.
- Local run context, known-finding hints, repetition/usage counters and errors.
- Both owned live/replay databases, including their published findings and run
  telemetry. Original seeded users/items/coupons and configured bug flags return.
- Recognized obsolete target folders and logs. Current backing databases remain
  usable and seeded; an empty event database is recreated.
- App-owned browser memory and Bazaar's account selection. Other open app tabs
  see the new workspace generation and discard stale data/cursors. The browser
  is also asked to clear its HTTP cache using `Clear-Site-Data: "cache"`; support
  depends on the browser/context. See the [browser documentation](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Clear-Site-Data).

Source, Git, `.env`/API keys, configuration and committed demo/results files stay
intact. Other output folders, unknown files within the workspace and external
saved-results inputs are preserved. Cleanup refuses unsafe source roots and
symlinks instead of following them. Reset is disabled in `--results` review mode.
This action does not delete data from Miko/Meko, flush Groq's provider-managed
prompt cache, or reset provider account quotas.

## API and failure handling

`POST /api/reset` with `{"confirmed":true}` returns HTTP 202. Poll
`GET /api/workspace` for `resetting`, `reset_failed` and `generation`. On success,
`/api/state` contains empty runs/actions/events/findings and no benchmark or gate.

If any step fails, the UI reports failure and new runs/writes remain blocked.
Correct the underlying filesystem issue and retry Reset. A partially completed
reset is never reported as successful. In-flight duplicate Reset requests reuse
the same operation. SSE IDs include a generation so old cursors do not hide new
events when database IDs restart.

## Verification

- `make check`: 18 focused Python checks, including reset/deletion ownership,
  active-run draining, benchmark stop, write/review exclusion, retry recovery,
  read-only results and generation/cursor handling.
- `node tests/check_reset_frontend.cjs`: confirmation/cancellation, browser-state
  clearing, stale response/review rejection, completion reload and retry controls.
- A scripted-provider integration on real disposable SQLite targets verified all
  eight planted cases and six comparison runs, then cleared the workspace,
  confirmed reseeding and exercised another active run/reset. Protected notes
  remained intact. Both frontend builds and package construction passed.

No paid AI run or deletion of the owner's actual workspace was used for these
checks. Historical real Groq acceptance evidence remains separate.
