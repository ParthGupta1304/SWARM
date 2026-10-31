"""
tools.py — M1 hardcoded tool definitions and executor.

In M2 these definitions are replaced by auto-generated ones from openapi.json.
The execute_tool() function is also replaced by the OpenAPI-driven adapter.
Both are kept behind the same interface so agent.py does not change.
"""

import json
import time
import requests
from typing import Any

# ── Tool definitions (OpenAI function-calling schema) ─────────────────────────
# Agents receive only the tools relevant to their role (enforced in agent.py).
# Keep descriptions concise — they go into every LLM call.

TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "list_items",
            "description": (
                "Browse items for sale in the marketplace. "
                "Returns item IDs, names, prices, and stock levels."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {
                        "type": "string",
                        "description": "Optional keyword to filter items by name.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_cart",
            "description": "Add an item to your shopping cart by its item_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "Item ID from list_items (e.g. 'item-001').",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of units to add. Must be >= 1.",
                        "minimum": 1,
                    },
                },
                "required": ["item_id", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "checkout",
            "description": (
                "Purchase all items currently in your cart. "
                "Returns an order confirmation with order_id and total."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]

# Lookup set for fast validation in the JSON fallback parser.
TOOL_NAMES: set[str] = {t["function"]["name"] for t in TOOL_DEFINITIONS}


def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    auth_token: str,
    base_url: str,
) -> tuple[int, str, float]:
    """
    Execute a tool against the target app over HTTP.
    Returns (http_status_code, response_body_text, latency_ms).

    In M2 this is replaced by the OpenAPI-generated adapter.
    """
    headers: dict[str, str] = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    t0 = time.perf_counter()
    try:
        if tool_name == "list_items":
            params = {}
            if arguments.get("search"):
                params["search"] = arguments["search"]
            r = requests.get(f"{base_url}/items", params=params, headers=headers, timeout=10)

        elif tool_name == "add_to_cart":
            r = requests.post(f"{base_url}/cart/add", json=arguments, headers=headers, timeout=10)

        elif tool_name == "checkout":
            r = requests.post(f"{base_url}/checkout", json={}, headers=headers, timeout=10)

        else:
            latency = (time.perf_counter() - t0) * 1000
            return 400, json.dumps({"error": f"unknown tool: {tool_name}"}), latency

        latency = (time.perf_counter() - t0) * 1000
        return r.status_code, r.text, latency

    except requests.RequestException as exc:
        latency = (time.perf_counter() - t0) * 1000
        return 503, json.dumps({"error": str(exc)}), latency

