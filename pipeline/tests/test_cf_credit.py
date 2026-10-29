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
import json
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
ONC = {**ON, "action_delay_ticks": 26}                  # + what the combo's follow_ups play needs (e1_eval.SelfPlaySide.apply)
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
        self.assertEqual(c["cf_p"], {**CF.P_DEFAULT, "rocket_tornado": 0.0})     # no action delay: no combo play (see below)
        self.assertEqual(CF.cf_cfg(ONC)["cf_p"], CF.P_DEFAULT)                    # the owner-required triggers are on by default
        self.assertEqual(CF.cf_cfg({**ONC, "cf_p": {"rocket": 1.0}})["cf_p"], {**CF.P_DEFAULT, "rocket": 1.0})
        self.assertEqual((c["cf_adv_scale"], c["cf_diag"]), (1.0, False))
        self.assertIsNotNone(CF.cf_cfg({**ON, "shaping": "tower_phat"}))        # the fast loop's Phi: the forks value it
        for bad in ({"advantage": "match_loo"}, {"gae_gamma_unit": "row"}, {"league": False}, {"branch_gate": True},
                    {"posture_head": True}, {"critic_ctx": "arch"}, {"kl_ref_gate_max_elixir": 3},
                    {"shaping": "tower_crown"}, {"princess_redirect": "potential"}, {"lead_protect": True},
                    {"habit_reward": True}, {"spell_value": True}, {"stored_values": True}, {"cf_credit": "yes"}, {"cf_horizon_ticks": 0},
                    {"cf_k": 0}, {"cf_p": {"rocket": 1.5}}, {"cf_p": {"nope": 0.1}}, {"cf_clip": 0},
                    {"cf_front_min_tiles": 9.0}, {"cf_audit_p": 2}, {"cf_shrink": 1}, {"cf_adv_scale": 0},
                    {"cf_adv_scale": 2.5}, {"cf_diag": 1}, {"cf_diag": "yes"}):
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

    def test_adv_scale_multiplies_the_training_advantage_only(self):
        rng = np.random.default_rng(3)
        samples = [{"trigger": "rocket", "cands": [{"q": rng.normal(0, .3, 2).tolist()} for _ in range(3)]} for _ in range(40)]
        c = {"cf_shrink": True, "cf_shrink_min": 30}
        base, rel = CF.batch_advantages(samples, c)
        sc, rel2 = CF.batch_advantages(samples, {**c, "cf_adv_scale": 0.72})
        same, _ = CF.batch_advantages(samples, {**c, "cf_adv_scale": 1.0})
        for a, b, e in zip(base, sc, same):
            np.testing.assert_allclose(b, 0.72 * a, rtol=0, atol=1e-12)
            np.testing.assert_array_equal(a, e)
        self.assertEqual(rel, rel2)                                               # the reliability is computed before the scale

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


# ------------------------------------------------------------------------------------------------------
# opt-in triggers: rocket_tornado (combo vs lone Rocket) and tornado_redirect (Tornado into our king)
# ------------------------------------------------------------------------------------------------------
OLD_P = {k: v for k, v in CF.P_DEFAULT.items() if k != "rocket_tornado"}   # ON has no action delay: rocket_tornado falls back to 0


