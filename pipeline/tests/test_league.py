"""Offline tests for the self-play LEAGUE (L68 T12b): e1_eval's SelfPlayMatch / run_selfplay_batch and rl_royale's
league sampling, snapshots, resume, monitors and the leash.

    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_league.py

No engine, no GPU, no royalegym: a fake RoyaleSelfPlayEnv (``_SPEnv``: both players' hands, a tick clock, an engine
face that logs every act with its tick and side) runs the REAL SelfPlayMatch / run_selfplay_batch with tiny random
GenModels (learner, frozen opponent) and a tiny S1Model (the icebow specialist). The real-engine version of the match
test is in test_royale_selfplay.py (Royale venv).
"""
from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import torch                                                              # noqa: E402

from pipeline import e1_eval as E                                         # noqa: E402
from pipeline import rl_royale as RL                                      # noqa: E402
from pipeline.dataset_gen import card_key                                 # noqa: E402
from pipeline.e1_view import Noise                                        # noqa: E402
from pipeline.model_gen import GenModel                                   # noqa: E402
from pipeline.tests.test_e1_batch import _tiny_model                      # noqa: E402
from pipeline.tests.test_obs_contract import TOWERS                       # noqa: E402
from pipeline.tests.test_rl_gen import _stub_learner                      # noqa: E402
from pipeline.tests.test_rl_royale import CFG                             # noqa: E402

ICEBOW = list(E.ICEBOW_ENGINE_DECK)
HOGEQ = ["HogRider", "Earthquake", "Log", "Cannon", "Musketeer", "IceSpirits", "Skeletons", "Valkyrie"]
VOCAB = ["<pad>"] + sorted({card_key(n) for n in ICEBOW + HOGEQ} | {"golem", "zap"})
TAU, T, D = 0.27, 0.5, 26
N_DEC = 14                                              # decision rounds per fake match (tail_cap = 90 + 10 N_DEC)


def _tiny_gen(seed=0):
    torch.manual_seed(seed)
    return GenModel(d=16, layers=1, heads=2, d_c=8, n_cards=len(VOCAB)).eval()


class _SPEng:
    def __init__(self, env):
        self.env, self.calls, self.last_episode = env, [], None

    def act(self, side, deck_index, x, y):
        self.env.log.append((self.env.tick, side, deck_index, x, y))
        if (side, self.env.tick) in self.env.refuse:
            return {"accepted": False, "result_code": 2008}
        return {"accepted": True, "result_code": 0}


class _SPEnv:
    """What SelfPlayMatch needs of RoyaleSelfPlayEnv. ``truth(side, tick)`` = each side's TRUE elixir in raw()."""

    _code_names = {2008: "out_of_territory"}

    def __init__(self, tail=10 * N_DEC, refuse=(), truth=None):
        self.tail, self.refuse = tail, set(refuse)
        self.truth = truth or (lambda s, t: 7.0)

    def reset(self, deck0, deck1, seed=0):
        self.decks = {0: [n.split("@")[0] for n in deck0], 1: [n.split("@")[0] for n in deck1]}
        self.seed, self.tick, self.terminated, self.log = seed, 90, False, []
        self.tail_cap = 90 + self.tail
        self.eng = _SPEng(self)
        self.advances = []
        return self.raw()

    @property
    def done(self):
        return self.terminated or self.tick >= self.tail_cap

    def _advance_to(self, t):
        self.advances.append(int(t))
        self.tick = max(self.tick, int(t))

    def costs(self, side):
        return [3] * 8

    def raw(self):
        towers = [{"side": s, "type": typ, "x": x, "y": y, "hp": hp, "max_hp": mhp, "destroyed": False}
                  for (s, typ, lane, x, y, hp, mhp) in TOWERS]
        ents = [{"side": 0, "x": 4000, "y": 9000 + self.tick, "card_id": 26000000, "name": "Knight", "hp": 1000,
                 "max_hp": 1400, "kind": 15, "entity_id": 1},
                {"side": 1, "x": 14000, "y": 22000 - self.tick, "card_id": 26000021, "name": "HogRider", "hp": 1200,
                 "max_hp": 1697, "kind": 15, "entity_id": 2}]
        players = [{"side": s, "elixir_exact": float(self.truth(s, self.tick)), "next_deck_index": 4,
                    "hand": [{"hand_index": i, "name": n} for i, n in enumerate(self.decks[s][:4])]} for s in (0, 1)]
        return {"tick": self.tick, "players": players, "entities": ents, "effects": [],
                "episode": {"crown_towers": towers}}

    def outcome(self, side):
        return ("win", (1, 0)) if side == 0 else ("loss", (0, 1))


