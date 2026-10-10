"""e1_eval's cfg["pipeline_decisions"] (L74): the model decides again while one of its plays is decided but not landed, on the
2-tick frame grid, <= FOLLOW_MAX_OUT outstanding, with the pending play in its view and its hand slot masked.

    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_e1_pipeline_decisions.py

No engine: test_league's fake RoyaleSelfPlayEnv (the benchmark path: SelfPlayMatch / SelfPlaySide) and test_e1_action_delay's
fake ghost env. The pending bodies / spell projectile of the REAL engine (_pending_raw, extrapolate.pending_board) are
patched out here and covered by the pod smoke (pod_pipeline_decisions.sh: RoyaleSim is Linux-only).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import e1_eval as E                                          # noqa: E402
from pipeline.tests import test_e1_action_delay as AD                      # noqa: E402
from pipeline.tests import test_league as TL                               # noqa: E402
from pipeline.tests.test_e1_follow_up import _Env                          # noqa: E402
from pipeline.tests.test_e1_opp_counter import T                           # noqa: E402

D = 26


# ---- pure ---------------------------------------------------------------------------------------------------------------
class TestPendingHand(unittest.TestCase):
    deck = list(range(8))

    def test_pending_card_hands_its_position_to_the_next_card(self):
        hand, nxt, pos = E.pending_hand(self.deck, [0, 1, 2, 3], 4, [], [1])
        self.assertEqual((hand, pos), ([0, 4, 2, 3], [1]))
        self.assertEqual(nxt, -1)                                  # four never-played queue cards: the next is unknown
        hand, nxt, pos = E.pending_hand(self.deck, [0, 1, 2, 3], 4, [4, 5, 6], [1])   # only card 7 never played: it is next
        self.assertEqual((hand, nxt), ([0, 4, 2, 3], 7))

    def test_executed_pending_card_is_skipped_and_two_pending_chain(self):
        hand, nxt, pos = E.pending_hand(self.deck, [0, 4, 2, 3], 5, [1], [1])           # card 1 already left the hand
        self.assertEqual((hand, pos), ([0, 4, 2, 3], []))
        hand, nxt, pos = E.pending_hand(self.deck, [0, 1, 2, 3], 4, [5, 6, 7], [1, 2])
        self.assertEqual(pos, [1, 2])
        self.assertEqual(hand[1], 4)                                # the first pending card gets the next card ...
        self.assertNotIn(2, hand)                                   # ... the second leaves too


class TestNextTick(unittest.TestCase):
    def side(self, lands, ready=0, de=10):
        s = SimpleNamespace(pend=[(l, 0.9, {}, None) for l in lands], _pipe_ready=ready, cfg={"decide_every": de})
        return lambda tick: E.Match._pipe_next_tick(s, tick)

    def test_frame_grid_while_one_is_outstanding(self):
        nt = self.side([116], ready=92)
        self.assertEqual(nt(90), 92)                                # the first frame after the first tap returned
        self.assertEqual(nt(92), 94)

    def test_not_before_the_first_tap_returned(self):
        self.assertEqual(self.side([116], ready=96)(90), 96)

    def test_at_the_cap_it_waits_for_a_landing_which_frees_a_slot_on_that_frame(self):
        self.assertEqual(self.side([116, 118], ready=92)(92), 116)  # the landing frame decides: one still outstanding

    def test_the_frame_that_shows_the_last_landing_never_decides(self):
        self.assertEqual(self.side([118], ready=92)(116), 120)      # 118: confirmation frame; 120 decides
        self.assertEqual(self.side([117], ready=92)(116), 120)      # a landing between frames: seen on 118, decide 120
        self.assertEqual(self.side([], ready=0)(116), 126)          # nothing outstanding: the ordinary cadence


# ---- SelfPlaySide (the SIM benchmark path) ----------------------------------------------------------------------------
def spy_match(script, cfg_over=None, env=None, opp_wait=True):
    """Drive one fake self-play match with scripted LEARNER decisions: script = {decision index: slot to play}; everything else
    waits (the opponent always waits). -> (match, learner decision ticks, per-decision allowed masks / views)."""
    E.SelfPlaySide._pending_raw = lambda self, raw, vt: raw         # the engine's bodies are the pod smoke's business
    learner, opp = E.GenPolicy(TL._tiny_gen(1), TL.VOCAB), E.GenPolicy(TL._tiny_gen(2), TL.VOCAB)
    env = env or TL._SPEnv()
    cfg = TL._cfg("live", record=False, **{"action_delay_ticks": D, **(cfg_over or {})})
    m = E.SelfPlayMatch(env, TL._spec(0, "snapA", 0), 0, cfg, TL._cfg("live", record=False, action_delay_ticks=D), learner, opp)
    ticks, seen, i = [], [], 0
    while True:
        due = m.due()
        if not due:
            break
        for s in due:
            s.prepare()
            if s is m.learner:
                _, _, p, hand = (lambda r: (None, None, r[2][0], r[3][0]))(
                    learner.forward_batch([s.gen_row(learner)], "cpu"))
                el, allowed, _ = s.pre(hand)
                seen.append(dict(tick=s._cur[0], el=el, allowed=allowed.copy(), blocked=list(s._blocked),
                                 hand=tuple(s._cur[2].my_hand), nxt=s._cur[2].my_next, pend=len(s.pend)))
                ticks.append(s._cur[0])
                slot = script.get(i)
                i += 1
                s.apply(0.9, {"play": slot is not None, "slot": -1 if slot is None else slot,
                              "cell": TL.N_DEC * 0 + 36 * 40 + 5 if slot is not None else -1,
                              "why": "gate" if slot is not None else "wait"})
            else:
                s.apply(0.9, {"play": False, "slot": -1, "cell": -1, "why": "wait"})
    return m, ticks, seen


class TestSelfPlayPipelined(unittest.TestCase):
    def test_second_decision_on_the_frame_grid_and_each_play_lands_at_its_tick(self):
        m, ticks, _ = spy_match({0: 0, 1: 1}, dict(pipeline_decisions=True))
        self.assertEqual(ticks[:5], [90, 92, 116, 120, 130])
        acts = [(t, s) for t, s, *_ in m.env.log if s == 0]
        self.assertEqual(acts, [(116, 0), (118, 0)])                # each at its OWN landing tick: 90 + 26, 92 + 26
        self.assertEqual(m.learner.pipe_n["second_plays"], 1)
        self.assertEqual(m.learner.pipe_n["decisions_pending"], 2)  # the decision at 92 (one outstanding) and at 116

    def test_off_is_the_old_lock(self):
        m, ticks, _ = spy_match({0: 0, 1: 1})
        self.assertEqual(ticks[:3], [90, 120, 150])                 # 116 landing -> 120; the play decided at 120 lands 146 -> 150
        self.assertEqual([(t, s) for t, s, *_ in m.env.log if s == 0], [(116, 0), (146, 0)])
        self.assertFalse(hasattr(m.learner, "pipe_n") and m.learner.pipe_n)

    def test_the_pending_view_blocks_the_slot_and_deducts_the_elixir(self):
        m, ticks, seen = spy_match({0: 0}, dict(pipeline_decisions=True))
        first, second = seen[0], seen[1]
        self.assertEqual((first["pend"], first["blocked"]), (0, []))
        self.assertEqual(second["pend"], 1)
        self.assertEqual(second["el"], 4)                           # 7 - the 3 elixir of the pending card
        self.assertNotIn(0, [i for i, a in enumerate(second["allowed"]) if a and i == 0])   # the played slot is not choosable
        self.assertEqual(len(second["hand"]), 4)
        self.assertNotEqual(second["hand"], first["hand"])          # the pending card left the view's hand ...
        self.assertEqual(sorted(second["blocked"]), sorted(set(second["blocked"])))
        for slot in second["blocked"]:
            self.assertFalse(second["allowed"][slot])               # ... and the card in its position is masked

    def test_unaffordable_second_play_is_refused_by_the_shared_verdict_and_counted(self):
        env = TL._SPEnv(truth=lambda s, t: 5.0)                    # 5 - 3 (pending) = 2 < 3
        m, ticks, _ = spy_match({0: 0, 1: 1}, dict(pipeline_decisions=True), env=env)
        self.assertEqual(m.learner.pipe_n["blocked_unaffordable"], 1)
        self.assertEqual([(t, s) for t, s, *_ in m.env.log if s == 0], [(116, 0)])

    def test_the_same_slot_twice_is_blocked_by_the_verdict(self):
        m, ticks, _ = spy_match({0: 0, 1: 0}, dict(pipeline_decisions=True))
        self.assertEqual(m.learner.pipe_n["blocked_slot_busy"], 1)
        self.assertEqual(len([1 for t, s, *_ in m.env.log if s == 0]), 1)

    def test_a_refused_first_play_changes_nothing_for_the_second(self):
        env = TL._SPEnv(refuse=[(0, 116)])
        m, ticks, _ = spy_match({0: 0, 1: 1}, dict(pipeline_decisions=True), env=env)
        self.assertEqual([(t, s) for t, s, *_ in m.env.log if s == 0], [(116, 0), (118, 0)])   # B still tried, on its own
        self.assertEqual(ticks[:4], [90, 92, 116, 120])             # the cadence does not depend on the refusal
        self.assertEqual((m.learner.n_att, m.learner.n_acc), (2, 1))

    def test_lethal_rocket_sees_the_outstanding_play_as_a_card_pending(self):
        from pipeline.decision_options import match_kwargs
        cfg = TL._cfg("live", record=False, lethal_rocket="ot", lethal_log="off")
        bs = SimpleNamespace(t_sec=100.0, my_elixir=5.0)
        mk = lambda pend: SimpleNamespace(cfg=cfg, tag="t", k=0, side=0, deck=SimpleNamespace(cards=["a"] * 8), _cur=(0, bs, None),  # noqa: E731
                                          state={"episode": {"crown_towers": []}}, pend=pend)
        self.assertFalse(match_kwargs([mk([])])["lethal"][0][2])
        self.assertTrue(match_kwargs([mk([(1, 0.9, {}, None)])])["lethal"][0][2])

    def test_tau_delta_and_hazard_step_reach_the_decider_only_while_pending(self):
        from pipeline.decision_options import match_kwargs
        cfg = TL._cfg("live", record=False, gate_decode="hazard_below_tau", pipeline_tau_delta=0.2)
        bs = SimpleNamespace(t_sec=100.0, my_elixir=5.0, units=[])
        mk = lambda pend, hz: SimpleNamespace(cfg=cfg, tag="t", k=0, side=0, deck=SimpleNamespace(cards=["a"] * 8),   # noqa: E731
                                              _cur=(0, bs, None), state={}, pend=pend, _hz_step_ticks=hz)
        out = match_kwargs([mk([], None), mk([(1, 0.9, {}, None)], 2), mk([(1, 0.9, {}, None)], 0)])
        self.assertEqual(out["tau_delta"], [0.0, 0.2, 0.2])
        self.assertEqual([round(x, 3) for x in out["step_s"]], [0.5, 0.1, 0.0])    # decide_every 10 ticks = 0.5 s; 2 ticks; 0 after a play

    def test_needs_a_delay(self):
        with self.assertRaises(ValueError):
            spy_match({0: 0}, dict(pipeline_decisions=True, action_delay_ticks=0))


# ---- ghost Match (the sequential evaluator) -----------------------------------------------------------------------------
class TestGhostPipelined(unittest.TestCase):
    def run_ghost(self, script, **cfg):
        E.Match._pending_raw = lambda self, raw, vt: raw
        env = _Env(lambda t: 9.0)
        return AD._scripted(script, D, env=env, pipeline_decisions=True, **cfg)

    def test_decisions_on_the_grid_and_plays_at_their_landing_tick(self):
        play2 = dict(AD.PLAY, slot=5)                              # slot 2 (3 elixir) then slot 5 (3 elixir)
        m, env, ticks = self.run_ghost([AD.PLAY, play2])
        self.assertEqual(ticks[:4], [T, T + 2, T + D, T + D + 4])
        self.assertEqual([c[0] for c in env.eng.calls], [T + D, T + D + 2])
        r = m.result()
        self.assertEqual(r["pipeline_decisions"]["second_plays"], 1)
        self.assertEqual([p["land_tick"] for p in r["plays"]], [T + D, T + D + 2])

    def test_follow_ups_and_pipeline_are_separate(self):
        from pipeline import e1_eval as e
        with self.assertRaises(ValueError):
            self.run_ghost([dict(AD.PLAY, follow_ups=[e.follow_up_spec(5, AD.CELL, 4)])])


if __name__ == "__main__":
    unittest.main()