class TestNewTriggerConfig(unittest.TestCase):
    def test_owner_required_triggers_are_on_by_default(self):
        """P3-FORK2 (lead 10-28): rocket_tornado 0.055 / tornado_redirect 0.0011 by default; the combo only where the config can
        play its follow_ups Tornado (else 0.0, silently, unless cf_p sets it -> test_validation); 0.0 explicit = the trigger off."""
        self.assertEqual((CF.P_DEFAULT["rocket_tornado"], CF.P_DEFAULT["tornado_redirect"]), (0.055, 0.0011))
        c = CF.cf_cfg(ON)
        self.assertEqual((c["cf_p"]["rocket_tornado"], c["cf_p"]["tornado_redirect"]), (0.0, 0.0011))
        c = CF.cf_cfg(ONC)
        self.assertEqual((c["cf_p"]["rocket_tornado"], c["cf_p"]["tornado_redirect"]), (0.055, 0.0011))
        for bad in ({"pipeline_decisions": True}, {"tap_loss": "0.1"}, {"tap_slow": 0.1}):
            self.assertEqual(CF.cf_cfg({**ONC, **bad})["cf_p"]["rocket_tornado"], 0.0, bad)
        self.assertEqual(CF.cf_cfg({**ONC, "cf_p": {"rocket_tornado": 0.0}})["cf_p"]["rocket_tornado"], 0.0)
        for name in CF.OPT_IN:
            self.assertIn(name, CF.TRIGGERS)

    def test_hash(self):
        can = CF.canonical({**ON})
        self.assertEqual(can["cf_p"], OLD_P)                                     # the fallback zero is not in the hash
        self.assertEqual(CF.canonical({**ON, "cf_p": {"rocket_tornado": 0.0}}), can)       # explicit 0.0 = the fallback
        self.assertFalse(set(CF.NEW_KEYS) & set(can))
        self.assertEqual(CF.canonical({**ON, "cf_combo_value": 6.0, "cf_adv_scale": 1.0, "cf_diag": False,
                                       "cf_p": {"tornado_redirect": CF.P_DEFAULT["tornado_redirect"]}}), can)
        canc = CF.canonical(ONC)
        self.assertEqual(canc["cf_p"], CF.P_DEFAULT)
        self.assertEqual(CF.canonical({**ONC, "cf_p": {"rocket_tornado": 0.055}}), canc)    # explicit = implicit
        self.assertNotEqual(canc, CF.canonical({**ONC, "cf_p": {"rocket_tornado": 0.0}}))
        on = CF.canonical({**ON, "cf_p": {"rocket_tornado": 0.5}})
        self.assertEqual(on["cf_p"]["rocket_tornado"], 0.5)
        self.assertNotEqual(on, can)
        self.assertEqual(CF.canonical({**ON, "cf_redirect_dist_tiles": 9.0})["cf_redirect_dist_tiles"], 9.0)
        self.assertEqual(CF.canonical({**ON, "cf_adv_scale": 0.72})["cf_adv_scale"], 0.72)
        self.assertIs(CF.canonical({**ON, "cf_diag": True})["cf_diag"], True)
        self.assertNotEqual(CF.canonical({**ON, "cf_diag": True}), can)
        base = RL.load_config(L16, [], False)
        self.assertEqual(RL.config_sha({**base, "cf_credit": True}),
                         RL.config_sha({**base, "cf_credit": True, "cf_p": {"tornado_redirect": CF.P_DEFAULT["tornado_redirect"]}}))
        self.assertNotEqual(RL.config_sha({**base, "cf_credit": True}),
                            RL.config_sha({**base, "cf_credit": True, "cf_p": {"tornado_redirect": 0.2}}))
        self.assertNotEqual(RL.config_sha({**base, "cf_credit": True}), RL.config_sha({**base, "cf_credit": True, "cf_adv_scale": 0.72}))

    def test_validation(self):
        delay = {"action_delay_ticks": 26}
        self.assertEqual(CF.cf_cfg({**ON, **delay, "cf_p": {"rocket_tornado": 0.3}})["cf_p"]["rocket_tornado"], 0.3)
        for bad in ({"cf_p": {"rocket_tornado": 0.3}},                         # no action delay: no follow_ups play
                    {**delay, "pipeline_decisions": True, "cf_p": {"rocket_tornado": 0.3}},
                    {**delay, "tap_loss": "0.1", "cf_p": {"rocket_tornado": 0.3}},
                    {"cf_combo_value": -1.0}, {"cf_redirect_dist_tiles": 0}):
            with self.assertRaises(SystemExit, msg=bad):
                CF.cf_cfg({**ON, **bad})
        CF.cf_cfg({**ON, "cf_p": {"tornado_redirect": 0.3}})                  # the redirect needs no follow-up
        with self.assertRaises(SystemExit):
            CF.cf_cfg({**ON, "cf_p": {"rocket_tornado": 0.055}})              # explicit > 0 without the follow_ups play: refused


class TestPerTriggerNoiseControls(unittest.TestCase):
    def test_config_and_hash(self):
        c = CF.cf_cfg({**ON, "cf_k_by": {"rocket": 4}, "cf_horizon_by": {"siege": 400}})
        self.assertEqual((CF.trigger_k(c, "rocket"), CF.trigger_k(c, "xbow")), (4, 2))
        self.assertEqual((CF.trigger_horizon(c, "siege"), CF.trigger_horizon(c, "xbow"), CF.trigger_horizon(c, "wincon")),
                         (400, 600, 300))
        c0 = CF.cf_cfg(ON)
        self.assertEqual((c0["cf_k_by"], c0["cf_horizon_by"]), ({}, CF.HORIZON_DEFAULT))
        self.assertEqual(CF.canonical({**ON, "cf_k_by": {}, "cf_horizon_by": None}), CF.canonical(ON))   # off = the old hash
        self.assertEqual(CF.canonical({**ON, "cf_horizon_by": dict(CF.HORIZON_DEFAULT)}), CF.canonical(ON))   # explicit = implicit
        self.assertNotEqual(CF.canonical({**ON, "cf_horizon_by": {"idle_full": 600}}), CF.canonical(ON))
        self.assertEqual(CF.cf_cfg({**ON, "cf_horizon_by": {"idle_full": 600}})["cf_horizon_by"]["idle_full"], 600)
        self.assertEqual(CF.trigger_horizon(c0, "wincon"), 300)
        self.assertNotEqual(CF.canonical({**ON, "cf_k_by": {"rocket": 4}}), CF.canonical(ON))
        self.assertEqual(CF.cf_cfg({**ON, "cf_horizon_sweep": [300, 150]})["cf_horizon_sweep"], [150, 300])
        self.assertEqual(CF.canonical({**ON, "cf_horizon_sweep": []}), CF.canonical(ON))
        self.assertNotEqual(CF.canonical({**ON, "cf_horizon_sweep": [150]}), CF.canonical(ON))
        for bad in ({"cf_k_by": {"nope": 3}}, {"cf_k_by": {"rocket": 1}}, {"cf_k_by": {"rocket": 2.5}},
                    {"cf_horizon_by": {"rocket": 0}}, {"cf_horizon_by": [600]}, {"cf_horizon_sweep": [0]},
                    {"cf_horizon_sweep": 300}):
            with self.assertRaises(SystemExit, msg=bad):
                CF.cf_cfg({**ON, **bad})

    def test_reliability_pools_triggers_with_different_k(self):
        rng = np.random.default_rng(1)
        sig = rng.standard_normal((200, 1))

        def adv(K):
            q = sig + 0.5 * rng.standard_normal((200, K))
            q = np.stack([q, -q])                                          # two candidates: [2, 200, K]
            return [(q[:, i, :] - q[:, i, :].mean(axis=0, keepdims=True)) for i in range(200)]
        a2, a4 = adv(2), adv(4)
        pooled = CF.reliability(a2 + a4)                                   # K = 2 and K = 4 samples together: first 2 columns
        self.assertEqual(pooled["n"], 800)
        self.assertGreater(pooled["factor"], 0.5)
        r4 = CF.reliability(a4)
        r2 = CF.reliability(a2)
        self.assertGreater(r4["snr"], r2["snr"])                           # more continuations -> a cleaner K-mean


