"""P2 opponents: the SIM decode of a timing-head checkpoint (decision_options gate_decode 'timing_head'; e1_eval
timing_decide_batch / timing_cfg / SelfPlaySide; REPORT_opponents section 2 "Decoding in the SIM").

    icebow/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider pipeline/tests/test_timing_head_decode.py

Covers: T = 1 draws reproduce the label rate and the tick pmf (synthetic, REPORT section 5's test); the card / cell draw
never takes a disallowed slot; decide() and the live (threshold) decoders refuse a model with no gate; the REAL
SelfPlayMatch on test_league's fake env: slots on the absolute 10-tick grid, plays issued at slot + j, the next slot
after a play, the per-slot play rate = h, the learner's match unchanged by which opponent it meets, opp_sim inputs.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import decision_options as DO                               # noqa: E402
from pipeline import e1_eval as E                                         # noqa: E402
from pipeline.model_gen import GenModel                                   # noqa: E402
from pipeline.tests.test_league import _SPEnv, _cfg, _run, _spec, _tiny_gen, VOCAB   # noqa: E402

CTX = {"band": 6, "mode": 8, "era": 4}
SIM = {"ctx": {"band": 1, "mode": 1, "era": 1}, "deck_keys": []}
H, PMF = 0.25, np.array([0.0, 0.5, 0.3, 0.2, 0, 0, 0, 0, 0, 0])


def _timing_gen(seed=0, h=H, pmf=PMF):
    """A tiny timing-head GenModel whose hazard is exactly h and tick pmf exactly ``pmf`` in every state."""
    torch.manual_seed(seed)
    m = GenModel(d=16, layers=1, heads=2, d_c=8, n_cards=len(VOCAB), timing=True, deck_enc=True, n_decks=2,
                 ctx_tokens=CTX).eval()
    with torch.no_grad():
        m.timing_head.weight.zero_()
        m.timing_head.bias.copy_(torch.tensor([math.log(h / (1 - h))] + [math.log(max(q, 1e-30)) for q in pmf]))
    return m


class TestDraws(unittest.TestCase):
    def test_t1_slot_draws_reproduce_the_label_rate_and_tick_pmf(self):
        rng = np.random.default_rng(0)
        z, lt = math.log(H / (1 - H)), np.log(np.maximum(PMF, 1e-30))
        n = 200_000
        got = [DO.timing_slot_draw(z, lt, rng) for _ in range(n)]
        ticks = np.array([j for j in got if j is not None])
        self.assertLess(abs(len(ticks) / n - H), 4 * math.sqrt(H * (1 - H) / n))
        freq = np.bincount(ticks, minlength=10) / len(ticks)
        np.testing.assert_allclose(freq, PMF, atol=4 * math.sqrt(0.25 / len(ticks)))

    def test_play_draw_only_allowed_and_softmax_frequencies(self):
        rng = np.random.default_rng(1)
        logits = np.array([0.0, 1.0, -np.inf, 2.0, 0.5, -np.inf, -np.inf, -np.inf])
        allowed = np.array([True, True, False, True, False, False, False, False])
        self.assertIsNone(DO.timing_play_draw(logits, np.zeros(8, bool), lambda s: np.zeros(4), rng))
        cells = np.array([0.0, 0.0, math.log(3.0), -np.inf])
        n = 40_000
        out = [DO.timing_play_draw(logits, allowed, lambda s: cells, rng) for _ in range(n)]
        slots = np.bincount([s for s, _ in out], minlength=8) / n
        want = np.where(allowed, np.exp(np.where(allowed, logits, 0)), 0)
        np.testing.assert_allclose(slots, want / want.sum(), atol=0.015)
        np.testing.assert_allclose(np.bincount([c for _, c in out], minlength=4) / n, [0.2, 0.2, 0.6, 0], atol=0.015)
        cold = [DO.timing_play_draw(logits, allowed, lambda s: cells, rng, T=0.05)[0] for _ in range(200)]
        self.assertEqual(set(cold), {3})                                  # T -> 0: the argmax

    def test_options_accept_it_and_the_gate_decoders_refuse_it(self):
        o = DO.DecisionOptions(gate_decode="timing_head")
        with self.assertRaises(ValueError):
            DO.decide({"card": torch.zeros(1, 8)}, [0.5], np.ones((1, 8), bool), np.zeros(1, bool), tau=.3,
                      options=o, rngs=[None], cell_logits=None)
        heads = {"card": torch.zeros(1, 8), "hazard": torch.zeros(1), "tick": torch.zeros(1, 10)}
        for fn in (lambda: E.live_decide_batch(None, {}, heads, [0.5], np.ones((1, 8), bool), np.zeros(1, bool), tau=.3),
                   lambda: E.live_decide(None, {}, heads, 0.5, np.ones(8, bool), tau=.3, stalled=False)):
            with self.assertRaises(ValueError):
                fn()

    def test_timing_cfg(self):
        c = E.timing_cfg(_cfg("sample", record=False, action_delay_ticks=26, extrapolate_ticks=26))
        self.assertEqual((c["gate_decode"], c["decide_every"], c["action_delay_ticks"], c["extrapolate_ticks"],
                          c["stall_elixir"]), ("timing_head", 10, 0, 0, None))
        for bad in ({"decide_every": 20}, {"record": True}, {"tap_loss": {"1x": 0.1}}, {"pipeline_decisions": True},
                    {"gate_decode": "hazard"}):
            with self.assertRaises(ValueError, msg=str(bad)):
                E.timing_cfg(_cfg("sample", **{"record": False, **bad}))

    def test_policy_needs_opp_sim_and_fills_the_context_row(self):
        with self.assertRaises(ValueError):
            E.GenPolicy(_timing_gen(), VOCAB)
        pol = E.GenPolicy(_timing_gen(), VOCAB, {"ctx": {"band": 1, "mode": 2, "era": 1},
                                                 "deck_keys": [[3, 1, 2, 4, 5, 6, 7, 8] + [0] * 8]})
        row = {"deck_card": np.array([3, 1, 2, 4, 5, 6, 7, 8]), "deck_form": np.zeros(8, np.int64)}
        self.assertEqual(pol.opp_inputs(row), {"ctx_band": 1, "ctx_mode": 2, "ctx_era": 1, "deck_gid": 1})
        self.assertEqual(pol.opp_inputs({**row, "deck_form": np.ones(8, np.int64)})["deck_gid"], 0)   # unknown deck
        self.assertEqual(E.opp_ctx_keys(_tiny_gen(0)), ())                 # a legacy GenModel: no extra row key
        self.assertIsNone(E.GenPolicy(_tiny_gen(0), VOCAB).opp_sim)


class TestFakeMatch(unittest.TestCase):
    """The REAL SelfPlayMatch / run_selfplay_batch on test_league's fake env (board = f(tick))."""

    TAIL = 2000

    def _match(self, opp, ocfg):
        learner = E.GenPolicy(_tiny_gen(11), VOCAB)
        log, orig = [], E.SelfPlaySide.apply

        def apply(s, p, d):
            log.append((s.side, int(s.env.tick), d["why"], d.get("th_tick"), bool(d["play"])))
            return orig(s, p, d)
        spy = []
        E.SelfPlaySide.apply = apply
        try:
            res, envs = _run([(0, _spec(0, "o", 0), 0, {"rollout_index": 0, "update": 0})], learner, {"o": (opp, ocfg)},
                             _cfg(action_delay_ticks=26), make_env=lambda: _SPEnv(tail=self.TAIL), n=1, spy=spy)
        finally:
            E.SelfPlaySide.apply = orig
        return spy[0], res[0], envs[0], log

    def test_slot_grid_play_ticks_rate_and_learner_untouched(self):
        ocfg = _cfg("sample", record=False, action_delay_ticks=26, extrapolate_ticks=26, T=1.0)
        m, res, env, log = self._match(E.GenPolicy(_timing_gen(3), VOCAB, SIM), ocfg)
        o = m.opp.side
        self.assertEqual((m.opp.cfg["decide_every"], m.opp.delay, m.opp.extrap), (10, 0, 0))
        dec = [x for x in log if x[0] == o]
        slots = [x for x in dec if x[2] in ("timing_wait", "timing_slot")]
        self.assertTrue(all(t % 10 == 0 for _, t, *_ in slots))
        self.assertEqual([t for _, t, *_ in slots], list(range(90, 90 + len(slots) * 10, 10)))   # every slot, in order
        drawn = [(t, j) for _, t, w, j, _ in slots if w == "timing_slot"]
        plays = [t for s, t, w, _, pl in dec if w == "timing" and pl]
        self.assertEqual(plays, [t + j for t, j in drawn][:len(plays)])  # played at slot + j (j > 0: PMF[0] = 0)
        acts = [t for t, side, *_ in env.log if side == o]
        self.assertEqual(acts, plays)                                    # issued at the drawn tick, no delay of ours
        n = len(slots)
        self.assertGreater(n, 150)
        self.assertLess(abs(len(drawn) / n - H), 4 * math.sqrt(H * (1 - H) / n))
        js = np.bincount([j for _, j in drawn], minlength=10) / len(drawn)
        self.assertTrue(set(np.flatnonzero(js)) <= {1, 2, 3})
        # the learner's decisions, plays and record do not depend on which opponent it meets (board = f(tick))
        legacy = self._match(E.GenPolicy(_tiny_gen(12), VOCAB), ocfg)
        L = m.learner.side
        self.assertEqual([x[:2] + x[4:] for x in log if x[0] == L], [x[:2] + x[4:] for x in legacy[3] if x[0] == L])
        for k in res["traj"]:
            np.testing.assert_array_equal(np.asarray(res["traj"][k]), np.asarray(legacy[1]["traj"][k]), err_msg=k)

    def test_plays_the_engine_still_holds_are_not_choosable(self):
        """crforge-like command delay (20 ticks): a slot issued < 20 ticks ago is not playable and its cost is off the
        elixir (fake board: 7 elixir always, every card costs 3 -> at most two plays in flight)."""
        def mk():
            e = _SPEnv(tail=self.TAIL)
            e.engine_delay_ticks = 20
            return e
        ocfg = _cfg("sample", record=False, T=1.0)
        learner, opp = E.GenPolicy(_tiny_gen(11), VOCAB), E.GenPolicy(_timing_gen(4, h=0.9), VOCAB, SIM)
        spy = []
        res, envs = _run([(0, _spec(0, "o", 0), 0, {"rollout_index": 0, "update": 0})], learner, {"o": (opp, ocfg)},
                         _cfg(action_delay_ticks=26), make_env=mk, n=1, spy=spy)
        o = spy[0].opp.side
        acts = [(t, di) for t, side, di, *_ in envs[0].log if side == o]
        self.assertGreater(len(acts), 40)
        for i, (t, di) in enumerate(acts):
            inflight = [x for x in acts[:i] if x[0] + 20 >= t]
            self.assertLessEqual(len(inflight), 1, (t, inflight))         # 7 - 3 = 4 >= 3, 7 - 6 = 1 < 3
            self.assertNotIn(di, [x[1] for x in inflight])
        self.assertGreater(spy[0].opp.n_noaff, 0)                         # drawn plays with nothing playable

    def test_seeded_and_never_live(self):
        ocfg = _cfg("sample", record=False, T=1.0)
        a = self._match(E.GenPolicy(_timing_gen(3), VOCAB, SIM), ocfg)
        b = self._match(E.GenPolicy(_timing_gen(3), VOCAB, SIM), ocfg)
        self.assertEqual(a[2].log, b[2].log)
        with self.assertRaises(ValueError):
            self._match(E.GenPolicy(_timing_gen(3), VOCAB, SIM), _cfg("live", record=False))


if __name__ == "__main__":
    unittest.main()
