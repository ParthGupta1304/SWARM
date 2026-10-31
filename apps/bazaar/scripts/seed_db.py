from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from bazaar.database import Base, SessionLocal, engine
from bazaar.models import Coupon, Item, User


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Bazaar with deterministic synthetic data.")
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    random.seed(args.seed)
    fixture_file = Path("seed_data.json")
    if not fixture_file.exists():
        fixture_file = Path(__file__).resolve().parent.parent / "seed_data.json"
    fixture = json.loads(fixture_file.read_text())
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal.begin() as db:
        users = {handle: User(handle=handle) for handle in fixture["users"]}
        db.add_all(users.values())
        db.flush()
        for raw_item in fixture["items"]:
            db.add(Item(
                seller_id=users[raw_item["seller"]].id,
                title=raw_item["title"],
                price_cents=raw_item["price_cents"],
                inventory=raw_item["inventory"],
                initial_inventory=raw_item["inventory"],
            ))
        db.add(Coupon(**fixture["coupon"]))
    print(f"Seeded Bazaar with seed={args.seed}")


if __name__ == "__main__":
    main()
