"""opp_elixir_count: accounting (regen, cap, phases, re-base) and detection on hand-built reader frames."""
import pytest

from pipeline import opp_elixir_count as oc

# --- accounting -------------------------------------------------------------------------------------------


def test_start_and_single_regen():
    c = oc.OppElixirCounter()
    assert c.at(0) == pytest.approx(6.0)
    assert c.at(10) == pytest.approx(6.178)            # corpus_v6 first frame, every replay
    assert c.at(206) == pytest.approx(9.6668)          # live probe1.jsonl side 0 elixir_raw 96668


def test_cap_loses_regen():
    c = oc.OppElixirCounter()
    assert c.at(1000) == 10.0
    c.play(1000, "knight", 3)
    assert c.at(1100) == pytest.approx(7.0 + 100 * 0.0178)   # regen banked while capped is gone


def test_phase_rates_and_boundaries():
    assert oc.regen_between(2390, 2410) == pytest.approx(10 * 0.0178 + 10 * 0.0357)
    assert oc.regen_between(4790, 4810) == pytest.approx(10 * 0.0357 + 10 * 0.0537)
    assert oc.regen_between(6010, 6100) == 0.0
    c = oc.OppElixirCounter()
    c.play(2400, "golem", 8)                           # 10 -> 2 at the start of double elixir
    assert c.at(2428) == pytest.approx(2.0 + 28 * 0.0357)


def test_unaffordable_play_rebases_up():
    c = oc.OppElixirCounter()
    c.play(0, "golem", 8)                              # estimate 6 < 8: the estimate was low
    assert c.rebases == 1 and c.rebase_total == pytest.approx(2.0)
    assert c.at(0) == pytest.approx(0.0)
    c.play(0, "mirror", None)                          # no fixed cost: recorded, not charged
    assert c.at(0) == pytest.approx(0.0) and len(c.plays) == 2


# --- detection --------------------------------------------------------------------------------------------
KNIGHT, SKELETONS, WITCH, GOLEM, PHOENIX, HUT = 26000000, 26000010, 26000007, 26000009, 26000087, 27000001


def ent(addr, side, cid, kind=14, hp=100, x=9000, y=20000):
    return {"address": addr, "category": 0, "kind": kind, "side": side, "x": x, "y": y, "card_id": cid,
            "level": 11, "hp": hp, "max_hp": hp}


def frame(tick, ents, elixir=(0, 0)):
    towers = [ent(f"0xt{s}{k}", s, -1, kind=k, hp=1000) for s in (0, 1) for k in (12, 13)]
    return {"battle_active": True, "game_tick": tick, "entities": towers + ents,
            "players": [{"side": 0, "elixir_raw": elixir[0], "hand_deck_indices": [-1] * 4},
                        {"side": 1, "elixir_raw": elixir[1], "hand_deck_indices": [0, 1, 2, 3]}]}


def test_catalog_ids_used_below():
    names = oc._catalog_names()
    assert [names[i] for i in (KNIGHT, SKELETONS, WITCH, GOLEM, PHOENIX, HUT)] == [
        "Knight", "Skeletons", "Witch", "Golem", "Phoenix", "GoblinHut"]


def test_new_address_is_one_play_and_charged_once():
    d = oc.PlayDetector()
    (ev,) = d.feed(frame(100, [ent("0xa", 0, KNIGHT)]))
    assert (ev.tick, ev.key, ev.cost) == (100, "knight", 3.0)
    assert d.feed(frame(102, [ent("0xa", 0, KNIGHT, kind=15)])) == []


def test_swarm_is_one_play():
    d = oc.PlayDetector()
    evs = d.feed(frame(100, [ent("0xs1", 0, SKELETONS, hp=81), ent("0xs2", 0, SKELETONS, hp=81)]))
    evs += d.feed(frame(102, [ent("0xs3", 0, SKELETONS, hp=81)]))
    assert len(evs) == 1 and evs[0].n_bodies == 3 and evs[0].cost == 1.0
    # the same card again after the window (corpus minimum re-play gap is 112 ticks) is a new play
    assert len(d.feed(frame(215, [ent("0xs4", 0, SKELETONS, hp=81)]))) == 1


def test_late_first_sight_still_charged():
    """F1: a body first seen after its deploy kind ended (troop 15, building 13) is still a play."""
    d = oc.PlayDetector()
    assert [e.key for e in d.feed(frame(100, [ent("0xk", 0, KNIGHT, kind=15)]))] == ["knight"]
    assert [e.key for e in d.feed(frame(200, [ent("0xh", 0, HUT, kind=13, hp=1180)]))] == ["goblin_hut"]


