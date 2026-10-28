"""cf_credit (pipeline/cf_credit.py + rl_royale ``cf_credit``): counterfactual credit from SIM forks (plan1026 P3, R_fork).

    ROYALE_RUNTIME=20261006 research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_cf_credit.py
    (engine tests on crforge: ROYALE_ENGINE=crforge + the pod's CRFORGE_* paths)

Covers: absent / null / false = the pre-change trainer (config hashes, collate bytes, two whole gae updates' records /
weights / beta / rng / checkpoint keys vs PRE, cf records in the results ignored); validation; the multi-action advantage
on toys whose answer is known (CRN pairing, the reliability factor / SNR, shrink rules, the slope audit); the rows (the
decision row's GAE advantage replaced by A_0, alternatives appended after the real rows, every other real row and every
value target unchanged, A = cf_w x clip(A_i / sd)); the behaviour log-probs the actor stores equal the learner's
recompute; a synthetic advantage moves the alternative's log-prob in its sign and gives value_head no gradient; the cell /
trigger geometry on hand-built engine states; and on the engine: a fork set is deterministic, leaves the real match
untouched, candidate 0's continuation-0 copy reproduces the real continuation over the horizon (engine hash, learner
plays, value), the audit extension leaves the horizon values unchanged, and a whole match with forced triggers gives
samples whose log-probs the learner recomputes."""
from __future__ import annotations

import copy
import subprocess
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import torch                                                              # noqa: E402

from pipeline import cf_credit as CF                                      # noqa: E402
from pipeline import e1_eval as E                                         # noqa: E402
from pipeline import rl_royale as RL                                      # noqa: E402
from pipeline.tests.test_rl_gae import SPEC, _learner, _strip, _Tmp       # noqa: E402
from pipeline.tests.test_rl_gamma_tick import _with_tick                  # noqa: E402
from pipeline.tests.test_rl_royale import TAU, T, _monitor_fields, _results, _tiny_model  # noqa: E402

PRE = "27988a7"             # the last commit before cf_credit: the absent-key reference
YAML = REPO / "pipeline" / "rl_royale.yaml"
L16 = REPO / "scratchpad/gauntlet/L74/stepd/cfg/stepd_l16_s74.yaml"
ON = {"cf_credit": True, "advantage": "gae", "gae_gamma_unit": "tick", "league": True}
GAE = dict(advantage="gae", critic_warmup_updates=1, seed=0, gae_gamma_unit="tick", gae_gamma_tick=0.99994)


def _pre_module():
    try:
        src = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE}:pipeline/rl_royale.py"], capture_output=True,
                             text=True, encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise unittest.SkipTest(f"git unavailable: {exc}")
    if src.returncode:
        raise unittest.SkipTest(f"git show {PRE} failed: {src.stderr.strip()}")
    mod = types.ModuleType("rl_royale_pre_cf")
    mod.__file__ = str(REPO / "pipeline" / "rl_royale.py")
    exec(compile(src.stdout, "rl_royale_pre_cf", "exec"), mod.__dict__)
    return mod


def _with_cf(model, results, seed=0, per_match=3, K=2, cfg=None):
    """Synthetic cf records (the actor's format) on synthetic sampler trajectories: up to ``per_match`` kept decisions
    with an allowed card; candidate 0 = the recorded decision, then a PLAY (an allowed slot, a random cell) and, where the
    row played, a WAIT; log-probs from cf_credit.alt_logprobs on the row's own forward (the actor's function), q random."""
    rng = np.random.default_rng(seed)
    cfg = cfg or {"tau": TAU, "T": T}
    for r in results:
        t, samples = r["traj"], []
        rows = [i for i in range(len(t["played"])) if t["gate_sampled"][i] and t["allowed"][i].any()][:per_match]
        for di in rows:
            enc, heads, _, _ = E.model_forward_batch(model, [t["tok"][di]], [t["mask"][di]], [t["sc"][di]], [t["past"][di]])
            d = {"allowed": t["allowed"][di], "gate_sampled": bool(t["gate_sampled"][di]), "play": bool(t["played"][di])}
            ch = {"kind": "chosen", "play": d["play"], "slot": int(t["slot"][di]) if d["play"] else -1,
                  "cell": int(t["cell"][di]) if d["play"] else -1, "lp_gate": float(t["lp_gate"][di]),
                  "lp_card": float(t["lp_card"][di]), "lp_cell": float(t["lp_cell"][di])}
            slot, cell = int(np.flatnonzero(d["allowed"])[0]), int(rng.integers(0, E.N_CELLS))
            cands = [ch, {"kind": "rocket_clump", "play": True, "slot": slot, "cell": cell,
                          **CF.alt_logprobs(model, enc, heads, d, slot, cell, cfg)}]
            if d["play"]:
                cands.append({"kind": "wait", "play": False, "slot": -1, "cell": -1,
                              **CF.alt_logprobs(model, enc, heads, d, -1, -1, cfg)})
            for a in cands:
                a.update(q=rng.normal(0, 0.2, K).tolist(), end=[0] * K, terminal=[False] * K, q_end=None)
            samples.append({"row": di, "tick": di, "trigger": "rocket", "audit": False, "to_end": False,
                            "cands": cands, "fork_ticks": 10, "wall_s": 0.1})
        r["cf"] = {"samples": samples, "wall_s": 0.5, "triggers": {"rocket": len(samples)}, "fired": {}, "capped": {},
                   "decisions": len(t["played"]), "fork_ticks": 10 * len(samples), "xbow_failed": 0, "k": K}
        r["wall_s"], r["end_tick"] = 10.0, 1000
    return results


