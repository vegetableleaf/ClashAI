"""pipeline/search_s0.py (L69 S0): fork fidelity / isolation, plain == e1_eval, the ported Scorer, the argmax rule.

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_search_s0.py

Needs royalegym/royalesim (the Royale stack venv); skipped elsewhere. Tiny random models: the properties are about the
machinery, not the policy.
"""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

try:
    from pipeline.royale_env import RoyaleSelfPlayEnv
    from pipeline import search_s0 as S
    from pipeline import e1_eval as E
except ImportError:                                   # no royalegym in this venv
    RoyaleSelfPlayEnv = None

ICEBOW = ["Tornado", "Tesla@evolution", "IceWizard", "Xbow", "Rocket", "Knight@evolution", "Log", "Skeletons"]
HOGEQ = ["HogRider", "Earthquake", "Log", "Cannon", "Musketeer", "IceSpirits", "Skeletons", "Valkyrie"]
CELL = E.GRID_X * 48 + 18 if RoyaleSelfPlayEnv else 0          # own half, board centre column (own-view frame)


def digest(obj, shared=()):
    """A comparable value of an object's python state (numpy arrays by bytes, RNGs by state), ``shared`` keys skipped."""
    if isinstance(obj, np.ndarray):
        return ("nd", str(obj.dtype), obj.shape, obj.tobytes())
    if isinstance(obj, np.random.Generator):
        return ("gen", repr(obj.bit_generator.state))
    if isinstance(obj, random.Random):
        return ("rand", obj.getstate())
    if isinstance(obj, dict):
        return tuple(sorted(((repr(k), digest(v)) for k, v in obj.items() if k not in shared), key=lambda x: x[0]))
    if isinstance(obj, (list, tuple)):
        return tuple(digest(v) for v in obj)
    if isinstance(obj, (set, frozenset)):
        return ("set", tuple(sorted(repr(v) for v in obj)))
    if isinstance(obj, (str, int, float, bool, type(None), np.generic)):
        return obj
    if hasattr(obj, "__dict__"):
        return (type(obj).__name__, digest(vars(obj)))
    return repr(obj)


def side_digest(s):
    return digest(vars(s), shared=S.SHARED_SIDE + ("t0",))


def env_digest(env):
    return digest(vars(env), shared=S.SHARED_ENV) + (digest(env.eng.last_episode),)


def tiny_models():
    import torch
    from pipeline.dataset_gen import card_key
    from pipeline.model_gen import GenModel
    from pipeline.model_v3 import S1Model
    vocab = ["<pad>"] + sorted({card_key(n) for n in ICEBOW + HOGEQ})
    torch.manual_seed(0)
    gen = E.GenPolicy(GenModel(d=16, layers=1, heads=2, d_c=8, n_cards=len(vocab)).eval(), vocab)
    opp_gen = E.GenPolicy(GenModel(d=16, layers=1, heads=2, d_c=8, n_cards=len(vocab)).eval(), vocab)
    s1 = S1Model(d=16, layers=1, heads=2).eval()
    return gen, opp_gen, s1


def runner(tail_cap=7200, horizon_s=4.0):
    gen, opp_gen, s1 = tiny_models()
    lcfg = S.live_cfg(S.TAU_PLAIN, "lattice")
    opps = {"s1": (s1, S.live_cfg(S.TAU_OPP, "lattice")), "gen": (opp_gen, S.live_cfg(S.TAU_OPP, "lattice"))}
    return S.Runner(gen, opps, lcfg, lambda: RoyaleSelfPlayEnv(tail_cap=tail_cap), horizon_s=horizon_s)


