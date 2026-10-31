"""Atomic deterministic resets for explicitly disposable Bazaar databases."""

import json
import random
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from .database import Base
from .models import Coupon, Item, User


def seed_database(database_url: str, seed: int, fixture_path: str | Path | None = None) -> None:
    fixture = json.loads(
        Path(fixture_path or Path(__file__).parent.parent / "seed_data.json").read_text()
    )
    rng = random.Random(seed)
    target = create_engine(database_url)
    preserved = {"wire_findings", "run_telemetry", "findings"}
    try:
        Base.metadata.create_all(target)
        # Keep table definitions and published reports. Readers see either the
        # previous or next fixture snapshot; dashboards never see missing tables.
        with target.begin() as connection:
            cleared = [
                table
                for table in reversed(Base.metadata.sorted_tables)
                if table.name not in preserved
            ]
            for table in cleared:
                connection.execute(table.delete())
            if connection.dialect.name == "postgresql":
                for table in cleared:
                    if "id" not in table.c:
                        continue
                    sequence = connection.execute(
                        text("SELECT pg_get_serial_sequence(:table_name, 'id')"),
                        {"table_name": table.name},
                    ).scalar()
                    if sequence:
                        quoted = ".".join(
                            connection.dialect.identifier_preparer.quote(part)
                            for part in sequence.split(".")
                        )
                        connection.exec_driver_sql(f"ALTER SEQUENCE {quoted} RESTART WITH 1")
            with Session(bind=connection) as db:
                users = {
                    handle: User(
                        handle=handle,
                        owner_key=("alice_seller" if handle == "erin_sockpuppet" else handle),
                    )
                    for handle in fixture["users"]
                }
                db.add_all(users.values())
                db.flush()
                for raw in fixture["items"]:
                    db.add(
                        Item(
                            seller_id=users[raw["seller"]].id,
                            title=raw["title"],
                            price_cents=raw["price_cents"] + rng.randrange(500),
                            inventory=raw["inventory"],
                            initial_inventory=raw["inventory"],
                        )
                    )
                db.add(Coupon(**fixture["coupon"]))
                db.commit()
    finally:
        target.dispose()
