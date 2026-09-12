"""Offline tests for E1 option B tooling (pipeline/e1_view.py, e1_pool.py, e1_eval.py, e1_score.py).

    icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_e1_baseline -v

No engine, no GPU, no training. The split test reads the frozen pool v1 files when they exist (skipped otherwise).
The live-rule parity test runs the REAL ``icebow/src/clashrl/student_live.StudentPolicy.decide`` on the same states
and the same (small, randomly initialised) S1Model as ``e1_eval.live_decide`` and requires identical actions.
"""
from __future__ import annotations

import json
import math
import sys
import tempfile
import time
import unittest
import zlib
from collections import Counter, deque
from dataclasses import replace
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import obs_contract as oc                       # noqa: E402
from pipeline import vocab                                    # noqa: E402
from pipeline import e1_eval, e1_pool, e1_score               # noqa: E402
from pipeline.dataset import _past, _tag_split                # noqa: E402
from pipeline.e1_view import live_view                        # noqa: E402
from pipeline.tests.test_obs_contract import ENGINE_DECK, raw_obs   # noqa: E402

SC_TOWER_HP = 7 + 36 + 9          # obs_contract.SCALAR_FEATURES: tower_hp_frac_6 starts at 52
SC_TOWER_KNOWN = SC_TOWER_HP + 6
SC_OPP_KNOWN = 6


def _deck():
    return oc.load_deck("icebow")


def _engine_bs(deck, extra_enemy: int = 6):
    """The obs-contract fixture board plus extra enemy bodies of classes icebow cannot produce, through the SAME
    compact path the eval uses (engine_play.compact_raw -> from_engine)."""
    from pipeline import engine_play as ep
    o = raw_obs(0)
    names = ["HogRider", "Musketeer", "Valkyrie", "Giant", "MiniPekka", "Wizard"]
    for i in range(extra_enemy):
        o["entities"].append({"side": 1, "x": 3000 + 2000 * i, "y": 18000 + 500 * i, "card_id": 26000100 + i,
                              "name": names[i % len(names)], "hp": 500, "max_hp": 1000, "kind": 15})
    return oc.from_engine(ep.compact_raw(o), 0, deck, engine_deck=ENGINE_DECK, unmapped=set())


