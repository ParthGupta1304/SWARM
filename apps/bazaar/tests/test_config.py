from bazaar.config import BUG_IDS, load_settings


def test_bug_catalog_is_frozen_to_the_eight_prd_bugs(monkeypatch):
    monkeypatch.setenv("BAZAAR_VERSION", "v1")
    assert set(BUG_IDS.values()) == {"E1", "E2", "E4", "E5", "E7", "S1", "S2", "S4"}
    assert all(load_settings().bugs.values())


def test_v2_fixes_only_the_announced_phase_two_bugs(monkeypatch):
    monkeypatch.setenv("BAZAAR_VERSION", "v2")
    bugs = load_settings().bugs
    assert not bugs["oversell_race"]
    assert not bugs["coupon_stacking"]
    assert bugs["double_payout"]
