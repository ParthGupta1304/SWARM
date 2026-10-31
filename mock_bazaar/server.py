# Mock Bazaar stub for M1/M2 testing.
# Runs on port 8001 so it does not clash with real Bazaar (port 8000).
# Tracks users, carts, orders, and refunds in memory.

from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import uuid

app = FastAPI(title="Mock Bazaar", version="0.2")

# ── In-memory state ──────────────────────────────────────────────────────────
users: dict[str, dict] = {}   # username → {password, user_id}
tokens: dict[str, str] = {}   # token    → user_id
carts: dict[str, list] = {}   # user_id  → [{item_id, quantity, name, price}]
orders: list[dict] = []       # list of orders
refunds: list[dict] = []      # list of refund requests

ITEMS = [
    {"item_id": "item-001", "name": "Vintage Lamp", "price": 25.00, "stock": 5},
    {"item_id": "item-002", "name": "Wooden Chair", "price": 45.00, "stock": 3},
    {"item_id": "item-003", "name": "Coffee Mug",   "price":  8.00, "stock": 10},
    {"item_id": "item-004", "name": "Wall Clock",   "price": 15.00, "stock": 2},
    {"item_id": "item-005", "name": "Desk Lamp",    "price": 30.00, "stock": 7},
]

# ── Auth helpers ─────────────────────────────────────────────────────────────
def get_user_id(authorization: str = Header(default="")) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    user_id = tokens.get(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user_id

# ── Request models ────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class AddToCartRequest(BaseModel):
    item_id: str
    quantity: int

class RefundRequest(BaseModel):
    order_id: str
    reason: str

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.post("/register", status_code=201, operation_id="register", summary="Register a new user")
def register(req: RegisterRequest):
    if req.username in users:
        raise HTTPException(status_code=409, detail="Username already taken")
    user_id = str(uuid.uuid4())[:8]
    users[req.username] = {"password": req.password, "user_id": user_id}
    carts[user_id] = []
    return {"user_id": user_id, "message": "registered"}

@app.post("/login", operation_id="login", summary="Login with username and password")
def login(req: LoginRequest):
    user = users.get(req.username)
    if not user or user["password"] != req.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = str(uuid.uuid4())
    tokens[token] = user["user_id"]
    return {"token": token}

@app.get("/items", operation_id="list_items", summary="List marketplace items")
def list_items(search: Optional[str] = None):
    results = ITEMS
    if search:
        results = [i for i in ITEMS if search.lower() in i["name"].lower()]
    return {"items": results}

@app.post("/cart/add", operation_id="add_to_cart", summary="Add an item to the shopping cart")
def add_to_cart(req: AddToCartRequest, user_id: str = Depends(get_user_id)):
    item = next((i for i in ITEMS if i["item_id"] == req.item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if req.quantity < 1:
        raise HTTPException(status_code=400, detail="Quantity must be >= 1")
    carts[user_id].append({
        "item_id": req.item_id,
        "quantity": req.quantity,
        "name": item["name"],
        "price": item["price"],
    })
    return {
        "message": f"Added {req.quantity}x {item['name']} to cart",
        "cart_size": len(carts[user_id]),
    }

@app.post("/checkout", operation_id="checkout", summary="Checkout current cart")
def checkout(user_id: str = Depends(get_user_id)):
    cart = carts.get(user_id, [])
    if not cart:
        raise HTTPException(status_code=400, detail="Cart is empty")
    total = sum(i["price"] * i["quantity"] for i in cart)
    order_id = str(uuid.uuid4())[:8]
    orders.append({"order_id": order_id, "user_id": user_id, "items": cart, "total": total})
    carts[user_id] = []
    return {"order_id": order_id, "total": round(total, 2), "message": "Order placed successfully"}

@app.post("/refunds/request", operation_id="request_refund", summary="Request a refund for an order")
def request_refund(req: RefundRequest, user_id: str = Depends(get_user_id)):
    order = next((o for o in orders if o["order_id"] == req.order_id and o["user_id"] == user_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found for this user")
    refund_id = str(uuid.uuid4())[:8]
    refund_entry = {"refund_id": refund_id, "order_id": req.order_id, "user_id": user_id, "reason": req.reason, "status": "pending"}
    refunds.append(refund_entry)
    return {"refund_id": refund_id, "status": "pending", "message": "Refund request submitted"}

@app.get("/health", operation_id="health", summary="Healthcheck endpoint")
def health():
    return {"status": "ok", "users": len(users), "orders": len(orders), "refunds": len(refunds)}
