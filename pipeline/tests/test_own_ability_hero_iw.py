"""L74 econ2 parity fix: a live frame with my Hero Ice Wizard must yield the TRAINING-style own-ability token
(ready_known 1, charges / cooldown from my own deploy + press history and the catalog), not 'readiness unknown'.
Run: icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_own_ability_hero_iw.py"""
import numpy as np

from pipeline.own_ability import ABILITY_COLS, catalog, observe, tokens

GID = {"ice-wizard": 62}
ME = 0


def frame(tick, hero=True):
    ents = [dict(side=ME, x=9000, y=8000, card_id=203000023, hp=700, max_hp=700, kind=15, address="0xa")] if hero else []
    ents.append(dict(side=1, x=9000, y=24000, card_id=26000000, hp=1400, max_hp=1400, kind=15, address="0xb"))
    return dict(game_tick=tick, entities=ents, projectiles=[], effects=[], players=[])


def row(tick, events, hero=True):
    return tokens(observe(frame(tick, hero), ME, "reader"), GID, events, tick)[0]


def test_catalog_has_hero_ice_wizard():
    spec = catalog()[("ice-wizard", 2)]
    assert spec["max_charges"] == 1 and spec["deploy_ms"] == 1000 and not spec.get("cooldown_ms")


def test_live_hero_frame_gives_training_style_token():
    assert observe(frame(100), ME, "reader") == [("ice-wizard", 2, 1, -1.0, 0.0)]
    deploy = [dict(card="ice-wizard", tick=100, side=ME, accepted=True, ability=False)]
    c = {k: i for i, k in enumerate(ABILITY_COLS)}
    r = row(110, deploy)                                   # deploying: not ready yet, 0.5 s to go (a training value)
    assert r[c["ready_known"]] == 1 and r[c["ready"]] == 0 and r[c["remaining_charges"]] == 1 and abs(r[c["cooldown_s"]] - .5) < 1e-6
    assert list(row(150, deploy)) == [62, 2, 1, 1, 1, 1, 0]          # ready, one charge
    press = deploy + [dict(card="IceWizard", tick=200, side=ME, accepted=True, ability=True)]   # live record_ability name
    assert list(row(210, press)) == [62, 2, 1, 0, 1, 0, 0]           # the one charge is spent


def test_public_observer_live_path():
    """The live pilot's path: PublicObserver.update(reader frame) + own_events (GenPilot.record_play / record_ability)."""
    from pipeline.public_observation import PublicObserver
    obs = PublicObserver(ME)
    for t in (90, 100, 150):
        obs.update(frame(t), source="reader")
    obs.own_events.append(dict(card="ice-wizard", tick=95, side=ME, accepted=True, ability=False))
    oa = obs.features(150, GID)["own_ability"]
    assert list(oa[0]) == [62, 2, 1, 1, 1, 1, 0] and not np.any(oa[1:])


def test_unknown_without_own_history_and_no_hero_unchanged():
    r = row(150, [])
    assert r[4] == 0 and r[5] == -1 and r[6] == -1                   # no deploy seen: stays explicitly unknown (contract)
    assert not np.any(tokens(observe(frame(150, hero=False), ME, "reader"), GID, [], 150))
