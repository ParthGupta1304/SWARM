from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from detect.contracts import Finding as CanonicalFinding

from .config import BUG_IDS
from .database import Base, SessionLocal, engine, get_db, settings
from .models import (
    ActivityEvent,
    Block,
    CartItem,
    Coupon,
    CouponRedemption,
    Finding,
    Item,
    ItemQuestion,
    Order,
    OrderLine,
    Payout,
    RequestError,
    Review,
    RunTelemetry,
    User,
    WireFinding,
)

Db = Annotated[Session, Depends(get_db, scope="function")]


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Bazaar API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def capture_application_errors(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        # Metadata only: do not persist credentials, bodies or raw tracebacks.
        error_class = type(exc).__name__[:100]

        def persist():
            with SessionLocal.begin() as db:
                db.add(
                    RequestError(
                        action_key=request.headers.get("x-swarm-action", "")[:160],
                        method=request.method,
                        path=request.url.path[:300],
                        error_class=error_class,
                    )
                )

        await asyncio.to_thread(persist)
        return JSONResponse({"error": type(exc).__name__}, status_code=500)


class CartRequest(BaseModel):
    user_id: int
    item_id: int
    quantity: int


class CheckoutRequest(BaseModel):
    user_id: int
    race_delay_ms: int = Field(default=0, ge=0, le=2_000)


class CouponRequest(BaseModel):
    user_id: int
    code: str
    race_delay_ms: int = Field(default=75, ge=0, le=2000)


class PayoutRequest(BaseModel):
    user_id: int
    amount_cents: int | None = Field(default=None, gt=0)
    race_delay_ms: int = Field(default=75, ge=0, le=2000)


class BlockRequest(BaseModel):
    blocker_id: int
    blocked_id: int


class QuestionRequest(BaseModel):
    author_id: int
    body: str = Field(min_length=1, max_length=1_000)


class ReviewRequest(BaseModel):
    author_id: int
    rating: int = Field(ge=1, le=5)
    body: str = Field(default="", max_length=1_000)


class FindingRequest(BaseModel):
    bug_id: str
    title: str
    severity: str = "high"
    verified: bool = False
    evidence: dict = Field(default_factory=dict)


def emit(db: Session, event_type: str, actor_id: int | None, **payload: object) -> None:
    db.add(ActivityEvent(event_type=event_type, actor_id=actor_id, payload=payload))


def get_or_404(db: Session, model, id_: int):
    entity = db.get(model, id_)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} {id_} not found")
    return entity


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "version": settings.version, "bugs_enabled": settings.bugs}


@app.get("/api/users", operation_id="list_users")
def list_users(db: Db):
    return list(db.scalars(select(User).order_by(User.id)))


@app.get("/api/items", operation_id="list_items")
def list_items(q: str = Query(default=""), db: Db = None):
    if settings.bugs["search_special_char_500"] and q == "[":
        # S4: the narrow, deterministic special-character edge case.
        raise RuntimeError("Bazaar search parser crashed on '['")
    statement = select(Item).order_by(Item.id)
    if q:
        statement = statement.where(Item.title.ilike(f"%{q}%"))
    return list(db.scalars(statement))


@app.post("/api/cart/items", operation_id="add_to_cart")
def add_cart_item(payload: CartRequest, db: Db):
    get_or_404(db, User, payload.user_id)
    get_or_404(db, Item, payload.item_id)
    if not settings.bugs["negative_cart_quantity"] and payload.quantity <= 0:
        raise HTTPException(status_code=422, detail="quantity must be positive")
    cart_item = db.scalar(
        select(CartItem).where(
            CartItem.user_id == payload.user_id, CartItem.item_id == payload.item_id
        )
    )
    if cart_item:
        cart_item.quantity += payload.quantity
    else:
        cart_item = CartItem(**payload.model_dump())
        db.add(cart_item)
    emit(db, "cart_item_added", payload.user_id, item_id=payload.item_id, quantity=payload.quantity)
    return {"user_id": payload.user_id, "item_id": payload.item_id, "quantity": cart_item.quantity}