def _cfg(policy="sample", record=True, **kw):
    c = {"policy": policy, "tau": TAU, "afford_mask": True, "stall_elixir": 9.0, "stall_seconds": 12.0,
         "obs": "clean", "noise": Noise(), "p_random": 0.0, "random_hand_only": False, "grid": "lattice",
         "device": "cpu", "decide_every": 10, "slot": 0, "port": 0, "T": T, "record": record}
    c.update(kw)
    return c


def _spec(i=0, opp="snapA", side=0, ldeck=HOGEQ, odeck=ICEBOW, typ="snapshot"):
    return {"tag": f"sp0000_{i:02d}", "opp": {"id": opp, "cat": "latest", "type": typ, "path": "x"},
            "learner_deck": list(ldeck), "learner_deck_name": "r2", "learner_bucket": "head",
            "opp_deck": list(odeck), "opp_deck_name": "icebow", "learner_side": side, "seed": 7}


def _run(jobs, learner, opponents, cfg, make_env=_SPEnv, n=2, spy=None):
    out, envs = [], []

    def mk():
        envs.append(make_env())
        return envs[-1]
    orig = E.SelfPlayMatch.__init__
    if spy is not None:
        def init(self, *a, **k):
            orig(self, *a, **k)
            spy.append(self)
        E.SelfPlayMatch.__init__ = init
    try:
        E.run_selfplay_batch(mk, learner, opponents, jobs, cfg, n, on_result=out.append)
    finally:
        E.SelfPlayMatch.__init__ = orig
    return out, envs


# ------------------------------------------------------------------------------------------------------
class TestSelfPlayMatch(unittest.TestCase):
    """Both sides act, each with its own mirrored side; only the learner is recorded; per-policy batching."""

    @classmethod
    def setUpClass(cls):
        cls.learner = E.GenPolicy(_tiny_gen(1), VOCAB)
        cls.opp = E.GenPolicy(_tiny_gen(2), VOCAB)
        cls.s1 = _tiny_model(3)
        opps = {"snapA": (cls.opp, _cfg("sample", record=False)), "s1": (cls.s1, _cfg("live", record=False, tau=0.05))}
        jobs = [(0, _spec(0, "snapA", 0), 0, {"rollout_index": 0, "update": 0}),
                (0, _spec(0, "snapA", 0), 1, {"rollout_index": 1, "update": 0}),
                (1, _spec(1, "s1", 1, ldeck=HOGEQ, odeck=ICEBOW, typ="s1"), 0, {"rollout_index": 0, "update": 0})]
        cls.spy = []
        cls.calls = Counter()
        orig = E.GenPolicy.forward_batch

        def counting(self, rows, device="cpu"):
            cls.calls[id(self)] += 1
            return orig(self, rows, device)
        E.GenPolicy.forward_batch = counting
        try:
            cls.res, cls.envs = _run(jobs, cls.learner, opps, _cfg(), n=3, spy=cls.spy)
        finally:
            E.GenPolicy.forward_batch = orig

    def test_both_sides_act(self):
        for m in self.spy:
            sides = {s for _, s, *_ in m.env.log}
            self.assertEqual(sides, {0, 1}, m.spec["tag"])
            self.assertGreater(m.learner.n_acc, 3)
            self.assertGreater(m.opp.n_acc, 3)

    def test_only_learner_recorded(self):
        self.assertEqual(len(self.res), 3)
        for r, m in zip(sorted(self.res, key=lambda r: (r["tag"], r["k"])),
                        sorted(self.spy, key=lambda m: (m.spec["tag"], m.learner.k))):
            self.assertEqual(len(r["traj"]["played"]), m.learner.n_dec)
            self.assertEqual(r["side"], m.learner.side)
            self.assertEqual(m.opp.traj, [])
            self.assertEqual(r["opp_side"]["plays_attempted"], m.opp.n_att)
            self.assertEqual(r["ghost_delivered"], m.opp.n_acc)                # the opponent's plays in the ghost keys
            self.assertEqual(r["league"]["opp"]["id"], m.spec["opp"]["id"])
            self.assertEqual(r["outcome"], "win" if m.learner.side == 0 else "loss")
            self.assertIn("hand_card", r["traj"])                              # the generalist's own rows

    def test_sides_mirror_and_act_on_own_deck(self):
        for m in self.spy:
            for s in m.sides:
                self.assertEqual(s.mirror, s.side == 1)
                self.assertEqual([x.split("@")[0] for x in s.engine_deck], m.env.decks[s.side])
            s1_side = [s for s in m.sides if s.model is self.s1]
            if s1_side:
                self.assertEqual(s1_side[0].deck, E.load_deck("icebow"))          # S1's own slot order

    def test_one_forward_per_policy_per_round(self):
        rounds = max(len(set(m.env.advances)) for m in self.spy) + 1
        self.assertLessEqual(self.calls[id(self.learner)], rounds + 1)         # batched across the 3 matches
        self.assertLessEqual(self.calls[id(self.opp)], rounds + 1)
        self.assertGreater(self.calls[id(self.learner)], 5)

    def test_learner_batch_collates_and_is_on_policy(self):
        Bn, st = RL.collate(self.res)
        B = RL.to_device(Bn, "cpu")
        self.assertEqual(st["groups"], 2)
        R = RL.ref_terms(self.learner.model, B, TAU, T)
        t = RL.policy_terms(self.learner.model, B, torch.arange(len(B["A"])), TAU, T)
        for k in ("lp_gate", "lp_card", "lp_cell"):
            self.assertLess(float((t[k] - B[k]).abs().max().detach()), 1e-4, k)
        self.assertEqual(R["x"].shape[0], len(B["A"]))

    def test_record_refused_on_opponent(self):
        with self.assertRaises(ValueError):
            E.run_selfplay_batch(_SPEnv, self.learner, {"a": (self.opp, _cfg("sample", record=True))}, [], _cfg(), 1,
                                 on_result=print)