# ------------------------------------------------------------------------------------------------------
class TestConfig(unittest.TestCase):
    def test_off_and_validation(self):
        for v in (None, False):
            self.assertIsNone(CF.cf_cfg({"cf_credit": v}))
        self.assertIsNone(CF.cf_cfg({}))
        with self.assertRaises(SystemExit):
            CF.cf_cfg({"cf_w": 2.0})                                       # a stray key without the switch
        c = CF.cf_cfg(ON)
        self.assertEqual(set(c), set(CF.DEFAULTS))
        self.assertEqual(c["cf_p"], CF.P_DEFAULT)
        self.assertEqual(CF.cf_cfg({**ON, "cf_p": {"rocket": 1.0}})["cf_p"], {**CF.P_DEFAULT, "rocket": 1.0})
        self.assertIsNotNone(CF.cf_cfg({**ON, "shaping": "tower_phat"}))        # the fast loop's Phi: the forks value it
        for bad in ({"advantage": "match_loo"}, {"gae_gamma_unit": "row"}, {"league": False}, {"branch_gate": True},
                    {"posture_head": True}, {"critic_ctx": "arch"}, {"kl_ref_gate_max_elixir": 3},
                    {"shaping": "tower_crown"}, {"princess_redirect": "potential"}, {"lead_protect": True},
                    {"habit_reward": True}, {"spell_value": True}, {"stored_values": True}, {"cf_credit": "yes"}, {"cf_horizon_ticks": 0},
                    {"cf_k": 0}, {"cf_p": {"rocket": 1.5}}, {"cf_p": {"nope": 0.1}}, {"cf_clip": 0},
                    {"cf_front_min_tiles": 9.0}, {"cf_audit_p": 2}, {"cf_shrink": 1}):
            with self.assertRaises(SystemExit, msg=bad):
                CF.cf_cfg({**ON, **bad})

    def test_hash_absent_is_historical_and_on_differs(self):
        P = _pre_module()
        for path in (YAML, L16):
            base = RL.load_config(path, [], False)
            ref = P.config_sha(P.load_config(path, [], False))
            for extra in ({}, {"cf_credit": None}, {"cf_credit": False}):
                self.assertEqual(RL.config_sha({**base, **extra}), ref, (path.name, extra))
        base = RL.load_config(L16, [], False)
        on = RL.config_sha({**base, "cf_credit": True})
        self.assertNotEqual(on, RL.config_sha(base))
        self.assertEqual(on, RL.config_sha({**base, "cf_credit": True, "cf_w": 1.0}))     # explicit default = implicit
        self.assertEqual(on, RL.config_sha({**base, "cf_credit": True, "cf_p": {"rocket": CF.P_DEFAULT["rocket"]}}))
        self.assertNotEqual(on, RL.config_sha({**base, "cf_credit": True, "cf_w": 2.0}))
        self.assertNotEqual(on, RL.config_sha({**base, "cf_credit": True, "cf_p": {"rocket": 0.5}}))

    def test_actor_cfg(self):
        base = {"tau": .35, "afford_mask": True, "stall_elixir": None, "stall_seconds": 12, "obs": "live", "grid": "lattice",
                "decide_every": 10, "T": .5}
        self.assertNotIn("cf", RL.actor_cfg(base, "rollout", 0, "cpu"))
        c = RL.actor_cfg({**base, "cf": {"cf_w": 1.0}}, "rollout", 0, "cpu")
        self.assertEqual(c["cf"], {"cf_w": 1.0})
        self.assertNotIn("cf", RL.actor_cfg({**base, "cf": {"cf_w": 1.0}}, "screen", 0, "cpu"))