@app.get("/api/cart/{user_id}", operation_id="get_cart")
def get_cart(user_id: int, db: Db):
    return list(db.scalars(select(CartItem).where(CartItem.user_id == user_id)))


@app.post("/api/coupons/apply", operation_id="apply_coupon")
async def apply_coupon(payload: CouponRequest, db: Db):
    return await asyncio.to_thread(_apply_coupon, payload, db)


def _apply_coupon(payload: CouponRequest, db: Session):
    if not settings.bugs["coupon_stacking"] and engine.dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    statement = select(Coupon).where(Coupon.code == payload.code.upper())
    if not settings.bugs["coupon_stacking"]:
        statement = statement.with_for_update()
    coupon = db.scalar(statement)
    if coupon is None:
        raise HTTPException(status_code=404, detail="coupon not found")
    existing = db.scalar(
        select(CouponRedemption).where(
            CouponRedemption.user_id == payload.user_id, CouponRedemption.coupon_id == coupon.id
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="coupon already applied")
    time.sleep(payload.race_delay_ms / 1000)
    db.add(CouponRedemption(user_id=payload.user_id, coupon_id=coupon.id))
    emit(db, "coupon_applied", payload.user_id, coupon_id=coupon.id, code=coupon.code)
    db.commit()
    return {"code": coupon.code, "discount_cents": coupon.discount_cents}


@app.post("/api/checkout", operation_id="checkout")
async def checkout(payload: CheckoutRequest, db: Db):
    return await asyncio.to_thread(_checkout, payload, db)


def _checkout(payload: CheckoutRequest, db: Session):
    if not settings.bugs["oversell_race"] and engine.dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    cart = list(db.scalars(select(CartItem).where(CartItem.user_id == payload.user_id)))
    if not cart:
        if settings.bugs["empty_cart_500"]:
            # S1: intentionally preserve an unhandled path for baseline testing.
            raise RuntimeError("empty cart total is undefined")
        raise HTTPException(status_code=422, detail="cart is empty")

    line_data: list[tuple[Item, CartItem]] = []
    subtotal = 0
    for cart_item in cart:
        statement = select(Item).where(Item.id == cart_item.item_id)
        if not settings.bugs["oversell_race"]:
            statement = statement.with_for_update()
        item = db.scalar(statement)
        if item is None or item.inventory < cart_item.quantity:
            raise HTTPException(status_code=409, detail="insufficient inventory")
        line_data.append((item, cart_item))
        subtotal += item.price_cents * cart_item.quantity

    # E1: two sessions can both pass the stock check before writing inventory.
    if payload.race_delay_ms:
        time.sleep(payload.race_delay_ms / 1_000)

    discount = db.scalar(
        select(func.coalesce(func.sum(Coupon.discount_cents), 0))
        .select_from(CouponRedemption)
        .join(Coupon, Coupon.id == CouponRedemption.coupon_id)
        .where(CouponRedemption.user_id == payload.user_id)
    )
    total = max(0, subtotal - int(discount or 0))
    order = Order(buyer_id=payload.user_id, total_cents=total)
    db.add(order)
    db.flush()
    for item, cart_item in line_data:
        item.inventory -= cart_item.quantity
        db.add(
            OrderLine(
                order_id=order.id,
                item_id=item.id,
                quantity=cart_item.quantity,
                unit_price_cents=item.price_cents,
            )
        )
        db.delete(cart_item)
    emit(db, "checkout_completed", payload.user_id, order_id=order.id, total_cents=total)
    db.commit()
    return {"order_id": order.id, "total_cents": total, "status": order.status}


def issue_payout(
    db: Session,
    order_id: int,
    user_id: int,
    kind: str,
    amount_cents: int | None,
    race_delay_ms: int,
) -> dict:
    if not settings.bugs["double_payout"] and engine.dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    statement = select(Order).where(Order.id == order_id)
    if not settings.bugs["double_payout"]:
        statement = statement.with_for_update()
    order = db.scalar(statement)
    if order is None:
        raise HTTPException(404, "order not found")
    if order.buyer_id != user_id:
        raise HTTPException(status_code=403, detail="only the buyer can claim this payout")
    already_paid = db.scalar(select(Payout).where(Payout.order_id == order_id))
    if already_paid:
        raise HTTPException(status_code=409, detail="order already compensated")
    time.sleep(race_delay_ms / 1000)
    amount = amount_cents or order.total_cents
    payout = Payout(order_id=order_id, kind=kind, amount_cents=amount)
    db.add(payout)
    buyer = get_or_404(db, User, user_id)
    buyer.balance_cents += amount
    emit(db, f"{kind}_issued", user_id, order_id=order_id, amount_cents=amount)
    db.commit()
    return {"order_id": order_id, "kind": kind, "amount_cents": amount}


@app.get("/api/users/{user_id}/orders", operation_id="list_orders")
def list_orders(user_id: int, db: Db):
    return list(db.scalars(select(Order).where(Order.buyer_id == user_id).order_by(Order.id)))


@app.post("/api/orders/{order_id}/refund", operation_id="request_refund")
async def request_refund(order_id: int, payload: PayoutRequest, db: Db):
    return await asyncio.to_thread(
        issue_payout,
        db,
        order_id,
        payload.user_id,
        "refund",
        payload.amount_cents,
        payload.race_delay_ms,
    )


@app.post("/api/orders/{order_id}/disputes", operation_id="open_dispute")
async def open_dispute(order_id: int, payload: PayoutRequest, db: Db):
    return await asyncio.to_thread(
        issue_payout,
        db,
        order_id,
        payload.user_id,
        "dispute_credit",
        payload.amount_cents,
        payload.race_delay_ms,
    )


@app.post("/api/blocks", operation_id="block_user")
def block_user(payload: BlockRequest, db: Db):
    db.add(Block(**payload.model_dump()))
    emit(db, "user_blocked", payload.blocker_id, blocked_id=payload.blocked_id)
    return {"ok": True}


@app.post("/api/items/{item_id}/questions", operation_id="ask_question")
def ask_question(item_id: int, payload: QuestionRequest, db: Db):
    item = get_or_404(db, Item, item_id)
    is_blocked = db.scalar(
        select(Block).where(
            Block.blocker_id == item.seller_id, Block.blocked_id == payload.author_id
        )
    )
    if is_blocked and not settings.bugs["block_bypass_question"]:
        raise HTTPException(status_code=403, detail="buyer is blocked by this seller")
    question = ItemQuestion(item_id=item_id, **payload.model_dump())
    db.add(question)
    db.flush()
    emit(db, "item_question_created", payload.author_id, item_id=item_id, seller_id=item.seller_id)
    return {"question_id": question.id, "item_id": item_id}


@app.post("/api/items/{item_id}/reviews", operation_id="create_review")
def create_review(item_id: int, payload: ReviewRequest, db: Db):
    item = get_or_404(db, Item, item_id)
    author = get_or_404(db, User, payload.author_id)
    seller = get_or_404(db, User, item.seller_id)
    if author.owner_key == seller.owner_key and not settings.bugs["self_dealing"]:
        raise HTTPException(status_code=403, detail="sellers cannot review their own item")
    review = Review(item_id=item_id, **payload.model_dump())
    db.add(review)
    db.flush()
    item.rating = ((float(item.rating) * item.rating_count) + payload.rating) / (
        item.rating_count + 1
    )
    item.rating_count += 1
    emit(db, "review_created", payload.author_id, item_id=item_id, rating=payload.rating)
    return {"review_id": review.id, "item_id": item_id}


@app.get("/api/events", include_in_schema=False)
def list_events(after_id: int = 0, limit: int = Query(default=100, le=500), db: Db = None):
    return list(
        db.scalars(
            select(ActivityEvent)
            .where(ActivityEvent.id > after_id)
            .order_by(ActivityEvent.id)
            .limit(limit)
        )
    )


@app.get("/api/events/stream", include_in_schema=False)
async def stream_events(after_id: int = 0):
    async def event_generator():
        last_id = after_id
        while True:
            with Session(engine) as db:
                events = list(
                    db.scalars(
                        select(ActivityEvent)
                        .where(ActivityEvent.id > last_id)
                        .order_by(ActivityEvent.id)
                    )
                )
            for event in events:
                last_id = event.id
                body = {
                    "id": event.id,
                    "type": event.event_type,
                    "actor_id": event.actor_id,
                    "payload": event.payload,
                    "created_at": event.created_at.isoformat(),
                }
                yield f"event: activity\ndata: {json.dumps(body)}\n\n"
            yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/findings", include_in_schema=False)
def create_finding(payload: CanonicalFinding | FindingRequest, db: Db):
    if isinstance(payload, CanonicalFinding):
        current = db.get(WireFinding, payload.id)
        data = payload.model_dump(mode="json")
        if current:
            if current.payload != data:
                raise HTTPException(409, "finding ID already has a different payload")
            return current.payload
        db.add(
            WireFinding(
                id=payload.id, run_id=payload.run_id, verified=payload.verified, payload=data
            )
        )
        emit(db, "finding_created", None, finding=data)
        return data
    if payload.bug_id not in BUG_IDS.values():
        raise HTTPException(status_code=422, detail="unknown planted bug id")
    finding = Finding(**payload.model_dump())
    db.add(finding)
    db.flush()
    emit(
        db,
        "finding_created",
        None,
        bug_id=payload.bug_id,
        title=payload.title,
        verified=payload.verified,
    )
    return {"id": finding.id, **payload.model_dump()}


@app.get("/api/findings", include_in_schema=False)
def list_findings(db: Db):
    return [row.payload for row in db.scalars(select(WireFinding))] + list(
        db.scalars(select(Finding).order_by(Finding.created_at.desc()))
    )


@app.get("/api/dashboard/summary", include_in_schema=False)
def dashboard_summary(db: Db):
    return {
        "version": settings.version,
        "enabled_bugs": [BUG_IDS[name] for name, enabled in settings.bugs.items() if enabled],
        "events": db.scalar(select(func.count(ActivityEvent.id))) or 0,
        "findings": (db.scalar(select(func.count(Finding.id))) or 0)
        + (db.scalar(select(func.count(WireFinding.id))) or 0),
        "verified_findings": (
            db.scalar(select(func.count(Finding.id)).where(Finding.verified.is_(True))) or 0
        )
        + (
            db.scalar(select(func.count(WireFinding.id)).where(WireFinding.verified.is_(True))) or 0
        ),
    }


@app.post("/api/runs/telemetry", include_in_schema=False)
def update_telemetry(payload: dict, db: Db):
    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not 1 <= len(run_id) <= 80:
        raise HTTPException(422, "run_id required")
    # Accept only public aggregate fields, never provider config or credentials.
    allowed = {
        "run_id",
        "condition",
        "seed",
        "status",
        "round",
        "tokens_used",
        "token_budget",
        "cost_usd",
        "elapsed_s",
        "agents",
    }
    if set(payload) - allowed:
        raise HTTPException(422, "unknown telemetry fields")
    current = db.get(RunTelemetry, run_id)
    if current:
        current.payload = payload
    else:
        db.add(RunTelemetry(run_id=run_id, payload=payload))
    emit(db, "run_progress", None, run=payload)
    return {"ok": True}


@app.get("/api/runs", include_in_schema=False)
def list_runs(db: Db):
    return [run.payload for run in db.scalars(select(RunTelemetry))]
