"""
tools.py — M1 hardcoded tool definitions and executor.

In M2 these definitions are replaced by auto-generated ones from openapi.json.
The execute_tool() function is also replaced by the OpenAPI-driven adapter.
Both are kept behind the same interface so agent.py does not change.
"""

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
) -> tuple[int | None, str, float]:
    """Legacy M1 entry point delegated to the canonical OpenAPI executor."""
    from pathlib import Path

    from adapters.openapi import OpenAPIAdapter

    if tool_name not in TOOL_NAMES:
        raise ValueError(f"unknown M1 tool: {tool_name}")
    adapter = OpenAPIAdapter(Path(__file__).parent.parent / "openapi.json", base_url)
    return adapter.execute_tool(tool_name, arguments, auth_token)