# ------------------------------------------------------------------------------------------------------
class TestLiveView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.deck = _deck()
        cls.bs = _engine_bs(cls.deck)
        cls.allowed = oc.mine_classes(cls.deck)

    def test_hp_known_full_king_full_opp_unknown(self):
        for s in range(40):
            v = live_view(self.bs, np.random.default_rng(s), self.deck)
            self.assertEqual(v.source, "degraded")
            self.assertIsNone(v.opp_elixir)
            self.assertTrue(all(u.hp_frac == 1.0 for u in v.units + v.spells))
            tok, mask, sc = oc.to_tokens(v, 64)
            if mask.any():
                self.assertTrue(np.all(tok[mask, 6] == 1.0) and np.all(tok[mask, 7] == 1.0))
            for i in (0, 3):                                  # my king, opp king (both alive in the fixture)
                self.assertTrue(v.towers[i].alive)
                self.assertEqual(v.towers[i].hp_frac, 1.0)
                self.assertEqual(sc[SC_TOWER_HP + i], 1.0)
                self.assertEqual(sc[SC_TOWER_KNOWN + i], 1.0)
            self.assertEqual(sc[SC_OPP_KNOWN], 0.0)
            self.assertEqual(v.my_elixir, float(int(self.bs.my_elixir)))

    def test_dead_king_stays_dead(self):
        towers = list(self.bs.towers)
        towers[3] = replace(towers[3], hp_frac=0.0, alive=False)
        v = live_view(replace(self.bs, towers=tuple(towers)), np.random.default_rng(1), self.deck)
        self.assertFalse(v.towers[3].alive)
        self.assertEqual(v.towers[3].hp_frac, 0.0)

    def test_unknown_side_resolved_outside_mine_classes(self):
        resolved = kept_unknown = 0
        for s in range(300):
            d = oc.degrade(self.bs, np.random.default_rng(s))
            v = live_view(self.bs, np.random.default_rng(s), self.deck)
            self.assertEqual(len(d.units), len(v.units))
            for du, vu in zip(d.units + d.spells, v.units + v.spells):
                self.assertEqual((du.cls, du.x, du.y, du.conf), (vu.cls, vu.x, vu.y, vu.conf))
                base = vocab.base_key(vocab.UNIT_VOCAB[vu.cls])
                if vu.side == -1:
                    self.assertIn(base, self.allowed, f"side -1 left on {base}")
                if du.side == -1 and base not in self.allowed:
                    self.assertEqual(vu.side, 1)
                    resolved += 1
                elif du.side == -1:
                    self.assertEqual(vu.side, -1)
                    kept_unknown += 1
                else:
                    self.assertEqual(vu.side, du.side)
        self.assertGreater(resolved, 0)
        self.assertGreater(kept_unknown, 0)

    def test_same_seed_identical_different_seed_differs(self):
        a = oc.to_tokens(live_view(self.bs, np.random.default_rng(7), self.deck), 64)
        b = oc.to_tokens(live_view(self.bs, np.random.default_rng(7), self.deck), 64)
        for x, y in zip(a, b):
            self.assertTrue(np.array_equal(x, y))
        diff = 0
        for s in range(8, 18):
            c = oc.to_tokens(live_view(self.bs, np.random.default_rng(s), self.deck), 64)
            diff += int(not all(np.array_equal(x, y) for x, y in zip(a, c)))
        self.assertEqual(diff, 10)

    def test_eval_seed_formula(self):
        self.assertEqual(e1_eval.obs_seed("ABC", 2), zlib.crc32(b"ABC:eval:2"))
        self.assertNotEqual(e1_eval.obs_seed("ABC", 0), e1_eval.obs_seed("ABC", 1))


# ------------------------------------------------------------------------------------------------------
class TestSplitRule(unittest.TestCase):
    def test_assign_split_synthetic(self):
        cands = [{"tag": "a", "group": "g1", "s1_split": "val"}, {"tag": "b", "group": "g1", "s1_split": "train"},
                 {"tag": "c", "group": "g2", "s1_split": "train"}, {"tag": "d", "group": "tag:d", "s1_split": "val"},
                 {"tag": "e", "group": "g3", "s1_split": "train"}, {"tag": "f", "group": "g3", "s1_split": "train"}]
        self.assertEqual(e1_pool.assign_split(cands),
                         {"a": "heldout", "b": "dropped", "c": "train", "d": "heldout", "e": "train", "f": "train"})

    def test_s1_rule_is_dataset_rule(self):
        for t in ("000YL9U0U8JL", "QQ", "L9YPLCC9G", "X" * 12):
            self.assertEqual(e1_pool.s1_split_of(t) == "val", _tag_split(t, 15) == 1)

    def test_forms_helpers(self):
        deck = _deck()
        want = e1_pool.deck_forms(deck)
        self.assertEqual({k for k, v in want.items() if v != "base"}, {"tesla", "knight"})
        self.assertEqual(e1_pool.final_forms(ENGINE_DECK), want)
        self.assertEqual(e1_pool.live_config_forms(), want)