def scripted_round(m, ds):
    """Fixed action sequence through the real machinery: every other decision, the first allowed slot at CELL."""
    import torch
    from pipeline.model_v3 import hand_mask_from_sc
    for s in ds:
        s.prepare()
    todo = []
    for s in ds:
        hand = hand_mask_from_sc(torch.from_numpy(s._obs[2])[None])[0].numpy()
        _, allowed, _ = s.pre(hand)
        if allowed.any() and s.n_dec % 2 == 0:
            d = {"play": True, "slot": int(np.flatnonzero(allowed)[0]), "cell": CELL, "why": "gate"}
        else:
            d = {"play": False, "slot": -1, "cell": -1, "why": "wait"}
        todo.append((s, d))
    for s, d in todo:
        s.apply(0.5, d)


def same_ds(f, m, ds):
    return [f.learner if s is m.learner else f.opp for s in ds]


@unittest.skipIf(RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestFork(unittest.TestCase):
    def _mid_match(self, stop_tick=1200):
        cfg = S.live_cfg(S.TAU_PLAIN, "lattice")
        spec = {"tag": "fork", "opp": {"id": "x"}, "learner_deck": ICEBOW, "opp_deck": HOGEQ, "learner_side": 1,
                "seed": 5}
        m = E.SelfPlayMatch(RoyaleSelfPlayEnv(), spec, 0, cfg, {**cfg, "tau": S.TAU_OPP})
        while True:
            ds = m.due()
            self.assertTrue(ds)
            if m.env.tick >= stop_tick:
                return m, ds
            scripted_round(m, ds)

    def test_fork_fidelity(self):
        """(1) a fork driven by the same fixed action sequence = the real match: engine hash, env + both sides."""
        m, ds = self._mid_match()
        self.assertTrue(m.learner.n_acc > 3 and m.opp.n_acc > 3)
        f = S.fork_into(m, RoyaleSelfPlayEnv(), m.env.core.save_state())
        self.assertEqual(f.env.core.state_hash(), m.env.core.state_hash())
        for x, xds in ((m, ds), (f, same_ds(f, m, ds))):
            while xds and x.env.tick < 2400:
                scripted_round(x, xds)
                xds = x.due()
        self.assertEqual(f.env.tick, m.env.tick)
        self.assertGreaterEqual(m.env.tick, 2400)
        self.assertEqual(f.env.core.state_hash(), m.env.core.state_hash())
        self.assertEqual(env_digest(f.env), env_digest(m.env))
        for a, b in ((f.learner, m.learner), (f.opp, m.opp)):
            self.assertEqual(side_digest(a), side_digest(b))
        self.assertGreater(m.learner.n_acc, 8)                   # the segment after the fork really played

    def test_fork_isolation(self):
        """(2) all candidate rollouts leave the real match's engine, env fields and both sides unchanged; the
        candidate lands at root + 26 inside its fork; the opponent keeps playing in the forks."""
        run = runner()
        m = run.setup("s1", 3, ICEBOW)
        st = {k: 0 for k in ("eligible", "searched", "overrides", "chose_wait", "plain_wait_overridden", "moved_cell",
                             "n_cands")}
        st["search_s"] = 0.0
        rng = random.Random(0)
        while True:
            ds = m.due()
            self.assertTrue(ds)
            if m.learner in ds and m.env.tick >= 900:
                for s in ds:
                    s.prepare()
                p, enc, heads, hand = S.forward(m.learner)
                _, allowed, _ = m.learner.pre(hand)
                if allowed.any():
                    break
                for s in ds:
                    s.apply(0.5, {"play": False, "slot": -1, "cell": -1, "why": "wait"})
                continue
            run.round(m, ds, "plain", st, rng)
        cands = S.shortlist(run.learner, enc, heads, allowed, 4, 3)
        self.assertGreaterEqual(len(cands), 3)
        root = int(m.env.tick)
        before = (m.env.core.state_hash(), env_digest(m.env), side_digest(m.learner), side_digest(m.opp))
        ws, sc = run.rollout_scores(m, ds, cands, p)
        after = (m.env.core.state_hash(), env_digest(m.env), side_digest(m.learner), side_digest(m.opp))
        self.assertEqual(before, after)
        self.assertEqual(len(sc), len(cands))
        self.assertTrue(all(np.isfinite([ws] + sc)))
        forks = run.last_forks
        self.assertTrue(all(f.env.tick == root + run.H for f in forks))
        self.assertEqual(forks[0].learner.n_att, m.learner.n_att)                  # WAIT fork: no play
        for f in forks[1:]:
            self.assertEqual(f.learner.plays[-1]["land_tick"], root + 26)
            self.assertEqual(f.learner.n_att, m.learner.n_att + 1)                  # the candidate, nothing else
        self.assertTrue(any(f.opp.n_att > m.opp.n_att for f in forks))             # the self-model opponent played
        self.assertIs(m.opp.model, run.opps["s1"][0])                             # the real opponent kept its policy


@unittest.skipIf(RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestPlainIsE1(unittest.TestCase):
    def test_plain_reproduces_run_selfplay_batch(self):
        """(3) the plain arm = e1_eval.run_selfplay_batch for the same setup/seed (whole learner record)."""
        run = runner(tail_cap=1200)
        for opp_id, deck, seed in (("s1", ICEBOW, 2), ("gen", HOGEQ, 3)):
            rec = run.play("plain", run.setup(opp_id, seed, deck))
            mine = dict(run.last_result)
            opp, ocfg = run.opps[opp_id]
            spec = {"tag": f"s0:{opp_id}:{seed}", "opp": {"id": opp_id}, "learner_deck": list(E.ICEBOW_ENGINE_DECK),
                    "opp_deck": list(deck), "learner_side": seed % 2, "seed": seed}
            out = []
            E.run_selfplay_batch(lambda: RoyaleSelfPlayEnv(tail_cap=1200), run.learner, {opp_id: (opp, ocfg)},
                                 [(0, spec, 0)], run.lcfg, 1, on_result=out.append)
            ref = dict(out[0])
            for r in (mine, ref):
                r.pop("wall_s")
            self.assertEqual(mine, ref)
            self.assertGreater(rec["plays_attempted"], 0)           # (a random tiny policy: its cells get refused)
            self.assertGreater(ref["opp_side"]["plays_attempted"], 0)
            self.assertEqual((rec["outcome"], rec["crowns_for"], rec["crowns_against"], rec["plays_accepted"]),
                             (ref["outcome"], ref["crowns_for"], ref["crowns_against"], ref["plays_accepted"]))


@unittest.skipIf(RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestScorer(unittest.TestCase):
    # threat_value.bodies_ignore_frac(db, ["knight"], tower_level=11, enemy_level=11), icebow card DB (at tower 15 it
    # is 0.3021846697339407 -- the hard-coded level this replaced)
    KNIGHT_FRAC = 0.6597358327221133
    P, K = 3052, 4824                    # RoyaleSim's princess / king max_hp = clashrl.levels PRINCESS_HP / KING_HP [11]

    @classmethod
    def state(cls, towers, units, crowns, pmax=None, kmax=None):
        from royalegym.protocol import EntityKind
        pmax, kmax = pmax or cls.P, kmax or cls.K
        ents = []
        for team, (l, r, k) in towers.items():
            ents += [SimpleNamespace(team=team, kind=EntityKind.PRINCESS_TOWER, hp=l, max_hp=pmax, card_id=-1),
                     SimpleNamespace(team=team, kind=EntityKind.PRINCESS_TOWER, hp=r, max_hp=pmax, card_id=-1),
                     SimpleNamespace(team=team, kind=EntityKind.KING_TOWER, hp=k, max_hp=kmax, card_id=-1)]
        ents += [SimpleNamespace(team=t, kind=kind, hp=hp, max_hp=hp, card_id=cid) for t, kind, hp, cid in units]
        return SimpleNamespace(entities=ents, players=[SimpleNamespace(crowns=c) for c in crowns])

    def test_hand_computed(self):
        """(4) level-11 towers. Before: all full, our Knight. After: their left princess dead (-1.0), our right princess
        -916 hp (-916/3052), one Xbow ours, three theirs (3 x 0.366 capped at 1.0), 1-0 crowns, spent 6. Hand:
        1.0 - 916/3052 - 6*0.061 + ((0.366 - 1.0) - (KNIGHT - 0)) + 1 = 0.040133..."""
        from royalegym.protocol import EntityKind
        cat = [SimpleNamespace(card_id=0, name="Knight", elixir=3, count=1),
               SimpleNamespace(card_id=1, name="Xbow", elixir=6, count=1)]
        sc = S.Scorer(cat, tower_level=11, card_level=11)
        full, tot = (self.P, self.P, self.K), (2 * self.P + self.K) / self.P
        s0 = sc.snapshot(self.state({0: full, 1: full}, [(0, EntityKind.TROOP, 500, 0)], (0, 0)), us=0)
        self.assertEqual((s0["bv1"], s0["cr0"], s0["cr1"]), (0.0, 0, 0))
        self.assertAlmostEqual(s0["ours"], tot)
        self.assertAlmostEqual(s0["theirs"], tot)
        self.assertAlmostEqual(s0["bv0"], self.KNIGHT_FRAC, places=12)
        xb = lambda t: (t, EntityKind.BUILDING, 1000, 1)
        after = {0: (self.P, self.P - 916, self.K), 1: (0, self.P, self.K)}
        s1 = sc.snapshot(self.state(after, [xb(0), xb(1), xb(1), xb(1)], (1, 0)), us=0)
        self.assertAlmostEqual(s1["ours"], tot - 916 / self.P)
        self.assertAlmostEqual(s1["theirs"], tot - 1.0)
        self.assertAlmostEqual(s1["bv0"], 0.366)
        self.assertAlmostEqual(s1["bv1"], 1.0)                   # 3 x 0.366 = 1.098 -> BOARD_CAP
        hand = 1.0 - 916 / 3052 - 6 * 0.061 + ((0.366 - 1.0) - (self.KNIGHT_FRAC - 0.0)) + 1.0 * (1 - 0)
        self.assertAlmostEqual(sc.score(s0, s1, 6.0), hand, places=12)
        self.assertAlmostEqual(hand, 0.04013310567893513, places=12)
        # the other side's view of the same pair: us = 1
        t0 = sc.snapshot(self.state({0: full, 1: full}, [(0, EntityKind.TROOP, 500, 0)], (0, 0)), us=1)
        t1 = sc.snapshot(self.state(after, [xb(0), xb(1), xb(1), xb(1)], (1, 0)), us=1)
        self.assertAlmostEqual(sc.score(t0, t1, 0.0), -0.4061331056789351, places=12)   # 916/3052 - 1 + (0.634 + K) - 1

    def test_dead_units_and_towers(self):
        from royalegym.protocol import EntityKind
        sc = S.Scorer([SimpleNamespace(card_id=0, name="Knight", elixir=3, count=1)], tower_level=11, card_level=11)
        s = sc.snapshot(self.state({0: (0, -5, 0), 1: (self.P, self.P, self.K)}, [(1, EntityKind.TROOP, 0, 0)], (0, 3)),
                        us=0)
        self.assertEqual((s["ours"], s["bv1"]), (0.0, 0.0))     # negative hp clipped; a 0-hp body is not on board

    def test_tower_level_must_match_the_state(self):
        """A Scorer whose tower_level is not the state's princess level refuses to score (the verifier's bug: 15 vs 11);
        engine_tower_level reads 11 / 15 from the tables and refuses unknown or mixed levels."""
        cat = [SimpleNamespace(card_id=0, name="Knight", elixir=3, count=1)]
        st11 = self.state({0: (self.P,) * 2 + (self.K,), 1: (self.P,) * 2 + (self.K,)}, [], (0, 0))
        with self.assertRaises(ValueError):
            S.Scorer(cat, tower_level=15, card_level=11).snapshot(st11, us=0)
        self.assertEqual(S.engine_tower_level(st11), 11)
        st15 = self.state({0: (4424, 4424, 7032), 1: (4424, 4424, 7032)}, [], (0, 0), pmax=4424, kmax=7032)
        self.assertEqual(S.engine_tower_level(st15), 15)
        S.Scorer(cat, tower_level=15, card_level=11).snapshot(st15, us=0)        # consistent -> fine
        for pm, km in ((1000, 2000), (3052, 7032)):                             # unknown / princess-king disagree
            with self.assertRaises(ValueError):
                S.engine_tower_level(self.state({0: (pm, pm, km), 1: (pm, pm, km)}, [], (0, 0), pmax=pm, kmax=km))

    def test_scorer_levels_are_the_engines(self):
        """The Scorer the Runner builds (make_scorer) uses the ENGINE's princess level and card level, and its
        threat_value tower HP is the engine's princess max_hp: fails if a level is hard-coded differently."""
        from clashrl import levels, threat_value as TV
        from royalegym.protocol import EntityKind
        env = RoyaleSelfPlayEnv()
        env.reset(ICEBOW, HOGEQ, seed=0)
        st = env.core.state()
        pmax = {e.max_hp for e in st.entities if e.kind == EntityKind.PRINCESS_TOWER}
        self.assertEqual(len(pmax), 1)
        pmax = pmax.pop()
        sc = S.make_scorer(env)
        self.assertEqual(sc.tower_level, levels.PRINCESS_HP.index(pmax))
        self.assertEqual(TV.tower_hp(sc.tower_level), pmax)
        self.assertEqual(sc.card_level, int(env.core.card_level))
        self.assertEqual((sc.tower_level, sc.card_level), (11, 11))              # RoyaleSim today, measured
        sc.snapshot(st, us=0)                                                     # the consistency check passes
        cards = {c.name: c for c in env.core.cards()}                           # DB stats at the engine's card level
        for n in ("Knight", "IceWizard", "HogRider", "Valkyrie"):
            from pipeline.dataset_gen import card_key
            self.assertEqual(levels.scale(sc.db.get(card_key(n))["hitpoints"], sc.card_level, levels.REF_LEVEL),
                             cards[n].hitpoints, n)


@unittest.skipIf(RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestChoose(unittest.TestCase):
    def test_argmax_rule(self):
        """(5) all equal -> WAIT; one dominating -> it; ties among candidates -> the first."""
        self.assertEqual(S.choose(0.0, [0.0, 0.0, 0.0]), -1)
        self.assertEqual(S.choose(0.2, [0.2, 0.2]), -1)
        self.assertEqual(S.choose(0.0, [-1.0, 0.5, 0.2]), 1)
        self.assertEqual(S.choose(0.0, [0.3, 0.3]), 0)
        self.assertEqual(S.choose(1.0, [0.5, 0.9]), -1)

    def test_arm_decide_follows_scores(self):
        cands = [{"play": True, "slot": s, "cell": c, "why": "search"} for s in (2, 5) for c in (100, 200)]
        orig = S.shortlist
        S.shortlist = lambda *a, **k: [dict(c) for c in cands]
        try:
            run = S.Runner.__new__(S.Runner)
            run.learner, run.topk, run.cells, run.search_min_p = None, 4, 3, 0.0
            plain = {"play": True, "slot": 2, "cell": 100, "why": "gate"}
            for scores, want in (([0.1, 0.1, 0.1, 0.1], None), ([0.0, 0.0, 0.9, 0.0], cands[2])):
                run.rollout_scores = lambda m, ds, cs, p, sc=scores: (0.1, list(sc))
                st = {k: 0 for k in ("searched", "overrides", "chose_wait", "plain_wait_overridden", "moved_cell",
                                     "n_cands")}
                st["search_s"] = 0.0
                d = run.arm_decide(None, None, "search", 0.5, None, None, np.ones(8, bool), plain, st, random.Random(0))
                if want is None:
                    self.assertEqual(d, S.WAIT)
                    self.assertEqual((st["chose_wait"], st["overrides"]), (1, 1))
                else:
                    self.assertEqual((d["slot"], d["cell"]), (want["slot"], want["cell"]))
                    self.assertEqual((st["chose_wait"], st["overrides"]), (0, 1))
        finally:
            S.shortlist = orig

    def test_search_min_p_gate(self):
        """--search-min-p: p < P and not stalled -> WAIT with NO rollout (unsearched); stalled or p >= P -> searched;
        force_play ignores it. P = 1.0 therefore turns every unstalled search decision into a plain-rule WAIT."""
        cands = [{"play": True, "slot": 2, "cell": 100, "why": "search"}]
        orig = S.shortlist
        S.shortlist = lambda *a, **k: [dict(c) for c in cands]
        calls = []
        try:
            run = S.Runner.__new__(S.Runner)
            run.learner, run.topk, run.cells = None, 4, 3
            run.rollout_scores = lambda m, ds, cs, p: calls.append(p) or (0.0, [1.0])      # candidate dominates
            plain_wait = {"play": False, "slot": 2, "cell": -1, "why": "wait"}
            for P, p, stalled, arm, want_search in ((1.0, 0.5, False, "search", False), (1.0, 0.99, False, "search", False),
                                                     (1.0, 0.5, True, "search", True), (0.4, 0.5, False, "search", True),
                                                     (0.0, 0.01, False, "search", True),
                                                     (1.0, 0.5, False, "force_play", True)):
                run.search_min_p = P
                st = {k: 0 for k in ("searched", "unsearched", "gate_skipped", "overrides", "chose_wait",
                                     "plain_wait_overridden", "moved_cell", "n_cands")}
                st["search_s"] = 0.0
                n0 = len(calls)
                d = run.arm_decide(None, None, arm, p, None, None, np.ones(8, bool), plain_wait, st, random.Random(0),
                                   stalled=stalled)
                case = (P, p, stalled, arm)
                if want_search:
                    self.assertEqual((st["searched"], st["unsearched"]), (1, 0), case)
                    self.assertTrue(d["play"], case)
                    self.assertEqual(len(calls) - n0, int(arm == "search"), case)
                else:
                    self.assertEqual(d, S.GATE_SKIP, case)
                    self.assertFalse(d["play"], case)
                    self.assertEqual((st["searched"], st["unsearched"], st["gate_skipped"], st["overrides"]),
                                     (0, 1, 1, 0), case)                    # = the plain WAIT: no override
                    self.assertEqual(len(calls), n0, case)                # no rollout ran
        finally:
            S.shortlist = orig


@unittest.skipIf(RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestNeverArm(unittest.TestCase):
    def test_never_plays_zero_cards(self):
        """never: our side attempts NO play (stall rule included) on a setup where plain does play; same pairing."""
        run = runner(tail_cap=1200)
        pl = run.play("plain", run.setup("s1", 2, ICEBOW))
        nv = run.play("never", run.setup("s1", 2, ICEBOW))
        self.assertGreater(pl["plays_attempted"], 0)
        self.assertEqual((nv["plays_attempted"], nv["plays_accepted"]), (0, 0))
        self.assertGreater(nv["decisions"], 50)
        self.assertGreater(run.last_result["opp_side"]["plays_attempted"], 0)   # tiny random cells: often refused
        self.assertEqual((nv["learner_side"], nv["opp_deck"], nv["seed"]), (pl["learner_side"], pl["opp_deck"], pl["seed"]))
        self.assertEqual((nv["device"], nv["search_min_p"]), ("cpu", 0.0))
        self.assertTrue(all(p["why"] != "stall" for p in run.last_result["plays"]))


if __name__ == "__main__":
    unittest.main()
