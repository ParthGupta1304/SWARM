# Integrated Phase 1 frontend

The UI preserves `origin/frontend` at `8a801fb`: white, ink and moss colors,
Instrument Sans/Inter/JetBrains Mono, landscape imagery, rounded cards and pill
navigation. The landing composition remains at `/`; `/dashboard` opens the run
interface directly. `/bazaar/` is the marketplace and `/console` is the fallback.
The owner's subsequent cleanup removes the workflow, oversight and configuration
sections and their navigation links. Navigation hides when scrolling down and
returns when scrolling up, with reduced-motion and keyboard-focus support.

Start with `uv run --no-sync python -m swarm.demo`. The launcher defaults to
`artifacts/phase1`; pass `--output artifacts/phase1-final` to use that existing
workspace. History is local to the selected output directory. Reset permanently
clears only that workspace after confirmation; it keeps configuration and keys.

The dashboard includes Start/Stop, a confirmed six-run benchmark, saved-run
selection, condition recall and round activity charts, usage, six-role score
tables and individual actor details. The planted-bug roster and toolbar's model,
population, budget and seed details are hidden. Empty values stay
unmeasured. Reviewed precision requires explicit assessments; replay success
does not automatically imply human acceptance. Scripted runs remain labelled.

Download the original JSON, Markdown report or event log from the selected run.
Replay and review remain backend/CLI capabilities; their former oversight UI
was removed at the owner's request. Rechecks are separate records; they do not
replace the original finding. Replay
uses HTTP/oracles without another LLM call. Start, replay and reset serialize
ownership of the targets; Stop also applies to an active recheck.

Configuration uses the server's persona templates and caps: up to ten
actors, all six roles, six regular rounds and the configured per-run budget.
The configuration section/sliders are removed; adjust the server YAML instead.
The CLI modal still exposes the configured YAML, and the server validates exports
against the runtime schema. Exports use
repository-root paths and environment-variable key names. Smaller populations
can reduce coverage. Benchmarks use three rounds in both conditions across
three held-out seeds, with separate budgeted judging overhead. Phase 2 is marked
planned and disabled.

When no run or current benchmark is selected, evaluation cards show the clearly
labelled historical real-Groq benchmark from `configs/phase1-evaluation.json`.
It is a sanitized summary recomputed from six canonical runs and evidence-bound
reviews in `artifacts/groq-phase1`, with evidence hashes for audit. It uses three
rounds per condition and seeds 11/22/33; it is separate from workspace history
and does not claim to measure the current six-round runtime. New selected-run
results take precedence, and missing multi-seed metrics remain unmeasured.

For Condition C the recorded mean emergent recall is 33.3% (2/5, 1/5, 2/5),
reviewed precision 100% (five supported verified findings, including human
acceptance of E7), mean time to first verified finding 53.5 seconds, and all-seed
repeatability 33.3% (E2 appears in every seed; E1 and E7 appear once each).
Mean estimated exploration cost is $0.0034506 per swarm run, excluding judge
overhead. Across the three runs the union covers three of five emergent bugs
(60%); that differs from the per-run mean recall displayed in the cards.

For development, run `npm ci --prefix frontend`, then `npm run dev --prefix
frontend` alongside the Python service on 8080. Vite proxies API/Bazaar traffic.
`npm run build --prefix frontend` type-checks and writes `dashboard/site/`.
Commit the generated assets with source changes so a Python-only checkout works.

Checks:

```sh
npm test --prefix frontend
npm run build --prefix frontend
uv run --no-sync python -m unittest discover -s tests -v
uv run --no-sync python tests/check_frontend_integration.py
node tests/check_frontend_browser.cjs
```

The two integration checks own temporary SQLite targets and a scripted provider,
including all six benchmark runs. They never call Groq or reset the user's
workspace. The browser check uses installed Google Chrome on macOS; set
`SWARM_CHROME` for another executable. It requires frontend dev dependencies and
the project `.venv`; screenshots/results go under ignored
`artifacts/frontend-browser-check/`. This checks UI/software behavior, not paid
model discovery or the Phase 1 real-AI acceptance gate.