@unittest.skipUnless(e1_pool.POOL_V1.exists() and e1_pool.SPLIT_V1.exists(), "pool v1 not built")
class TestFrozenSplit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = e1_pool.verify_split(e1_pool.POOL_V1, e1_pool.SPLIT_V1)
        cls.frozen = json.loads(e1_pool.SPLIT_V1.read_text(encoding="utf-8"))

    def test_sha_and_counts(self):
        self.assertTrue(self.v["sha_ok"])
        self.assertEqual(self.v["rule_mismatch"], 0)
        self.assertEqual(self.v["row_vs_frozen_mismatch"], 0)
        self.assertEqual(self.v["counts"], self.frozen["counts"])
        self.assertEqual(self.frozen["counts"], {"heldout": 293, "train": 1505, "dropped": 12})
        self.assertEqual(self.v["n_pool"], self.v["n_frozen"])

    def test_no_heldout_group_has_s1_train_member_in_train(self):
        self.assertEqual(self.v["groups_heldout_and_train"], [])
        groups: dict[str, list[dict]] = {}
        for t, d in self.frozen["tags"].items():
            groups.setdefault(d["group"], []).append({"tag": t, **d})
        for t, d in self.frozen["tags"].items():
            if d["split"] != "heldout":
                continue
            self.assertEqual(d["s1_split"], "val")
            self.assertEqual(_tag_split(t, 15), 1)
            for m in groups[d["group"]]:
                self.assertIn(m["split"], ("heldout", "dropped"))
                if m["s1_split"] == "train":
                    self.assertEqual(m["split"], "dropped")


