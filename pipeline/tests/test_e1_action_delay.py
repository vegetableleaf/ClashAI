"""e1_eval's cfg["action_delay_ticks"] arm (L68 T9): a play decided at tick T enters the engine at T + D, as live.

    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_e1_action_delay.py

No engine: test_e1_opp_counter's fake ghost env (ticks one at a time, delivers ghosts) with an engine face that logs
the tick of every act. Elixir is spent only inside ``eng.act`` (RoyaleSim / the real engine alike), so "no act before
T + D" IS "no elixir spent before landing"; the card stays in hand for the same reason.
"""
from __future__ import annotations

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
from pipeline.tests.test_e1_batch import _tiny_model                      # noqa: E402
from pipeline.tests.test_e1_eval_gen import VOCAB, _cfg, _tiny_gen        # noqa: E402
from pipeline.tests.test_e1_opp_counter import T, _expected, _GhostEnv    # noqa: E402

D = 26
CELL = 36 * 40 + 5
PLAY = {"play": True, "slot": 2, "cell": CELL, "why": "gate"}
WAIT = {"play": False, "slot": -1, "cell": -1, "why": "wait"}


class _TickEng:
    def __init__(self, env, state):
        self.env, self.state, self.calls, self.last_episode = env, state, [], {"winner": 0, "crowns": [1, 0]}

    def act(self, side, deck_index, x, y):
        self.calls.append((self.env.tick, deck_index, x, y))
        if self.env.tick in self.env.refuse_at:
            return {"accepted": False, "result_code": 13}
        return {"accepted": True, "result_code": 0}

    def observe(self):
        return self.state


class _Env(_GhostEnv):
    def __init__(self, tail=120, refuse_at=(), end_at=None):
        super().__init__()
        self.tail, self.refuse_at, self.end_at = tail, set(refuse_at), end_at

    def reset(self, entry):
        st = super().reset(entry)
        self.tail_cap = T + self.tail
        self.eng = _TickEng(self, st)
        return st

    def _advance_to(self, t):
        while self.tick < t and not self.terminated:
            self.tick += 1
            self._fire_ghosts_at(self.tick)
            if self.end_at is not None and self.tick >= self.end_at:
                self.terminated = True
        self.eng.state = self._state()


def _scripted(script, delay, env=None, **cfg_over):
    """Drive one Match with decisions from ``script`` (list, then WAIT) -> (Match, env, decision ticks)."""
    env = env or _Env()
    cfg = {**_cfg(), **cfg_over}
    if delay is not None:
        cfg["action_delay_ticks"] = delay
    m = E.Match(env, oc.load_deck("icebow"), {"tag": "t0"}, 0, cfg)
    ticks, script = [], list(script)
    m.views = []
    while not m.done:
        m.prepare()
        ticks.append(m._cur[0])
        m.views.append(m._cur[2])
        m.apply(0.9, script.pop(0) if script else WAIT)
    return m, env, ticks


def _strip(r):
    return {k: v for k, v in r.items() if k != "wall_s"}


class TestDelayZero(unittest.TestCase):
    def test_unset_equals_zero_and_acts_on_decision_tick(self):
        a, ea, ta = _scripted([PLAY, WAIT, PLAY], None)
        b, eb, tb = _scripted([PLAY, WAIT, PLAY], 0)
        self.assertEqual((_strip(a.result()), ea.eng.calls, ta), (_strip(b.result()), eb.eng.calls, tb))
        self.assertEqual(ta, list(range(T, T + 120, 10)))
        self.assertEqual([c[0] for c in ea.eng.calls], [T, T + 20])
        self.assertEqual([p[0] for p in a.done_plays], [T, T + 20])
        for k in ("action_delay_ticks", "plays_unlanded", "plays_refused_at_landing"):
            self.assertNotIn(k, a.result())
        self.assertNotIn("land_tick", a.result()["plays"][0])

    def test_models_unset_equals_zero(self):
        for model in (_tiny_model(0), E.GenPolicy(_tiny_gen(1), VOCAB)):
            out = []
            for delay in (None, 0):
                env, res = _Env(), []
                cfg = _cfg() if delay is None else {**_cfg(), "action_delay_ticks": delay}
                E.run_batch(lambda: env, model, oc.load_deck("icebow"), [(0, {"tag": "t0"}, 0)], cfg, 1,
                            on_result=res.append)
                out.append((_strip(res[0]), env.eng.calls))
            self.assertEqual(out[0], out[1])
            self.assertGreater(out[0][0]["plays_attempted"], 0)

    def test_negative_refused(self):
        with self.assertRaises(ValueError):
            _scripted([], -1)