class TestAdvantageToy(unittest.TestCase):
    """The multi-action advantage where the right answer is known."""

    def test_crn_shift_cancels(self):
        # 3 candidates, true values 0.2 / 0 / -0.2; each continuation adds a COMMON shift (CRN): +0.3, -0.7
        q = [[0.5, -0.5], [0.3, -0.7], [0.1, -0.9]]
        A = CF.sample_adv([{"q": x} for x in q])
        np.testing.assert_allclose(A.mean(axis=1), [0.2, 0.0, -0.2], atol=1e-12)
        np.testing.assert_allclose(A, [[0.2, 0.2], [0.0, 0.0], [-0.2, -0.2]], atol=1e-12)

    def test_reliability_recovers_known_signal_and_noise(self):
        rng = np.random.default_rng(0)
        s_sig, s_noise, K, n = 0.1, 0.2, 2, 20000
        advs = []
        for _ in range(n):
            mu = rng.normal(0, s_sig, 3)
            q = mu[:, None] + rng.normal(0, 1, K)[None, :] + rng.normal(0, s_noise, (3, K))   # common shift + noise
            advs.append(CF.sample_adv([{"q": x} for x in q]))
        r = CF.reliability(advs)
        # centred over 3 candidates both parts scale by 2/3: the factor and the SNR are scale-free
        want_factor = s_sig ** 2 / (s_sig ** 2 + s_noise ** 2 / K)
        self.assertAlmostEqual(r["factor"], want_factor, delta=0.02)
        self.assertAlmostEqual(r["snr"], np.sqrt(K * s_sig ** 2 / s_noise ** 2), delta=0.05)
        self.assertAlmostEqual(r["r_split"], s_sig ** 2 / (s_sig ** 2 + s_noise ** 2), delta=0.02)

    def test_batch_advantages_shrink_rules(self):
        rng = np.random.default_rng(1)
        smp = [{"trigger": "rocket" if i % 2 else "siege",
                "cands": [{"q": rng.normal(0, 1, 2).tolist()} for _ in range(3)]} for i in range(40)]
        c = CF.cf_cfg(ON)
        adv, rel = CF.batch_advantages(smp, {**c, "cf_shrink": False})
        for s, a in zip(smp, adv):                                         # unshrunk = Q_i - mean_j Q_j
            q = np.asarray([x["q"] for x in s["cands"]]).mean(axis=1)
            np.testing.assert_allclose(a, q - q.mean(), atol=1e-12)
        adv2, rel2 = CF.batch_advantages(smp, {**c, "cf_shrink_min": 30})  # 60 values per trigger: its own factor
        f = rel2["rocket"]["factor"]
        np.testing.assert_allclose(adv2[1], f * adv[1], atol=1e-12)
        adv3, rel3 = CF.batch_advantages(smp, {**c, "cf_shrink_min": 100})  # per trigger too few, pooled 120: pooled
        np.testing.assert_allclose(adv3[1], rel3["_pooled"]["factor"] * adv[1], atol=1e-12)
        adv4, _ = CF.batch_advantages(smp, {**c, "cf_shrink_min": 1000})   # nothing has enough: unshrunk
        np.testing.assert_allclose(adv4[1], adv[1], atol=1e-12)

    def test_slope_audit(self):
        rng = np.random.default_rng(2)
        smp = []
        for _ in range(400):
            cands = []
            for _ in range(3):
                q = float(rng.normal(0, 0.5))
                cands.append({"q": [q, q], "terminal": [False, False], "q_end": float(np.clip(1.0 * q + rng.normal(0, 0.3), -1, 1))})
            smp.append({"audit": True, "cands": cands})
        smp.append({"audit": False, "cands": [{"q": [9.0, 9.0], "terminal": [False, False], "q_end": -9.0}] * 3})
        a = CF.slope_audit(smp)
        self.assertEqual(a["levels"]["n"], 1200)
        self.assertTrue(0.8 < a["levels"]["slope"] < 1.0, a)                # the +-1 clip pulls it below 1
        self.assertTrue(0.8 < a["diffs"]["slope"] < 1.0, a)


class TestGeometry(unittest.TestCase):
    def test_front_cells(self):
        from pipeline import decision_options as DO
        x, y = DO.cell_centres_tiles("lattice")
        m = CF.front_cells(3.5, 25.5, "lattice", 5.0, 8.0)
        self.assertGreater(int(m.sum()), 10)
        d = np.hypot(x[m] - 3.5, y[m] - 25.5)
        self.assertTrue((x[m] < 9).all() and (y[m] >= CF.TERRITORY_Y_TILES).all() and (y[m] < 25.5).all())
        self.assertTrue(((d >= 5) & (d <= 8)).all())
        self.assertTrue((x[CF.front_cells(14.5, 25.5, "lattice", 5.0, 8.0)] >= 9).all())

    def test_siege_cells(self):
        from pipeline import decision_options as DO
        x, y = DO.cell_centres_tiles("lattice")
        troop = CF.siege_cells(3.5, 12.0, "lattice", "TROOP", "knight", 2.0)       # a Mortar on their side
        self.assertTrue(troop.any() and (y[troop] >= CF.TERRITORY_Y_TILES).all() and (y[troop] <= 19.5).all())
        rocket = CF.siege_cells(3.5, 12.0, "lattice", "CARDKIND.SPELL", "rocket", 2.0)
        self.assertTrue(rocket.any() and (np.hypot(x[rocket] - 3.5, y[rocket] - 12.0) <= 2.0).all())
        near_king = CF.siege_cells(9.0, 5.0, "lattice", "SPELL", "rocket", 2.0)
        self.assertFalse((near_king & DO.tower_cover_cells("lattice", DO.rocket_radius_tiles())[0]).any())

    def test_xbow_reach_cells(self):
        from pipeline import decision_options as DO
        x, y = DO.cell_centres_tiles("lattice")
        # side 0 (mirror False): an alive enemy princess at engine tile (3.5, 25.5) = my frame (3.5, 32 - 25.5 = 6.5)
        s = NS(side=0, mirror=False, state={"episode": {"crown_towers": [
            {"side": 1, "type": "princess", "x": 3.5 * 1000, "y": 25.5 * 1000, "hp": 100, "destroyed": False},
            {"side": 1, "type": "princess", "x": 14.5 * 1000, "y": 25.5 * 1000, "hp": 0, "destroyed": True}]}})
        r = CF.xbow_reach_cells(s, "lattice")
        tx, ty = CF.raw_tiles(s.state["episode"]["crown_towers"][0], False)
        self.assertAlmostEqual(tx, 3.5, places=3)
        self.assertTrue(r.any() and (y[r] >= CF.TERRITORY_Y_TILES).all())
        self.assertTrue((np.hypot(x[r] - tx, y[r] - ty) <= DO.XBOW_REACH_TILES).all())
        self.assertTrue((x[r] < 11.5).all())          # within 13 of (3.5, 6.5) at y >= 17: x <= 11.2; the dead R adds none

    def test_gate_logprob_is_finite_and_complementary(self):
        for z in (-40.0, -1.0, 0.3, 40.0):
            d = {"gate_sampled": True}
            a, b = CF.gate_logprob(z, d, {"tau": .35, "T_gate": .1}), CF.gate_logprob(z, d, {"tau": .35, "T_gate": .1}, False)
            self.assertTrue(np.isfinite(a) and np.isfinite(b))
            self.assertAlmostEqual(np.exp(a) + np.exp(b), 1.0, places=12)
        self.assertEqual(CF.gate_logprob(1.0, {"gate_sampled": False}, {"tau": .35}), 0.0)