class TestNewTriggerGeometry(unittest.TestCase):
    def test_pull_centre(self):
        cx, cy = CF.pull_centre(3.5, 16.0, 9.0, 29.5, 4.75)
        self.assertAlmostEqual(np.hypot(cx - 3.5, cy - 16.0), 4.75, places=9)             # reach tiles from the unit
        self.assertLess(np.hypot(9.0 - cx, 29.5 - cy), np.hypot(9.0 - 3.5, 29.5 - 16.0))   # closer to the king
        self.assertAlmostEqual((cx - 3.5) * (29.5 - 16.0) - (cy - 16.0) * (9.0 - 3.5), 0.0, places=9)   # on the segment
        self.assertEqual(CF.pull_centre(8.0, 27.0, 9.0, 29.5, 4.75), (9.0, 29.5))           # target within reach: the target
        self.assertEqual(CF.pull_centre(0.0, 31.9, 0.0, 40.0, 4.75), (0.5, 31.5))           # kept on the board
        self.assertEqual(CF.pull_centre(5.0, 5.0, 5.0, 5.0, 4.75), (5.0, 5.0))

    def test_drifted_moves_the_aim_toward_my_side_by_speed_times_flight(self):
        from pipeline import decision_options as DO
        bodies = np.array([[1.0, 5.0, 10.0, 4.0, 0.5, 0.0, 0.05], [2.0, 12.0, 14.0, 3.0, 0.5, 0.0, 0.0]])
        x, y = CF.drifted(bodies, 5.0, 10.0)
        self.assertEqual(x, 5.0)
        self.assertGreater(y, 10.0 + 0.05 * DO.rocket_lands_in(5.0, 10.0) - 1e-6 - 0.5)       # about speed x flight
        self.assertLess(y, 10.0 + 0.05 * (DO.rocket_lands_in(5.0, 10.0) + 6))
        self.assertEqual(CF.drifted(bodies, 12.0, 14.0), (12.0, 14.0))                      # a standing body: no lead
        self.assertEqual(CF.drifted(bodies, 1.0, 1.0), (1.0, 1.0))                          # no body near the target
        self.assertEqual(CF.drifted(bodies[:0], 5.0, 10.0), (5.0, 10.0))

    def test_rocket_lead_config_and_hash(self):
        self.assertEqual(CF.cf_cfg(ON)["cf_rocket_lead"], "off")
        self.assertEqual(CF.cf_cfg({**ON, "cf_rocket_lead": "drift"})["cf_rocket_lead"], "drift")
        with self.assertRaises(SystemExit):
            CF.cf_cfg({**ON, "cf_rocket_lead": "on"})
        self.assertEqual(CF.canonical({**ON, "cf_rocket_lead": "off"}), CF.canonical(ON))
        self.assertEqual(CF.canonical({**ON, "cf_rocket_lead": "drift"})["cf_rocket_lead"], "drift")

    def test_cell_at_is_nearest_centre(self):
        from pipeline import decision_options as DO
        x, y = DO.cell_centres_tiles("lattice")
        c = CF.cell_at("lattice", 3.4, 22.6)
        self.assertEqual(c, int(np.argmin(np.hypot(x - 3.4, y - 22.6))))
        self.assertLess(np.hypot(x[c] - 3.4, y[c] - 22.6), 1.0)

    def test_redirect_target(self):
        from pipeline import vocab

        def unit(name, tx, ty, side=1):
            return NS(side=side, cls=vocab.UNIT_VOCAB.index(name), x=tx / 18.0, y=ty / 32.0, hp_frac=1.0)

        def side(units, dead=()):
            tw = [{"side": 0, "type": "king", "x": 9000.0, "y": 2500.0}, {"side": 0, "type": "princess", "x": 3500.0, "y": 6500.0},
                  {"side": 0, "type": "princess", "x": 14500.0, "y": 6500.0}]     # my frame: king (9, 29.5), princesses y 25.5
            for i, t in enumerate(tw):
                t.update(hp=0 if i in dead else 1000, destroyed=i in dead)
            return NS(side=0, mirror=False, state={"episode": {"crown_towers": tw}}, _cur=(100, NS(units=units)))
        c = CF.cf_cfg(ON)
        hog = unit("hog_rider", 3.5, 16.5)                                     # on the bridge, 9 tiles from our L princess
        tg = CF.redirect_target(side([hog]), c)
        self.assertEqual(tg["name"], "hogrider")
        self.assertAlmostEqual(tg["d"], 9.0, places=3)
        self.assertEqual((tg["princess"], tg["king"]), ((3.5, 25.5), (9.0, 29.5)))
        near = unit("knight", 12.0, 22.0)                                      # nearer to the R princess: wins
        self.assertEqual(CF.redirect_target(side([hog, near]), c)["name"], "knight")
        self.assertIsNone(CF.redirect_target(side([unit("balloon", 3.5, 20.0)]), c))     # a flyer is not pulled to the king
        self.assertIsNone(CF.redirect_target(side([unit("hog_rider", 3.5, 12.0)]), c))   # still on their bank
        self.assertIsNone(CF.redirect_target(side([unit("cannon", 3.5, 20.0)]), c))      # a building never moves
        self.assertIsNone(CF.redirect_target(side([unit("hog_rider", 3.5, 16.5, side=0)]), c))   # our own unit
        self.assertIsNone(CF.redirect_target(side([hog], dead=(1,)), c))       # one princess down: the redirect is off
        self.assertIsNone(CF.redirect_target(side([hog], dead=(0,)), c))       # no king, no redirect
        self.assertIsNone(CF.redirect_target(side([unit("hog_rider", 14.5, 15.5)]), {**c, "cf_redirect_dist_tiles": 5.0}))
        ck = CF.cf_cfg({**ON, "cf_redirect_king_tiles": 9.0})                # P3-FORK3: + a distance limit to OUR king (off = above)
        self.assertIsNone(CF.redirect_target(side([hog]), ck))                # the bridge Hog is 14.1 tiles from our king
        self.assertEqual(CF.redirect_target(side([hog, near]), ck)["name"], "knight")   # (12, 22) is 7.9 tiles from it
        self.assertEqual(CF.canonical({**ON, "cf_redirect_king_tiles": None}), CF.canonical(ON))
        self.assertNotEqual(CF.canonical({**ON, "cf_redirect_king_tiles": 9.0}), CF.canonical(ON))
        for bad in (0, -1.0, "9"):
            with self.assertRaises(SystemExit):
                CF.cf_cfg({**ON, "cf_redirect_king_tiles": bad})


