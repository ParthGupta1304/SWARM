# Frontend branch integration for the working Phase 1 MVP

Date: 2026-11-01
Status: Written integration scope approved by the owner; implemented on `codex/frontend-integration`.
Reference: `origin/frontend` at `8a801fb`.
Working MVP base: `b0beace` (Groq, 10 actors, six regular rounds and workspace reset).

## Goal and source of truth

Implement the UI already committed under `frontend/`, preserving its visual
identity and making Phase 1 controls and data displays real. The latest two
commits complete dashboard/oversight and App/modal/footer assembly; their four
ancestor commits supply required assets, styles and configuration components.
Integrate that complete branch without discarding the working backend, cache
improvements, six-round setting, reset behavior or Bazaar storefront.

The delivered UI must distinguish measured results from examples, unsupported
features and missing data. It must never turn a visual toggle into a claim that
a replay succeeded or silently describe generated CLI YAML as executable when
it does not match the runtime's configuration schema.

## Visual specification

Follow the reference JSX, spacing, imagery, rounded cards, pill controls, borders,
icons and responsive structure. Do not introduce another theme or additional
ornament. Preserve the landing page's supplied composition rather than replacing
it with generic statistics cards. Use the same component language for operational
controls, charts, details and error/empty/loading states.

- Palette: white `#ffffff`, ink `#14170f`, moss `#4a5d0e`, meadow `#b5c44c`,
  sage `#e5eacb`, mist `#f5f6f0`; preserve the supplied border/muted tokens.
- Type: Instrument Sans headings, Inter body and JetBrains Mono data/code.
- Layout: existing maximum 1180px content width, responsive single/two-column
  cards, generous whitespace and compact, aligned table rows.
- Interaction: keyboard-visible focus, accessible names and tables, focus-trapped
  dialogs with Escape/return-focus behavior, reduced-motion support and readable
  contrast. Keep the existing visual identity when correcting accessibility issues.
- Figures use actual values, explicit denominators, legends and accessible text.
  An unknown/unassessed value is shown as an em dash with an explanation.

## Pages and wireframe

`/` preserves the branch landing composition and section ordering. `/dashboard`
opens a focused operational view using its existing dashboard/card components.
Existing section links keep working. Bazaar remains available at `/bazaar/`.
The old console remains available at `/console` for fallback/debugging.

```text
Landing: reference navigation → hero → proof → workflow → oversight
         → live dashboard preview → configuration → CLI modal/footer

Dashboard: reference navigation + real model/connection/run identity
           condition selector + Start / Stop / Benchmark / Reset
           existing KPI row + distinct bugs found / catalog total
           [measured recall chart + eight-bug table] [role/actor table]
           [round activity/usage chart + compact event table]
           finding selection → evidence/replay drawer + human review
           configuration/export within the reference card language
```

Charts/tables concentrate operational information. Raw request/replay JSON remains
available in expandable evidence details rather than occupying the primary view.

## Data and control binding

- Use the local Python service as the only backend and provider boundary.
  A shared typed client/store consumes existing state, SSE, review and workspace
  endpoints, including reset generations and reconnect behavior.
- Start/Stop/Reset retain their current semantics. Reset requires confirmation,
  drains work, clears only the owned workspace and refreshes other app tabs.
- Default to actual configured Groq GPT-OSS 120B, 10 actors and six regular rounds.
  The UI benchmark must explicitly use the documented three rounds per condition
  and three seeds; both conditions keep identical model/budget/policy settings.
- Show total distinct verified IDs (for example 3/8), emergent/single-user split,
  verification state, elapsed time, token/cached-token use and estimated cost.
  Do not call replay verification “precision” without the required judge/review
  assessments. Repeatability and baseline/swarm comparisons require measured
  matching runs, not invented data or one run extrapolated across seeds.
- Use the server's frozen bug catalog and persona metadata, avoiding divergent
  frontend copies of models, bug semantics or role counts. Aggregate the ten
  actors into the existing six-role table, with actor drilldown including valid
  actions, invalid decisions, stop reasons, objective score units and costs.
- Build charts from measured data: grouped recall bars by condition/category,
  per-round action counts and usage where accounted. Do not equate tokens on
  executed actions with total billed tokens when invalid decisions also consumed
  usage. All charts have a table/text alternative and valid empty states.
- Add a run-history selector backed by this workspace's saved canonical run,
  finding and event exports. Previous real results remain inspectable after a
  server restart without starting another paid run. Label live, saved, scripted
  and incomplete data; never silently mix them into one comparison.
