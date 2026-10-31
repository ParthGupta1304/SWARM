"""Explicit scripted fallback: real Bazaar actions/replay, synthetic model decisions.

This is never AI-discovery evidence. It needs no credential or external service.
"""

import json
import re
import socket
import threading
import time
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request

app = FastAPI(title="Scripted demo provider — not AI")


@app.post("/v1/chat/completions")
async def completion(request: Request):
    body = await request.json()
    tools = body.get("tools", [])
    names = {tool["function"]["name"] for tool in tools}
    count = sum(message["role"] == "tool" for message in body["messages"])
    for message in body["messages"]:
        content = message.get("content") or ""
        if content.startswith("Actor state: "):
            count = json.loads(content.split(": ", 1)[1])["completed_actions"]
    match = re.search(r"Role: ([^.]+)", body["messages"][0]["content"]) if tools else None
    role = match.group(1) if match else ""

    def orders():
        # Prefer the latest account-scoped observation over earlier tool history.
        for message in reversed(body["messages"]):
            content = message.get("content") or ""
            if content.startswith("Local memory: "):
                memory = json.loads(content.split(": ", 1)[1])
                for entry in reversed(memory["observations"]):
                    event = entry["value"]
                    result = event.get("result")
                    if event.get("operation") == "checkout" and isinstance(result, dict):
                        return [{"id": result["order_id"], "buyer_id": event["request"]["user_id"]}]
            if message["role"] == "user" and message.get("content", "").startswith(
                "Recent marketplace observations: "
            ):
                for event in json.loads(message["content"].split(": ", 1)[1]):
                    result = event.get("result")
                    if event.get("operation") == "checkout" and isinstance(result, dict):
                        return [{"id": result["order_id"], "buyer_id": event["request"]["user_id"]}]
            if message["role"] == "tool":
                try:
                    value = json.loads(message["content"])
                except (ValueError, TypeError):
                    continue
                if (
                    isinstance(value, list)
                    and value
                    and isinstance(value[0], dict)
                    and "buyer_id" in value[0]
                ):
                    return value
                if isinstance(value, dict) and "order_id" in value:
                    return [{"id": value["order_id"], "buyer_id": 4}]
        return []

    tool, args = "list_items", {}
    if role in ["casual_buyer", "impatient_clicker"]:
        tool, args = [
            ("add_to_cart", {"item_id": 1, "quantity": 1}),
            ("checkout", {"race_delay_ms": 100}),
            ("list_items", {"q": "["}),
            ("checkout", {}),
            ("add_to_cart", {"item_id": 2, "quantity": -1}),
            ("list_items", {}),
        ][min(count, 5)]
    elif role == "bargain_hunter":
        tool, args = "apply_coupon", {"code": "SWARM20", "race_delay_ms": 100}
    elif role == "sock_puppet" and "fulfil_order" in names:
        pending = [order for order in orders() if order["buyer_id"] == 5]
        tool, args = (
            ("block_user", {"blocked_id": 6})
            if count == 0
            else (
                ("fulfil_order", {"order_id": pending[0]["id"]}) if pending else ("list_sales", {})
            )
        )
    elif role == "sock_puppet":
        tool, args = [
            ("add_to_cart", {"item_id": 2, "quantity": 1}),
            ("checkout", {}),
            ("list_orders", {}),
            ("list_orders", {}),
            ("create_review", {"item_id": 2, "rating": 5}),
            ("list_orders", {}),
        ][min(count, 5)]
    elif role == "fraudster" and "request_refund" in names:
        owned = [order for order in orders() if order["buyer_id"] == 4]
        tool, args = [
            ("add_to_cart", {"item_id": 3, "quantity": 1}),
            ("checkout", {}),
            ("list_orders", {}),
        ][min(count, 2)]
        if count >= 3 and owned:
            tool, args = "request_refund", {"order_id": owned[0]["id"], "race_delay_ms": 100}
    elif role == "fraudster":
        owned = [order for order in orders() if order["buyer_id"] == 4]
        tool, args = (
            ("open_dispute", {"order_id": owned[0]["id"], "race_delay_ms": 100})
            if count >= 3 and owned
            else ("list_orders", {})
        )
    elif role == "troll":
        tool, args = (
            ("list_items", {})
            if count == 0
            else ("ask_question", {"item_id": 1, "body": "Hello, can you contact me?"})
        )
    message = {"role": "assistant", "content": "Earlier scripted actions summarized."}
    if tools:
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "fixture-" + uuid4().hex,
                    "type": "function",
                    "function": {"name": tool, "arguments": json.dumps(args)},
                }
            ],
        }
    return {
        "id": "scripted-" + uuid4().hex,
        "object": "chat.completion",
        "created": 1,
        "model": "scripted-fixture",
        "choices": [
            {"index": 0, "message": message, "finish_reason": "tool_calls" if tools else "stop"}
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
    }


class ScriptedProvider:
    def __enter__(self):
        self.socket = socket.socket()
        self.socket.bind(("127.0.0.1", 0))
        self.url = f"http://127.0.0.1:{self.socket.getsockname()[1]}/v1"
        self.server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        self.thread = threading.Thread(
            target=lambda: self.server.run(sockets=[self.socket]), daemon=True
        )
        self.thread.start()
        for _ in range(100):
            if self.server.started:
                return self
            time.sleep(0.05)
        self.__exit__()
        raise RuntimeError("Scripted fallback provider did not start")

    def __exit__(self, *_):
        self.server.should_exit = True
        self.thread.join(timeout=10)
        self.socket.close()
