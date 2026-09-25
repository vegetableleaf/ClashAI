"""pipeline/extrapolate.py (L68 T10) + e1_eval's cfg["extrapolate_ticks"].

    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_extrapolate.py
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import e1_eval as E                                         # noqa: E402
from pipeline import engine_play as ep                                    # noqa: E402
from pipeline import obs_contract as oc                                   # noqa: E402
from pipeline.e1_view import Noise                                        # noqa: E402
from pipeline.extrapolate import extrapolate                              # noqa: E402
from pipeline.live_mem import to_observe                                  # noqa: E402
from pipeline.opp_elixir_count import regen_between                       # noqa: E402
from pipeline.tests.test_e1_action_delay import D, PLAY, WAIT, _Env, _scripted, _strip   # noqa: E402
from pipeline.tests.test_e1_batch import _tiny_model                      # noqa: E402
from pipeline.tests.test_e1_eval_gen import VOCAB, _cfg, _tiny_gen        # noqa: E402
from pipeline.tests.test_e1_opp_counter import T, _expected               # noqa: E402
from pipeline.tests.test_obs_contract import raw_obs                      # noqa: E402

H = 26


def _raw(tick, ents, el=5.0, opp_el=3.0):
    return {"tick": tick, "players": [{"side": 0, "elixir_exact": el}, {"side": 1, "elixir_exact": opp_el}],
            "entities": ents, "episode": {"crown_towers": [{"side": 0, "type": "king", "x": 9000, "y": 3000}]}}


def _ent(eid, x, y, side=0, card_id=26000000):
    return {"entity_id": eid, "side": side, "x": x, "y": y, "card_id": card_id, "name": "Knight", "hp": 1, "max_hp": 1}


def _frame(tick, ents, el_raw=50000):
    """Live reader frame (probe1.jsonl keys): game_tick, entities by address, towers as card_id -1 entities."""
    return {"game_tick": tick, "battle_active": True,
            "players": [{"side": 1, "elixir_raw": 30000, "hand_deck_indices": [-1] * 4, "next_deck_index": -1},
                        {"side": 0, "elixir_raw": el_raw, "hand_deck_indices": [0, 1, 2, 3], "next_deck_index": 4}],
            "entities": ents}


def _rent(addr, x, y, card_id=26000000, kind=15, side=0):
    return {"address": addr, "side": side, "x": x, "y": y, "card_id": card_id, "kind": kind, "hp": 100, "max_hp": 100}


class TestPure(unittest.TestCase):
    def test_motion_from_two_frames(self):
        prev = _raw(100, [_ent(1, 1000, 2000)])
        cur = _raw(110, [_ent(1, 1100, 1800)])
        out = extrapolate(cur, prev, H, 0)
        self.assertAlmostEqual(out["entities"][0]["x"], 1100 + 10 * H)          # v = 100 / 10 ticks
        self.assertAlmostEqual(out["entities"][0]["y"], 1800 - 20 * H)
        self.assertEqual(cur["entities"][0]["x"], 1100)                         # inputs not modified
        self.assertEqual(cur["tick"], 110)

    def test_velocity_uses_actual_tick_gap(self):
        out = extrapolate(_raw(130, [_ent(1, 1300, 5000)]), _raw(100, [_ent(1, 1000, 5000)]), H, 0)
        self.assertAlmostEqual(out["entities"][0]["x"], 1300 + 10 * H)          # 300 / 30 ticks

    def test_clamped_to_board(self):
        prev = _raw(100, [_ent(1, 500, 31500), _ent(2, 17500, 300)])
        cur = _raw(110, [_ent(1, 100, 31900), _ent(2, 17900, 100)])
        e = extrapolate(cur, prev, H, 0)["entities"]
        self.assertEqual((e[0]["x"], e[0]["y"]), (0.0, 32000.0))
        self.assertEqual((e[1]["x"], e[1]["y"]), (18000.0, 0.0))

    def test_new_towers_and_mismatch_static(self):
        prev = _raw(100, [_ent(1, 1000, 1000), _ent(3, 1000, 1000, card_id=26000001), _ent(4, 1000, 1000, side=1)])
        cur = _raw(110, [_ent(2, 2000, 2000), _ent(3, 3000, 3000), _ent(4, 4000, 4000)])
        e = extrapolate(cur, prev, H, 0)["entities"]
        self.assertEqual([(x["x"], x["y"]) for x in e], [(2000, 2000), (3000, 3000), (4000, 4000)])
        # the obs-contract fixture: crown towers as card_id -1 entities (no id) AND episode.crown_towers
        a, b = raw_obs(0), raw_obs(0)
        a["tick"] -= 10
        for ent in b["entities"]:
            ent["x"] = ent["x"] + 50 if ent["card_id"] < 0 else ent["x"]
        out = extrapolate(b, a, H, 0)
        self.assertEqual([x for x in out["entities"] if x["card_id"] < 0],
                         [x for x in b["entities"] if x["card_id"] < 0])
        self.assertEqual(out["episode"], b["episode"])

    def test_no_prev_or_zero_gap_no_motion(self):
        cur = _raw(110, [_ent(1, 1100, 1800)])
        for prev in (None, _raw(110, [_ent(1, 0, 0)])):
            out = extrapolate(cur, prev, H, 0)
            self.assertEqual((out["entities"][0]["x"], out["entities"][0]["y"]), (1100, 1800))
            self.assertEqual(out["tick"], 110 + H)

    def test_clock_and_phase(self):
        t0 = 2400 - 10                                                           # crosses double elixir (120 s)
        deck = oc.load_deck("icebow")
        cur = raw_obs(0)
        cur["tick"] = t0
        before = oc.from_engine(cur, 0, deck, unmapped=set())
        after = oc.from_engine(extrapolate(cur, None, H, 0), 0, deck, unmapped=set())
        self.assertFalse(before.double_elixir)
        self.assertTrue(after.double_elixir)
        self.assertAlmostEqual(after.t_sec, (t0 + H) * oc.TICK_S)

    def test_my_elixir_regen_cap_and_boundary(self):
        out = extrapolate(_raw(2390, [], el=5.0), None, H, 0)
        me, them = out["players"]
        self.assertAlmostEqual(me["elixir_exact"], 5.0 + 10 * 0.0178 + 16 * 0.0357)   # single -> double at 2400
        self.assertAlmostEqual(me["elixir_exact"], 5.0 + regen_between(2390, 2390 + H))
        self.assertEqual(them["elixir_exact"], 3.0)                               # opponent: the caller's job
        self.assertEqual(extrapolate(_raw(100, [], el=9.9), None, H, 0)["players"][0]["elixir_exact"], 10.0)
        side1 = extrapolate(_raw(100, [], el=5.0), None, H, 1)["players"]
        self.assertEqual((side1[0]["elixir_exact"], side1[1]["elixir_exact"]), (5.0, 3.0 + regen_between(100, 126)))

    def test_reader_frame_shape(self):
        tower = _rent("0xT", 9000, 3000, card_id=-1, kind=12)
        prev = _frame(200, [tower, _rent("0xA", 3000, 10000)])
        cur = _frame(210, [dict(tower, x=9500), _rent("0xA", 3000, 10500), _rent("0xB", 5000, 5000)])
        out = extrapolate(cur, prev, H, 0)
        self.assertEqual(out["game_tick"], 210 + H)
        xy = {e["address"]: (e["x"], e["y"]) for e in out["entities"]}
        self.assertEqual(xy["0xT"], (9500, 3000))                                 # tower: never moved
        self.assertAlmostEqual(xy["0xA"][1], 10500 + 50 * H)
        self.assertEqual(xy["0xB"], (5000, 5000))                                 # new: stays put
        el = {p["side"]: p["elixir_raw"] for p in out["players"]}
        self.assertAlmostEqual(el[0], 50000 + regen_between(210, 210 + H) * 1e4)
        self.assertEqual(el[1], 30000)
        # the same frames through live_mem.to_observe (entity_id = address) give the same motion
        names = ["Knight"] * 8
        o = extrapolate(to_observe(cur, 0, names), to_observe(prev, 0, names), H, 0)
        self.assertEqual(o["tick"], 210 + H)
        self.assertEqual({e["entity_id"]: (e["x"], e["y"]) for e in o["entities"]},
                         {k: v for k, v in xy.items() if k != "0xT"})
        self.assertAlmostEqual(o["players"][0]["elixir_exact"], el[0] / 1e4)


class _MovingEnv(_Env):
    """The action-delay fake env with unit 0 walking +7 x / -3 y per tick."""

    def _state(self):
        st = super()._state()
        e = st["entities"][0]
        e["x"], e["y"] = e["x"] + 7 * (self.tick - T), e["y"] - 3 * (self.tick - T)
        return st


class TestE1(unittest.TestCase):
    def test_unset_equals_zero(self):
        for model in (_tiny_model(0), E.GenPolicy(_tiny_gen(1), VOCAB)):
            out = []
            for h in (None, 0):
                env, res = _Env(), []
                cfg = _cfg() if h is None else {**_cfg(), "extrapolate_ticks": h}
                E.run_batch(lambda: env, model, oc.load_deck("icebow"), [(0, {"tag": "t0"}, 0)], cfg, 1,
                            on_result=res.append)
                out.append((_strip(res[0]), env.eng.calls))
            self.assertEqual(out[0], out[1])
            self.assertNotIn("extrapolate_ticks", out[0][0])
        a, _, _ = _scripted([PLAY, WAIT, PLAY], None)
        b, _, _ = _scripted([PLAY, WAIT, PLAY], None, extrapolate_ticks=0)
        self.assertEqual([v for v in a.views], [v for v in b.views])

    def test_negative_refused(self):
        with self.assertRaises(ValueError):
            _scripted([], None, extrapolate_ticks=-1)

    def test_decision_sees_extrapolated_board(self):
        deck = oc.load_deck("icebow")
        env = _MovingEnv()
        m, _, ticks = _scripted([], None, env=env, extrapolate_ticks=H)
        self.assertEqual(ticks[:3], [T, T + 10, T + 20])
        self.assertAlmostEqual(m.views[0].t_sec, T * oc.TICK_S)                  # first decision: not extrapolated
        for i in (1, 2):
            t = ticks[i]
            env.tick = t - 10
            prev = env._state()
            env.tick = t
            want = oc.from_engine(ep.compact_raw(extrapolate(env._state(), prev, H, 0)), 0, deck,
                                  engine_deck=m.engine_deck, unmapped=set())
            self.assertEqual(m.views[i], want)
            self.assertAlmostEqual(m.views[i].t_sec, (t + H) * oc.TICK_S)
            self.assertAlmostEqual(m.views[i].my_elixir, 6.37 + regen_between(t, t + H))
        self.assertEqual(m.result()["extrapolate_ticks"], H)

    def test_past_dt_uses_extrapolated_clock(self):
        m = E.Match(_Env(), oc.load_deck("icebow"), {"tag": "t0"}, 0, {**_cfg(), "extrapolate_ticks": H})
        m.prepare()
        m.apply(0.9, PLAY)                                                          # lands at T (no delay)
        m.prepare()
        self.assertEqual(m._cur[0], T + 10)
        self.assertAlmostEqual(float(m._obs[3][0][3]), (10 + H) * oc.TICK_S, places=6)

    def test_composes_with_delay_and_opp_counter(self):
        m, env, ticks = _scripted([PLAY, PLAY], D, extrapolate_ticks=H, opp_elixir="counter",
                                  noise=Noise(opp_elixir=True), obs="live")
        self.assertEqual(ticks[:2], [T, T + 30])
        self.assertEqual([c[0] for c in env.eng.calls], [T + D, T + 30 + D])   # landing unchanged
        self.assertAlmostEqual(m.views[0].opp_elixir, _expected("counter", T), places=9)
        for t, v in list(zip(ticks, m.views))[1:]:                                 # counter at tick + H, no new plays
            self.assertAlmostEqual(v.opp_elixir, min(10.0, _expected("counter", t) + regen_between(t, t + H)), places=9)
        r = m.result()
        self.assertEqual((r["extrapolate_ticks"], r["action_delay_ticks"]), (H, D))
        self.assertEqual((r["opp_counter"]["fed"], r["opp_counter"]["dropped"]), (4, 1))

    def test_both_policy_kinds_batched(self):
        for model in (_tiny_model(0), E.GenPolicy(_tiny_gen(1), VOCAB)):
            env, res = _MovingEnv(tail=200), []
            E.run_batch(lambda: env, model, oc.load_deck("icebow"), [(0, {"tag": "t0"}, 0)],
                        {**_cfg(), "extrapolate_ticks": H, "action_delay_ticks": D}, 1, on_result=res.append)
            self.assertGreater(res[0]["plays_attempted"], 0, type(model).__name__)
            self.assertEqual(res[0]["extrapolate_ticks"], H)


if __name__ == "__main__":
    unittest.main()
