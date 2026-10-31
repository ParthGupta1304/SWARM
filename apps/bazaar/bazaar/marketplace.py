"""Synthetic marketplace user flows; all routes share the planted-bug database."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .database import get_db
from .models import (
    Block,
    CartItem,
    Item,
    ItemQuestion,
    ListingReport,
    Message,
    Order,
    OrderLine,
    Review,
    User,
)

router = APIRouter()
Db = Annotated[Session, Depends(get_db, scope="function")]


class Account(BaseModel):
    handle: str = Field(min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


class Listing(BaseModel):
    seller_id: int
    title: str = Field(min_length=3, max_length=160)
    price_cents: int = Field(gt=0)
    inventory: int = Field(gt=0, le=10000)


class Fulfilment(BaseModel):
    seller_id: int


class DirectMessage(BaseModel):
    sender_id: int
    recipient_id: int
    body: str = Field(min_length=1, max_length=1000)


class Report(BaseModel):
    reporter_id: int
    reason: str = Field(min_length=3, max_length=300)


class CartRemoval(BaseModel):
    user_id: int


@router.post("/api/cart/items/{item_id}/remove", operation_id="remove_from_cart")
def remove_from_cart(item_id: int, payload: CartRemoval, db: Db):
    line = db.scalar(
        select(CartItem).where(CartItem.user_id == payload.user_id, CartItem.item_id == item_id)
    )
    if line is None:
        raise HTTPException(404, "This item is not in your bag")
    db.delete(line)
    return {"removed": True}


def require(db, model, identifier):
    row = db.get(model, identifier)
    if row is None:
        raise HTTPException(404, "Resource not found")
    return row


@router.post("/api/users", operation_id="create_user")
def create_user(payload: Account, db: Db):
    if db.scalar(select(User).where(User.handle == payload.handle)):
        raise HTTPException(409, "This handle is already registered")
    user = User(handle=payload.handle, owner_key=payload.handle)
    db.add(user)
    db.flush()
    return user


@router.post("/api/items", operation_id="create_listing")
def create_listing(payload: Listing, db: Db):
    require(db, User, payload.seller_id)
    item = Item(**payload.model_dump(), initial_inventory=payload.inventory)
    db.add(item)
    db.flush()
    return item


@router.get("/api/items/{item_id}", operation_id="get_item")
def get_item(item_id: int, db: Db):
    item = require(db, Item, item_id)
    return {
        "item": item,
        "reviews": list(db.scalars(select(Review).where(Review.item_id == item_id))),
        "questions": [
            {
                "id": q.id,
                "item_id": q.item_id,
                "author_id": q.author_id,
                "body": q.body,
                "created_at": q.created_at,
            }
            for q in db.scalars(select(ItemQuestion).where(ItemQuestion.item_id == item_id))
        ],
    }


@router.get("/api/sellers/{seller_id}/orders", operation_id="list_sales")
def list_sales(seller_id: int, db: Db):
    return list(
        db.scalars(
            select(Order).join(OrderLine).join(Item).where(Item.seller_id == seller_id).distinct()
        )
    )


@router.post("/api/orders/{order_id}/fulfil", operation_id="fulfil_order")
def fulfil_order(order_id: int, payload: Fulfilment, db: Db):
    order = require(db, Order, order_id)
    sellers = set(
        db.scalars(select(Item.seller_id).join(OrderLine).where(OrderLine.order_id == order_id))
    )
    if sellers != {payload.seller_id}:
        raise HTTPException(403, "Only the seller can fulfil this order")
    order.status = "fulfilled"
    return {"order_id": order.id, "status": order.status}


@router.post("/api/messages", operation_id="send_message")
def send_message(payload: DirectMessage, db: Db):
    require(db, User, payload.sender_id)
    require(db, User, payload.recipient_id)
    blocked = db.scalar(
        select(Block).where(
            Block.blocker_id == payload.recipient_id, Block.blocked_id == payload.sender_id
        )
    )
    if blocked:
        raise HTTPException(403, "This user has blocked direct messages from you")
    message = Message(**payload.model_dump())
    db.add(message)
    db.flush()
    return message


@router.get("/api/users/{user_id}/messages", operation_id="list_messages")
def list_messages(user_id: int, db: Db):
    return list(
        db.scalars(
            select(Message)
            .where(or_(Message.sender_id == user_id, Message.recipient_id == user_id))
            .order_by(Message.id)
        )
    )


@router.post("/api/items/{item_id}/reports", operation_id="report_listing")
def report_listing(item_id: int, payload: Report, db: Db):
    require(db, Item, item_id)
    require(db, User, payload.reporter_id)
    report = ListingReport(item_id=item_id, **payload.model_dump())
    db.add(report)
    db.flush()
    return {"report_id": report.id, "status": "received"}
