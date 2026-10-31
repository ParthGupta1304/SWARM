"""
run_m1.py — M1 entry point.

Runs ONE casual_buyer agent against the mock Bazaar server.
Acceptance check: agent completes a browse-and-buy flow and every action
appears in swarmtest_events.jsonl.

Usage:
  # Terminal 1 — start mock server
  uvicorn mock_bazaar.server:app --port 8001 --reload

  # Terminal 2 — run the agent
  python -m swarm.run_m1
"""

import uuid
import sys
import os
import json
from pathlib import Path

# Make sure repo root is on the path when running as a script.
sys.path.insert(0, str(Path(__file__).parent.parent))

from swarm.agent import AgentLoop

# ── Config ────────────────────────────────────────────────────────────────────
RUN_ID = str(uuid.uuid4())[:8]
SEED = 1
APP_BASE_URL = "http://localhost:8001"
PROVIDER_BASE_URL = "http://localhost:11434/v1"
MODEL = "qwen2.5-coder:7b"
MAX_STEPS = 15      # short cap for M1 testing
MAX_TOKENS = 20000


def main():
    print(f"\nSwarmtest M1 — run_id={RUN_ID}  seed={SEED}")
    print(f"App:      {APP_BASE_URL}")
    print(f"Provider: {PROVIDER_BASE_URL}  model={MODEL}")
    print(f"Events:   swarmtest_events.jsonl\n")

    agent = AgentLoop(
        agent_id=f"agent-{SEED}-casual-0",
        role="casual_buyer",
        objective=(
            "Browse available items in the marketplace. "
            "Pick one item you like, add it to your cart, and complete checkout."
        ),
        score_desc="1 point if checkout succeeds, 0 otherwise",
        provider_base_url=PROVIDER_BASE_URL,
        model=MODEL,
        api_key="ollama",
        app_base_url=APP_BASE_URL,
        run_id=RUN_ID,
        seed=SEED,
    )

    result = agent.run(max_steps=MAX_STEPS, max_tokens=MAX_TOKENS)

    # ── Print final report ────────────────────────────────────────────────────
    print(f"\n{'='*54}")
    print(f"  M1 Run Complete")
    print(f"{'='*54}")
    print(f"  Score            : {result.get('score', 0)}/1")
    print(f"  Steps taken      : {result.get('steps', 0)}")
    print(f"  Tokens used      : {result.get('tokens_used', 0)}")
    print(f"  Invalid tool rate: {result.get('invalid_rate', 0):.1%}")
    print(f"  Used JSON fallback: {result.get('used_json_fallback', False)}")
    print(f"{'='*54}")

    # ── Verify events file ────────────────────────────────────────────────────
    events_file = Path("swarmtest_events.jsonl")
    if events_file.exists():
        events = [json.loads(l) for l in events_file.read_text().splitlines() if l.strip()]
        run_events = [e for e in events if e.get("run_id") == RUN_ID]
        print(f"\n  Events logged for this run: {len(run_events)}")
        print(f"  Tools called: {[e['tool'] for e in run_events]}")
    else:
        print("\n  [WARN] No events file found — something went wrong.")

    if result.get("score") == 1:
        print("\n  [SUCCESS] M1 ACCEPTANCE CHECK PASSED")
    else:
        print("\n  [FAIL] M1 ACCEPTANCE CHECK FAILED (checkout did not succeed)")
        sys.exit(1)


if __name__ == "__main__":
    main()

