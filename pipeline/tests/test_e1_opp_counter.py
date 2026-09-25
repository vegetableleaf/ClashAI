"""e1_eval's cfg["opp_elixir"] arm (L68 T8b): opponent elixir from a COUNTER fed the ghost's delivered plays.

    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_e1_opp_counter.py

No engine, no model: a fake env with RoyalePoolEnv's ghost-delivery shape (``_advance_to`` stops every tick and calls
``_fire_ghosts_at(tick)``; a refused ghost is retried) serves the obs-contract fixture board, with the opponent's TRUE
elixir set by a test function so the tests can vary it.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import e1_eval as E                                         # noqa: E402
from pipeline import obs_contract as oc                                   # noqa: E402
from pipeline.e1_view import ALL_NOISE_OFF, Noise                         # noqa: E402
from pipeline.opp_elixir_count import OppElixirCounter, card_cost, card_db  # noqa: E402
from pipeline.tests.test_e1_eval_gen import FINAL, _Eng, _cfg             # noqa: E402
from pipeline.tests.test_obs_contract import TICK, raw_obs                # noqa: E402

T = TICK
# (scheduled tick, card slug, first tick the engine accepts it; None = refused for good)
GHOSTS = [(T - 50, "knight", T - 50),            # delivered during the warm-up (before the first decision)
          (T + 3, "the-log", T + 3),             # bodiless spell
          (T + 4, "hog-rider", None),            # refused -> never delivered
          (T + 6, "musketeer", T + 9),           # retried: delivered at T+9, not at its scheduled T+6
          (T + 10, "goblin-barrel", T + 10),     # body spell, delivered exactly on a decision tick
          (T + 25, "graveyard", T + 25)]         # body spell
N_DEC = 4                                        # decisions at T, T+10, T+20, T+30


class _GhostEnv:
    def __init__(self, truth=lambda t: 3.0):
        self.side, self.opp, self._mirror = 0, 1, False
        self.final_decks = {0: [{"name": n, "form": f, "cost": c} for n, f, c in FINAL]}
        self.truth = truth

    def _state(self):
        st = raw_obs(0)
        st["tick"] = self.tick
        st["players"][1] = dict(st["players"][1], elixir_exact=float(self.truth(self.tick)))
        return st

    def reset(self, entry):
        self.terminated, self.episode = False, None
        self.ghost_ok = self.ghost_rejected = 0
        self.ghost_cards_delivered, self.ghost_reject_reasons, self.ghost_events = Counter(), {}, []
        self._todo = list(GHOSTS)
        self.tick, self.tail_cap = T - 60, T + 10 * N_DEC
        self.eng = _Eng(None)
        self._advance_to(T)                                            # warm-up, as RoyalePoolEnv.reset
        return self.eng.state

    def _fire_ghosts_at(self, tick):
        still = []
        for g in self._todo:
            sched, card, ok_at = g
            if sched > tick:
                still.append(g)
            elif ok_at is not None and tick >= ok_at:
                self.ghost_ok += 1
                self.ghost_cards_delivered[card] += 1
                self.ghost_events.append((sched, 1, "accepted"))
            elif ok_at is not None:
                still.append(g)                                         # retried next tick
            else:
                self.ghost_rejected += 1
        self._todo = still

    def _advance_to(self, t):
        while self.tick < t:
            self.tick += 1
            self._fire_ghosts_at(self.tick)
        self.eng.state = self._state()

    def ghost_undelivered(self):
        return len(self._todo)

    def _tower_hp(self, state):
        return None

    def _crowns(self, hp):
        return (0, 0)


WAIT = {"play": False, "slot": -1, "cell": -1, "why": "wait"}


def _play(mode, truth=lambda t: 3.0, noise=None, obs="live"):
    """Run one fake match; -> (Match, env, [(tick, view.opp_elixir, sc opp cols)] per decision)."""
    env = _GhostEnv(truth)
    cfg = {**_cfg(), "obs": obs, "noise": noise if noise is not None else Noise(opp_elixir=True)}
    if mode:
        cfg["opp_elixir"] = mode
    m = E.Match(env, oc.load_deck("icebow"), {"tag": "t0"}, 0, cfg)
    seen = []
    while not m.done:
        tok, mask, sc, past = m.prepare()
        seen.append((m._cur[0], m._cur[2].opp_elixir, (float(sc[5]), float(sc[6]))))
        m.apply(0.0, WAIT)
    return m, env, seen


def _expected(mode, tick):
    """Independent: the counter fed by hand with the deliveries (at their DELIVERY tick) the mode keeps, <= tick."""
    keep = {"counter_all": {"knight", "the_log", "musketeer", "goblin_barrel", "graveyard"},
            "counter": {"knight", "musketeer", "goblin_barrel", "graveyard"}}[mode]
    c = OppElixirCounter()
    for _, card, ok_at in GHOSTS:
        key = card.replace("-", "_")
        if ok_at is not None and ok_at <= tick and key in keep:
            c.play(ok_at, key, card_cost(key))
    return c.at(tick)


class TestCounterArm(unittest.TestCase):
    def test_feeds_only_delivered_plays_at_or_before_now(self):
        for mode in E.OPP_ELIXIR_MODES:
            m, env, seen = _play(mode)
            self.assertEqual([t for t, _, _ in seen], [T, T + 10, T + 20, T + 30])
            for tick, est, (sc_el, sc_known) in seen:
                self.assertAlmostEqual(est, _expected(mode, tick), places=9, msg=(mode, tick))
                self.assertAlmostEqual(sc_el, est / 10.0, places=6)     # reaches the tokens
                self.assertEqual(sc_known, 1.0)
            # delivered list = delivery ticks, refused hog never there, retried musketeer at T+9
            self.assertEqual(env.opp_delivered, [(T - 50, "knight"), (T + 3, "the-log"), (T + 9, "musketeer"),
                                                 (T + 10, "goblin-barrel"), (T + 25, "graveyard")])
            r = m.result()["opp_counter"]
            self.assertEqual((r["fed"], r["dropped"]), (5, 0) if mode == "counter_all" else (4, 1))

    def test_graveyard_not_fed_before_its_tick(self):
        _, _, seen = _play("counter")
        est20 = dict((t, e) for t, e, _ in seen)[T + 20]
        self.assertAlmostEqual(est20, _expected("counter", T + 20))
        self.assertNotAlmostEqual(est20 - _expected("counter", T + 30), 0.0)

    def test_future_delivery_waits(self):
        m, env, _ = _play("counter_all")
        before = m.opp_fed
        env.opp_delivered.append((T + 999, "golem"))
        m.opp_estimate(T + 30)
        self.assertEqual(m.opp_fed, before)
        m.opp_estimate(T + 999)
        self.assertEqual(m.opp_fed, before + 1)

    def test_never_reads_true_opp_elixir(self):
        import random
        rnd = random.Random(0)
        for mode in E.OPP_ELIXIR_MODES:
            m1, _, a = _play(mode, truth=lambda t: 3.0)
            m2, _, b = _play(mode, truth=lambda t: rnd.uniform(0, 10))
            self.assertEqual([x[1] for x in a], [x[1] for x in b])
            self.assertNotEqual(m1.result()["opp_counter"]["mae"], m2.result()["opp_counter"]["mae"])

    def test_bad_mode_refused(self):
        with self.assertRaises(ValueError):
            _play("counterz")


class TestUnset(unittest.TestCase):
    def test_opp_elixir_untouched_and_env_untapped(self):
        for noise, obs, want in ((Noise(), "live", None), (ALL_NOISE_OFF, "live", 3.0), (Noise(), "clean", 3.0)):
            m, env, seen = _play(None, noise=noise, obs=obs)
            self.assertTrue(all(e == want for _, e, _ in seen), (noise, obs, seen))
            self.assertFalse(hasattr(env, "opp_delivered"))
            self.assertNotIn("_fire_ghosts_at", vars(env))
            self.assertNotIn("opp_counter", m.result())


class TestBodilessRule(unittest.TestCase):
    def test_same_rule_as_eval_accounting(self):
        p = REPO / "scratchpad/gauntlet/L68/opp_elixir/eval_accounting.py"
        spec = importlib.util.spec_from_file_location("_eval_accounting", p)
        ea = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ea)
        self.assertEqual(set(E.BODY_SPELLS), set(ea.BODY_SPELLS))
        for key in card_db().cards:
            self.assertEqual(E.opp_play_kept("counter", key), ea.keep("reader", key), key)
            self.assertTrue(E.opp_play_kept("counter_all", key))
        self.assertFalse(E.opp_play_kept("counter", "the_log"))
        self.assertTrue(E.opp_play_kept("counter", "graveyard"))


if __name__ == "__main__":
    unittest.main()
