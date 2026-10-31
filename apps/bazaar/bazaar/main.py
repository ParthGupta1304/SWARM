from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import BUG_IDS
from .database import Base, engine, get_db, settings
from .models import (
    ActivityEvent, Block, CartItem, Coupon, CouponRedemption, Finding, Item,
    ItemQuestion, Order, OrderLine, Payout, Review, User,
)

Db = Annotated[Session, Depends(get_db)]


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


class PayoutRequest(BaseModel):
    user_id: int
    amount_cents: int | None = Field(default=None, gt=0)


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


@app.get("/health")
def health():
    return {"status": "ok", "version": settings.version, "bugs_enabled": settings.bugs}


@app.get("/api/users")
def list_users(db: Db):
    return list(db.scalars(select(User).order_by(User.id)))


@app.get("/api/items")
def list_items(q: str = Query(default=""), db: Db = None):
    if settings.bugs["search_special_char_500"] and q == "[":
        # S4: the narrow, deterministic special-character edge case.
        raise RuntimeError("Bazaar search parser crashed on '['")
    statement = select(Item).order_by(Item.id)
    if q:
        statement = statement.where(Item.title.ilike(f"%{q}%"))
    return list(db.scalars(statement))


@app.post("/api/cart/items")
def add_cart_item(payload: CartRequest, db: Db):
    get_or_404(db, User, payload.user_id)
    get_or_404(db, Item, payload.item_id)
    if not settings.bugs["negative_cart_quantity"] and payload.quantity <= 0:
        raise HTTPException(status_code=422, detail="quantity must be positive")
    cart_item = db.scalar(select(CartItem).where(CartItem.user_id == payload.user_id, CartItem.item_id == payload.item_id))
    if cart_item:
        cart_item.quantity += payload.quantity
    else:
        cart_item = CartItem(**payload.model_dump())
        db.add(cart_item)
    emit(db, "cart_item_added", payload.user_id, item_id=payload.item_id, quantity=payload.quantity)
    return {"user_id": payload.user_id, "item_id": payload.item_id, "quantity": cart_item.quantity}


@app.get("/api/cart/{user_id}")
def get_cart(user_id: int, db: Db):
    return list(db.scalars(select(CartItem).where(CartItem.user_id == user_id)))


@app.post("/api/coupons/apply")
def apply_coupon(payload: CouponRequest, db: Db):
    coupon = db.scalar(select(Coupon).where(Coupon.code == payload.code.upper()))
    if coupon is None:
        raise HTTPException(status_code=404, detail="coupon not found")
    existing = db.scalar(select(CouponRedemption).where(CouponRedemption.user_id == payload.user_id, CouponRedemption.coupon_id == coupon.id))
    if existing and not settings.bugs["coupon_stacking"]:
        raise HTTPException(status_code=409, detail="coupon already applied")
    db.add(CouponRedemption(user_id=payload.user_id, coupon_id=coupon.id))
    emit(db, "coupon_applied", payload.user_id, coupon_id=coupon.id, code=coupon.code)
    return {"code": coupon.code, "discount_cents": coupon.discount_cents}


@app.post("/api/checkout")
async def checkout(payload: CheckoutRequest, db: Db):
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
        await asyncio.sleep(payload.race_delay_ms / 1_000)

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
        db.add(OrderLine(order_id=order.id, item_id=item.id, quantity=cart_item.quantity, unit_price_cents=item.price_cents))
        db.delete(cart_item)
    emit(db, "checkout_completed", payload.user_id, order_id=order.id, total_cents=total)
    return {"order_id": order.id, "total_cents": total, "status": order.status}


def issue_payout(db: Session, order_id: int, user_id: int, kind: str, amount_cents: int | None) -> dict:
    order = get_or_404(db, Order, order_id)
    if order.buyer_id != user_id:
        raise HTTPException(status_code=403, detail="only the buyer can claim this payout")
    already_paid = db.scalar(select(Payout).where(Payout.order_id == order_id))
    if already_paid and not settings.bugs["double_payout"]:
        raise HTTPException(status_code=409, detail="order already compensated")
    amount = amount_cents or order.total_cents
    payout = Payout(order_id=order_id, kind=kind, amount_cents=amount)
    db.add(payout)
    buyer = get_or_404(db, User, user_id)
    buyer.balance_cents += amount
    emit(db, f"{kind}_issued", user_id, order_id=order_id, amount_cents=amount)
    return {"order_id": order_id, "kind": kind, "amount_cents": amount}