class TestSelfPlayCounters(unittest.TestCase):
    """cfg["opp_elixir"]: each side's counter is fed ONLY the other side's ACCEPTED plays, at their landing tick,
    never either side's true elixir."""

    def _match(self, truth=None, refuse=(), delay=0):
        learner, opp = E.GenPolicy(_tiny_gen(4), VOCAB), E.GenPolicy(_tiny_gen(5), VOCAB)
        fed = {}
        from pipeline.opp_elixir_count import OppElixirCounter
        orig = OppElixirCounter.play

        def spy(self, t, key, cost):
            fed.setdefault(id(self), []).append((int(t), key))
            return orig(self, t, key, cost)
        OppElixirCounter.play = spy
        spy_m = []
        try:
            cfg = _cfg(opp_elixir="counter_all", action_delay_ticks=delay)
            res, envs = _run([(0, _spec(0, "o", 0), 0, {"rollout_index": 0, "update": 0})], learner,
                             {"o": (opp, {**cfg, "record": False})}, cfg,
                             make_env=lambda: _SPEnv(truth=truth, refuse=refuse), n=1, spy=spy_m)
        finally:
            OppElixirCounter.play = orig
        m = spy_m[0]
        return m, res[0], {s.side: fed.get(id(s.opp_counter), []) for s in m.sides}

    def test_fed_only_other_sides_accepted_plays(self):
        refuse = {(1, t) for t in range(90, 400, 30)}                   # some opponent plays refused by the engine
        m, r, fed = self._match(refuse=refuse)
        for s in m.sides:
            got = fed[s.side]
            self.assertTrue(got, s.side)
            self.assertEqual(got, s.other.accepted[:len(got)])           # in order, a prefix: accepted plays only
            self.assertEqual(len(s.other.accepted), s.other.n_acc)
            last_dec = 90 + 10 * (s.n_dec - 1)
            # everything the other side landed BEFORE this side's last look (a play made on that same tick is made
            # after both sides looked: invisible to board and counter alike)
            self.assertEqual(got, [x for x in s.other.accepted if x[0] < last_dec])
        self.assertFalse({t for t, _ in m.opp.accepted} & {t for _, t in refuse})
        self.assertGreater(m.opp.n_att - m.opp.n_acc, 0)                 # the refusals happened

    def test_never_reads_true_elixir(self):
        _, a, _ = self._match(truth=lambda s, t: 7.0 if s == 0 else 7.5)
        _, b, _ = self._match(truth=lambda s, t: 7.0 if s == 0 else 9.9)    # opponent's TRUE elixir differs
        for k in ("played", "slot", "cell", "lp_gate"):
            np.testing.assert_array_equal(a["traj"][k], b["traj"][k])
        np.testing.assert_array_equal(a["traj"]["sc"], b["traj"]["sc"])
        self.assertNotEqual(a["opp_counter"]["bias"], b["opp_counter"]["bias"])   # the truth only reaches the diagnostic

    def test_delayed_plays_land_later_and_feed_at_landing(self):
        m, r, fed = self._match(delay=D)
        for s in m.sides:
            acts = [t for (t, sd, *_) in m.env.log if sd == s.side]
            self.assertEqual(acts, [p["land_tick"] for p in s.plays if "land_tick" in p and p.get("reason") !=
                                    "match_over_before_landing"])
            for p in s.plays:
                self.assertEqual(p["land_tick"], p["tick"] + D)
        for s in m.sides:
            self.assertEqual(fed[s.side], s.other.accepted[:len(fed[s.side])])
            self.assertTrue(all(t % 10 == (90 + D) % 10 for t, _ in fed[s.side]))   # landing ticks, not decision ones