try:                                   # royale_env first: it activates the pinned runtime (a bare royalegym import would not)
    from pipeline.tests import test_search_s0 as TS
    RoyaleSelfPlayEnv = TS.RoyaleSelfPlayEnv
except Exception:                                                         # noqa: BLE001
    RoyaleSelfPlayEnv = None
try:
    from royalegym.protocol import EntityKind
except Exception:                                                         # noqa: BLE001
    EntityKind = None


@unittest.skipIf(EntityKind is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestTriggersOnStates(unittest.TestCase):
    """siege_target / xbow_watch on hand-built engine states (side 0 = us at low y in RoyaleSim, 18000 units a tile)."""

    def ent(self, uid, team, kind, tx, ty, hp=1000, target=None, card=0):
        return NS(uid=uid, team=team, kind=kind, x=tx * 18000.0, y=ty * 18000.0, hp=hp, target_uid=target, card_id=card)

    def towers(self, foe_hp=1000):
        K, P = EntityKind.KING_TOWER, EntityKind.PRINCESS_TOWER
        return [self.ent(1, 0, K, 9, 2.5), self.ent(2, 0, P, 3.5, 6.5), self.ent(3, 0, P, 14.5, 6.5),
                self.ent(4, 1, K, 9, 29.5), self.ent(5, 1, P, 3.5, 25.5, foe_hp), self.ent(6, 1, P, 14.5, 25.5)]

    def test_siege_target(self):
        env = NS(names={7: "Mortar", 8: "Cannon", 9: "Xbow"})
        B = EntityKind.BUILDING
        far_cannon = self.ent(20, 1, B, 9, 24, card=8)                            # their defence: neither locked nor siege
        self.assertIsNone(CF.siege_target(env, 0, NS(entities=self.towers() + [far_cannon])))
        mortar = self.ent(21, 1, B, 3.5, 17.0, card=7)                           # in reach of our L princess, not locked yet
        tg = CF.siege_target(env, 0, NS(entities=self.towers() + [far_cannon, mortar]))
        self.assertEqual((tg["uid"], tg["locked"], tg["princess"]), (21, False, (3.5 * 18000.0, 6.5 * 18000.0)))
        locked = self.ent(22, 1, B, 14.0, 20.0, target=3, card=8)                # a Cannon locked on our R princess wins
        tg = CF.siege_target(env, 0, NS(entities=self.towers() + [mortar, locked]))
        self.assertEqual((tg["uid"], tg["locked"], tg["princess"]), (22, True, (14.5 * 18000.0, 6.5 * 18000.0)))
        self.assertIsNone(CF.siege_target(env, 1, NS(entities=self.towers() + [mortar])))   # our own side's view

    def test_xbow_watch_counts_reach_without_lock(self):
        env, B = NS(names={9: "Xbow"}), EntityKind.BUILDING
        st = CF.new_state(NS(tag="t", k=0, cfg={}))
        reach = self.ent(30, 0, B, 3.5, 15.0, card=9)                            # 10.5 tiles from their L princess
        back = self.ent(31, 0, B, 9.0, 5.0, card=9)                              # defensive: no reach
        CF.xbow_watch(st, env, 0, 100, NS(entities=self.towers() + [reach, back]))
        self.assertEqual(st["xb"], {30: [True, False], 31: [False, False]})
        CF.xbow_watch(st, env, 0, 110, NS(entities=self.towers()))              # both gone: only the reach one failed
        self.assertEqual((st["xb_failed"], st["xb_fail_tick"], st["xb"]), (1, 110, {}))
        locked = self.ent(32, 0, B, 3.5, 15.0, target=5, card=9)
        CF.xbow_watch(st, env, 0, 200, NS(entities=self.towers() + [locked]))
        CF.xbow_watch(st, env, 0, 210, NS(entities=self.towers()))
        self.assertEqual(st["xb_failed"], 1)                                     # it locked: not a failure


# ------------------------------------------------------------------------------------------------------
class TestAbsentIsPre(_Tmp):
    """cf_credit absent / null / false: collate and whole gae updates are those of PRE, cf records in the results ignored."""

    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)              # multi-thread CPU reductions differ run to run at ~1e-8
        cls.P = _pre_module()
        cls.model = _tiny_model(6)
        cls.results = _with_tick(_with_cf(cls.model, _monitor_fields(_results(cls.model, SPEC, seed=13))))

    def test_collate_identical(self):
        for kw in ({"advantage": "match_loo"}, {"advantage": "gae"}, {"advantage": "gae", "gamma_tick": 0.99994}):
            Bp, sp = self.P.collate(copy.deepcopy(self.results), 2.0, **kw)
            Bn, sn = RL.collate(copy.deepcopy(self.results), 2.0, **kw)
            self.assertEqual(sorted(Bn), sorted(Bp))
            for k in Bp:
                self.assertEqual(Bn[k].tobytes(), Bp[k].tobytes(), k)
            self.assertEqual(sn, sp)

    def test_updates_identical(self):
        self.P.CKPT_ROOT = self.tmp
        runs = {}
        for name, mod, extra in (("pre", self.P, {}), ("absent", RL, {}), ("null", RL, {"cf_credit": None}),
                                 ("false", RL, {"cf_credit": False})):
            L = _learner(mod, self.model, self.results, self.tmp / name, **GAE, **extra)
            recs = [_strip(L.one_update(u)[0]) for u in range(2)]
            ck = torch.load(L.ck_dir / "unit_latest.pt", map_location="cpu", weights_only=True)
            runs[name] = (recs, L.beta, {k: v.clone() for k, v in L.model.state_dict().items()},
                          L.rng.bit_generator.state, sorted(ck["rl"]), ck["rl"]["config_sha256"])
        recs_p, beta_p, sd_p, rng_p, keys_p, sha_p = runs["pre"]
        for name in ("absent", "null", "false"):
            recs, beta, sd, rng, keys, sha = runs[name]
            self.assertEqual(recs, recs_p, name)
            self.assertEqual((beta, rng, keys, sha), (beta_p, rng_p, keys_p, sha_p), name)
            for k in sd_p:
                self.assertTrue(torch.equal(sd[k], sd_p[k]), (name, k))


