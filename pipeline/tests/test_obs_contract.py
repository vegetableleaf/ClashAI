"""Tests for the shared observation contract (spec section 4). unittest-style so they run without pytest:
``icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_obs_contract -v`` (pytest also collects them).
Nothing here runs the detector, the engine, or the game -- only yaml / json data files."""
from __future__ import annotations

import glob
import json
import sys
import unittest
from pathlib import Path

import numpy as np
import yaml

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import obs_contract as oc  # noqa: E402
from pipeline import vocab  # noqa: E402

ICEBOW = REPO / "icebow"
ENGINE_DECK = ["Tesla@evolution", "Knight@evolution", "Xbow", "IceWizard", "Skeletons", "Log", "Rocket", "Tornado"]


def _clashrl():
    """icebow's clashrl (for Detection / CardDB); skipped where its deps are missing."""
    src = str(ICEBOW / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    import clashrl  # noqa: F401
    return clashrl


# ------------------------------------------------------------------------------------------------------
# synthetic engine board (side 0 = me): 5 units both sides incl. one flyer, one spell effect, towers with
# partial hp, elixir 6.37, hand of 4 deck cards. Engine units: 1000 per tile, y up from MY back wall.
# ------------------------------------------------------------------------------------------------------
UNITS = [  # (side, x, y, name, hp, max_hp, kind)
    (0, 4000, 9000, "Knight", 1000, 1400, 15),
    (0, 8000, 10500, "Xbow", 1600, 1600, 13),
    (0, 5000, 13000, "Skeletons", 81, 81, 14),
    (1, 14000, 20000, "HogRider", 1200, 1697, 15),
    (1, 13000, 22000, "BabyDragon", 900, 1100, 15),     # the flyer
]
EFFECTS = [(0, 14000, 25000, "Rocket")]
TOWERS = [  # (side, type, lane, x, y, hp, max_hp)
    (0, "king", None, 9000, 3000, 4824, 4824),
    (0, "princess", "left", 3500, 6500, 2000, 3052),
    (0, "princess", "right", 14500, 6500, 3052, 3052),
    (1, "king", None, 9000, 29000, 4824, 4824),
    (1, "princess", "left", 3500, 25500, 500, 3052),
    (1, "princess", "right", 14500, 25500, 3052, 3052),
]
TICK = 1200
HAND = ["Tesla", "Knight", "Xbow", "IceWizard"]
FLYERS = {"BabyDragon"}


def raw_obs(my_side: int = 0) -> dict:
    """observe()-shaped dict (env.py:187-255 keys). my_side=1 gives the SAME board seen from side 1:
    coordinates mirrored, sides swapped, so both must produce an identical BoardState."""
    def m(side, x, y):
        return ((1 - side), 18000 - x, 32000 - y) if my_side == 1 else (side, x, y)
    ents = []
    for i, (s, x, y, name, hp, mhp, kind) in enumerate(UNITS):
        s, x, y = m(s, x, y)
        ents.append({"side": s, "x": x, "y": y, "card_id": 26000000 + i, "name": name, "hp": hp, "max_hp": mhp,
                     "kind": kind, "category": 5000000 + i, "entity_id": 5000000 + i})
    for (s, typ, lane, x, y, hp, mhp) in TOWERS:                 # crown towers ALSO appear as card_id -1 entities
        s, x, y = m(s, x, y)
        ents.append({"side": s, "x": x, "y": y, "card_id": -1, "hp": hp, "max_hp": mhp, "kind": 12 if typ == "king" else 13})
    towers = []
    for (s, typ, lane, x, y, hp, mhp) in TOWERS:
        s, x, y = m(s, x, y)
        towers.append({"side": s, "type": typ, "lane": lane, "x": x, "y": y, "hp": hp, "max_hp": mhp, "destroyed": hp <= 0})
    effects = []
    for (s, x, y, name) in EFFECTS:
        s, x, y = m(s, x, y)
        effects.append({"side": s, "x": x, "y": y, "card_id": 28000003, "name": name})
    me = {"side": my_side, "elixir": 6.37, "elixir_raw": 63700, "elixir_exact": 6.37,
          "hand_deck_indices": [0, 1, 2, 3], "cycle_deck_indices": [4, 5, 6, 7], "next_deck_index": 4,
          "hand": [{"hand_index": i, "deck_index": i, "card_id": 0, "level": 11, "name": n} for i, n in enumerate(HAND)]}
    them = {"side": 1 - my_side, "elixir": 3.0, "elixir_raw": 30000, "elixir_exact": 3.0,
            "hand_deck_indices": [0, 1, 2, 3], "cycle_deck_indices": [4, 5, 6, 7], "next_deck_index": 4, "hand": []}
    return {"tick": TICK, "elapsed_seconds": TICK * 0.05, "coherent": True,
            "players": [me, them] if my_side == 0 else [them, me],
            "entities": ents, "projectiles": [], "effects": effects,
            "episode": {"terminated": False, "crowns": [0, 0], "crown_towers": towers}}


def frame_obs() -> dict:
    """The list-encoded record_full frame of the same board (replay_drive.py:317-330 layout)."""
    return {"tick": TICK, "elixir": [6.37, 3.0],
            "entities": [list(u) for u in UNITS] + [[s, x, y, "-1", hp, mhp, 12] for (s, _t, _l, x, y, hp, mhp) in TOWERS],
            "towers": [list(t) for t in TOWERS],
            "projectiles": [], "effects": [list(e) for e in EFFECTS],
            "players": [{"side": 0, "elixir": 6.37, "hand": HAND, "hand_pos": [0, 1, 2, 3], "cycle_pos": [4, 5, 6, 7], "next": 4},
                        {"side": 1, "elixir": 3.0, "hand": [], "hand_pos": [], "cycle_pos": [], "next": 0}]}


class TestVocab(unittest.TestCase):
    def test_detector_classes_match_yaml(self):
        cls = yaml.safe_load((ICEBOW / "config" / "detect_classes.yaml").read_text(encoding="utf-8"))["classes"]
        self.assertEqual(list(vocab.DETECTOR_CLASSES), list(cls))
        self.assertEqual(vocab.N_DETECTOR, 230)
        self.assertEqual(vocab.unit_id("spirit_empress_air"), 230)

    def test_spell_and_building_sets_match_kb(self):
        try:
            _clashrl()
            from clashrl import card_threat
            from clashrl.cards import CardDB
        except Exception as e:                            # pragma: no cover
            self.skipTest(f"clashrl not importable: {e}")
        db = CardDB(path=ICEBOW / "config" / "cards.yaml")
        kinds = {c: db.kind(card_threat.base_key(c)) for c in vocab.DETECTOR_CLASSES}
        self.assertEqual({c for c, k in kinds.items() if k == "spell"}, set(vocab.SPELL_CLASSES))
        self.assertEqual({c for c, k in kinds.items() if k == "building"}, set(vocab.BUILDING_CLASSES))
        self.assertEqual(len(vocab.SPELL_CLASSES), 46)
        self.assertEqual(len(vocab.AOE_CLASSES), 20)
        for c in vocab.DETECTOR_CLASSES:                  # base_key mirrors card_threat.base_key
            self.assertEqual(vocab.base_key(c), card_threat.base_key(c))

    def test_engine_names(self):
        self.assertEqual(vocab.engine_unit_id("Xbow"), vocab.unit_id("x_bow"))
        self.assertEqual(vocab.engine_unit_id("Log"), vocab.unit_id("the_log"))
        self.assertEqual(vocab.engine_unit_id("Tesla@evolution"), vocab.unit_id("tesla"))
        self.assertEqual(vocab.engine_unit_id("MergeMaiden_Mounted"), vocab.unit_id("spirit_empress_air"))
        self.assertIsNone(vocab.engine_unit_id("-1"))
        self.assertIsNone(vocab.engine_unit_id("CHAR_DISABLED_1"))
        # sub-spawns: measured max_hp values (obs_contract_impl.md)
        self.assertEqual(vocab.engine_unit_id("Golem", 5120), vocab.unit_id("golem"))
        self.assertEqual(vocab.engine_unit_id("Golem", 1039), vocab.unit_id("golemite"))
        self.assertEqual(vocab.engine_unit_id("LavaHound", 3581), vocab.unit_id("lava_hound"))
        self.assertEqual(vocab.engine_unit_id("LavaHound", 215), vocab.unit_id("lava_pups"))
        self.assertEqual(vocab.engine_unit_id("ElixirGolem", 1569), vocab.unit_id("elixir_golem"))
        self.assertEqual(vocab.engine_unit_id("ElixirGolem", 762), vocab.unit_id("elixir_golemite"))
        self.assertEqual(vocab.engine_unit_id("ElixirGolem", 360), vocab.unit_id("elixir_blob"))
        self.assertEqual(vocab.engine_unit_id("RoyalRecruits", 547), vocab.unit_id("royal_recruit"))
        self.assertEqual(vocab.engine_unit_id("WitchMother", 529), vocab.unit_id("mother_witch"))
        # spawn-spell bodies carry the spell's name in the engine (measured hp values)
        self.assertEqual(vocab.engine_unit_id("BarbLog", 716), vocab.unit_id("barbarians"))
        self.assertEqual(vocab.engine_unit_id("Graveyard", 81), vocab.unit_id("skeletons"))
        self.assertEqual(vocab.engine_unit_id("GoblinBarrel", 202), vocab.unit_id("goblins"))
        self.assertEqual(vocab.engine_unit_id("RoyalDelivery", 547), vocab.unit_id("royal_recruit"))
        self.assertEqual(vocab.engine_unit_id("Graveyard"), vocab.unit_id("graveyard"))   # a card name, no body
        # effects -> the _aoe class when the detector has one; unit attacks / tower shots are not spells
        self.assertEqual(vocab.engine_spell_id("Rocket"), vocab.unit_id("rocket_aoe"))
        self.assertEqual(vocab.engine_spell_id("Log"), vocab.unit_id("the_log_aoe"))
        self.assertEqual(vocab.engine_spell_id("Mirror"), vocab.unit_id("mirror"))
        self.assertIsNone(vocab.engine_spell_id("Xbow"))
        self.assertIsNone(vocab.engine_spell_id("-1"))
        self.assertTrue(vocab.is_spell(vocab.unit_id("rocket_aoe")))
        self.assertFalse(vocab.is_spell(vocab.unit_id("knight")))

    def test_every_in_use_catalog_card_maps(self):
        p = REPO / "research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json"
        if not p.exists():
            self.skipTest("catalog not on disk")
        cards = json.loads(p.read_text(encoding="utf-8"))["cards"]
        inuse = [c for c in cards if c.get("standard_1v1") and not c.get("not_in_use") and not c.get("not_visible")]
        self.assertEqual(len(inuse), 122)
        missing = [c["display_name"] for c in inuse if vocab.engine_unit_id(c["display_name"]) is None]
        self.assertEqual(missing, [])
        allmiss = sorted(c["display_name"] for c in cards if vocab.engine_unit_id(c["display_name"]) is None)
        self.assertTrue(all(n.startswith("CHAR_DISABLED") for n in allmiss), allmiss)


class TestDecks(unittest.TestCase):
    def test_decks_load(self):
        for name, first in (("icebow", "tornado"), ("hogeq", "hog_rider")):
            d = oc.load_deck(name)
            self.assertEqual(len(d.cards), 8)
            self.assertEqual(d.cards[0], first)
            self.assertTrue(d.config.exists(), d.config)
            self.assertTrue((d.src_dir / "clashrl" / "actions.py").exists())
        ice = oc.load_deck("icebow")
        self.assertEqual(set(ice.cards), {"tesla_evo", "knight_evo", "x_bow", "ice_wizard", "skeletons", "the_log",
                                          "rocket", "tornado"})
        self.assertEqual(ice.card_id_of("tesla"), vocab.unit_id("tesla_evo"))      # base-key match
        self.assertEqual(ice.card_id_of("tesla_evo"), vocab.unit_id("tesla_evo"))
        self.assertEqual(ice.card_id_of("hog_rider"), -1)
        self.assertEqual(ice.slot_of(None), -1)


class TestGeometry(unittest.TestCase):
    """Spec test 3 + the y-convention statement: me at the BOTTOM = ny near 1; my king row ny = 0.90625."""

    def test_engine_xy_convention(self):
        self.assertAlmostEqual(oc.MY_KING_Y, 0.90625)
        self.assertEqual(oc._engine_xy(9000, 3000, False), (0.5, oc.MY_KING_Y))
        self.assertEqual(oc._engine_xy(3500, 6500, False), (oc.PRINCESS_X_L, oc.MY_PRINCESS_Y))
        self.assertEqual(oc._engine_xy(9000, 29000, False), (0.5, oc.OPP_KING_Y))
        # the same physical tower seen from side 1 lands on the same board point
        self.assertEqual(oc._engine_xy(18000 - 9000, 32000 - 3000, True), (0.5, oc.MY_KING_Y))
        self.assertEqual(oc._engine_xy(18000 - 3500, 32000 - 6500, True), (oc.PRINCESS_X_L, oc.MY_PRINCESS_Y))

    def test_towers_land_on_frame_anchors(self):
        deck = oc.load_deck("icebow")
        try:
            warp = oc.board_warp(deck)
        except Exception as e:                            # pragma: no cover
            self.skipTest(f"BoardWarp import failed: {e}")
        self.assertTrue(warp.ok)
        cfg = yaml.safe_load(deck.config.read_text(encoding="utf-8"))
        my, en = cfg["env"]["my_towers"], cfg["env"]["enemy_towers"]
        # side-0 king (9000, 3000) -> bottom-centre of the frame = the config's my_towers king anchor
        fx, fy = warp.board_to_frame(*oc._engine_xy(9000, 3000, False))
        self.assertAlmostEqual(fx, (my[2][0] + en[2][0]) / 2, places=6)
        self.assertAlmostEqual(fy, my[2][1], places=6)
        self.assertGreater(fy, 0.5)                       # bottom half of the screen
        self.assertAlmostEqual(fx, 0.5, delta=0.01)
        # princess towers -> documented lanes: my L (3500, 6500), my R (14500, 6500), enemy L/R
        fx, fy = warp.board_to_frame(*oc._engine_xy(3500, 6500, False))
        self.assertAlmostEqual(fx, (my[0][0] + en[0][0]) / 2, places=6)
        self.assertAlmostEqual(fy, (my[0][1] + my[1][1]) / 2, places=6)
        fx, fy = warp.board_to_frame(*oc._engine_xy(14500, 6500, False))
        self.assertAlmostEqual(fx, (my[1][0] + en[1][0]) / 2, places=6)
        fx, fy = warp.board_to_frame(*oc._engine_xy(3500, 25500, False))
        self.assertAlmostEqual(fy, (en[0][1] + en[1][1]) / 2, places=6)
        self.assertLess(fy, 0.5)
        # the river sits at board 0.5 <-> the measured frame line
        self.assertAlmostEqual(warp.board_to_frame(0.5, 0.5)[1], cfg["env"]["board_edges"]["river"], places=6)


class TestEngineAdapter(unittest.TestCase):
    def setUp(self):
        self.deck = oc.load_deck("icebow")

    def test_raw_dict(self):
        bs = oc.from_engine(raw_obs(0), 0, self.deck, engine_deck=ENGINE_DECK)
        self.assertEqual(bs.source, "engine")
        self.assertEqual(bs.t_source, "tick")
        self.assertAlmostEqual(bs.t_sec, 60.0)
        self.assertFalse(bs.double_elixir)
        self.assertAlmostEqual(bs.my_elixir, 6.37)
        self.assertTrue(bs.my_elixir_exact)
        self.assertAlmostEqual(bs.opp_elixir, 3.0)
        self.assertEqual(bs.my_hand, tuple(self.deck.card_id_of(n) for n in ("tesla", "knight", "x_bow", "ice_wizard")))
        self.assertEqual(bs.my_next, vocab.unit_id("skeletons"))
        self.assertEqual(len(bs.units), 5)                # towers (card_id -1) dropped
        self.assertEqual(len(bs.spells), 1)
        self.assertEqual(bs.spells[0].cls, vocab.unit_id("rocket_aoe"))
        self.assertEqual([t.kind for t in bs.towers], ["king", "princess", "princess"] * 2)
        self.assertEqual([t.lane for t in bs.towers], [None, "L", "R"] * 2)
        self.assertEqual([t.side for t in bs.towers], [0, 0, 0, 1, 1, 1])
        self.assertAlmostEqual(bs.towers[1].hp_frac, 2000 / 3052)
        self.assertAlmostEqual(bs.towers[4].hp_frac, 500 / 3052)
        self.assertTrue(all(t.alive for t in bs.towers))
        k = bs.units[0]
        self.assertEqual((k.cls, k.side), (vocab.unit_id("knight"), 0))
        self.assertAlmostEqual(k.x, 4000 / 18000)
        self.assertAlmostEqual(k.y, 1 - 9000 / 32000)
        self.assertAlmostEqual(k.hp_frac, 1000 / 1400)
        self.assertFalse(k.deploying)
        self.assertTrue(bs.units[2].deploying)            # kind 14
        self.assertIsNone(k.age_sec)
        self.assertEqual(bs.deck, self.deck.card_ids)

    def test_history_gives_age(self):
        hist: dict = {}
        oc.from_engine(raw_obs(0), 0, self.deck, history=hist)
        o2 = raw_obs(0)
        o2["tick"] = TICK + 40
        bs = oc.from_engine(o2, 0, self.deck, history=hist)
        self.assertTrue(all(abs(u.age_sec - 2.0) < 1e-9 for u in bs.units))

    def test_frame_form_equals_raw(self):
        a = oc.from_engine(raw_obs(0), 0, self.deck, engine_deck=ENGINE_DECK)
        b = oc.from_engine(frame_obs(), 0, self.deck, engine_deck=ENGINE_DECK)
        self.assertEqual(a, b)

    def test_mirror(self):
        """Spec test 2: the same board given as side 1 (coordinates mirrored) -> identical BoardState."""
        a = oc.from_engine(raw_obs(0), 0, self.deck, engine_deck=ENGINE_DECK)
        b = oc.from_engine(raw_obs(1), 1, self.deck, engine_deck=ENGINE_DECK)
        self.assertEqual(a, b)

    def test_destroyed_tower_and_unmapped(self):
        o = raw_obs(0)
        o["episode"]["crown_towers"] = [t for t in o["episode"]["crown_towers"] if not (t["side"] == 1 and t["lane"] == "left")]
        o["entities"].append({"side": 1, "x": 9000, "y": 20000, "card_id": 999, "name": "CHAR_DISABLED_1", "hp": 5, "max_hp": 5, "kind": 15})
        with self.assertRaises(oc.UnmappedName):
            oc.from_engine(o, 0, self.deck)
        um: set = set()
        bs = oc.from_engine(o, 0, self.deck, unmapped=um)
        self.assertEqual(um, {"CHAR_DISABLED_1"})
        self.assertFalse(bs.towers[4].alive)
        self.assertEqual(bs.towers[4].hp_frac, 0.0)
        self.assertEqual(bs.my_next, -1)                  # no engine_deck -> next unknown
        # phase flags from tick
        o["tick"] = 3700
        bs = oc.from_engine(o, 0, self.deck, unmapped=um)
        self.assertTrue(bs.double_elixir and bs.overtime)

    def test_real_engine_frames(self):
        """Spec test 4: every frame of one recorded file -> 0 unmapped names, all coordinates in [0, 1]."""
        files = sorted(glob.glob(str(REPO / "scratchpad/gauntlet/ext/batch_v2/replay_*.json")))
        files = files or sorted(glob.glob(str(REPO / "scratchpad/gauntlet/ext/replay_*.json")))
        if not files:
            self.skipTest("no recorded engine frames on disk")
        rec = json.loads(Path(files[0]).read_text(encoding="utf-8"))
        decks = rec.get("final_decks") or {}
        my_side = next((int(s) for s, d in decks.items() if any(str(n).startswith("Xbow") for n in d)), 0)
        um: set = set()
        n = 0
        for key in ("frames", "play_frames"):
            for fr in rec.get(key) or []:
                bs = oc.from_engine(fr, my_side, self.deck, engine_deck=decks.get(str(my_side)), unmapped=um)
                n += 1
                for u in bs.units + bs.spells:
                    self.assertTrue(0.0 <= u.x <= 1.0 and 0.0 <= u.y <= 1.0, (Path(files[0]).name, fr["tick"], u))
                    self.assertIn(u.side, (0, 1))
                self.assertEqual(len(bs.towers), 6)
        if um:
            print("UNMAPPED engine names:", sorted(um))
        self.assertEqual(um, set(), f"unmapped engine names in {Path(files[0]).name}: {sorted(um)}")
        self.assertGreater(n, 0)
        # the icebow side's hand resolves to deck cards on a play frame that carries players
        pf = next((f for f in rec.get("play_frames") or [] if f.get("players")), None)
        if pf is not None:
            bs = oc.from_engine(pf, my_side, self.deck, engine_deck=decks.get(str(my_side)))
            self.assertNotIn(-1, bs.my_hand)
            self.assertNotEqual(bs.my_next, -1)


class TestLiveAdapter(unittest.TestCase):
    """Spec test 1: the synthetic pair. Detections are placed by BoardWarp's FORWARD map on the engine tiles
    (frame = board_to_frame(board)); the adapter must bring them back to the same board points."""

    def setUp(self):
        self.deck = oc.load_deck("icebow")
        try:
            _clashrl()
            from clashrl.replay_mine import Detection
            self.Detection = Detection
            self.warp = oc.board_warp(self.deck)
        except Exception as e:                            # pragma: no cover
            self.skipTest(f"clashrl not importable in this interpreter: {e}")

    def detections(self):
        cls_of = {"Knight": "knight", "Xbow": "x_bow", "Skeletons": "skeletons", "HogRider": "hog_rider",
                  "BabyDragon": "baby_dragon", "Rocket": "rocket_aoe"}
        dets = []
        for (s, x, y, name, hp, mhp, kind) in UNITS:
            fx, fy = self.warp.board_to_frame(*oc._engine_xy(x, y, False))
            if name in FLYERS:                            # sprite drawn above the shadow: cy high, ground_cy = true y
                dets.append(self.Detection(cls_of[name], fx, fy - 0.045, 0.05, 0.05, 0.8, "enemy" if s else "mine", ground_cy=fy))
            else:
                dets.append(self.Detection(cls_of[name], fx, fy, 0.05, 0.05, 0.9, "enemy" if s else "mine"))
        for (s, x, y, name) in EFFECTS:
            fx, fy = self.warp.board_to_frame(*oc._engine_xy(x, y, False))
            dets.append(self.Detection(cls_of[name], fx, fy, 0.1, 0.1, 0.7, "mine"))
        return dets

    def reads(self):
        return oc.LiveReads(elixir_int=6, hand_names=("tesla", "knight_evo", "x_bow", "ice_wizard"), next_name="skeletons",
                            tower_hp=(None, 2000 / 3052, 3052 / 3052, None, 500 / 3052, 1.0), t_sec=60.0, t_source="clock")

    def test_pair(self):
        eng = oc.from_engine(raw_obs(0), 0, self.deck, engine_deck=ENGINE_DECK)
        live = oc.from_live(self.detections(), self.reads(), self.deck)
        self.assertEqual(live.source, "live")
        self.assertEqual(len(live.units), len(eng.units))
        self.assertEqual(len(live.spells), len(eng.spells))
        for a, b in zip(eng.units + eng.spells, live.units + live.spells):
            self.assertEqual(a.cls, b.cls)
            self.assertEqual(a.side, b.side)
            self.assertLessEqual(abs(a.x - b.x), 0.5 / 18)
            self.assertLessEqual(abs(a.y - b.y), 0.5 / 32)
            self.assertIsNone(b.hp_frac)
            self.assertIsNone(b.deploying)
            self.assertLess(b.conf, 1.0)
        for ta, tb in zip(eng.towers, live.towers):
            self.assertEqual((ta.alive, ta.kind, ta.lane, ta.side), (tb.alive, tb.kind, tb.lane, tb.side))
        self.assertAlmostEqual(eng.my_elixir, 6.37)
        self.assertEqual(live.my_elixir, 6.0)
        self.assertFalse(live.my_elixir_exact)
        self.assertIsNone(live.opp_elixir)
        self.assertEqual(eng.my_hand, live.my_hand)
        self.assertEqual(eng.my_next, live.my_next)
        self.assertIsNone(live.towers[0].hp_frac)         # king hp never printed live
        self.assertTrue(live.towers[0].alive)

    def test_unknown_team_kept(self):
        d = self.detections()[0]
        d.team = "unknown"
        live = oc.from_live([d], self.reads(), self.deck)
        self.assertEqual(len(live.units), 1)
        self.assertEqual(live.units[0].side, -1)


class TestDegrade(unittest.TestCase):
    """Spec test 5: deterministic under a seed; over 2,000 draws on a 10-unit board keeps 0.855 +- 0.02 and
    adds (1 - 0.886) / 0.886 +- 0.02 false positives per kept unit."""

    def board(self):
        deck = oc.load_deck("icebow")
        o = raw_obs(0)
        extra = [(0, 3000, 8000, "IceWizard", 500, 590, 15), (0, 6000, 7000, "Tesla", 1000, 1200, 13),
                 (1, 5000, 24000, "Musketeer", 600, 720, 15), (1, 12000, 26000, "Cannon", 700, 800, 13),
                 (1, 9000, 21000, "Minions", 190, 190, 15)]
        for i, (s, x, y, name, hp, mhp, kind) in enumerate(extra):
            o["entities"].append({"side": s, "x": x, "y": y, "card_id": 100 + i, "name": name, "hp": hp, "max_hp": mhp, "kind": kind})
        bs = oc.from_engine(o, 0, deck, engine_deck=ENGINE_DECK)
        self.assertEqual(len(bs.units), 10)
        return bs

    def test_deterministic(self):
        bs = self.board()
        a = oc.degrade(bs, np.random.default_rng(7), pos_sigma_tiles=0.3, unknown_team_rate=0.05)
        b = oc.degrade(bs, np.random.default_rng(7), pos_sigma_tiles=0.3, unknown_team_rate=0.05)
        self.assertEqual(a, b)
        self.assertEqual(a.source, "degraded")
        self.assertEqual(a.t_source, "clock")
        self.assertEqual(a.my_elixir, 6.0)
        self.assertFalse(a.my_elixir_exact)
        self.assertIsNone(a.opp_elixir)
        self.assertIsNone(a.towers[0].hp_frac)
        self.assertIsNotNone(a.towers[1].hp_frac)
        for u in a.units:
            self.assertIsNone(u.hp_frac)
            self.assertIsNone(u.deploying)
            self.assertIsNone(u.age_sec)
            self.assertTrue(0.0 <= u.x <= 1.0 and 0.0 <= u.y <= 1.0)

    def test_rates(self):
        bs = self.board()
        rng = np.random.default_rng(123)
        kept = fps = 0
        for _ in range(2000):
            d = oc.degrade(bs, rng)
            n = len(d.units)
            # a false positive is a duplicate: same kind, jittered; count = tokens beyond the kept originals.
            # Kept originals have conf drawn but keep their exact position; FPs sit >= ~1 tile away.
            orig = {(u.x, u.y) for u in bs.units}
            k = sum(1 for u in d.units if (u.x, u.y) in orig)
            kept += k
            fps += n - k
        recall = kept / (2000 * 10)
        fp_per_kept = fps / kept
        self.assertAlmostEqual(recall, 0.855, delta=0.02)
        self.assertAlmostEqual(fp_per_kept, (1 - 0.886) / 0.886, delta=0.02)


class TestTokens(unittest.TestCase):
    """Spec test 6: shapes + mask; a 70-unit board truncates to 64 by the documented rule (nearest the river)."""

    def test_shapes(self):
        deck = oc.load_deck("icebow")
        bs = oc.from_engine(raw_obs(0), 0, deck, engine_deck=ENGINE_DECK)
        toks, mask, sc = oc.to_tokens(bs)
        self.assertEqual(toks.shape, (64, oc.F))
        self.assertEqual(mask.shape, (64,))
        self.assertEqual(sc.shape, (oc.S,))
        self.assertEqual((toks.dtype, mask.dtype, sc.dtype), (np.float32, np.bool_, np.float32))
        self.assertEqual(int(mask.sum()), 6)              # 5 units + 1 spell
        self.assertEqual(oc.F, 14)
        self.assertEqual(oc.S, 70)
        spell_rows = toks[mask][:, 13]
        self.assertEqual(int(spell_rows.sum()), 1)
        self.assertAlmostEqual(float(sc[0]), 60 / 300, places=6)
        self.assertAlmostEqual(float(sc[3]), 0.637, places=6)
        self.assertEqual(float(sc[4]), 1.0)               # exact elixir
        self.assertEqual(float(sc[6]), 1.0)               # opp known
        hand = sc[7:43].reshape(4, 9)
        self.assertTrue((hand.sum(axis=1) == 1).all())
        self.assertEqual([int(np.argmax(r)) for r in hand], [deck.slot_of("tesla"), deck.slot_of("knight"),
                                                              deck.slot_of("x_bow"), deck.slot_of("ice_wizard")])
        self.assertEqual(int(np.argmax(sc[43:52])), deck.slot_of("skeletons"))
        self.assertEqual(list(sc[52 + 6:52 + 12]), [1.0] * 6)   # hp known x6 (engine)
        self.assertEqual(list(sc[64:70]), [1.0] * 6)             # alive x6
        # cls column carries the vocab id as a float
        self.assertEqual(int(toks[mask][:, 0].max()), max(u.cls for u in bs.units + bs.spells))
        # unknown hand slot -> the 9th bucket
        bs2 = oc.BoardState(**{**bs.__dict__, "my_hand": (-1, -1, -1, -1), "my_next": -1})
        _, _, sc2 = oc.to_tokens(bs2)
        self.assertEqual([int(np.argmax(r)) for r in sc2[7:43].reshape(4, 9)], [8] * 4)

    def test_truncation_rule(self):
        deck = oc.load_deck("icebow")
        base = oc.from_engine(raw_obs(0), 0, deck, engine_deck=ENGINE_DECK)
        rng = np.random.default_rng(0)
        units = tuple(oc.Unit(vocab.unit_id("knight"), int(i % 2), float(rng.random()), float(rng.random()), 1.0, False, None, 1.0)
                      for i in range(70))
        bs = oc.BoardState(**{**base.__dict__, "units": units, "spells": ()})
        toks, mask, _ = oc.to_tokens(bs, max_units=64)
        self.assertEqual(int(mask.sum()), 64)
        kept_d = sorted(abs(y - 0.5) for y in toks[:, 5])
        all_d = sorted(abs(u.y - 0.5) for u in units)
        np.testing.assert_allclose(np.asarray(kept_d, dtype=np.float64), np.asarray(all_d[:64]), atol=1e-6)  # tokens are float32
        self.assertTrue((np.diff(np.abs(toks[:, 5] - 0.5)) >= -1e-7).all())   # emitted in rank order


if __name__ == "__main__":
    unittest.main(verbosity=2)
