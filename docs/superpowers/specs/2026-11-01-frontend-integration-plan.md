# Frontend integration implementation sequence

The owner approved the written specification. The writing-plans skill is not
installed locally; this sequence follows the approved scope.

1. Merge the reference branch (complete), pin a working frontend toolchain and
   preserve a source reference for visual comparison.
2. Add safe typed server adapters for catalog/config, current/saved run history,
   evidence downloads and asynchronous real rechecks. Reuse owned targets and
   reset/run coordination. Validate all run/config overrides against server caps.
3. Add shared frontend state/API bindings and connect the supplied components:
   live dashboard charts/tables, run controls/history, replay/review, configuration
   and clipboard/download. Keep reference palette/type/imagery/layout intact.
4. Serve compiled UI at / and /dashboard, retain /console and /bazaar, and include
   assets/config in packages. Keep credentials server-side.
5. Type/build/unit/API/browser checks and real disposable scripted workflow;
   inspect responsive screenshots against reference. Document limits, commit and
   reload the idle launcher without deleting the owner's historical evidence.

Completed: reference merge, typed adapters, all supported UI controls, production
assets and packaging. Ten frontend and 22 Python tests, real disposable
SQLite/scripted integration, Chrome workflows at three widths, reconnect/error/
clipboard checks and clean wheel startup passed. The idle Groq launcher was
reloaded on 8080; Bazaar, dashboard, landing and fallback routes passed. Paid AI
was not run. Screenshots/results are local under `artifacts/frontend-browser-check/`
and `artifacts/frontend-ui-check/`; user workspace artifacts were not reset.