@app.post("/api/orders/{order_id}/refund")
def request_refund(order_id: int, payload: PayoutRequest, db: Db):
    return issue_payout(db, order_id, payload.user_id, "refund", payload.amount_cents)


@app.post("/api/orders/{order_id}/disputes")
def open_dispute(order_id: int, payload: PayoutRequest, db: Db):
    return issue_payout(db, order_id, payload.user_id, "dispute_credit", payload.amount_cents)


@app.post("/api/blocks")
def block_user(payload: BlockRequest, db: Db):
    db.add(Block(**payload.model_dump()))
    emit(db, "user_blocked", payload.blocker_id, blocked_id=payload.blocked_id)
    return {"ok": True}


@app.post("/api/items/{item_id}/questions")
def ask_question(item_id: int, payload: QuestionRequest, db: Db):
    item = get_or_404(db, Item, item_id)
    is_blocked = db.scalar(select(Block).where(Block.blocker_id == item.seller_id, Block.blocked_id == payload.author_id))
    if is_blocked and not settings.bugs["block_bypass_question"]:
        raise HTTPException(status_code=403, detail="buyer is blocked by this seller")
    question = ItemQuestion(item_id=item_id, **payload.model_dump())
    db.add(question)
    db.flush()
    emit(db, "item_question_created", payload.author_id, item_id=item_id, seller_id=item.seller_id)
    return {"question_id": question.id, "item_id": item_id}


@app.post("/api/items/{item_id}/reviews")
def create_review(item_id: int, payload: ReviewRequest, db: Db):
    item = get_or_404(db, Item, item_id)
    if item.seller_id == payload.author_id and not settings.bugs["self_dealing"]:
        raise HTTPException(status_code=403, detail="sellers cannot review their own item")
    review = Review(item_id=item_id, **payload.model_dump())
    db.add(review)
    db.flush()
    item.rating = ((float(item.rating) * item.rating_count) + payload.rating) / (item.rating_count + 1)
    item.rating_count += 1
    emit(db, "review_created", payload.author_id, item_id=item_id, rating=payload.rating)
    return {"review_id": review.id, "item_id": item_id}


@app.get("/api/events")
def list_events(after_id: int = 0, limit: int = Query(default=100, le=500), db: Db = None):
    return list(db.scalars(select(ActivityEvent).where(ActivityEvent.id > after_id).order_by(ActivityEvent.id).limit(limit)))


@app.get("/api/events/stream")
async def stream_events(after_id: int = 0):
    async def event_generator():
        last_id = after_id
        while True:
            with Session(engine) as db:
                events = list(db.scalars(select(ActivityEvent).where(ActivityEvent.id > last_id).order_by(ActivityEvent.id)))
            for event in events:
                last_id = event.id
                body = {"id": event.id, "type": event.event_type, "actor_id": event.actor_id, "payload": event.payload, "created_at": event.created_at.isoformat()}
                yield f"event: activity\\ndata: {json.dumps(body)}\\n\\n"
            yield ": heartbeat\\n\\n"
            await asyncio.sleep(1)
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/findings")
def create_finding(payload: FindingRequest, db: Db):
    if payload.bug_id not in BUG_IDS.values():
        raise HTTPException(status_code=422, detail="unknown planted bug id")
    finding = Finding(**payload.model_dump())
    db.add(finding)
    db.flush()
    emit(db, "finding_created", None, bug_id=payload.bug_id, title=payload.title, verified=payload.verified)
    return {"id": finding.id, **payload.model_dump()}


@app.get("/api/findings")
def list_findings(db: Db):
    return list(db.scalars(select(Finding).order_by(Finding.created_at.desc())))


@app.get("/api/dashboard/summary")
def dashboard_summary(db: Db):
    return {
        "version": settings.version,
        "enabled_bugs": [BUG_IDS[name] for name, enabled in settings.bugs.items() if enabled],
        "events": db.scalar(select(func.count(ActivityEvent.id))) or 0,
        "findings": db.scalar(select(func.count(Finding.id))) or 0,
        "verified_findings": db.scalar(select(func.count(Finding.id)).where(Finding.verified.is_(True))) or 0,
    }