def test_spawn_of_live_parent_not_charged():
    d = oc.PlayDetector()
    w = ent("0xw", 0, WITCH, hp=839)
    # witch arrives with her first skeletons (Witch card id, hp 81) in the same frame: one play
    assert len(d.feed(frame(100, [w, ent("0xw0", 0, WITCH, hp=81)]))) == 1
    # a later wave, even in a deploying kind: a higher-hp Witch body is on the board -> spawn
    assert d.feed(frame(300, [w, ent("0xw1", 0, WITCH, kind=14, hp=81)])) == []
    # golem dies between frames and golemites appear: the golem was on the board last frame -> spawn
    g = ent("0xg", 0, GOLEM, hp=5120)
    assert len(d.feed(frame(400, [w, g]))) == 1 and d.feed(frame(880, [w, g])) == []
    assert d.feed(frame(900, [w, ent("0xg1", 0, GOLEM, hp=1039), ent("0xg2", 0, GOLEM, hp=1039)])) == []
    # a 3 s reader gap swallows a second golem's death: its golemites are still a spawn
    g2 = ent("0xh2", 0, GOLEM, hp=5120, x=4000)
    assert len(d.feed(frame(950, [w, g2]))) == 1 and d.feed(frame(1100, [w, g2])) == []
    assert d.feed(frame(1200, [w, ent("0xg3", 0, GOLEM, hp=1039, x=4000)])) == []
    # phoenix egg (lower hp) dies and the reborn phoenix appears beside it -> death spawn, not a play
    p = ent("0xp", 0, PHOENIX, hp=1052, x=5000)
    assert len(d.feed(frame(2000, [p]))) == 1 and d.feed(frame(2150, [p])) == []
    assert d.feed(frame(2160, [ent("0xe", 0, PHOENIX, hp=317, x=5000)])) == []
    assert d.feed(frame(2220, [ent("0xp2", 0, PHOENIX, kind=15, hp=1052, x=5300)])) == []
    # the witch's max_hp becomes unreadable (-1): her next wave is still a spawn
    wu = ent("0xw", 0, WITCH, hp=-1)
    assert d.feed(frame(2300, [wu])) == [] and d.feed(frame(2320, [wu, ent("0xw3", 0, WITCH, hp=81)])) == []
    # a second Witch cast while the first is alive IS a play
    assert len(d.feed(frame(2500, [w, ent("0xw2", 0, WITCH, hp=839, x=3000)]))) == 1
    assert d.spawns == 7


def test_late_hut_then_waves_charged_once():
    """F2: hut first seen late (kind 13) together with its first wave; neither that wave nor later ones
    (whose hp was never a play reference) are charged."""
    d = oc.PlayDetector()
    hut = ent("0xh", 0, HUT, kind=13, hp=1180)
    evs = d.feed(frame(500, [hut, ent("0xg1", 0, HUT, kind=15, hp=133)]))
    assert [(e.key, e.cost, e.n_bodies) for e in evs] == [("goblin_hut", 4.0, 2)]
    for t in (600, 700, 800):
        assert d.feed(frame(t, [hut, ent(f"0xg{t}", 0, HUT, kind=14, hp=133)])) == []
    # hut first seen late WITHOUT a wave, then waves
    d = oc.PlayDetector()
    assert len(d.feed(frame(500, [hut]))) == 1
    assert d.feed(frame(640, [hut, ent("0xg9", 0, HUT, kind=14, hp=133)])) == []   # past the swarm window


class NoElixir(dict):
    """A player block that fails the test if anyone reads elixir_raw."""

    def __getitem__(self, k):
        assert k != "elixir_raw", "detection read elixir_raw"
        return super().__getitem__(k)

    def get(self, k, default=None):
        assert k != "elixir_raw", "detection read elixir_raw"
        return super().get(k, default)


def test_my_side_and_towers_ignored_and_elixir_never_read():
    live = oc.LiveOppElixir()
    f = frame(100, [ent("0xm", 1, KNIGHT), ent("0xo", 0, SKELETONS, hp=81)])
    f["players"] = [NoElixir(p) for p in f["players"]]
    assert live.update(f) == pytest.approx(6.0 + 100 * 0.0178 - 1)    # only the opponent's skeletons
    assert live.detector.my_side == 1 and [p[1] for p in live.counter.plays] == ["skeletons"]


def test_live_wrapper():
    live = oc.LiveOppElixir()
    assert live.update(frame(100, [ent("0xa", 0, KNIGHT)])) == pytest.approx(6.0 + 100 * 0.0178 - 3)


def test_live_tolerates_no_visible_hand_and_resets():
    """F6: frames without a visible hand are skipped; tick going back or a new battle object resets."""
    live = oc.LiveOppElixir()
    f0 = frame(50, [ent("0xa", 0, KNIGHT)])
    for p in f0["players"]:
        p["hand_deck_indices"] = [-1] * 4
    assert live.update(f0) == pytest.approx(6.0 + 50 * 0.0178) and live.counter.plays == []
    live.update(frame(100, [ent("0xa", 0, KNIGHT)]))
    assert [p[1] for p in live.counter.plays] == ["knight"]
    assert live.update(frame(10, [])) == pytest.approx(6.178)          # tick went back: new match
    assert live.counter.plays == [] and live.detector.seen == set()
    f1, f2 = frame(200, [ent("0xb", 0, KNIGHT)]), frame(210, [])
    f1["chain"], f2["chain"] = {"battle": "0x1"}, {"battle": "0x2"}
    live.update(f1)
    assert len(live.counter.plays) == 1
    assert live.update(f2) == pytest.approx(6.0 + 210 * 0.0178) and live.counter.plays == []
    live.reset()
    assert live.counter.tick == 0 and live.battle is None
