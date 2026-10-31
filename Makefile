.PHONY: setup serve openapi check frontend benchmark
setup:
	uv sync --locked --extra postgres --extra charts
frontend:
	npm ci --prefix frontend
	npm run build --prefix frontend
	npm ci --prefix apps/bazaar/web
	npm run build --prefix apps/bazaar/web
benchmark:
	uv run --no-sync swarmtest benchmark --config swarmtest.yaml
serve:
	uv run --no-sync python -m swarm.demo
openapi:
	DATABASE_URL=sqlite:////tmp/swarm-openapi.sqlite3 uv run --no-sync python -c 'import json; from pathlib import Path; from apps.bazaar.bazaar.main import app; Path("apps/bazaar/openapi.json").write_text(json.dumps(app.openapi(), indent=2) + "\n")'
check:
	uv run --no-sync ruff check .
	uv run --no-sync ruff format --check .
	uv run --no-sync python -m unittest discover -s tests -v
	uv run --no-sync python -m compileall -q swarm adapters apps dashboard detect verify bench memory