class TestRows(_Tmp):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.model = _tiny_model(7)
        with torch.no_grad():                 # non-uniform cells: a stricter log-prob check
            cls.model.cell_bias.copy_(torch.from_numpy(np.random.default_rng(5).normal(size=E.N_CELLS).astype("float32")))
        cls.results = _with_tick(_with_cf(cls.model, _monitor_fields(_results(cls.model, SPEC, seed=21))))
        cls.cf = CF.cf_cfg(ON)
        cls.kw = {"advantage": "gae", "gamma_tick": 0.99994}

    def _both(self, cf=None):
        B0, s0 = RL.collate(copy.deepcopy(self.results), 2.0, **self.kw)
        B1, s1 = RL.collate(copy.deepcopy(self.results), 2.0, **self.kw, cf=cf or self.cf)
        return B0, s0, B1, s1

    def _samples(self):
        """(match j, real row index in B, sample) in collate's order."""
        out, off = [], 0
        for j, r in enumerate(self.results):
            keep = r["traj"]["gate_sampled"] | r["traj"]["played"]
            for smp in r["cf"]["samples"]:
                out.append((j, off + int(keep[:smp["row"]].sum()), smp))
            off += int(keep.sum())
        return out

    def test_collate_marks_decision_rows_and_appends_alternatives(self):
        B0, s0, B1, s1 = self._both({**self.cf, "cf_shrink": False})
        n = len(B0["A"])
        smp = self._samples()
        alts = [(j, s, a) for j, _, s in smp for a in s["cands"][1:]]
        self.assertEqual(len(B1["A"]), n + len(alts))
        self.assertEqual(B1["cf"].tolist(), [False] * n + [True] * len(alts))
        self.assertEqual(sorted(B1), sorted(list(B0) + ["cf", "cf_q"]))
        for k in B0:
            self.assertEqual(B1[k][:n].tobytes(), B0[k].tobytes(), k)       # the real rows: byte-identical
        self.assertEqual({k: v for k, v in s1.items() if k != "cf"}, s0)
        rows = {row for _, row, _ in smp}
        self.assertTrue(np.isnan(B1["cf_q"][[i for i in range(n) if i not in rows]]).all())
        for j, row, s in smp:
            q = np.asarray([a["q"] for a in s["cands"]]).mean(axis=1)
            self.assertAlmostEqual(B1["cf_q"][row], q[0] - q.mean(), places=12)
            self.assertEqual(bool(B1["played"][row]), s["cands"][0]["play"])
        i = n
        for j, row, s in smp:
            q = np.asarray([a["q"] for a in s["cands"]]).mean(axis=1)
            t = self.results[j]["traj"]
            for a, qi in zip(s["cands"][1:], q[1:]):
                self.assertEqual(B1["tok"][i].tobytes(), t["tok"][s["row"]].tobytes())
                self.assertEqual(B1["allowed"][i].tolist(), t["allowed"][s["row"]].tolist())
                self.assertEqual((bool(B1["played"][i]), int(B1["slot"][i]), int(B1["cell"][i]), int(B1["match"][i])),
                                 (a["play"], a["slot"], a["cell"], j))
                self.assertAlmostEqual(B1["cf_q"][i], qi - q.mean(), places=12)
                self.assertEqual(B1["r_step"][i], 0.0)
                self.assertAlmostEqual(B1["lp_old"][i], a["lp_gate"] + a["lp_card"] + a["lp_cell"], places=12)
                i += 1
        self.assertEqual(s1["cf"]["rows"], len(alts))
        self.assertEqual(s1["cf"]["by_kind"]["wait"]["n"], sum(a["kind"] == "wait" for _, _, a in alts))
        self.assertEqual(s1["cf"]["fork_ticks_per_match_tick"], sum(r["cf"]["fork_ticks"] for r in self.results)
                         / (1000 * len(self.results)))
        with self.assertRaises(ValueError):
            RL.collate(copy.deepcopy(self.results), 2.0, advantage="match_loo", cf=self.cf)

    def test_gae_replaces_decision_rows_only(self):
        B0, _, B1, _ = self._both()
        n = len(B0["A"])
        cfg = {**GAE, **ON, "cf_w": 2.0, "cf_clip": 1.5}
        T0, T1 = RL.to_device(B0, "cpu"), RL.to_device(B1, "cpu")
        g0, g1 = RL.gae_batch(self.model, T0, cfg), RL.gae_batch(self.model, T1, cfg)
        q = B1["cf_q"]
        has = np.isfinite(q)
        real_plain = ~has[:n]
        np.testing.assert_array_equal(T1["A"][:n].numpy()[real_plain], T0["A"].numpy()[real_plain])
        np.testing.assert_array_equal(T1["ret"][:n].numpy(), T0["ret"].numpy())    # every value target unchanged
        np.testing.assert_array_equal(T1["ret"][n:].numpy(), np.zeros(len(q) - n))
        self.assertEqual({k: v for k, v in g1.items() if k != "cf"}, g0)
        want = 2.0 * np.clip(q[has] / (g0["adv_std"] + 1e-8), -1.5, 1.5)
        np.testing.assert_allclose(T1["A"].numpy()[has], want, rtol=0, atol=1e-12)
        self.assertEqual((g1["cf"]["rows"], g1["cf"]["replaced"]), (len(q) - n, int(has[:n].sum())))

    def test_stored_logprobs_equal_learner_recompute(self):
        _, _, B1, _ = self._both()
        B = RL.to_device(B1, "cpu")
        idx = torch.nonzero(B["cf"]).squeeze(-1)
        self.assertGreater(len(idx), 5)
        self.assertTrue((~B["played"][idx]).any() and B["played"][idx].any())   # wait AND play alternatives
        with torch.no_grad():
            t = RL.policy_terms(self.model, B, idx, TAU, T)
        for k in ("lp_gate", "lp_card", "lp_cell"):
            self.assertLess(float((t[k] - B[k][idx]).abs().max()), 1e-5, k)   # pod torch: 1.1e-6 (1-row vs batched float32 forward)

    def _batch(self, sign: float):
        _, _, B1, _ = self._both()
        B = RL.to_device(B1, "cpu")
        RL.gae_batch(self.model, B, {**GAE, **ON})
        alt = int(torch.nonzero(B["cf"] & B["played"]).squeeze(-1)[0])
        B["A"] = torch.zeros_like(B["A"])
        B["A"][alt] = sign
        return B, alt

    def test_synthetic_advantage_gradient_sign(self):
        for sign in (1.0, -1.0):
            model = copy.deepcopy(self.model)
            B, alt = self._batch(sign)
            R = RL.ref_terms(model, B, TAU, T)
            ii = torch.tensor([alt])
            with torch.no_grad():
                t0 = RL.policy_terms(model, B, ii, TAU, T)
            opt = torch.optim.SGD(model.parameters(), lr=0.05)
            loss, _ = RL.minibatch_loss(model, B, R, torch.arange(len(B["A"])), tau=TAU, T=T, clip=0.2, beta=0.0,
                                        n_total=len(B["A"]))
            opt.zero_grad()
            loss.backward()
            opt.step()
            with torch.no_grad():
                t1 = RL.policy_terms(model, B, ii, TAU, T)
            lp0 = float(t0["lp_gate"] + t0["lp_card"] + t0["lp_cell"])
            lp1 = float(t1["lp_gate"] + t1["lp_card"] + t1["lp_cell"])
            self.assertGreater(sign * (lp1 - lp0), 0, sign)

    def test_alt_rows_reach_no_value_head_and_no_kl(self):
        model = copy.deepcopy(self.model)
        B, alt = self._batch(1.0)
        R = RL.ref_terms(model, B, TAU, T)
        idx = torch.nonzero(B["cf"]).squeeze(-1)
        loss, st = RL.minibatch_loss(model, B, R, idx, tau=TAU, T=T, clip=0.2, beta=1.0, n_total=len(B["A"]),
                                     vf={"coef": 1.0, "clip": 0.2, "policy": True})
        loss.backward()
        vh = [p.grad for n, p in model.named_parameters() if n.startswith("value_head.")]
        self.assertTrue(vh and all(g is None or float(g.abs().max()) == 0.0 for g in vh))
        self.assertEqual((st["kl_gate"], st["kl_card"], st["kl_cell"], st["l_v"]), (0.0, 0.0, 0.0, 0.0))
        self.assertIsNone(st["ent_gate"])
        others = [p.grad for n, p in model.named_parameters() if not n.startswith("value_head.") and p.grad is not None]
        self.assertTrue(any(float(g.abs().max()) > 0 for g in others))       # the policy gradient does flow