class _NoHand(Exception):
    pass


@unittest.skipIf(RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestNewTriggerForks(unittest.TestCase):
    def test_candidates_and_forks_play_the_scripted_second_card(self):
        """At the first decision with the Rocket and the Tornado both affordable and >= 9 elixir: the combo candidate (the
        Rocket + a follow_ups Tornado) is built by candidates() from a combo plan and its fork plays BOTH cards while the
        lone Rocket's fork plays the Rocket only; the redirect candidates (king pull, centre on the unit) are distinct cells
        whose king-pull centre is nearer the king than the unit; every Q is finite."""
        got: dict = {}
        from pipeline import decision_options as DO

        class Spy(CF.Runner):
            def hook(self, live, todo):
                if not live or "done" in got:
                    return
                m = live[0]
                for s, p, d in todo:
                    if s is not m.learner:
                        continue
                    names, al = CF.slot_names(s), np.asarray(d["allowed"], bool)
                    hand = {str(h["name"]).lower() for pl in s.state["players"] if int(pl["side"]) == s.side for h in pl["hand"]}
                    if not {"rocket", "tornado"} <= hand:
                        raise _NoHand(hand)                               # this seed's opening hand: try the next
                    rk, tk = CF._slot_of(names, al, "rocket"), CF._slot_of(names, al, "tornado")
                    got.setdefault("seen", []).append((int(m.env.tick), rk is not None, tk is not None, round(CF.own_elixir(s), 1)))
                    if rk is None or tk is None or not d["gate_sampled"] or CF.own_elixir(s) < 9.0:
                        d["play"] = False                                 # wait: the elixir builds, the hand stays
                        continue
                    c = {**self.c, "cf_max_alts": 4}
                    m.cf_state = CF.new_state(s)
                    cell = TS.CELL
                    m.cf_state["combo_hit"] = (rk, tk, cell, (8, 14), 7.0, "rocket")
                    cands = CF.candidates(m, s, d, "rocket_tornado", c)
                    entries = [x for x in todo if x[0] is m.learner or x[0] is m.opp]
                    out = self.rollouts(m, entries, cands, seed=3)
                    got["k3"] = (int(m.env.tick), self.rollouts(m, entries, cands[:2], seed=3, k=3, horizon=300))
                    c0 = self.c
                    self.c = {**c0, "cf_horizon_sweep": [60, 120]}
                    got["sweep"] = self.rollouts(m, entries, cands, seed=3)                  # the SAME forks, Q also at 60 / 120
                    self.c = c0
                    forks = {}
                    for fi, f in enumerate(self.last_forks):
                        if fi < len(cands):                                   # continuation 0 of each candidate
                            forks[cands[fi]["kind"]] = [str(x) for x in f.learner.accepted]
                    got.update(done=True, cands=cands, out=out, forks=forks, rk=rk, tk=tk, cell=cell, names=names)
                    m.cf_state["redirect_target"] = {"name": "hogrider", "bx": 3.5, "by": 16.5, "king": (9.0, 29.5),
                                                     "princess": (3.5, 25.5), "d": 9.0}
                    got["red"] = CF.candidates(m, s, d, "tornado_redirect", c)
                    got["tor_cells"] = (DO.cell_centres_tiles(s.cfg["grid"]), tk)
                    return

        for seed in range(40):
            got.clear()
            gen, opp_gen, lcfg, ocfg, spec = _setup()
            try:
                with patch.object(CF, "Runner", Spy):
                    E.run_selfplay_batch(lambda: RoyaleSelfPlayEnv(tail_cap=TAIL), gen, {"gen": (opp_gen, ocfg)},
                                         [(0, {**spec, "seed": seed}, 0)], lcfg, 1, on_result=lambda r: None)
            except _NoHand:
                continue
            break
        both = [x for x in got.get("seen", []) if x[1] and x[2]]
        self.assertIn("done", got, f"no decision with Rocket + Tornado affordable at >= 9 elixir; decisions {len(got.get('seen', []))}, "
                                   f"both-affordable {both[:12]}")
        root, o3 = got["k3"]                                                       # per-sample K and horizon (cf_k_by / cf_horizon_by)
        self.assertTrue(all(len(a["q"]) == 3 and len(a["end"]) == 3 for a in o3["cands"]))
        self.assertTrue(all(root + 300 <= e < root + 300 + 120 for a in o3["cands"] for e in a["end"]), o3["cands"])
        for a, b in zip(got["out"]["cands"], got["sweep"]["cands"]):                  # the sweep changes nothing it measures
            self.assertEqual((a["q"], a["end"], a["terminal"]), (b["q"], b["end"], b["terminal"]))
            self.assertNotIn("qh", a)
            self.assertEqual(sorted(b["qh"]), ["120", "60"])
            for h in ("60", "120"):
                self.assertTrue(len(b["qh"][h]) == 2 and all(np.isfinite(v) for v in b["qh"][h]), b["qh"])
            self.assertNotEqual(b["qh"]["60"], b["qh"]["120"])
        self.assertEqual(got["sweep"]["fork_ticks"], got["out"]["fork_ticks"])
        kinds = [a["kind"] for a in got["cands"]]
        self.assertEqual(kinds[0], "chosen")
        self.assertIn("combo", kinds)
        combo = got["cands"][kinds.index("combo")]
        self.assertEqual((combo["slot"], combo["cell"]), (got["rk"], got["cell"]))
        fu = combo["follow_ups"]
        self.assertEqual((len(fu), fu[0]["slot"], fu[0]["cell"], fu[0]["after_ticks"]), (1, got["tk"], got["cell"], 11 + 2))
        for a, r in zip(got["cands"], got["out"]["cands"]):
            self.assertTrue(all(np.isfinite(q) for q in r["q"]), a["kind"])
        cb = got["out"]["cands"][kinds.index("combo")]
        self.assertEqual(cb["follow"][0].get("fired"), 1, cb["follow"])               # the scripted Tornado fired in continuation 0
        self.assertNotIn("follow", got["out"]["cands"][0])                            # the chosen candidate has none
        plays = [eval(x) for x in got["forks"]["combo"]]                     # (landing tick, card slug) of the fork's learner
        first = [t for t, n in plays if n == "rocket"]
        second = [t for t, n in plays if n == "tornado"]
        self.assertTrue(first and second and 0 <= second[0] - first[0] <= 20, plays)      # the scripted Tornado follows the Rocket
        for kind, acc in got["forks"].items():                                    # a lone Rocket (rocket_clump) has no scripted Tornado
            pl = [eval(x) for x in acc]
            if kind != "combo" and pl and pl[0][1] == "rocket":
                self.assertFalse(any(n == "tornado" and 0 <= t - pl[0][0] <= 20 for t, n in pl[1:]), (kind, pl))
        red = got["red"]
        rk_ = [a["kind"] for a in red]
        self.assertTrue({"tornado_king", "tornado_on"} <= set(rk_), rk_)
        (x, y), tk = got["tor_cells"]
        cells = {a["kind"]: a["cell"] for a in red if a["play"]}
        self.assertEqual(len(set(cells.values())), len(cells))
        kc, uc = cells["tornado_king"], cells["tornado_on"]
        self.assertLess(np.hypot(x[kc] - 9.0, y[kc] - 29.5), np.hypot(x[uc] - 9.0, y[uc] - 29.5))
        self.assertTrue(all(a["slot"] == tk for a in red if a["kind"].startswith("tornado")))


class TestRocketEmpty(unittest.TestCase):
    """P3-FORK3: cf_rocket_empty / cf_diag_plays config (bool, opt-in, absent = the cf-on hash unchanged) + the empty cell."""

    def test_config_and_hash(self):
        c = CF.cf_cfg(ON)
        self.assertEqual((c["cf_rocket_empty"], c["cf_diag_plays"]), (False, False))
        self.assertIs(CF.cf_cfg({**ON, "cf_rocket_empty": True})["cf_rocket_empty"], True)
        self.assertIs(CF.cf_cfg({**ON, "cf_diag": True, "cf_diag_plays": True})["cf_diag_plays"], True)
        for bad in ({"cf_rocket_empty": 1}, {"cf_diag_plays": True}, {"cf_diag": True, "cf_diag_plays": "yes"}):
            with self.assertRaises(SystemExit):
                CF.cf_cfg({**ON, **bad})
        can = CF.canonical(ON)
        self.assertEqual(CF.canonical({**ON, "cf_rocket_empty": False, "cf_diag_plays": False}), can)
        self.assertNotEqual(CF.canonical({**ON, "cf_rocket_empty": True}), can)
        with self.assertRaises(SystemExit):                                     # off: a stray key refuses
            CF.cf_cfg({"cf_rocket_empty": True})

    def test_empty_rocket_cell(self):
        from pipeline import decision_options as DO
        grid = "lattice"
        x, y = DO.cell_centres_tiles(grid)

        def ent(bx, by, side=1):                                               # board tiles (my frame) -> engine units
            return {"side": side, "x": bx * 1000.0, "y": 32000.0 * (1 - by / 32.0), "name": "knight"}

        tw = [{"side": 1, "type": t, "x": bx * 1000.0, "y": 32000.0 * (1 - by / 32.0), "hp": 1000, "destroyed": False}
              for t, bx, by in (("king", 9.0, 3.0), ("princess", 3.5, 6.5), ("princess", 14.5, 6.5))]

        def side(ents):
            return NS(side=0, mirror=False, state={"entities": ents, "episode": {"crown_towers": tw}})
        c0 = CF.empty_rocket_cell(side([]), grid)
        self.assertLess(np.hypot(x[c0] - 9.0, y[c0] - 12.0), 0.8)               # the first point, nothing near it
        self.assertEqual(CF.empty_rocket_cell(side([ent(3.5, 16.0)]), grid), c0)    # a bridge body is 6.8 tiles away
        self.assertEqual(CF.empty_rocket_cell(side([ent(9.0, 12.0, side=0)]), grid), c0)   # our own body never blocks
        c1 = CF.empty_rocket_cell(side([ent(9.0, 16.0)]), grid)                 # 4 tiles from (9, 12) -> the next point (9, 9.5)
        self.assertLess(np.hypot(x[c1] - 9.0, y[c1] - 9.5), 0.8)
        self.assertIsNone(CF.empty_rocket_cell(side([ent(9.0, 12.0)]), grid))  # every point within 5.5 tiles of it
        for cx, cy in CF.EMPTY_ROCKET_TILES:                                  # no point is within reach of a crown tower
            self.assertTrue(all(np.hypot(cx - t["x"] / 1000.0, cy - 32.0 * (1 - t["y"] / 32000.0)) > CF.EMPTY_CLEAR_TILES
                                for t in tw))

class TestMacros(unittest.TestCase):
    """P3-FORK3: the P6 macros rocket_cycle (rocket_cycle.after2) / def_xbow (def_xbow_hard) as opt-in fork triggers."""

    def test_library_pin_and_config(self):
        import hashlib
        lib = REPO / "scratchpad/gauntlet/L74/plan1026/macros/LIBRARY.json"
        self.assertEqual(hashlib.sha256(lib.read_bytes()).hexdigest(), CF.MACRO_LIB_SHA256)      # a new library = re-check
        L = {m["id"]: m for m in json.loads(lib.read_text(encoding="utf-8"))["macros"]}
        rc, dx = L[CF.MACROS["rocket_cycle"]], L[CF.MACROS["def_xbow"]]
        self.assertEqual([q["card"] for q in rc["prefix"]], ["rocket"])
        self.assertEqual((rc["window_ticks"], rc["horizon_ticks"]), (CF.RC_WINDOW, CF.MACRO_HORIZON["rocket_cycle"]))
        self.assertIn(">= 2 failed", rc["start_condition"])
        self.assertIn("tick 2400", L[rc["refine_of"]]["start_condition"])
        self.assertIn("lower-HP", rc["prefix"][0]["place"])
        self.assertEqual([q["card"] for q in dx["prefix"]], ["x_bow", "x_bow"])
        self.assertEqual((dx["window_ticks"], dx["horizon_ticks"]), (CF.DX_COUNTER_WITHIN, CF.MACRO_HORIZON["def_xbow"]))
        self.assertIn("22.5", dx["prefix"][0]["place"])
        c0 = CF.cf_cfg(ON)                                                       # absent = off, the old hash
        self.assertNotIn("rocket_cycle", c0["cf_p"])
        self.assertEqual(CF.canonical({**ON, "cf_p": {"rocket_cycle": 0.0, "def_xbow": 0.0}}), CF.canonical(ON))
        c = CF.cf_cfg({**ON, "cf_p": {"rocket_cycle": 1.0, "def_xbow": 0.3}, "cf_horizon_by": {"rocket_cycle": 7000}})
        self.assertEqual((CF.trigger_horizon(c, "rocket_cycle"), CF.trigger_horizon(c, "def_xbow"),
                          CF.trigger_horizon(c0, "def_xbow"), CF.trigger_horizon(c0, "rocket")), (7000, 1200, 1200, 600))
        self.assertNotEqual(CF.canonical({**ON, "cf_p": {"def_xbow": 0.3}}), CF.canonical(ON))
        self.assertEqual(CF.TRIGGERS[-1], "random")

    def test_matchup_ctx(self):
        deck = ["HogRider", "Earthquake", "Log", "Cannon", "Musketeer", "IceSpirits", "Skeletons", "Valkyrie"]
        costs = [4, 3, 2, 3, 4, 1, 1, 4]

        def ctx(acc, est, names=deck, tick=100):
            m = NS(opp=NS(engine_deck=names, deck_index_of_slot=list(range(8)), costs=costs, accepted=acc))
            return CF.matchup_ctx(m, NS(public=NS(estimate_at=lambda t: est), side=0), tick)
        self.assertEqual(ctx([], 5.0), ("EQ", "unrevealed", False))
        five = [(10, "hog_rider"), (20, "log"), (30, "cannon"), (40, "ice_spirits"), (50, "skeletons")]
        self.assertEqual(ctx(five, 5.0), ("EQ", "ready", True))                 # Hog 4 plays ago: back in hand, affordable
        self.assertEqual(ctx(five, 2.0), ("EQ", "short", True))
        self.assertEqual(ctx(five[:2], 5.0), ("EQ", "cycled", False))           # Hog 1 play ago: still cycling
        self.assertEqual(ctx(five[:4] + [(150, "skeletons")], 5.0)[1], "cycled")   # a play landing after the tick is not seen
        siege = ["Xbow", "Tesla", "Log", "Knight", "Rocket", "Skeletons", "IceSpirits", "Fireball"]
        self.assertEqual(ctx(five, 5.0, names=siege)[0], "SIEGE")
        beat = ["Golem", "NightWitch", "Lumberjack", "BabyDragon", "Tornado", "Lightning", "Barbarians", "Zap"]
        self.assertEqual(ctx([], 5.0, names=beat)[0], "BEATDOWN")
        other = ["Miner", "Poison", "Log", "Knight", "Bats", "Tesla", "IceSpirits", "Skeletons"]
        self.assertEqual(ctx([], 5.0, names=other)[0], "OTHER")


@unittest.skipIf(RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestMacroPrefixFork(unittest.TestCase):
    def test_prefix_plays_the_counter_lock_and_leaves_other_candidates_alone(self):
        """At the first decision with the X-Bow affordable: [chosen, X-Bow now + a prefix step] forked K = 3 over 3,000 ticks.
        The prefix outcome is recorded per continuation; a fired step put its card into that fork's learner plays, landing
        after the action delay from ``fired`` ticks after the root, on a reach cell of the step's lane; candidate 0's Q equals
        a fork set without the prefix candidate (the prefix never touches another candidate's copies); the real match is
        untouched."""
        got: dict = {}

        class Spy(CF.Runner):
            def hook(self, live, todo):
                if not live or "done" in got:
                    return
                m = live[0]
                for s, p, d in todo:
                    if s is not m.learner:
                        continue
                    al = np.asarray(d["allowed"], bool)
                    xk = CF._slot_of(CF.slot_names(s), al, "xbow")
                    hand = {CF._norm(h["name"]) for pl in s.state["players"] if int(pl["side"]) == s.side for h in pl["hand"]}
                    got.setdefault("seen", []).append((int(s._cur[0]), xk, bool(d["gate_sampled"]), int(al.sum()), "xbow" in hand))
                    if xk is None or not d["gate_sampled"] or int(s._cur[0]) < 200:
                        if "xbow" in hand:
                            d["play"] = False                             # X-Bow in hand: save up for it
                        continue                                          # else the policy plays on: its hand cycles
                    pol = CF._Pol(s, d)
                    a = pol.cand("xbow_def_tile", xk, "argmax")
                    # the step's card is the 1-elixir Skeletons (this random tiny policy rarely holds 6 elixir with the X-Bow in
                    # hand: the mechanism under test is the scripted play at the step's first availability, not its economics)
                    a["prefix"] = [{"card": "skeletons", "where": "reach_lane", "lane": "L", "within": 3000}]
                    ch = _chosen(d)
                    entries = [x for x in todo if x[0] is m.learner or x[0] is m.opp]
                    h0 = (m.env.core.state_hash(), TS.env_digest(m.env), TS.side_digest(m.learner))
                    got["one"] = self.rollouts(m, entries, [ch], seed=5, k=3, horizon=3000)
                    got["two"] = self.rollouts(m, entries, [ch, a], seed=5, k=3, horizon=3000)
                    got["acc"] = [[(int(t), str(n)) for t, n in f.learner.accepted] for f in self.last_forks]
                    got["n0"] = len(m.learner.accepted)
                    got["same"] = (m.env.core.state_hash(), TS.env_digest(m.env), TS.side_digest(m.learner)) == h0
                    got["root"] = int(m.env.tick)
                    got["reach"] = CF.xbow_reach_cells(s, s.cfg["grid"])
                    from pipeline import decision_options as DO
                    got["x"] = DO.cell_centres_tiles(s.cfg["grid"])[0]
                    got["done"] = True
                    return

        gen, opp_gen, lcfg, ocfg, spec = _setup()
        with patch.object(CF, "Runner", Spy):
            E.run_selfplay_batch(lambda: RoyaleSelfPlayEnv(tail_cap=TAIL), gen, {"gen": (opp_gen, ocfg)}, [(0, spec, 0)],
                                 lcfg, 1, on_result=lambda r: None)
        self.assertIn("done", got, got.get("seen", [])[:60])
        self.assertTrue(got["same"])
        one, two = got["one"]["cands"][0], got["two"]["cands"][0]
        self.assertEqual((one["q"], one["end"]), (two["q"], two["end"]))
        self.assertNotIn("prefix", two)
        pre = got["two"]["cands"][1]["prefix"]
        self.assertEqual(len(pre), 3)
        fired = 0
        for k, outc in enumerate(pre):
            self.assertEqual(len(outc), 1)
            self.assertTrue(set(outc[0]) & {"fired", "lapsed", "no_cell", "pending"}, outc)
            if "fired" in outc[0]:
                fired += 1
                acc = got["acc"][2 * k + 1][got["n0"]:]                         # continuation-major: (k, candidate 1)
                sk = [t for t, n in acc if n == "skeletons" and t - got["root"] >= outc[0]["fired"]]
                self.assertTrue(sk and 0 <= sk[0] - got["root"] - outc[0]["fired"] <= 120, (acc, outc))   # landed after its delay(s)
                self.assertTrue(got["reach"][outc[0]["cell"]] and got["x"][outc[0]["cell"]] < 9.0, outc)   # lane L, in reach
                self.assertTrue(got["reach"].any())
        self.assertGreater(fired, 0, pre)

@unittest.skipIf(RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestEngineRefusal(unittest.TestCase):
    def test_a_refused_fork_drops_its_sample_and_the_match_goes_on(self):
        """An engine (JVM) exception inside a fork set: that sample is dropped and recorded in ``fork_errors``, the real match
        plays to its end with the other samples; any other exception still propagates."""
        class UnsupportedOperationException(Exception):
            pass
        UnsupportedOperationException.__module__ = "java.lang"           # what jpype gives a JVM exception class
        calls = {"n": 0}

        def trig(m, s, d, c):
            al = np.asarray(d["allowed"], bool)
            if int(s._cur[0]) < 300 or calls["n"] >= 3 or not al.any() or not d["gate_sampled"]:
                return []
            calls["n"] += 1
            return ["random"]

        class Boom(CF.Runner):
            def rollouts(self, m, *a, **kw):
                if calls["n"] == 2:
                    raise UnsupportedOperationException("Deflect_3000014 deflects proj from the king tower without a target")
                return super().rollouts(m, *a, **kw)
        with patch.object(CF, "triggers", trig):
            _, r = _run(Boom)
        self.assertEqual(len(r["cf"]["samples"]), 2)
        self.assertEqual(len(r["cf"]["fork_errors"]), 1)
        self.assertIn("UnsupportedOperationException", r["cf"]["fork_errors"][0])
        self.assertTrue(r.get("outcome") or r.get("end_tick"))
        self.assertFalse(CF.engine_refusal(ValueError("ours")))

        class Bug(CF.Runner):
            def rollouts(self, m, *a, **kw):
                raise KeyError("a bug of ours")
        calls["n"] = 0
        with patch.object(CF, "triggers", trig), self.assertRaises(KeyError):
            _run(Bug)

@unittest.skipIf(RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestDiag(unittest.TestCase):
    def test_diag_records_context_parts_and_changes_no_value(self):
        """cf_diag on: the same triggered forks give the SAME q / end ticks as with it off; every sample carries ctx (tick, 10-float
        snapshot, hand, enemy bodies), every horizon-stopped candidate a dg record whose Phi + critic parts rebuild q, the match
        record the opponent; off: none of those keys."""
        calls = {"n": 0}

        def trig(m, s, d, c):
            al = np.asarray(d["allowed"], bool)
            if int(s._cur[0]) < 300 or calls["n"] >= 3 or not al.any() or not d["gate_sampled"]:
                return []
            calls["n"] += 1
            return ["random"]

        res = {}
        for diag in (False, True):
            calls["n"] = 0
            with patch.object(CF, "triggers", trig):
                _, res[diag] = _run(CF.Runner, cf_diag=diag, cf_horizon_sweep=[60], **({"cf_diag_plays": True} if diag else {}))
        off, on = res[False]["cf"], res[True]["cf"]
        self.assertEqual(len(on["samples"]), 3)
        for k in ("ctx",):
            self.assertTrue(all(k not in s for s in off["samples"]))
        self.assertNotIn("opp", off)
        self.assertEqual(set(on["opp"]), {"opp", "opp_deck", "learner_deck", "style", "opp_T", "opp_tau"})
        for a, b in zip(off["samples"], on["samples"]):
            self.assertEqual((a["tick"], a["trigger"]), (b["tick"], b["trigger"]))
            self.assertEqual(b["ctx"]["tick"], b["tick"])
            self.assertEqual(len(b["ctx"]["snap"]), 10)
            self.assertEqual(len(b["ctx"]["hand"]), 4)
            self.assertTrue(all(len(f) == 3 for f in b["ctx"]["foe_half"]))
            for ca, cb in zip(a["cands"], b["cands"]):
                self.assertEqual((ca["q"], ca["end"], ca["terminal"], ca["qh"]), (cb["q"], cb["end"], cb["terminal"], cb["qh"]))
                self.assertNotIn("dg", ca)
                self.assertTrue(all(cb["terminal"]) or {"stop", "60"} <= set(cb["dg"]), cb["dg"].keys())
                for k in range(len(cb["q"])):
                    if cb["terminal"][k]:
                        continue
                    ph, v = cb["dg"]["stop"]["phi"][k], cb["dg"]["stop"]["v"][k]
                    g = 0.99994 ** (cb["end"][k] - a["tick"])
                    self.assertAlmostEqual(cb["q"][k], g * (ph + v), places=12)
                    self.assertEqual(len(cb["dg"]["stop"]["snap"][k]), 10)
                    self.assertTrue(all(x >= 0 for x in cb["dg"]["stop"]["np"][k]) and len(cb["dg"]["stop"]["np"][k]) == 2)
                    pl = cb["dg"]["stop"]["pl"][k]                               # cf_diag_plays: the cards behind those counts
                    self.assertEqual([len(z) for z in pl], cb["dg"]["stop"]["np"][k])
                    self.assertTrue(all(0 <= dt <= cb["end"][k] - a["tick"] + 40 and isinstance(n, str) for z in pl for dt, n in z), pl)
        json.dumps(on)                                                            # JSON-able (the pilot dump)


if __name__ == "__main__":
    unittest.main()