class TestDelayed(unittest.TestCase):
    def test_lands_at_T_plus_D_no_decisions_while_pending(self):
        m, env, ticks = _scripted([PLAY, PLAY], D)
        # decided at T -> lands T+26; next decision = first grid tick after landing (T+30); nothing in between
        self.assertEqual(ticks[:3], [T, T + 30, T + 60])
        self.assertEqual([c[0] for c in env.eng.calls], [T + D, T + 30 + D])
        x, y = ep.cell_center(CELL, "lattice")
        X, Y = ep.cell_to_engine(CELL, False, "lattice")
        self.assertEqual(env.eng.calls[0][2:], (X, Y))                          # the cell chosen at T, not revised
        self.assertEqual(m.done_plays, [(T + D, 2, x, y), (T + 30 + D, 2, x, y)])   # past = LANDING tick + position
        self.assertEqual(m.last_play_tick, T + 30 + D)
        r = m.result()
        self.assertEqual([(p["tick"], p["land_tick"]) for p in r["plays"]], [(T, T + D), (T + 30, T + 30 + D)])
        self.assertEqual((r["action_delay_ticks"], r["plays_attempted"], r["plays_accepted"]), (D, 2, 2))
        self.assertEqual((r["plays_refused_at_landing"], r["plays_unlanded"]), (0, 0))
        self.assertEqual(r["decisions"], len(ticks))

    def test_past_seen_at_next_decision_uses_landing_tick(self):
        m, _, _ = _scripted([PLAY], D)
        past = E._past(m.done_plays, T + 30)
        self.assertAlmostEqual(float(past[0][3]), (30 - D) * oc.TICK_S, places=6)

    def test_multiple_of_grid(self):
        _, env, ticks = _scripted([PLAY], 20)
        self.assertEqual(ticks[:2], [T, T + 30])                                 # first grid tick AFTER T+20
        self.assertEqual([c[0] for c in env.eng.calls], [T + 20])

    def test_refused_at_landing_counted_not_retried(self):
        m, env, ticks = _scripted([PLAY], D, env=_Env(refuse_at={T + D}))
        self.assertEqual([c[0] for c in env.eng.calls], [T + D])                 # one act, never retried
        r = m.result()
        self.assertEqual((r["plays_attempted"], r["plays_accepted"], r["plays_refused_at_landing"]), (1, 0, 1))
        self.assertEqual(r["refuse_reasons"], {ep.RESULT_CODE_NAMES[13]: 1})
        self.assertEqual(m.done_plays, [])
        self.assertEqual(ticks[1], T + 30)                                       # decisions resume on the grid

    def test_match_over_before_landing(self):
        m, env, ticks = _scripted([PLAY], D, env=_Env(end_at=T + 15))
        self.assertEqual(env.eng.calls, [])
        r = m.result()
        self.assertEqual((r["plays_unlanded"], r["plays_refused_at_landing"]), (1, 0))
        self.assertEqual(r["refuse_reasons"], {"match_over_before_landing": 1})
        self.assertEqual(ticks, [T])

    def test_tail_cap_before_landing(self):
        m, env, _ = _scripted([WAIT] * 10 + [PLAY], D, env=_Env(tail=110))    # decided at T+100, cap T+110
        self.assertEqual(env.eng.calls, [])
        self.assertEqual(m.result()["plays_unlanded"], 1)

    def test_composes_with_opp_counter(self):
        m, _, ticks = _scripted([PLAY, PLAY], D, opp_elixir="counter", noise=Noise(opp_elixir=True), obs="live")
        self.assertEqual(ticks[:2], [T, T + 30])
        r = m.result()["opp_counter"]
        self.assertEqual((r["fed"], r["dropped"]), (4, 1))                       # every delivery still reaches it
        for t, v in zip(ticks, m.views):                                         # estimate AT each decision
            self.assertAlmostEqual(v.opp_elixir, _expected("counter", t), places=9)

    def test_both_policy_kinds_batched(self):
        for model in (_tiny_model(0), E.GenPolicy(_tiny_gen(1), VOCAB)):
            env, res = _Env(tail=200), []
            E.run_batch(lambda: env, model, oc.load_deck("icebow"), [(0, {"tag": "t0"}, 0)],
                        {**_cfg(), "action_delay_ticks": D}, 1, on_result=res.append)
            r = res[0]
            self.assertGreater(r["plays_attempted"], 1, type(model).__name__)
            for p in r["plays"]:
                self.assertEqual((p["tick"] - T) % 10, 0)                         # decisions stay on the grid
                self.assertEqual(p["land_tick"], p["tick"] + D)
            dec = [p["tick"] for p in r["plays"]]
            self.assertTrue(all(b - a >= 30 for a, b in zip(dec, dec[1:])), dec)   # none while pending
            self.assertEqual([c[0] for c in env.eng.calls], [p["land_tick"] for p in r["plays"]
                                                              if p["land_tick"] <= T + 200])
            self.assertEqual(r["plays_unlanded"], sum(p["land_tick"] > T + 200 for p in r["plays"]))


if __name__ == "__main__":
    unittest.main()