# ------------------------------------------------------------------------------------------------------
class TestLiveRuleParity(unittest.TestCase):
    """e1_eval's live rule vs the REAL student_live.StudentPolicy.decide on constructed states."""

    @classmethod
    def setUpClass(cls):
        import torch
        src = str(REPO / "icebow" / "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from clashrl import student_live as sl
        from pipeline.model_v3 import S1Model, cell_xy, hand_mask_from_sc
        torch.set_num_threads(2)
        torch.manual_seed(0)
        cls.torch, cls.sl = torch, sl
        cls.model = S1Model(d=32, layers=1, heads=4).eval()
        with torch.no_grad():                           # spread the gate so tau 0.27 lands on both sides
            cls.model.gate_head.bias.fill_(-0.8)
        cls.deck = _deck()
        cls.base = live_view(_engine_bs(cls.deck), np.random.default_rng(3), cls.deck)
        # live ids = deck slot index; costs from the live CardDB convention (tesla 4, x_bow 6, rocket 6, log 2 ...)
        cls.deck_keys = list(cls.deck.cards)
        cost = {"tornado": 3, "tesla": 4, "ice_wizard": 3, "x_bow": 6, "rocket": 6, "knight": 3, "the_log": 2, "skeletons": 1}
        cls.costs = [float(cost[vocab.base_key(c)]) for c in cls.deck.cards]

        class _Warp:
            def board_to_frame(self, x, y):
                return x, y

        class _Actions:
            warp = _Warp()

            def cell_at(self, nx, ny):
                return 0

        sp = object.__new__(sl.StudentPolicy)
        sp._torch, sp._cell_xy, sp._hand_mask, sp.GRID_X = torch, cell_xy, hand_mask_from_sc, 36
        sp.dev = torch.device("cpu")
        sp.grid_kind = "lattice"
        sp.model = cls.model
        sp.deck = cls.deck
        sp.actions = _Actions()
        sp.fill_missing = True
        sp._past = deque(maxlen=8)
        sp._plays_match = 0
        sp.stats = {}
        sp.stall_elixir = 9.0
        sp.stall_seconds = 12.0
        sp._last_play_t = None
        sp.dump_low_gate = None
        sp._match_idx = 0
        sp.last = {}
        cls.sp = sp

    def _ours(self, bs, *, tau, idle_s, afford_mask=True):
        tok, mask, sc = oc.to_tokens(bs, 64)
        tick = 2000
        enc, heads, p, hand = e1_eval.model_forward(self.model, tok, mask, sc, _past([], tick))
        el = float(int(bs.my_elixir))
        allowed = e1_eval.allowed_slots(hand, self.costs, el, afford_mask=afford_mask)
        st = e1_eval.anti_stall(el, tick, tick - int(round(idle_s / oc.TICK_S)), 9.0, 12.0)
        return p, e1_eval.live_decide(self.model, enc, heads, p, allowed, tau=tau, stalled=st)

    def _theirs(self, bs, *, tau, idle_s, hand_slots):
        sl = self.sl
        self.sp.gate_tau = tau
        self.sp._last_play_t = time.time() - idle_s
        orig = sl.from_live
        sl.from_live = lambda *a, **k: bs
        try:
            reads = oc.LiveReads(elixir_int=int(bs.my_elixir), hand_names=(None,) * 4, next_name=None,
                                 tower_hp=(None,) * 6, t_sec=bs.t_sec, t_source="clock")
            res = self.sp.decide([], reads, list(hand_slots), self.deck_keys, card_elixir=self.costs)
        finally:
            sl.from_live = orig
        return res, dict(self.sp.last)

    def test_same_actions_as_student_live(self):
        hands = [(1, 3, 4, 2), (0, 5, 6, 7), (3, 4, 1, 5)]
        n = plays = waits = stalls = noaff = 0
        for elixir in (0.4, 2.7, 3.2, 6.0, 9.0, 10.0):
            for hand in hands:
                for idle_s in (0.0, 5.0, 13.5):
                    for tau in (0.0, 0.27, 0.35, 1.0):
                        bs = replace(self.base, my_elixir=float(int(elixir)),
                                     my_hand=tuple(self.deck.card_ids[s] for s in hand))
                        p, d = self._ours(bs, tau=tau, idle_s=idle_s)
                        res, last = self._theirs(bs, tau=tau, idle_s=idle_s, hand_slots=hand)
                        n += 1
                        self.assertAlmostEqual(p, last["p_play"], places=6)
                        if d["why"] == "no_affordable":
                            noaff += 1
                            self.assertIsNone(res)
                            self.assertTrue(last.get("no_mappable_card"))
                            continue
                        self.assertEqual(d["slot"], last["deck_slot"], (elixir, hand, idle_s, tau))
                        if not d["play"]:
                            waits += 1
                            self.assertIsNone(res, (elixir, hand, idle_s, tau))
                            continue
                        plays += 1
                        self.assertIsNotNone(res, (elixir, hand, idle_s, tau))
                        self.assertEqual(d["cell"], last["student_cell"])
                        self.assertEqual(d["why"] == "stall", bool(last.get("stall")))
                        stalls += int(d["why"] == "stall")
                        self.assertLessEqual(self.costs[d["slot"]], float(int(elixir)) + 1e-6)
        self.assertEqual(n, 6 * 3 * 3 * 4)
        for name, v in (("plays", plays), ("waits", waits), ("stalls", stalls), ("no_affordable", noaff)):
            self.assertGreater(v, 0, name)

    def test_affordability_mask_semantics(self):
        hand = np.array([True, True, False, True, False, False, True, False])
        costs = [3, 4, 3, 6, 6, 3, 2, 1]
        self.assertEqual(e1_eval.allowed_slots(hand, costs, 3.0).tolist(),
                         [True, False, False, False, False, False, True, False])
        self.assertEqual(e1_eval.allowed_slots(hand, costs, 1.0).tolist(), [False] * 8)
        self.assertEqual(e1_eval.allowed_slots(hand, costs, 1.0, afford_mask=False).tolist(), hand.tolist())

    def test_anti_stall_boundaries(self):
        self.assertTrue(e1_eval.anti_stall(9.0, 1240, 1000, 9.0, 12.0))      # 240 ticks = 12.0 s
        self.assertFalse(e1_eval.anti_stall(9.0, 1239, 1000, 9.0, 12.0))
        self.assertFalse(e1_eval.anti_stall(8.0, 5000, 0, 9.0, 12.0))
        self.assertFalse(e1_eval.anti_stall(10.0, 5000, 0, None, 12.0))

    def test_tau_threshold_is_strict(self):
        import torch
        tok, mask, sc = oc.to_tokens(self.base, 64)
        enc, heads, p, hand = e1_eval.model_forward(self.model, tok, mask, sc, _past([], 100))
        allowed = np.ones(8, dtype=bool)
        self.assertFalse(e1_eval.live_decide(self.model, enc, heads, p, allowed, tau=p, stalled=False)["play"])
        self.assertTrue(e1_eval.live_decide(self.model, enc, heads, p, allowed, tau=p - 1e-6, stalled=False)["play"])
        self.assertTrue(e1_eval.live_decide(self.model, enc, heads, p, allowed, tau=p, stalled=True)["play"])


# ------------------------------------------------------------------------------------------------------
class TestPoolEnvMixin(unittest.TestCase):
    class _Eng:
        def __init__(self, script):
            self.script = list(script)
            self.calls = []

        def act(self, side, deck_index, x, y):
            self.calls.append((side, deck_index, x, y))
            return self.script.pop(0)

    def _env(self, script, retry=(13, 1050)):
        env = e1_pool.PoolV1Mixin()
        env.side, env.opp, env.elixir_slack = 1, 0, 40
        env.eng = self._Eng(script)
        env._gi, env._pending = 0, []
        env.ghost_ok = env.ghost_rejected = env.our_cmd_ok = env.our_cmd_refused = 0
        env.ghost_reject_reasons, env.ghost_events, env.our_cmd_reasons = {}, [], {}
        env.ghost_cards_delivered = Counter()
        env.retry_codes = retry
        env._ghosts = [{"tick": 100, "sched": 100, "deck_index": 2, "x": 1, "y": 2, "card": "golem"}]
        return env

    def test_retry_codes(self):
        refuse13 = {"accepted": False, "result_code": 13, "placement_valid": True}
        ok = {"accepted": True, "result_code": 0}
        env = self._env([refuse13, ok])
        env._fire_ghosts_at(100)
        env._fire_ghosts_at(101)
        self.assertEqual((env.ghost_ok, env.ghost_rejected, env.ghost_cards_delivered["golem"]), (1, 0, 1))
        env = self._env([refuse13], retry=(1050,))
        env._fire_ghosts_at(100)
        self.assertEqual((env.ghost_ok, env.ghost_rejected), (0, 1))
        self.assertEqual(env.ghost_reject_reasons, {"not_enough_elixir": 1})
        self.assertEqual(env.ghost_undelivered(), 0)

    def test_parity_merge_order_and_sides(self):
        env = self._env([])
        env.final_decks = {0: [{"slug": s} for s in "abcdefgh"], 1: [{"slug": s} for s in "ijklmnop"]}
        env.entry = {"ghost_commands": [{"tick": 100, "card": "c", "x": 1, "y": 1, "play_index": 1, "ability": 0},
                                        {"tick": 130, "card": None, "x": None, "y": None, "play_index": 4, "ability": 1},
                                        {"tick": 120, "card": "a", "x": 1, "y": 1, "play_index": 3, "ability": 0}],
                     "icebow_commands": [{"tick": 100, "card": "k", "x": 2, "y": 2, "play_index": 0, "ability": 0},
                                         {"tick": 110, "card": "p", "x": 2, "y": 2, "play_index": 2, "ability": 0}]}
        env._merge_our_commands()
        self.assertEqual([(g["play_index"], g["side"], g["deck_index"]) for g in env._ghosts],
                         [(0, 1, 2), (1, 0, 2), (2, 1, 7), (3, 0, 0)])
        ok = {"accepted": True, "result_code": 0}
        env.eng = self._Eng([ok, ok])
        env._fire_ghosts_at(100)
        self.assertEqual([c[0] for c in env.eng.calls], [1, 0])        # our play_index 0 fires before ghost's 1
        self.assertEqual((env.our_cmd_ok, env.ghost_ok), (1, 1))

    def test_resolve_decks_asserts_final_order(self):
        env = e1_pool.PoolV1Mixin()
        deck = [{"name": n, "form": "base"} for n in ("A", "B", "C", "D", "E", "F", "G", "H")]
        entry = {"tag": "t", "icebow_side": 1, "ghost_side": 0, "icebow_deck": deck, "ghost_deck": deck,
                 "deck_order": "final", "final_decks": {"0": list("ABCDEFGH"), "1": list("ABCDEFGH")}}
        final, hit = env._resolve_decks(entry)
        self.assertTrue(hit)
        entry["final_decks"]["1"] = list("BACDEFGH")
        with self.assertRaises(RuntimeError):
            env._resolve_decks(entry)


# ------------------------------------------------------------------------------------------------------
class TestEvalGuards(unittest.TestCase):
    def test_refuses_existing_nonempty_out_before_loading_anything(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "matches.jsonl").write_text("{}\n", encoding="utf-8")
            with self.assertRaises(SystemExit) as cm:
                e1_eval.main(["--port", "38031", "--ckpt", "nope.pt", "--pool", str(Path(td) / "missing_pool.jsonl"),
                              "--out", td])
            self.assertIn("REFUSING", str(cm.exception))
            e1_eval.refuse_existing_out(Path(td), resume=True)            # resume is the only way in
        with tempfile.TemporaryDirectory() as td:
            e1_eval.refuse_existing_out(Path(td))                        # empty dir is fine
            with self.assertRaises(SystemExit):
                e1_eval.refuse_existing_out(Path(td) / "new", resume=True)

    def test_shards_cover_tasks_disjointly(self):
        idx = list(range(7))
        t0 = e1_eval.make_tasks(idx, [0, 1], (0, 2))
        t1 = e1_eval.make_tasks(idx, [0, 1], (1, 2))
        self.assertEqual(sorted(t0 + t1), sorted((i, k) for i in idx for k in (0, 1)))
        self.assertFalse(set(t0) & set(t1))
        self.assertEqual(abs(len(t0) - len(t1)) <= 1, True)

    def test_parse_entries(self):
        entries = [{"tag": t} for t in ("A", "B", "C", "D")]
        self.assertEqual(e1_eval.parse_entries("1:3", entries), [1, 2])
        self.assertEqual(e1_eval.parse_entries("all", entries), [0, 1, 2, 3])
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "tags.txt"
            p.write_text("D\nB\n", encoding="utf-8")
            self.assertEqual(e1_eval.parse_entries(str(p), entries), [3, 1])
        with self.assertRaises(SystemExit):
            e1_eval.parse_entries("0:9", entries)


# ------------------------------------------------------------------------------------------------------
def _line(tag, k, outcome, *, slot=0, seconds=200.0, after=False, delivered=40, distinct=8, real="win", att=20, acc=18):
    return {"tag": tag, "k": k, "slot": slot, "outcome": outcome, "crowns_for": 1 if outcome == "win" else 0,
            "crowns_against": 1 if outcome == "loss" else 0, "seconds": seconds, "after_script": after,
            "ghost_delivered": delivered, "ghost_distinct_delivered": distinct, "real_outcome": real,
            "plays_attempted": att, "plays_accepted": acc, "stall_fired": 1, "no_affordable": 5, "ghost_refused": 0,
            "ghost_undelivered": 0, "degraded_equals_decisions": True, "wall_s": 21.0, "policy": "live"}


class TestScorer(unittest.TestCase):
    def _write(self, d: Path, lines):
        d.mkdir(parents=True, exist_ok=True)
        (d / "matches.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")

    def test_summary_and_clustered_ci(self):
        run = []
        for i in range(40):
            o = "win" if i < 28 else ("draw" if i == 28 else "loss")
            for k in (0, 1):                                       # identical outcome across seeds: fully clustered
                run.append(_line(f"T{i:02d}", k, o, slot=k, after=(o == "win" and i < 7),
                                 delivered=(5 if i < 4 else 20 if i < 20 else 50), distinct=(2 if i < 3 else 7),
                                 real=("loss" if i % 3 == 0 else "win")))
        with tempfile.TemporaryDirectory() as td:
            self._write(Path(td) / "a", run[:40])
            self._write(Path(td) / "b", run[40:] + [run[0]])           # a duplicate (tag, k) -> counted, last kept
            rep = e1_score.score([Path(td) / "a", Path(td) / "b"])
            rep2 = e1_score.score([Path(td) / "a", Path(td) / "b"])
        s = rep["run"]
        self.assertEqual(rep["duplicates_dropped"], 1)
        self.assertEqual((s["matches"], s["entries"], s["W"], s["D"], s["L"]), (80, 40, 56, 2, 22))
        self.assertAlmostEqual(s["winrate"], 0.7)
        ci = s["winrate_entry_weighted"]
        self.assertEqual(ci, rep2["run"]["winrate_entry_weighted"])      # fixed seed -> reproducible
        self.assertLess(ci["lo"], 0.7)
        self.assertGreater(ci["hi"], 0.7)
        naive = s["unclustered_normal_95"]
        self.assertGreater(ci["hi"] - ci["lo"], 1.15 * (naive[1] - naive[0]))   # n_eff 40, not 80
        self.assertEqual(s["per_seed"]["0"]["n"], 40)
        self.assertEqual(s["per_slot"]["1"]["wins"], 28)
        self.assertEqual(s["decided_before_script_end"], {"n": 66, "wins": 42, "winrate": 42 / 66})
        self.assertEqual(s["wins_after_script"], 14)
        self.assertEqual(s["buckets"]["ghost_delivered"]["<=10"]["wins"], 8)
        self.assertEqual(s["buckets"]["ghost_distinct_delivered"]["<=3"]["n"], 6)
        self.assertEqual(s["wins_where_real_pro_lost"], 20)             # i in {0,3,...,27} -> 10 entries x 2 seeds
        self.assertAlmostEqual(s["accepted_fraction"], 0.9)
        self.assertAlmostEqual(s["plays_per_min"], 20 / (200 / 60))

    def test_paired_and_mcnemar(self):
        run = [_line(f"T{i}", 0, "win") for i in range(10)]
        ctrl = [_line(f"T{i}", 0, "win" if i < 2 else "loss", seconds=100.0) for i in range(10)]
        with tempfile.TemporaryDirectory() as td:
            self._write(Path(td) / "run", run)
            self._write(Path(td) / "ctrl", ctrl)
            rep = e1_score.score([Path(td) / "run"], {"none": [Path(td) / "ctrl"]})
            md = e1_score.to_markdown(rep, "t")
        p = rep["controls"]["none"]["paired"]
        self.assertEqual((p["pairs"], p["both_win"], p["run_win_only"], p["control_win_only"], p["neither"]), (10, 2, 8, 0, 0))
        self.assertAlmostEqual(p["delta_winrate"], 0.8)
        self.assertAlmostEqual(p["mcnemar_exact_p"], 2 * 0.5 ** 8)
        self.assertAlmostEqual(p["survival_delta_s_mean"], 100.0)
        self.assertIn("Paired vs control `none`", md)
        self.assertEqual(e1_score.mcnemar_exact(0, 0), 1.0)
        self.assertAlmostEqual(e1_score.mcnemar_exact(3, 3), 1.0)

    def test_parity_summary(self):
        lines = [{"tag": f"P{i}", "k": 0, "slot": i % 2, "mode": "parity", "hash_match": i != 3, "opening_hash_match": True}
                 for i in range(20)]
        with tempfile.TemporaryDirectory() as td:
            self._write(Path(td) / "par", lines)
            rep = e1_score.score([Path(td) / "par"])
        q = rep["parity"]
        self.assertEqual((q["n"], q["hash_match"], q["gate_19_of_20"]), (20, 19, True))
        self.assertEqual([m["tag"] for m in q["mismatches"]], ["P3"])
        self.assertNotIn("run", rep)


if __name__ == "__main__":
    unittest.main()
