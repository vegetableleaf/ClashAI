"""RoyaleSelfPlayEnv (pipeline/royale_env.py, L68 T12a): two policy-driven sides on RoyaleSim, no ghost.

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_royale_selfplay.py

Needs royalegym/royalesim (the Royale stack venv); skipped elsewhere.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

try:
    from pipeline.royale_env import RoyalePoolEnv, RoyaleSelfPlayEnv, UnsupportedDeck
except ImportError:                                   # no royalegym in this venv
    RoyaleSelfPlayEnv = None

ICEBOW = ["Tornado", "Tesla@evolution", "IceWizard", "Xbow", "Rocket", "Knight@evolution", "Log", "Skeletons"]
HOGEQ = ["HogRider", "Earthquake", "Log", "Cannon", "Musketeer", "IceSpirits", "Skeletons", "Valkyrie"]
STARTER = ["Knight", "GoblinHut", "Goblins", "Arrows", "Fireball", "Giant", "Musketeer", "MiniPekka"]
CELL = {0: (9000, 10000), 1: (9000, 22000)}            # own half, pool units (1,000 / tile), side 0 at low y


def cheapest_policy(env, obs, side, cost):
    """Play the cheapest affordable hand card at the side's fixed cell; None when nothing is affordable."""
    me = next(p for p in obs["players"] if p["side"] == side)
    names = [env.names[c] for c in env.deck_ids[side]]
    hand = sorted((cost[h["name"]], names.index(h["name"])) for h in me["hand"])
    if not hand or hand[0][0] > me["elixir_exact"]:
        return None
    return env.act(side, hand[0][1], *CELL[side])


def play_scripted(env, deck0, deck1, seed, every=20):
    cost = {c.name: c.elixir for c in env.core.cards()}
    obs = env.reset(deck0, deck1, seed)
    played = {0: 0, 1: 0}
    while not env.done:
        for s in (0, 1):
            r = cheapest_policy(env, obs, s, cost)
            played[s] += bool(r and r["accepted"])
        obs = env.advance_to(env.tick + every)
    return played