- Add narrowly scoped read adapters for history/evidence where existing APIs
  lack them. IDs/path access stay confined to recognized workspace artifacts.

## Replay, review and exports

- Replace the reference verifier's local “Verified” toggle with real asynchronous
  re-verification of a selected saved/current finding on the owned replay target.
  Reuse existing reset/oracle/verifier hooks. Serialize this with run/reset work,
  expose queued/running/completed/error states and support cooperative stop.
- Preserve original evidence and show a recheck as a separate result with target
  version/seed. A failed oracle or infrastructure check is inconclusive, never
  a silently claimed fix or a changed original verification record.
- Human review submits an explicit evidence-bound decision through the existing
  review API. Inspection and replay do not auto-complete human acceptance.
- Provide JSON/report/config downloads for real selected data. Clipboard controls
  report success only after the browser accepts the copy operation.

## Configuration and feature boundaries

- Connect the reference population/budget sliders and CLI modal to a single
  selected configuration. Defaults come from the current server, not the branch's
  20-agent/Anthropic/Gemini placeholders. Selected counts must sum exactly.
- Validate supported overrides on the server using existing persona templates,
  fixed identities and tool allowlists. Enforce configured population/budget
  ceilings; retain the current 10-agent maximum and six-round regular limit.
  Changing role mixes may reduce scenario coverage and must not promise recall.
- YAML preview/export must validate as the actual `RunConfig` with usable
  project-relative spec/fixture/invariant paths and an environment-variable key
  name. It must not embed credentials or rewrite the user's `.env`.
- Keep provider credentials/server ownership out of browser bundles. Remove
  unused AI Studio/Gemini scaffolding and stale model/key instructions.
- Phase 2 memory/hosted features remain clearly marked planned/unavailable;
  they do not appear to run when clicked. Informational workflow illustrations
  are labelled examples. Supported Phase 1 interactions must all function.
- This UI integration does not change agent reasoning, planted bugs, verification
  requirements or the accepted interpretation of the latest three findings.

## Implementation outline

1. Create `codex/frontend-integration` from the working MVP and merge
   `origin/frontend`, preserving both histories. Keep the supplied visual assets.
2. Establish a working pinned frontend toolchain/lockfile, typed service layer,
   shared state and configuration schema binding. Reuse existing components.
3. Connect dashboard charts/tables, history, controls, reviews and real replay;
   implement only the supporting server adapters/controller operations needed.
4. Serve the compiled frontend from the existing Python launcher, with `/assets`
   and image/PDF routes, same-origin APIs and a Vite development proxy. Include
   built assets in packaging; keep `/bazaar/` and legacy console working.
5. Check source-design fidelity at desktop/tablet/mobile sizes, keyboard/dialog
   behavior, reset/reconnect/error states and all supported interactions.
6. Update docs/progress, commit locally and reload the idle launcher. No GitHub
   push or automatic paid AI acceptance benchmark is part of this request.

## Validation

- Capture/reference the original branch and compare the integrated landing page
  using matching viewports/fonts and reduced-motion settings. Functional content
  and accessibility corrections are the only intended visual differences.
- Type-check, production build and frontend configuration/data-adapter tests.
  Generated configurations validate against Python models; caps, totals and
  secret exclusion are checked.
- Browser checks at 390px, 768px and 1440px: section/routes, navigation, charts,
  filters, history/detail selection, clipboard/export, dialog focus and keyboard
  controls; no horizontal page overflow or client runtime errors.
- Scripted end-to-end checks for Start/Stop/Benchmark/Reset, generation handling,
  real replay/review and saved-result inspection. Include failures/reconnects and
  unsupported feature states. Paid-provider errors are presented honestly.
- Existing backend/efficiency/reset checks and real disposable Bazaar/scripted
  integration continue passing. Preserve the owner's saved results during tests.
- Package/clean-copy startup includes all required frontend assets and no keys.

## Workflow checklist

- [x] Inspect branch commits, supplied visual tokens and all interactive surfaces.
- [x] Assess visual companion: use the supplied design as the reference, no new visual choice required.
- [x] Resolve Phase 1 scope from the selected design and working MVP.
- [x] Compare a static merge, direct replacement and shared typed data integration.
- [x] Recommend typed integration and write/self-review this specification.
- [x] Owner reviews the written integration scope.
- [x] Implement, visually verify, validate and reload.