class TestOneUpdateOn(_Tmp):
    def test_two_updates_with_cf(self):
        torch.set_num_threads(1)
        model = _tiny_model(6)
        res = _with_tick(_with_cf(model, _monitor_fields(_results(model, SPEC, seed=13))))
        L = _learner(RL, model, res, self.tmp / "on", **GAE, league=True, cf_credit=True)
        recs = [L.one_update(u)[0] for u in range(2)]              # u0 = critic warm-up, u1 = a policy step
        n_alt = sum(len(s["cands"]) - 1 for r in res for s in r["cf"]["samples"])
        for rec in recs:
            self.assertEqual(rec["cf"]["rows"], n_alt)
            self.assertEqual(rec["gae"]["cf"]["rows"], n_alt)
            self.assertEqual(rec["gae"]["cf"]["replaced"], sum(len(r["cf"]["samples"]) for r in res))
            self.assertLess(rec["first_minibatch"]["ratio_maxdev"], RL.ASSERT_RATIO)   # the alt rows' old log-probs too
        self.assertTrue(any(" | cf samples " in ln for ln in L.log.lines))
        ck = torch.load(L.ck_dir / "unit_latest.pt", map_location="cpu", weights_only=True)
        L0 = _learner(RL, model, res, self.tmp / "off", **GAE, league=True)
        L0.one_update(0)
        ck0 = torch.load(L0.ck_dir / "unit_latest.pt", map_location="cpu", weights_only=True)
        self.assertNotEqual(ck["rl"]["config_sha256"], ck0["rl"]["config_sha256"])


