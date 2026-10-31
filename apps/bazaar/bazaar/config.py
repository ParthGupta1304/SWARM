from __future__ import annotations

import json
import os
from dataclasses import dataclass


BUG_IDS = {
    "oversell_race": "E1",
    "coupon_stacking": "E2",
    "double_payout": "E4",
    "self_dealing": "E5",
    "block_bypass_question": "E7",
    "empty_cart_500": "S1",
    "negative_cart_quantity": "S2",
    "search_special_char_500": "S4",
}


@dataclass(frozen=True)
class Settings:
    database_url: str
    version: str
    bugs: dict[str, bool]


def load_settings() -> Settings:
    version = os.getenv("BAZAAR_VERSION", "v1")
    # v2 fixes the two Phase 2 regression checks requested by the PRD.
    bugs = {name: True for name in BUG_IDS}
    if version == "v2":
        bugs.update({"oversell_race": False, "coupon_stacking": False})
    overrides = json.loads(os.getenv("BAZAAR_BUG_OVERRIDES", "{}"))
    for name, value in overrides.items():
        if name not in bugs:
            raise ValueError(f"Unknown Bazaar feature flag: {name}")
        bugs[name] = bool(value)
    return Settings(
        database_url=os.getenv(
            "DATABASE_URL", "sqlite:///bazaar_local.db"
        ),
        version=version,
        bugs=bugs,
    )