@unittest.skipIf(RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestSelfPlay(unittest.TestCase):
    def test_seeded_deal_reproducible_and_deck_consistent(self):
        env = RoyaleSelfPlayEnv()
        obs = env.reset(ICEBOW, HOGEQ, seed=3)
        a = {s: list(env.deal[s]) for s in (0, 1)}
        env.reset(ICEBOW, HOGEQ, seed=3)
        self.assertEqual(a, env.deal)
        env.reset(ICEBOW, HOGEQ, seed=4)
        self.assertNotEqual(a, env.deal)
        for s in (0, 1):
            self.assertEqual(sorted(a[s]), sorted(env.decks[s]))
            me = next(p for p in obs["players"] if p["side"] == s)
            self.assertEqual([h["name"] for h in me["hand"]], a[s][:4])          # hand = first four of the deal
            self.assertEqual(env.decks[s][me["next_deck_index"]], a[s][4])      # next = the fifth
        self.assertEqual(obs["tick"], 90)                                        # warm-up as RoyalePoolEnv

    def test_both_sides_act(self):
        env = RoyaleSelfPlayEnv()
        cost = {c.name: c.elixir for c in env.core.cards()}
        obs = env.reset(ICEBOW, HOGEQ, seed=0)
        for s in (0, 1):
            r = cheapest_policy(env, obs, s, cost)
            self.assertTrue(r and r["accepted"], r)
        obs = env.advance_to(env.tick + 30)
        self.assertEqual({e["side"] for e in obs["entities"] + obs["effects"]}, {0, 1})   # (a Log is an effect)
        for s in (0, 1):                                        # a queued card (deal slot 6) is not playable
            self.assertEqual(env.act(s, env.decks[s].index(env.deal[s][6]), *CELL[s]),
                             {"accepted": False, "result_code": 1003})

    def test_raw_matches_pool_env_for_same_deal_and_plays(self):
        sp = RoyaleSelfPlayEnv()
        sp.reset(ICEBOW, HOGEQ, seed=7)
        # a pool entry whose deck lists ARE the self-play deal and whose scripts are empty -> deal_order = identity
        item = lambda n: {"name": n, "slug": n}
        entry = {"tag": "t", "icebow_side": 0, "ghost_side": 1, "icebow_deck": [item(n) for n in sp.deal[0]],
                 "ghost_deck": [item(n) for n in sp.deal[1]], "icebow_commands": [], "ghost_commands": []}
        pool = RoyalePoolEnv(seed=7)
        pool.reset(entry)

        def same(a, b):
            for pa, pb in zip(a.pop("players"), b.pop("players")):   # next_deck_index indexes each env's deck order
                self.assertEqual(sp.decks[pa["side"]][pa.pop("next_deck_index")],
                                 pool.final_decks[pb["side"]][pb.pop("next_deck_index")]["name"])
                self.assertEqual(pa, pb)
            self.assertEqual(a, b)

        same(sp.raw(), pool.raw())
        for t in (90, 150):
            for s in (0, 1):
                cid = sp.core.state().players[s].hand[0]
                nm = sp.names[cid]
                ra = sp.act(s, sp.decks[s].index(nm), *CELL[s])
                rb = pool.eng.act(side=s, deck_index=sp.deal[s].index(nm), x=CELL[s][0], y=CELL[s][1])
                self.assertEqual(ra, rb)
            sp.advance_to(t + 60)
            pool._advance_to(t + 60)
            same(sp.raw(), pool.raw())
        self.assertEqual(sp.core.state_hash(), pool.core.state_hash())
        # each side's mirrored view (from_engine) is the same BoardState from either env
        from pipeline.obs_contract import from_engine, load_deck
        dk = load_deck("icebow")
        for s in (0, 1):
            va = from_engine(sp.raw(), s, dk, engine_deck=sp.decks[s], unmapped=set())
            vb = from_engine(pool.raw(), s, dk, engine_deck=[it["name"] for it in pool.final_decks[s]], unmapped=set())
            self.assertEqual(va, vb)
            self.assertTrue(va.units)

    def test_scripted_match_runs_to_completion(self):
        env = RoyaleSelfPlayEnv()
        played = play_scripted(env, ICEBOW, HOGEQ, seed=1)
        self.assertTrue(env.done)
        self.assertLessEqual(env.tick, env.tail_cap)
        self.assertGreater(min(played.values()), 20, played)
        o0, c0 = env.outcome(0)
        o1, c1 = env.outcome(1)
        self.assertEqual(c0, c1[::-1])
        self.assertEqual({o0, o1}, {"draw"} if o0 == "draw" else {"win", "loss"})
        self.assertTrue(all(0 <= c <= 3 for c in c0))

    def test_unloadable_deck_raises(self):
        env = RoyaleSelfPlayEnv()
        with self.assertRaises(UnsupportedDeck):
            env.reset(STARTER, HOGEQ, seed=0)                   # GoblinHut: not in RoyaleSim's catalogue
        with self.assertRaises(UnsupportedDeck):
            env.reset(ICEBOW, HOGEQ[:7] + ["Log"], seed=0)      # duplicate card

    def test_nine_cards_with_a_duplicate_raises(self):
        """T12b fix (a): 8 distinct ids is not enough -- the list must also BE 8 long."""
        env = RoyaleSelfPlayEnv()
        with self.assertRaises(UnsupportedDeck):
            env.reset(ICEBOW, HOGEQ + ["Log"], seed=0)           # 9 items, 8 distinct
        with self.assertRaises(UnsupportedDeck):
            env.reset(ICEBOW[:7], HOGEQ, seed=0)                 # 7

    def test_failed_reset_leaves_state_untouched(self):
        """T12b fix (b): validation happens before any assignment."""
        env = RoyaleSelfPlayEnv()
        env.reset(ICEBOW, HOGEQ, seed=5)
        before = (dict(env.decks), dict(env.deck_ids), env.seed, env.tick)
        with self.assertRaises(UnsupportedDeck):
            env.reset(STARTER, HOGEQ, seed=9)
        with self.assertRaises(UnsupportedDeck):
            env.reset(ICEBOW, HOGEQ + ["Log"], seed=9)
        self.assertEqual((dict(env.decks), dict(env.deck_ids), env.seed, env.tick), before)

    def test_costs_are_the_catalogue(self):
        env = RoyaleSelfPlayEnv()
        env.reset(ICEBOW, HOGEQ, seed=0)
        cat = {c.name: c.elixir for c in env.core.cards()}
        for s in (0, 1):
            self.assertEqual(env.costs(s), [cat[n] for n in env.decks[s]])


@unittest.skipIf(RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestLeagueMatchOnRoyaleSim(unittest.TestCase):
    """T12b: e1_eval.run_selfplay_batch on the REAL engine, the full live condition on both sides (clean obs, opp
    counter, delay 26, extrapolate 26): tiny random GenModels (learner, frozen snapshot) and a tiny S1Model (the icebow
    specialist, icebow only)."""

    def test_selfplay_batch_under_live_condition(self):
        import numpy as np
        import torch
        from pipeline import e1_eval as E
        from pipeline.dataset_gen import card_key
        from pipeline.e1_view import Noise
        from pipeline.model_gen import GenModel
        from pipeline.model_v3 import S1Model
        vocab = ["<pad>"] + sorted({card_key(n) for n in ICEBOW + HOGEQ})
        torch.manual_seed(0)
        learner = E.GenPolicy(GenModel(d=16, layers=1, heads=2, d_c=8, n_cards=len(vocab)).eval(), vocab)
        snap = E.GenPolicy(GenModel(d=16, layers=1, heads=2, d_c=8, n_cards=len(vocab)).eval(), vocab)
        s1 = S1Model(d=16, layers=1, heads=2).eval()
        cfg = {"policy": "sample", "tau": 0.27, "afford_mask": True, "stall_elixir": 9.0, "stall_seconds": 12.0,
               "obs": "live", "noise": Noise(**{n: False for n in E.NOISE_NAMES}), "p_random": 0.0,
               "random_hand_only": False, "grid": "lattice", "device": "cpu", "decide_every": 10, "slot": 0, "port": 0,
               "T": 0.5, "record": True, "opp_elixir": "counter", "action_delay_ticks": 26, "extrapolate_ticks": 26}
        ocfg = {**cfg, "record": False}
        spec = lambda i, opp, side, od: {"tag": f"sp_{i}", "opp": {"id": opp, "type": opp}, "learner_deck": HOGEQ,
                                         "opp_deck": od, "learner_side": side, "seed": i}
        jobs = [(0, spec(0, "snap", 0, HOGEQ), 0, {"rollout_index": 0, "update": 0}),
                (1, spec(1, "s1", 1, ICEBOW), 0, {"rollout_index": 0, "update": 0})]
        out = []
        E.run_selfplay_batch(lambda: RoyaleSelfPlayEnv(), learner, {"snap": (snap, ocfg), "s1": (s1, ocfg)}, jobs,
                             cfg, 2, on_result=out.append)
        self.assertEqual(len(out), 2)
        for r in out:
            self.assertIn(r["outcome"], ("win", "loss", "draw"))
            self.assertGreater(r["plays_accepted"], 5, r["tag"])
            self.assertGreater(r["opp_side"]["plays_accepted"], 5, r["tag"])
            self.assertEqual(len(r["traj"]["played"]), r["decisions"])
            self.assertTrue(all(p["land_tick"] == p["tick"] + 26 for p in r["plays"]))
            oc = r["opp_counter"]
            self.assertGreater(oc["fed"] + oc["dropped"], 0)
            self.assertLessEqual(oc["fed"] + oc["dropped"], r["opp_side"]["plays_accepted"])
            self.assertEqual(r["extrapolate_ticks"], 26)
            self.assertTrue(np.isfinite(r["traj"]["lp_cell"]).all())


if __name__ == "__main__":
    unittest.main()