class TestCounterSchedule(unittest.TestCase):
    """T12b a2: the opp-elixir counter counts with the COUNTED engine's regen schedule."""

    def test_default_is_the_real_engine_schedule(self):
        from pipeline import opp_elixir_count as oc
        a, b = oc.OppElixirCounter(), oc.OppElixirCounter(schedule=None)
        self.assertEqual(a.schedule, oc.REGEN_SCHEDULE)
        for t in (0, 100, 2400, 4799, 4800, 5000, 6002, 7000):
            self.assertEqual(a.regen(0, t), oc.regen_between(0, t))
        a.play(300, "knight", 3.0)
        b.play(300, "knight", 3.0)
        for t in (500, 2500, 5000, 6100):
            self.assertEqual(a.at(t), b.at(t))

    def test_royalesim_schedule_has_no_triple_phase(self):
        from pipeline import opp_elixir_count as oc
        sim = ((0, 1 / 56), (2400, 1 / 28), (6000, 0.0))
        c = oc.OppElixirCounter(schedule=sim)
        self.assertAlmostEqual(c.regen(4800, 5400), 600 / 28)
        self.assertAlmostEqual(oc.regen_between(4800, 5400), 600 * 0.0537)
        c.play(4800, "golem", 8.0)                                            # from 10 (capped) -> 2.0 at 4800
        self.assertAlmostEqual(c.at(4856), 2.0 + 56 / 28)

    def test_match_uses_env_schedule(self):
        learner, opp = E.GenPolicy(_tiny_gen(30), VOCAB), E.GenPolicy(_tiny_gen(31), VOCAB)
        sim = ((0, 1 / 56), (2400, 1 / 28), (6000, 0.0))

        class SimEnv(_SPEnv):
            elixir_regen_schedule = sim
        cfg = _cfg(opp_elixir="counter_all", extrapolate_ticks=26)
        for mk, want in ((SimEnv, sim), (_SPEnv, None)):
            spy = []
            _run([(0, _spec(0, "o", 0), 0)], learner, {"o": (opp, {**cfg, "record": False})}, cfg, make_env=mk, n=1,
                 spy=spy)
            from pipeline.opp_elixir_count import REGEN_SCHEDULE
            for s in spy[0].sides:
                self.assertEqual(s.opp_counter.schedule, want or REGEN_SCHEDULE)

    def test_royale_env_declares_the_measured_schedule(self):
        src = (REPO / "pipeline" / "royale_env.py").read_text(encoding="utf-8")
        self.assertIn("REGEN_SCHEDULE = ((0, 1 / 56), (2400, 1 / 28), (6000, 0.0))", src)
        self.assertIn("self.elixir_regen_schedule = REGEN_SCHEDULE", src)


class TestSelfPlayDelayInterleave(unittest.TestCase):
    def test_other_side_keeps_deciding_while_pending(self):
        learner = E.GenPolicy(_tiny_gen(6), VOCAB)
        opp = E.GenPolicy(_tiny_gen(7), VOCAB)
        cfg = _cfg(action_delay_ticks=D, tau=0.01)                         # the learner plays nearly every decision
        ocfg = _cfg("live", record=False, tau=0.999, stall_elixir=None, action_delay_ticks=D)   # the opponent waits
        spy = []
        res, envs = _run([(0, _spec(0, "o", 0), 0)], learner, {"o": (opp, ocfg)}, cfg, n=1, spy=spy)
        m = spy[0]
        L = [p for p in m.learner.plays]
        self.assertTrue(L)
        opp_ticks = set(range(90, m.env.tail_cap, 10))                      # the waiting opponent decides every 10
        self.assertEqual(m.opp.n_dec, len(opp_ticks))
        dec_ticks = [p["tick"] for p in L]
        for a, b in zip(dec_ticks, dec_ticks[1:]):
            self.assertGreaterEqual(b - a, 30)                             # the learner: next decision after landing
        self.assertEqual(m.opp.n_att, 0)
        self.assertEqual([t for (t, sd, *_) in m.env.log if sd == m.learner.side],
                         [p["land_tick"] for p in L if p.get("reason") != "match_over_before_landing"])


