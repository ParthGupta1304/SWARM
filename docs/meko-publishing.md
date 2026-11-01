# Meko finding publishing

The default launcher reads `swarmtest.yaml`, whose `findings_store.type` is
`meko`. Set `MEKO_API_KEY` and `MEKO_DATAPACK_ID` in the repository's local `.env`.
Credentials are read again when publishing, so a newly edited key is used.
Explicit configs with `findings_store.type: local` remain local-only.

Dashboard and CLI runs save their reports and event evidence first, then publish
verified findings to Meko. Each finding gets a replay JSON artifact and a
searchable `finding_<finding-id>.md` Knowledge Base document under the configured
datapack, attributed to `swarmtest:verifier`. Publishing happens after the measured
run, so network/upload delays do not affect discovery timing or agent memory.
Unverified candidates stay in the local report and are not published as verified
regression checks.

Each run directory contains `findings-sync.json` and `findings.sqlite3`. The sync
record tracks each finding as `published`, `pending`, `local`, or `unverified`.
Meko documents must finish indexing before they are marked published. Missing
credentials, MCP errors and upload/indexing failures produce a pending sync
record and an actionable dashboard error; the saved local report remains intact.
Reset workspace removes local run directories, including their sync records;
it does not delete anything from Meko.

To retry a particular run or publish a previously saved report:

```sh
uv run --no-sync swarmtest publish --config swarmtest.yaml \
  --output artifacts/phase1-final/<run-id>
```

The command performs no model calls. Successful receipts for unchanged findings
at the same destination are skipped; failed items are attempted again. A workspace
directory can also be passed to publish all of its saved run reports. Review that
directory before doing so.

Verification on the existing run `2ed4e97d-d925-4d2f-b8d8-e3673dcad570` published
its three verified findings. Local tests cover automatic dashboard publishing
after export, visible failures, local retention, retry deduplication, CLI publishing
without model calls, MCP JSON/SSE responses, and polling for completed indexing.
