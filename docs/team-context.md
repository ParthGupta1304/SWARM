# Shared context when Meko is unavailable

Dev2 currently cannot connect to Meko MCP. This does not prevent GitHub code
contributions or written handoffs. The connection's root cause is unknown until
the client name and redacted error are available.

This is a documented fallback proposal for coordination during the outage.
It supplements the shared Meko protocol and does not change application APIs,
module ownership, or the Phase 2 product-memory architecture.

## What each agent reads

Before major work, fetch the latest repository state and read:

1. `README.md` for current project setup and module ownership.
2. `progress.md` for the overall delivery state and integration dependencies.
3. `docs/dev3-integration.md` and `docs/contracts/` for implemented APIs.
4. The relevant developer handoff and the current code on its cited branch/commit.
5. Meko decisions and handoffs when MCP is available.

Important decisions recalled from Meko should be checked against the code.
When records disagree, inspect their commit/date and status, and resolve the
difference with the affected owner before changing a contract. A proposal is
not an accepted team decision merely because another agent copied it.

## Dev2's fallback workflow

- Continue working on a dedicated `dev2/...` branch in `swarm/` and `adapters/`.
- Keep `docs/handoffs/dev2.md` up to date on that same branch. Use the template
  fields to record completed work, the current implementation, paths, API
  contracts, direct checks, pending work and known issues.
- Record decisions with reasoning, alternatives, trade-offs and module impact.
  Record bugs with error, root cause (or explicitly unknown), solution and paths.
- Commit the handoff with the implementation and push the branch. Context can
  be shared before the feature is ready to merge into main.
- Keep the handoff specific to Dev2. Dev3 maintains the overall `progress.md`
  summary during this fallback; other developers should use their own handoffs
  to reduce edits to the same file.
- Coordinate root packaging/lockfile and public contract changes with affected
  owners. A handoff file is a coordination record, not an exclusive file lock.
- If both GitHub and Meko are unavailable, save the same handoff locally and
  commit/push when GitHub access returns. Do not claim an unpushed note is shared.

## Copying committed context into Meko

An agent with a working Meko connection can read Dev2's pushed handoff and
relevant code, then store a concise, attributed summary in the shared datapack.
To request that from this chat, provide the branch or commit and ask:

> Sync Dev2's handoff from branch `dev2/<feature>` into Meko.

The relay should record:

- Source author: Dev2; relay author: the connected agent.
- Repository, branch, exact source commit SHA and handoff path.
- Completed work, current implementation, paths and API contracts.
- Direct checks and their actual outcomes, pending tasks and known issues.
- Decision status, reasoning, alternatives, trade-offs and module impact.

Check whether that source commit/handoff revision was already copied before
creating another record. If context changes, add a dated update that references
the old revision; do not silently rewrite the original author or decision.
For a handoff committed with its implementation, the relay obtains the source
SHA from Git, rather than asking the file to contain its own commit hash.

No automatic watcher or background GitHub-to-Meko synchronization is installed.
Updates become available in Meko after a connected agent explicitly relays them.
If Meko is down for everyone, the committed GitHub handoffs remain accessible.

## Instructions Dev2 can give his agent

> You are Dev2 on SWARM. Meko MCP is unavailable in this client. Before major
> work, read README.md, progress.md, docs/team-context.md,
> docs/dev3-integration.md, docs/contracts/, and docs/handoffs/dev2.md. Verify
> context against the current code. Own swarm/ and adapters/; coordinate shared
> contract and root configuration changes. Work on a dev2/... branch, maintain
> docs/handoffs/dev2.md, directly check each finished feature, and commit/push
> the code and handoff together. Distinguish proposals from approved decisions.
> Never put secrets in Git, handoffs or shared memory. Do not wait for Meko
> connectivity to save progress in GitHub.

## Connection repair information

Collect the agent/client name and version, whether the connection uses native
HTTP or a local proxy/installer, and the exact redacted error. Do not copy keys,
tokens or full private configuration into Git or Meko. Until that evidence is
available, an authentication failure, unsupported transport and network failure
are possibilities rather than a diagnosed root cause.