class TestFrozenOpponent(unittest.TestCase):
    def test_opponent_weights_never_change_across_an_update(self):
        learner_m, opp_m, s1_m = _tiny_gen(8), _tiny_gen(9), _tiny_model(10)
        before = {k: copy.deepcopy(m.state_dict()) for k, m in (("opp", opp_m), ("s1", s1_m))}
        learner = E.GenPolicy(learner_m, VOCAB)
        opps = {"o": (E.GenPolicy(opp_m, VOCAB), _cfg("sample", record=False)),
                "s1": (s1_m, _cfg("sample", record=False))}
        jobs = [(i, _spec(i, o, i % 2, odeck=ICEBOW, typ="s1" if o == "s1" else "snapshot"), g,
                 {"rollout_index": g, "update": 0}) for i, o in enumerate(("o", "s1")) for g in range(2)]
        res, _ = _run(jobs, learner, opps, _cfg(), n=4)
        for j, r in enumerate(res):
            r["outcome"] = ("win", "loss")[j % 2]
        Bn, _ = RL.collate(res)
        B = RL.to_device(Bn, "cpu")
        ref = copy.deepcopy(learner_m).eval()
        R = RL.ref_terms(ref, B, TAU, T)
        opt = torch.optim.Adam(learner_m.parameters(), lr=1e-3)
        RL.ppo_update(learner_m, opt, B, R, {"minibatch": 64, "ppo_epochs": 2, "tau": TAU, "T": T, "clip": 0.2,
                                             "grad_clip": 0.5}, 0.3, np.random.default_rng(0))
        moved = any(not torch.equal(a, b) for a, b in zip(learner_m.state_dict().values(), ref.state_dict().values()))
        self.assertTrue(moved)                                               # the learner did train
        for k, m in (("opp", opp_m), ("s1", s1_m)):
            for (n, a), b in zip(m.state_dict().items(), before[k].values()):
                self.assertTrue(torch.equal(a, b), f"{k}.{n}")


# ------------------------------------------------------------------------------------------------------
class TestDeckSampling(unittest.TestCase):
    CFG = {"league_mix": {"latest": 0.35, "older": 0.25, "init": 0.2, "s1": 0.2}, "init": "init.pt",
           "league_specialist": "s1.pt", "league_icebow_share": 0.2}

    @classmethod
    def setUpClass(cls):
        cls.census = RL.league_decks(REPO / "scratchpad/gauntlet/L68/selfplay/loadable_decks.json")
        cls.p = RL.deck_weights([d["sides"] for d in cls.census], 0.5, 0.5)

    def test_census_without_icebow(self):
        self.assertEqual(len(self.census), 182)                               # 183 loadable, icebow removed
        ice = sorted(n.split("@")[0] for n in ICEBOW)
        self.assertFalse(any(sorted(d["engine"]) == ice for d in self.census))
        self.assertEqual(sum(d["bucket"] == "head" for d in self.census), RL.HEAD_DECKS)

    def test_weight_rule_and_floor(self):
        s = np.array([10000.0, 400.0, 100.0, 1.0])
        p = RL.deck_weights(s, 0.5, 0.5)
        w = np.sqrt(s)
        w = np.maximum(w, 0.5 * w.mean())
        np.testing.assert_allclose(p, w / w.sum())
        self.assertEqual(p[2], p[3])                                          # both at the floor
        np.testing.assert_allclose(RL.deck_weights(s, 1.0, 0.0), s / s.sum())
        self.assertAlmostEqual(float(self.p.sum()), 1.0)

    def test_icebow_share_and_s1_only_icebow(self):
        rng = np.random.default_rng(0)
        specs = RL.sample_matchups(rng, 20000, 3, [{"id": "snap_u0010", "path": "a"}, {"id": "snap_u0020", "path": "b"}],
                                   self.CFG, self.census, self.p)
        ld = np.array([s["learner_deck_name"] == "icebow" for s in specs])
        self.assertAlmostEqual(ld.mean(), 0.2, delta=0.012)                    # ~4 sigma at n = 20,000
        s1 = [s for s in specs if s["opp"]["type"] == "s1"]
        self.assertAlmostEqual(len(s1) / len(specs), 0.2, delta=0.012)
        self.assertTrue(all(s["opp_deck"] == ICEBOW for s in s1))
        od = np.array([s["opp_deck_name"] == "icebow" for s in specs if s["opp"]["type"] != "s1"])
        self.assertAlmostEqual(od.mean(), 0.2, delta=0.015)
        self.assertAlmostEqual(np.mean([s["learner_side"] for s in specs]), 0.5, delta=0.015)
        top = self.census[0]["name"]
        share = np.mean([s["learner_deck_name"] == top for s in specs])
        self.assertAlmostEqual(share, 0.8 * self.p[0], delta=0.006)
        self.assertEqual(len({s["tag"] for s in specs}), len(specs))

    def test_opponent_categories(self):
        mix = self.CFG["league_mix"]
        self.assertEqual(set(RL.opponent_mix(0, mix)), {"latest", "init", "s1"})
        self.assertEqual(set(RL.opponent_mix(1, mix)), {"latest", "init", "s1"})
        self.assertEqual(set(RL.opponent_mix(2, mix)), set(RL.OPP_CATS))
        self.assertAlmostEqual(sum(RL.opponent_mix(0, mix).values()), 1.0)
        rng = np.random.default_rng(1)
        got = [RL.sample_opponent(rng, [], mix, "init.pt", "s1.pt") for _ in range(500)]
        self.assertEqual({g["type"] for g in got}, {"init", "s1"})           # latest = the init before any snapshot
        snaps = [{"id": f"snap_u{u:04d}", "path": f"p{u}"} for u in (10, 20, 30)]
        got = [RL.sample_opponent(rng, snaps, mix, "init.pt", "s1.pt") for _ in range(3000)]
        latest = [g for g in got if g["cat"] == "latest"]
        older = [g for g in got if g["cat"] == "older"]
        self.assertTrue(all(g["id"] == "snap_u0030" for g in latest))
        self.assertEqual({g["id"] for g in older}, {"snap_u0010", "snap_u0020"})
        self.assertAlmostEqual(len(latest) / len(got), 0.35, delta=0.03)