# ------------------------------------------------------------------------------------------------------
# the engine (RoyaleSim by default; crforge with ROYALE_ENGINE=crforge)
# ------------------------------------------------------------------------------------------------------
TAIL = 1500
H = 200


def _setup(tau_phase=None, T_gate=None, opp_policy="sample", **cf):
    from pipeline import search_s0 as S
    gen, opp_gen, _ = TS.tiny_models()
    lcfg = {**S.live_cfg(S.TAU_PLAIN, "lattice"), "policy": "sample", "record": True, "record_tick": True, "T": 0.5,
            "rollout_index": 0,
            "update": 0, "cf": {**CF.cf_cfg({**ON, "cf_horizon_ticks": H, **cf}), "v_scale": 1.0, "gamma_tick": 0.99994}}
    if tau_phase is not None:
        lcfg["tau_phase"] = tau_phase
    if T_gate is not None:
        lcfg["T_gate"] = T_gate
    ocfg = {**S.live_cfg(S.TAU_OPP, "lattice"), "policy": opp_policy, "T": 0.5}
    spec = {"tag": "cf-test", "opp": {"id": "gen"}, "learner_deck": list(TS.ICEBOW), "opp_deck": list(TS.HOGEQ),
            "learner_side": 1, "seed": 5}
    return gen, opp_gen, lcfg, ocfg, spec


def _run(Runner, **kw):
    gen, opp_gen, lcfg, ocfg, spec = _setup(**kw)
    out = []
    with patch.object(CF, "Runner", Runner):
        E.run_selfplay_batch(lambda: RoyaleSelfPlayEnv(tail_cap=TAIL), gen, {"gen": (opp_gen, ocfg)}, [(0, spec, 0)],
                             lcfg, 1, on_result=out.append)
    return gen, out[0]


def _chosen(d):
    return {"kind": "chosen", "play": bool(d["play"]), "slot": int(d["slot"]) if d["play"] else -1,
            "cell": int(d["cell"]) if d["play"] else -1, "lp_gate": float(d["lp_gate"]), "lp_card": float(d["lp_card"]),
            "lp_cell": float(d["lp_cell"])}


