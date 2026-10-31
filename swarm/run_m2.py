"""
run_m2.py — M2 Acceptance Check and OpenAPI-driven Agent Run.

Demonstrates:
  1. Dynamic generation of tools from openapi.json (register, login, list_items,
     add_to_cart, checkout, request_refund).
  2. Acceptance check: Adding a new endpoint to an OpenAPI spec automatically
     generates a new tool definition with zero code changes.
  3. Running an agent whose tools are entirely generated and executed by OpenAPIAdapter.

Usage:
  # Terminal 1 — Start mock Bazaar (port 8001)
  uv run uvicorn mock_bazaar.server:app --port 8001

  # Terminal 2 — Run M2 check
  uv run python -m swarm.run_m2
"""

import copy
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters.openapi import OpenAPIAdapter
from swarm.agent import AgentLoop


def test_acceptance_check():
    """
    Acceptance check M2:
    Adding a new endpoint to the spec makes a new tool appear with no code changes.
    """
    print("\n" + "=" * 60)
    print("  M2 Acceptance Check: Dynamic Tool Generation")
    print("=" * 60)

    spec_path = Path("openapi.json")
    if not spec_path.exists():
        raise FileNotFoundError("openapi.json missing!")

    adapter = OpenAPIAdapter(spec_path, "http://localhost:8001")
    initial_tools = adapter.get_tool_names()
    print(f"Initial tools from openapi.json ({len(initial_tools)}):")
    print(f"  {sorted(initial_tools)}")

    expected_ops = {"register", "login", "list_items", "add_to_cart", "checkout", "request_refund"}
    missing = expected_ops - initial_tools
    if missing:
        print(f"[FAIL] Missing expected operations: {missing}")
        return False
    print("[OK] All 6 required operations present in openapi.json")

    # ── Inject a brand new endpoint dynamically into the spec ─────────────────
    modified_spec = copy.deepcopy(adapter.spec)
    new_path = "/cart/items/{item_id}"
    modified_spec["paths"][new_path] = {
        "delete": {
            "summary": "Remove an item from the shopping cart",
            "operationId": "remove_from_cart",
            "parameters": [
                {
                    "name": "item_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                    "description": "Item ID to remove",
                }
            ],
            "responses": {
                "200": {"description": "Item removed"},
            },
        }
    }

    # Pass the modified spec to the adapter
    new_adapter = OpenAPIAdapter(modified_spec, "http://localhost:8001")
    new_tools = new_adapter.get_tool_names()
    print(f"\nDynamically injected endpoint: DELETE {new_path} (operationId: remove_from_cart)")
    print(f"New tool set ({len(new_tools)}):")
    print(f"  {sorted(new_tools)}")

    if "remove_from_cart" in new_tools:
        tool_def = new_adapter.get_tool_definitions(["remove_from_cart"])[0]
        print("\nGenerated Tool Definition for 'remove_from_cart':")
        print(json.dumps(tool_def, indent=2))
        print("\n[SUCCESS] ACCEPTANCE CHECK PASSED: New tool generated with NO code changes!")
        return True
    else:
        print("\n[FAIL] ACCEPTANCE CHECK FAILED: remove_from_cart was not generated.")
        return False


def run_openapi_agent():
    """Run one casual_buyer using the OpenAPIAdapter."""
    print("\n" + "=" * 60)
    print("  Running Agent with OpenAPI-Generated Tools")
    print("=" * 60)

    run_id = str(uuid.uuid4())[:8]
    seed = 1
    app_base_url = "http://localhost:8001"
    provider_base_url = "http://localhost:11434/v1"
    model = "qwen2.5-coder:7b"

    adapter = OpenAPIAdapter("openapi.json", app_base_url)

    # Casual buyer uses browse, add to cart, and checkout from openapi
    buyer_tools = adapter.get_tool_definitions(["list_items", "add_to_cart", "checkout"])

    agent = AgentLoop(
        agent_id=f"agent-{seed}-openapi-buyer",
        role="casual_buyer",
        objective="Browse items, select one item, add it to your cart, and complete checkout.",
        score_desc="1 point if checkout succeeds, 0 otherwise",
        provider_base_url=provider_base_url,
        model=model,
        api_key="ollama",
        app_base_url=app_base_url,
        run_id=run_id,
        seed=seed,
        tool_definitions=buyer_tools,
        adapter=adapter,
    )

    try:
        result = agent.run(max_steps=12, max_tokens=20000)
    finally:
        agent.close()

    print("\n" + "=" * 60)
    print("  Agent Summary")
    print("=" * 60)
    print(f"  Score            : {result.get('score', 0)}")
    print(f"  Steps taken      : {result.get('steps', 0)}")
    print(f"  Tokens used      : {result.get('tokens_used', 0)}")
    print(f"  Invalid tool rate: {result.get('invalid_rate', 0):.1%}")
    print(f"  Used fallback    : {result.get('used_json_fallback', False)}")
    print("=" * 60)

    return result.get("score") == 1


if __name__ == "__main__":
    check_ok = test_acceptance_check()
    if not check_ok:
        sys.exit(1)

    # Check if mock server is up
    import requests

    server_online = False
    try:
        r = requests.get("http://localhost:8001/health", timeout=2)
        if r.status_code == 200:
            server_online = True
    except Exception:
        pass

    if server_online:
        agent_ok = run_openapi_agent()
        if not agent_ok:
            sys.exit(1)
    else:
        print("\nNote: Mock Bazaar server is not running on http://localhost:8001.")
        print("To run the live agent loop, start the server in another terminal:")
        print("  uv run uvicorn mock_bazaar.server:app --port 8001")
        print("And re-run:")
        print("  uv run python -m swarm.run_m2")