class TestLeash(unittest.TestCase):
    def test_cell_is_the_old_rule(self):
        rng = np.random.default_rng(0)
        for _ in range(200):
            upd = {f"kl_{h}": float(rng.exponential(0.1)) for h in ("gate", "card", "cell")}
            if rng.random() < 0.2:
                upd["kl_cell"] = None
            v, d = RL.leash_kl(upd, "cell")
            self.assertEqual(d, "cell")
            self.assertEqual(RL.adapt_beta(0.3, v, 0.1, 0.03, 3.0), RL.adapt_beta(0.3, upd["kl_cell"] or 0.0, 0.1, 0.03, 3.0))

    def test_max_uses_the_max(self):
        self.assertEqual(RL.leash_kl({"kl_gate": 0.3, "kl_card": 0.01, "kl_cell": 0.05}, "max"), (0.3, "gate"))
        self.assertEqual(RL.leash_kl({"kl_gate": None, "kl_card": 0.2, "kl_cell": 0.05}, "max"), (0.2, "card"))
        v, _ = RL.leash_kl({"kl_gate": 0.3, "kl_card": 0.01, "kl_cell": 0.05}, "max")
        self.assertEqual(RL.adapt_beta(0.3, v, 0.1), 0.6)                    # gate over 1.5 x target -> x2
        self.assertEqual(RL.adapt_beta(0.3, 0.05, 0.1), 0.15)                # cell alone would have halved it
        with self.assertRaises(ValueError):
            RL.leash_kl({}, "sum")

    def test_yaml(self):
        import yaml
        y = yaml.safe_load((REPO / "pipeline" / "rl_royale.yaml").read_text(encoding="utf-8"))
        self.assertEqual(y["leash"], "max")
        self.assertFalse(y["league"])