@unittest.skipIf(RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestForks(unittest.TestCase):
    def test_determinism_isolation_crn_audit_and_baseline_reproduces_the_real_continuation(self):
        """At one learner decision (tick >= 600, a card affordable), cands = [chosen, a play, a wait], K = 2:
        (1) two fork sets give identical q / end ticks / end engine hashes, and the real match is unchanged;
        (2) the audit run (continuation 0 on to the match end) gives the same horizon q and a terminal q_end;
        (3) continuation 1 is reseeded: its RNG streams differ from continuation 0's;
        (4) candidate 0's continuation-0 copy, stopped at its learner decision >= root + H, shows the same engine hash,
        the same learner plays since the root and the same value as the real match when it gets there."""
        got: dict = {}

        class Spy(CF.Runner):
            def hook(self, live, todo):
                if not live:
                    return
                m = live[0]
                for s, p, d in todo:
                    if s is not m.learner:
                        continue
                    tick = int(m.env.tick)
                    if "root" not in got and tick >= 600 and np.asarray(d["allowed"]).any() and d["gate_sampled"]:
                        m.cf_state = CF.new_state(s)
                        entries = [x for x in todo if x[0] is m.learner or x[0] is m.opp]
                        before = (m.env.core.state_hash(), TS.env_digest(m.env), TS.side_digest(m.learner),
                                  TS.side_digest(m.opp))
                        slot = int(np.flatnonzero(d["allowed"])[0])
                        lp = {"lp_gate": 0.0, "lp_card": 0.0, "lp_cell": 0.0}
                        cands = [_chosen(d), {"kind": "x", "play": True, "slot": slot, "cell": TS.CELL, **lp},
                                 {"kind": "wait", "play": False, "slot": -1, "cell": -1, **lp}]
                        runs = []
                        for _ in range(2):
                            out = self.rollouts(m, entries, cands, seed=7)
                            runs.append((out, [f.env.core.state_hash() for f in self.last_forks]))
                        f0, f1 = self.last_forks[0], self.last_forks[3]          # candidate 0, continuations 0 / 1
                        crn = (f0.learner.rng_behave.bit_generator.state != f1.learner.rng_behave.bit_generator.state)
                        aud = self.rollouts(m, entries, cands, seed=7, audit=True)
                        after = (m.env.core.state_hash(), TS.env_digest(m.env), TS.side_digest(m.learner),
                                 TS.side_digest(m.opp))
                        c0 = self.c                                   # + the tower_phat Phi at s_v_scale 2
                        self.c = {**c0, "phi_mode": "tower_phat", "phi_params": {}, "v_scale": 2.0}
                        basephi = self.rollouts(m, entries, cands[:1], seed=7)["cands"][0]
                        self.c = c0
                        base = self.rollouts(m, entries, cands[:1], seed=7)["cands"][0]
                        f = self.last_forks[0]
                        n0 = len(m.learner.plays)
                        got.update(root=tick, runs=runs, iso=(before == after), base=base, aud=aud, crn=crn, basephi=basephi,
                                   fork_hash=f.env.core.state_hash(), fork_plays=f.learner.plays[n0:], n0=n0)
                    elif "root" in got and "real" not in got and not got["base"]["terminal"][0] \
                            and tick == got["base"]["end"][0]:
                        enc, _ = CF.forward_one(s)
                        with torch.no_grad():
                            v = float(RL.value_scalar(s.model.model.value_head(enc["g"]))[0])
                        got["real"] = (m.env.core.state_hash(), m.learner.plays[got["n0"]:], v)
                        from pipeline import reward_shaping as RS
                        got["phi"] = float(RS.state_phi("tower_phat", [RS.tower_phat_record(s.state, s.side)], {})[0])

        _run(Spy)
        self.assertIn("root", got)
        (o1, h1), (o2, h2) = got["runs"]
        self.assertEqual((o1, h1), (o2, h2))
        self.assertTrue(got["iso"], "the forks changed the real match")
        self.assertTrue(got["crn"], "continuation 1 was not reseeded")
        for a, b in zip(o1["cands"], got["aud"]["cands"]):
            self.assertEqual((a["q"], a["end"]), (b["q"], b["end"]))                  # the audit leaves q alone
            self.assertIsNone(a["q_end"])
            self.assertTrue(b["q_end"] is not None and abs(b["q_end"]) <= 1.0)
        self.assertGreater(got["aud"]["fork_ticks"], o1["fork_ticks"])
        root = got["root"]
        self.assertGreaterEqual(got["base"]["end"][0], root + H)
        self.assertIn("real", got, "the real match never reached the baseline fork's stop tick")
        h, plays, v = got["real"]
        self.assertEqual(h, got["fork_hash"])
        self.assertEqual(plays, got["fork_plays"])
        self.assertGreater(len(plays), 0)
        g = 0.99994 ** (got["base"]["end"][0] - root)
        self.assertAlmostEqual(got["base"]["q"][0], g * v, places=12)
        self.assertEqual(got["basephi"]["end"], got["base"]["end"])
        self.assertAlmostEqual(got["basephi"]["q"][0], g * (got["phi"] + 2.0 * v), places=12)

    def test_end_to_end_samples_and_logprobs(self):
        """A whole match through run_selfplay_batch with the real Runner (triggers forced at a few decisions: Rocket
        alternatives where affordable, else policy-sampled ones), tau_phase + T_gate: the cf record reaches the result,
        collate builds the rows and policy_terms recomputes their stored log-probs."""
        calls = {"n": 0}

        def trig(m, s, d, c):
            names, al = CF.slot_names(s), np.asarray(d["allowed"], bool)
            if int(s._cur[0]) < 300 or calls["n"] >= 6 or not al.any() or not d["gate_sampled"]:
                return []
            calls["n"] += 1
            return ["rocket", "random"] if al[names.index("rocket")] else ["random"]

        with patch.object(CF, "triggers", trig):
            gen, res = _run(CF.Runner, tau_phase=[0.3, 0.4, 0.5], T_gate=0.3)
        self.assertIn("cf", res)
        smp = res["cf"]["samples"]
        n_alt = sum(len(s["cands"]) - 1 for s in smp)
        self.assertGreater(n_alt, 2)
        for s in smp:
            for a in s["cands"]:
                self.assertTrue(all(np.isfinite(q) for q in a["q"]) and len(a["q"]) == 2)
                self.assertTrue(np.isfinite(a["lp_gate"] + a["lp_card"] + a["lp_cell"]))
        res = {**res, "entry_index": 0}
        B, st = RL.collate([res], 2.0, advantage="gae", gamma_tick=0.99994, cf=CF.cf_cfg(ON))
        self.assertEqual(st["cf"]["rows"], n_alt)
        Bt = RL.to_device(B, "cpu")
        idx = torch.nonzero(Bt["cf"]).squeeze(-1)
        with torch.no_grad():
            t = RL.policy_terms(gen.model, Bt, idx, 0.35, 0.5, T_gate=0.3)
        for k in ("lp_gate", "lp_card", "lp_cell"):
            self.assertLess(float((t[k] - Bt[k][idx]).abs().max()), 1e-5, k)
        rows = np.flatnonzero(np.isfinite(B["cf_q"][:len(B["cf"]) - n_alt]))
        self.assertEqual(len(rows), len(smp))                            # every decision row re-credited
        self.assertGreater(st["cf"]["fork_ticks_per_match_tick"], 0)


if __name__ == "__main__":
    unittest.main()