# ------------------------------------------------------------------------------------------------------
class TestLeagueLearner(unittest.TestCase):
    """Snapshots, the pool, resume, the league update record."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rl_league_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        orig = RL.CKPT_ROOT
        RL.CKPT_ROOT = self.tmp / "ck"
        self.addCleanup(setattr, RL, "CKPT_ROOT", orig)

    def _learner(self, model, **kw):
        cfg = dict(CFG, init="init.pt", lr=1e-4, tau=TAU, T=T, adv_clip=2.0, minibatch=64, ppo_epochs=2, clip=0.2,
                   grad_clip=0.5, kl_target=0.1, beta_min=0.03, beta_max=3.0, screen_every=1000, proagree_every=1000,
                   save_every=1, max_updates=5, league=True, league_snapshot_every=2, league_snapshot_keep=3,
                   league_mix={"latest": 0.35, "older": 0.25, "init": 0.2, "s1": 0.2}, league_icebow_share=0.2,
                   league_specialist="s1.pt", league_opp_policy="sample", leash="max")
        cfg.update(kw)
        L = _stub_learner(cfg, {"d_c": 8, "card_vocab": list(VOCAB)}, model, self.tmp)
        L.league = {"snapshots": []}
        L.census = RL.league_decks(REPO / "scratchpad/gauntlet/L68/selfplay/loadable_decks.json")
        L.census_p = RL.deck_weights([d["sides"] for d in L.census], 0.5, 0.5)
        L.ref = copy.deepcopy(model).eval()
        return L

    def test_snapshot_pool_and_resume_round_trip(self):
        L = self._learner(_tiny_gen(11))
        numbered = L.ck_dir / "unit_u0002.pt"
        numbered.write_bytes(b"NUMBERED")                                     # a kept numbered checkpoint, same update
        evicted = []
        for u in (2, 4, 6, 8, 10):
            L.update = u
            sid, ev = L._snapshot()
            self.assertEqual(sid, f"snap_u{u:04d}")
            self.assertTrue(all(f.exists() for f in ev))                      # _snapshot itself deletes nothing
            evicted += L._delete_evicted(ev)
        self.assertEqual([s["id"] for s in L.league["snapshots"]], ["snap_u0006", "snap_u0008", "snap_u0010"])
        self.assertEqual(evicted, ["unit_snap_u0002.pt", "unit_snap_u0004.pt"])
        for u in (2, 4):
            self.assertFalse((L.ck_dir / f"unit_snap_u{u:04d}.pt").exists())   # evicted -> deleted
        for u in (6, 8, 10):
            self.assertTrue((L.ck_dir / f"unit_snap_u{u:04d}.pt").exists())
        self.assertEqual(numbered.read_bytes(), b"NUMBERED")                  # numbered checkpoints never touched
        self.assertEqual(L._delete_evicted([self.tmp / "elsewhere_snap.pt", L.ck_dir / "unit_latest.pt"]), [])
        pol, info = E.load_policy(REPO / L.league["snapshots"][-1]["path"], "cpu")
        self.assertIsInstance(pol, E.GenPolicy)
        for a, b in zip(L.model.state_dict().values(), pol.model.state_dict().values()):
            self.assertTrue(torch.equal(a, b))
        RL.sample_matchups(L.rng, 7, 10, L.league["snapshots"], L.cfg, L.census, L.census_p)   # advance the stream
        path = self.tmp / "ck" / "unit" / "unit_latest.pt"
        L._atomic_save(L._payload(None), path)
        L2 = self._learner(_tiny_gen(12))
        L2._restore(path)
        self.assertEqual(L2.league, L.league)
        self.assertEqual(L2.rng.bit_generator.state, L.rng.bit_generator.state)
        a = RL.sample_matchups(L.rng, 5, 11, L.league["snapshots"], L.cfg, L.census, L.census_p)
        b = RL.sample_matchups(L2.rng, 5, 11, L2.league["snapshots"], L2.cfg, L2.census, L2.census_p)
        self.assertEqual(a, b)                                               # the sampling continues identically

    def test_snapshot_holds_weights_and_load_metadata_only(self):
        L = self._learner(_tiny_gen(21))
        L.opt.zero_grad()
        sum(p.float().pow(2).sum() for p in L.model.parameters()).backward()
        L.opt.step()                                                          # non-empty Adam moments
        L.update = 3
        L._snapshot()
        path = L.ck_dir / "unit_snap_u0003.pt"
        ck = torch.load(path, map_location="cpu", weights_only=True)
        self.assertEqual(set(ck), {"model", "args", "deck", "epoch", "n_params", "gen", "d_c", "card_vocab", "snapshot"})
        full = self.tmp / "full.pt"
        torch.save(L._payload(None), full)
        self.assertLess(path.stat().st_size, 0.5 * full.stat().st_size)      # no optimizer moments / rl state
        pol, _ = E.load_policy(path, "cpu")
        for a, b in zip(L.model.state_dict().values(), pol.model.state_dict().values()):
            self.assertTrue(torch.equal(a, b))

    def test_snapshot_overwrite_guard(self):
        L = self._learner(_tiny_gen(22))
        L.update = 4
        L._snapshot()
        path = L.ck_dir / "unit_snap_u0004.pt"
        mtime = path.stat().st_mtime_ns
        L.league["snapshots"].clear()
        L._snapshot()                                                         # identical weights: kept, not rewritten
        self.assertEqual(path.stat().st_mtime_ns, mtime)
        self.assertTrue(any("identical weights" in m for m in L.log.lines))
        with torch.no_grad():
            next(L.model.parameters()).add_(1.0)
        L.league["snapshots"].clear()
        with self.assertRaisesRegex(RuntimeError, "DIFFERENT weights"):
            L._snapshot()
        self.assertEqual(L.league["snapshots"], [])

    def test_league_keys_validated(self):
        good = {"league_snapshot_every": 10, "league_snapshot_keep": 8, "league_icebow_share": 0.2,
                "league_mix": {"latest": 0.35, "older": 0.25, "init": 0.2, "s1": 0.2}, "league_deck_alpha": 0.5,
                "league_deck_floor": 0.5, "league_opp_policy": "sample"}
        RL.validate_league(good)
        RL.validate_league({**good, "league_icebow_share": 0, "league_mix": {"init": 1.0}})
        for key, bad in (("league_snapshot_every", 0), ("league_snapshot_every", 2.5), ("league_snapshot_keep", 0),
                         ("league_snapshot_keep", True), ("league_icebow_share", 1.2), ("league_icebow_share", -0.1),
                         ("league_mix", {"latest": -0.1, "init": 1.0}), ("league_mix", {"latest": 0, "init": 0}),
                         ("league_mix", {"latest": 1.0, "newest": 1.0}), ("league_mix", {"init": float("nan")}),
                         ("league_deck_alpha", -1), ("league_opp_policy", "greedy")):
            with self.assertRaises(SystemExit, msg=(key, bad)) as cm:
                RL.validate_league({**good, key: bad})
            self.assertIn(key, str(cm.exception))

    def test_resume_of_pre_leash_run_keeps_cell(self):
        L = self._learner(_tiny_gen(13), leash="cell")
        path = self.tmp / "ck" / "unit" / "unit_latest.pt"
        obj = L._payload(None)
        del obj["rl"]["config"]["leash"]
        L._atomic_save(obj, path)
        L2 = self._learner(_tiny_gen(14), leash="max")
        L2._restore(path)
        self.assertEqual(L2.cfg["leash"], "cell")

    def test_league_update_record_and_snapshot(self):
        model = _tiny_gen(15)
        learner = E.GenPolicy(model, VOCAB)
        opp = E.GenPolicy(_tiny_gen(16), VOCAB)
        jobs = [(i, _spec(i, "o", i % 2), g, {"rollout_index": g, "update": 1}) for i in range(2) for g in range(2)]
        res, _ = _run(jobs, learner, {"o": (opp, _cfg("sample", record=False))}, _cfg(), n=4)
        for j, r in enumerate(res):
            r["outcome"] = ("win", "loss", "draw")[j % 3]
        L = self._learner(model)
        L.update = 7
        L.rollout = lambda u: (list(res), {"picked": [], "actors": {}, "skipped": 0, "league": []})
        L.league["snapshots"] = [{"id": f"snap_u{u:04d}", "update": u, "path": str(L.ck_dir / f"unit_snap_u{u:04d}.pt")}
                                 for u in (2, 4, 6)]                         # a full pool (keep 3)
        for x in L.league["snapshots"]:
            Path(x["path"]).write_bytes(b"old")
        order = []
        real_save = L.save
        L.save = lambda *a, **k: (order.append(("save", Path(L.league["snapshots"][0]["path"]).exists())),
                                  real_save(*a, **k))[1]
        rec, reasons, crash = L.one_update(7)
        self.assertFalse(crash)
        self.assertEqual(order, [("save", True)])                            # _latest saved while the evictee existed
        self.assertEqual(rec["snapshot_deleted"], ["unit_snap_u0002.pt"])    # ... and deleted only after it
        self.assertFalse((L.ck_dir / "unit_snap_u0002.pt").exists())
        self.assertEqual(rec["snapshot"], "snap_u0008")                      # update 8 % league_snapshot_every 2
        self.assertEqual(rec["league_pool"], ["snap_u0004", "snap_u0006", "snap_u0008"])
        lg = rec["league"]
        self.assertEqual(lg["by_opp"]["snapshot"]["n"], 4)
        self.assertEqual(sum(v["n"] for v in lg["by_deck"].values()), 4)
        self.assertEqual(lg["draws"], sum(r["outcome"] == "draw" for r in res))
        self.assertEqual(rec["leash"], "max")
        self.assertEqual(rec["kl_leash"], max(rec["kl_gate"], rec["kl_card"], rec["kl_cell"]))
        ck = torch.load(L.ck_dir / "unit_latest.pt", map_location="cpu", weights_only=True)
        self.assertEqual(ck["rl"]["league"]["snapshots"][-1]["id"], "snap_u0008")
        self.assertTrue(any("league wr" in m for m in L.log.lines))


class TestEvalCLI(unittest.TestCase):
    def test_condition_flags_parse_and_reach_cfg(self):
        a = E.build_parser().parse_args(["--port", "0", "--out", "x", "--opp-elixir", "counter", "--action-delay", "26",
                                         "--extrapolate", "26", "--noise-off", "all"])
        self.assertEqual((a.opp_elixir, a.action_delay, a.extrapolate), ("counter", 26, 26))
        self.assertEqual(E.parse_noise_off(a.noise_off), Noise(**{n: False for n in E.NOISE_NAMES}))
        d = E.build_parser().parse_args(["--port", "0", "--out", "x"])
        self.assertEqual((d.opp_elixir, d.action_delay, d.extrapolate), (None, 0, 0))

    def test_rl_gate_emits_the_run_condition(self):
        import io
        from contextlib import redirect_stdout
        from pipeline import rl_gate
        live = {"noise_off": "all", "opp_elixir": "counter", "action_delay_ticks": 26, "extrapolate_ticks": 26}
        buf = io.StringIO()
        with redirect_stdout(buf):
            rl_gate.print_commands("a.pt", "b.pt", "out", "royale", live)
        lines = [x for x in buf.getvalue().splitlines() if "pipeline.e1_eval" in x]
        self.assertEqual(len(lines), 2)
        for x in lines:
            self.assertIn("--noise-off all --opp-elixir counter --action-delay 26 --extrapolate 26", x)
            args = x.split("pipeline.e1_eval ", 1)[1].split()
            p = E.build_parser().parse_args(args)                             # e1_eval accepts exactly these flags
            self.assertEqual((p.opp_elixir, p.action_delay, p.extrapolate), ("counter", 26, 26))
        self.assertEqual(rl_gate.condition_flags({"noise_off": [], "opp_elixir": None, "action_delay_ticks": 0,
                                                  "extrapolate_ticks": 0}), "")


if __name__ == "__main__":
    unittest.main()
