"""C2 / F2 context-aware critic (rl_royale ``critic_ctx: arch | full``; L74 reward/REWARD_ARCHITECTURE.md 5 / 2).

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_critic_ctx.py

Covers: absent / null critic_ctx = the pre-change trainer (config hash, collate, whole updates, checkpoint keys --
compared with the commit before the change); validation; pipeline.archetypes on RoyaleSim body names; the actor's ctx
rows on the real SelfPlayMatch (test_league's fake env); zero-init = the plain critic exactly; the value loss reaches
only value_head + CtxHead under vf_trunk_grad false; checkpoint save -> resume; one_update end to end (arch, full).
"""
from __future__ import annotations

import copy
import importlib.util
import subprocess
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import torch                                                              # noqa: E402

from pipeline import archetypes as AR                                     # noqa: E402
from pipeline import rl_royale as RL                                      # noqa: E402
from pipeline.tests.test_rl_gae import SPEC, TAU, T, _learner, _strip, _Tmp   # noqa: E402
from pipeline.tests.test_rl_royale import _monitor_fields, _results, _tiny_model  # noqa: E402

PRE = "a8440d6"             # the last commit before critic_ctx: the absent-key reference
YAML = REPO / "pipeline" / "rl_royale.yaml"
GAE = dict(advantage="gae", critic_warmup_updates=1, seed=0)


def _pre_module():
    try:
        src = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE}:pipeline/rl_royale.py"], capture_output=True,
                             text=True, encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise unittest.SkipTest(f"git unavailable: {exc}")
    if src.returncode:
        raise unittest.SkipTest(f"git show {PRE} failed: {src.stderr.strip()}")
    mod = types.ModuleType("rl_royale_pre_ctx")
    mod.__file__ = str(REPO / "pipeline" / "rl_royale.py")
    exec(compile(src.stdout, "rl_royale_pre_ctx", "exec"), mod.__dict__)
    return mod


def _with_ctx(results, seed=0):
    """Synthetic ctx rows (valid ranges) on every trajectory; matches 0 and 2 end with tank_flag 1."""
    rng = np.random.default_rng(seed)
    out = copy.deepcopy(results)
    for j, r in enumerate(out):
        n = len(r["traj"]["played"])
        c = np.stack([rng.integers(0, len(AR.ARCH_IDS), n), np.zeros(n, int), rng.integers(0, 3, n),
                      rng.integers(0, 4, n), rng.integers(0, 4, n)], 1).astype(np.int64)
        if j % 2 == 0:
            c[n // 2:, 1] = 1
        r["traj"]["ctx"] = c
    return out


# ------------------------------------------------------------------------------------------------------
class TestConfig(unittest.TestCase):
    def test_hash(self):
        cfg = RL.load_config(YAML, [], False)
        self.assertNotIn("critic_ctx", cfg)
        P = _pre_module()
        self.assertEqual(RL.config_sha(cfg), P.config_sha(cfg))                     # the historical hash
        self.assertEqual(RL.config_sha(cfg), RL.config_sha(dict(cfg, critic_ctx=None)))
        on = {m: RL.config_sha(dict(cfg, critic_ctx=m)) for m in ("arch", "full")}
        self.assertNotIn(RL.config_sha(cfg), on.values())
        self.assertNotEqual(on["arch"], on["full"])

    def test_load_config_override(self):
        cfg = RL.load_config(YAML, ["advantage=gae", "critic_ctx=full"], False)
        self.assertEqual(cfg["critic_ctx"], "full")
        self.assertEqual(RL.adv_cfg(cfg)["critic_ctx"], "full")

    def test_adv_cfg(self):
        self.assertEqual(RL.adv_cfg({}), RL.GAE_DEFAULTS)                          # absent: the R1 dict exactly
        self.assertNotIn("critic_ctx", RL.adv_cfg({"advantage": "gae", "critic_ctx": None}))
        for m in ("arch", "full"):
            self.assertEqual(RL.adv_cfg({"advantage": "gae", "critic_ctx": m})["critic_ctx"], m)
        for bad in ({"advantage": "gae", "critic_ctx": "phase"}, {"advantage": "gae", "critic_ctx": "ARCH"},
                    {"advantage": "gae", "critic_ctx": 1}, {"advantage": "gae", "critic_ctx": ["arch"]},
                    {"critic_ctx": "arch"}, {"advantage": "match_loo", "critic_ctx": "full"}):
            with self.assertRaises(SystemExit, msg=bad) as cm:
                RL.adv_cfg(bad)
            self.assertIn("critic_ctx", str(cm.exception))

    def test_actor_cfg(self):
        base = {**RL.load_config(YAML, [], False), "grid": "lattice"}
        self.assertNotIn("record_ctx", RL.actor_cfg(base, "rollout", 0, "cpu"))
        self.assertNotIn("record_ctx", RL.actor_cfg({**base, "critic_ctx": None}, "rollout", 0, "cpu"))
        for m in ("arch", "full"):
            self.assertIs(RL.actor_cfg({**base, "critic_ctx": m}, "rollout", 0, "cpu")["record_ctx"], True)
            self.assertNotIn("record_ctx", RL.actor_cfg({**base, "critic_ctx": m}, "screen", 0, "cpu"))


# ------------------------------------------------------------------------------------------------------
# RoyaleSim catalogue spellings (RustEngine.cards() names, 2026-10-15) of every card the archetype sets name
SIM = {"tank": ["Golem", "LavaHound", "Giant", "RoyalGiant", "Pekka", "ElectroGiant", "GoblinGiant", "GiantSkeleton",
                "ElixirGolem"],
       "bridge": ["Assassin", "BattleRam", "Ghost", "EliteArcher"],
       "bait": ["GoblinBarrel", "SkeletonArmy", "GoblinGang", "Princess", "BlowdartGoblin", "Rascals", "MinionHorde",
                "Bats"],
       "weak": ["BarbarianHut", "RoyalRecruits", "ThreeMusketeers", "MovingCannon", "MiniSparkys", "SkeletonKing",
                "SkeletonBalloon", "Goblinstein", "FirespiritHut", "AngryBarbarians", "BabyDragon", "MegaKnight"],
       "other": ["Monk"]}


class TestArchetypes(unittest.TestCase):
    def test_faithful_copy(self):
        path = REPO / "scratchpad" / "gauntlet" / "L74" / "weekend" / "archetypes.py"
        spec = importlib.util.spec_from_file_location("archetypes_weekend", path)
        W = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(W)
        for k in ("BRIDGE", "BAIT", "TANK", "WEAK", "ORDER"):
            self.assertEqual(getattr(AR, k), getattr(W, k), k)
        self.assertEqual({k: v for k, v in AR.ALIAS.items() if k in W.ALIAS}, W.ALIAS)
        self.assertEqual(set(AR.ALIAS) - set(W.ALIAS), {"elitearcher"})
        for names in (["Royal Giant", "Monk"], ["P.E.K.K.A", "Bandit"], ["Golem"], ["Goblin Barrel", "Princess",
                      "Dart Goblin"], ["Baby Dragon"], ["Hog Rider"], []):
            self.assertEqual(AR.classify(names), W.classify(names), names)

    def test_sim_names(self):
        c = (lambda xs: {AR.canon(x) for x in xs})
        self.assertEqual(c(SIM["tank"]), AR.TANK)
        self.assertEqual(c(SIM["bridge"]), AR.BRIDGE)
        self.assertEqual(c(SIM["bait"]), AR.BAIT)
        self.assertEqual(c(SIM["weak"]), AR.WEAK)
        for a, b in (("Pekka", "PEKKA"), ("PEKKA", "P.E.K.K.A"), ("LavaHound", "Lava Hound"), ("Assassin", "Bandit"),
                     ("Ghost", "Royal Ghost"), ("BlowdartGoblin", "Dart Goblin"), ("EliteArcher", "Magic Archer"),
                     ("IceSpirits", "Ice Spirit"), ("Golem@evo", "golem")):
            self.assertEqual(AR.canon(a), AR.canon(b), (a, b))
        for names, want in ((["RoyalGiant", "Monk"], "royal_giant_monk"), (["RoyalGiant"], "royal_giant"),
                            (["LavaHound", "Golem"], "lava_hound"), (["Golem", "Pekka"], "golem"),
                            (["Pekka", "Assassin"], "pekka_bridge"), (["Pekka", "EliteArcher"], "pekka_bridge"),
                            (["Pekka"], "other"), (["GoblinBarrel", "Princess", "BlowdartGoblin"], "hyperbait"),
                            (["GoblinBarrel", "SkeletonArmy", "GoblinGang", "Giant"], "other"),
                            (["BabyDragon", "HogRider"], "weak_other"), (["HogRider", "Knight"], "other")):
            self.assertEqual(AR.classify(names), want, names)
        self.assertEqual(AR.ARCH_IDS, ("none_seen",) + AR.ORDER + ("other",))
        self.assertEqual(len(AR.ARCH_IDS), 9)

    def test_names_exist_in_the_engine(self):
        """The spellings above are the real RoyaleSim catalogue's (skipped where royalegym does not import)."""
        try:
            from pipeline.royale_runtime import activate
            activate()
            from pipeline import royale_heroiw as heroiw
            from royalegym.rust_engine import RustEngine
            names = {c.name for c in RustEngine(**heroiw.engine_options()).cards()}
        except Exception as exc:                                          # noqa: BLE001
            raise unittest.SkipTest(f"royalegym unavailable: {exc!r}")
        missing = [n for v in SIM.values() for n in v if n not in names]
        self.assertEqual(missing, [])


# ------------------------------------------------------------------------------------------------------
class TestRecording(unittest.TestCase):
    """e1_eval's real SelfPlayMatch on test_league's fake env, clock moved to ticks 2200..3800 (decide_every 100) so
    one match crosses both phase edges; the foe board and the crowns change over time."""

    def _run(self, side, **cfg):
        from pipeline import e1_eval as E
        from pipeline.tests import test_league as TL

        class Env(TL._SPEnv):
            def reset(self, *a, **k):
                st = super().reset(*a, **k)
                self.tick, self.tail_cap = 2200, 3800
                return st

            def raw(self):
                st = super().raw()
                t = self.tick
                knight = next(e for e in st["entities"] if e["side"] == 0)
                foe = ([] if t < 2500 else ["HogRider"] if t < 2900 else ["Golem"] if t < 3500 else ["RoyalGiant", "Monk"])
                st["entities"] = [knight] + [dict(knight, side=1, name=n, entity_id=10 + i) for i, n in enumerate(foe)]
                st["crowns"] = [0, 0] if t < 3000 else [1, 0] if t < 3700 else [1, 2]
                return st

        learner, opp = E.GenPolicy(TL._tiny_gen(1), TL.VOCAB), E.GenPolicy(TL._tiny_gen(2), TL.VOCAB)
        jobs = [(0, TL._spec(0, "snapA", side), 0, {"rollout_index": 0, "update": 0})]
        res, _ = TL._run(jobs, learner, {"snapA": (opp, TL._cfg("sample", record=False, decide_every=100))},
                         TL._cfg(decide_every=100, record_tick=True, **cfg), make_env=Env, n=1)
        return res[0]["traj"]

    def test_rows(self):
        for side in (0, 1):
            tj = self._run(side, record_ctx=True)
            ctx, tick = tj["ctx"], tj["tick"]
            self.assertEqual((ctx.dtype, ctx.shape), (np.dtype(np.int64), (len(tick), 5)))
            for row, t in zip(ctx.tolist(), tick.tolist()):
                if side == 0:                                   # foe = side 1: none, Hog, Golem (+Hog), RG + Monk
                    arch = ("none_seen" if t < 2500 else "other" if t < 2900 else "golem" if t < 3500
                            else "royal_giant_monk")
                    tank = int(t >= 2900)
                else:                                           # foe = side 0: the Knight from the start
                    arch, tank = "other", 0
                c = [0, 0] if t < 3000 else [1, 0] if t < 3700 else [1, 2]
                want = [AR.ARCH_IDS.index(arch), tank, 0 if t < 2400 else 1 if t < 3600 else 2, c[side], c[1 - side]]
                self.assertEqual(row, want, (side, t))
            self.assertEqual(set(ctx[:, 2].tolist()), {0, 1, 2})                    # non-vacuous: all phases seen
            if side == 0:
                self.assertEqual(set(ctx[:, 0].tolist()), {AR.ARCH_IDS.index(a) for a in
                                                           ("none_seen", "other", "golem", "royal_giant_monk")})

    def test_absent_is_unchanged(self):
        """Without record_ctx: no ctx key, and every other array is byte-identical (recording does not change play)."""
        on, off = self._run(0, record_ctx=True), self._run(0)
        self.assertNotIn("ctx", off)
        self.assertEqual(sorted(off), sorted(k for k in on if k != "ctx"))
        for k in off:
            self.assertEqual(off[k].tobytes(), on[k].tobytes(), k)


# ------------------------------------------------------------------------------------------------------
class TestCritic(_Tmp):
    @classmethod
    def setUpClass(cls):
        cls.model = _tiny_model(6)
        cls.results = _monitor_fields(_results(cls.model, SPEC, seed=13))
        cls.ctx_results = _with_ctx(cls.results)

    def _B(self):
        Bn, _ = RL.collate(copy.deepcopy(self.ctx_results), 2.0, advantage="gae")
        return Bn, RL.to_device(Bn, "cpu")

    def test_collate(self):
        Bn, _ = self._B()
        B0, _ = RL.collate(copy.deepcopy(self.results), 2.0, advantage="gae")
        self.assertEqual(sorted(Bn), sorted(list(B0) + ["ctx"]))
        for k in B0:
            self.assertEqual(Bn[k].tobytes(), B0[k].tobytes(), k)
        for j, r in enumerate(self.ctx_results):
            t = r["traj"]
            np.testing.assert_array_equal(Bn["ctx"][Bn["match"] == j], t["ctx"][t["gate_sampled"] | t["played"]])

    def test_zero_init_is_the_plain_critic(self):
        _, B = self._B()
        idx = torch.arange(len(B["A"]))
        for mode in ("arch", "full"):
            head = RL.CtxHead(mode, self.model.value_head.in_features)
            self.assertEqual(head.net[0].in_features, 16 + (10 if mode == "arch" else 21))
            self.assertTrue(torch.equal(RL.value_rows(self.model, B), RL.value_rows(self.model, B, ctx_head=head)))
            with torch.no_grad():
                a = RL.policy_terms(self.model, B, idx, TAU, T, value=True)["v"]
                b = RL.policy_terms(self.model, B, idx, TAU, T, value=True, ctx_head=head)["v"]
            self.assertTrue(torch.equal(a, b))
            Ba, Bb = dict(B), dict(B)
            sa = RL.gae_batch(self.model, Ba, {"advantage": "gae"})
            sb = RL.gae_batch(self.model, Bb, {"advantage": "gae"}, ctx_head=head)
            self.assertEqual(sa, {k: v for k, v in sb.items() if k != "ctx_tank"})
            for k in ("A", "ret", "v_old"):
                self.assertTrue(torch.equal(Ba[k], Bb[k]), k)
            ct = sb["ctx_tank"]
            self.assertEqual(ct["tank"]["rows"], int(sum((B["match"] == j).sum() for j in (0, 2))))
            self.assertEqual(ct["tank"]["rows"] + ct["no_tank"]["rows"], len(B["A"]))
            sel = np.isin(B["match"].numpy(), [0, 2])
            v, ret = Bb["v_old"].numpy(), Bb["ret"].numpy()
            self.assertAlmostEqual(ct["tank"]["value_loss"], float((0.5 * (v[sel] - ret[sel]) ** 2).mean()), places=12)
            self.assertAlmostEqual(ct["no_tank"]["explained_var"], RL.explained_variance(v[~sel], ret[~sel]), places=12)

    def test_value_loss_reaches_value_head_and_ctx_head_only(self):
        """vf_trunk_grad false: the value loss's gradient on every non-value_head model parameter is exactly the policy
        loss's (the critic adds nothing there), and the CtxHead gets a gradient (last layer first, it starts at 0)."""
        _, B = self._B()
        RL.gae_batch(self.model, B, {"advantage": "gae"})
        R = RL.ref_terms(copy.deepcopy(self.model).eval(), B, TAU, T)
        N = len(B["A"])
        kw = dict(tau=TAU, T=T, clip=0.2, beta=0.3, n_total=N)
        model = copy.deepcopy(self.model)
        head = RL.CtxHead("full", model.value_head.in_features)
        grads = {}
        for name, vf in (("pol", None), ("both", {"coef": 0.5, "clip": 0.2, "policy": True, "trunk_grad": False,
                                                  "ctx_head": head})):
            model.zero_grad(set_to_none=True)
            head.zero_grad(set_to_none=True)
            loss, _ = RL.minibatch_loss(model, B, R, torch.arange(N), vf=vf, **kw)
            loss.backward()
            grads[name] = {n: None if p.grad is None else p.grad.clone() for n, p in model.named_parameters()}
        for n, g in grads["pol"].items():
            if not n.startswith("value_head."):
                o = grads["both"][n]
                self.assertTrue((g is None and (o is None or not o.any())) or torch.equal(g, o), n)
        self.assertIsNotNone(head.net[2].weight.grad)
        self.assertTrue(head.net[2].weight.grad.abs().sum() > 0)

    def test_steps_move_ctx_head_not_policy(self):
        """Warm-up (policy frozen): a few optimizer steps move value_head and every CtxHead tensor, nothing else."""
        L = _learner(RL, self.model, self.ctx_results, self.tmp, critic_ctx="full", vf_trunk_grad=False,
                     **{**GAE, "critic_warmup_updates": 2})
        L._ctx_setup()
        h0 = {n: p.detach().clone() for n, p in L.ctx_head.named_parameters()}
        m0 = {n: p.detach().clone() for n, p in L.model.named_parameters()}
        for u in range(2):
            rec, _, crash = L.one_update(u)
            self.assertFalse(crash)
            self.assertTrue(rec["gae"]["critic_warmup"])
        moved = [n for n, p in L.ctx_head.named_parameters() if not torch.equal(p, h0[n])]
        self.assertEqual(sorted(moved), sorted(h0))
        mm = [n for n, p in L.model.named_parameters() if not torch.equal(p, m0[n])]
        self.assertTrue(mm)
        self.assertTrue(all(n.startswith("value_head.") for n in mm), mm)
        self.assertFalse(any(k.startswith("ctx") for k in L.model.state_dict()))

    def test_one_update_end_to_end(self):
        for mode in ("arch", "full"):
            L = _learner(RL, self.model, self.ctx_results, self.tmp / mode, critic_ctx=mode, **GAE)
            L._ctx_setup()
            for u in range(3):                                 # warm-up, then two policy updates
                rec, _, crash = L.one_update(u)
                self.assertFalse(crash)
                self.assertEqual(rec["gae"]["critic_ctx"], mode)
                ct = rec["gae"]["ctx_tank"]
                self.assertEqual(ct["tank"]["rows"] + ct["no_tank"]["rows"], rec["rows"])
                self.assertIsNotNone(ct["tank"]["value_loss"])
                self.assertTrue(np.isfinite(rec["gae"]["l_v"]))
            self.assertFalse(rec["gae"]["critic_warmup"])

    def test_checkpoint_resume(self):
        L = _learner(RL, self.model, self.ctx_results, self.tmp / "a", critic_ctx="arch", **GAE)
        L._ctx_setup()
        for u in range(2):
            L.one_update(u)
        ck = torch.load(L.ck_dir / "unit_latest.pt", map_location="cpu", weights_only=True)
        self.assertIn("ctx_head", ck["rl"])
        self.assertIn("ctx_optimizer", ck["rl"])
        self.assertFalse(any("ctx" in k for k in ck["model"]))              # the model's state_dict is untouched
        L2 = _learner(RL, _tiny_model(9), self.ctx_results, self.tmp / "b", critic_ctx="arch", **GAE)
        L2._ctx_setup()
        L2.ref = copy.deepcopy(L.ref)
        L2._restore(L.ck_dir / "unit_latest.pt")
        for (n, a), b in zip(L.ctx_head.state_dict().items(), L2.ctx_head.state_dict().values()):
            self.assertTrue(torch.equal(a, b), n)
        s1, s2 = L.ctx_opt.state_dict()["state"], L2.ctx_opt.state_dict()["state"]
        self.assertEqual(sorted(s1), sorted(s2))
        for k in s1:
            self.assertTrue(torch.equal(s1[k]["exp_avg"], s2[k]["exp_avg"]))
        # the next update from the restored learner = the original's (same weights, Adam, rng)
        ra, _, _ = L.one_update(2)
        rb, _, _ = L2.one_update(2)
        self.assertEqual(_strip(ra), _strip(rb))
        # a checkpoint WITHOUT critic_ctx resumed into a critic_ctx learner: the head stays at its zero start
        L3 = _learner(RL, self.model, self.results, self.tmp / "c", **GAE)
        L3.one_update(0)
        L4 = _learner(RL, self.model, self.ctx_results, self.tmp / "d", critic_ctx="arch", **GAE)
        L4._ctx_setup()
        z = {n: p.detach().clone() for n, p in L4.ctx_head.named_parameters()}
        L4._restore(L3.ck_dir / "unit_latest.pt")
        self.assertTrue(all(torch.equal(p, z[n]) for n, p in L4.ctx_head.named_parameters()))
        self.assertTrue(any("no ctx_head" in m for m in L4.log.lines))


# ------------------------------------------------------------------------------------------------------
class TestAbsentIsPre(_Tmp):
    """critic_ctx absent or null: collate, whole gae updates (records, weights, beta, rng) and the checkpoint's rl
    keys are those of the commit before the change; ctx rows in the results are ignored without the key."""

    @classmethod
    def setUpClass(cls):
        cls.P = _pre_module()
        cls.model = _tiny_model(6)
        cls.results = _monitor_fields(_results(cls.model, SPEC, seed=13))

    def test_updates_identical(self):
        self.P.CKPT_ROOT = self.tmp
        runs = {}
        for name, mod, extra in (("pre", self.P, {}), ("absent", RL, {}), ("null", RL, {"critic_ctx": None})):
            L = _learner(mod, self.model, self.results, self.tmp / name, **GAE, **extra)
            recs = [_strip(L.one_update(u)[0]) for u in range(3)]
            ck = torch.load(L.ck_dir / "unit_latest.pt", map_location="cpu", weights_only=True)
            runs[name] = (recs, L.beta, {k: v.clone() for k, v in L.model.state_dict().items()},
                          L.rng.bit_generator.state, sorted(ck["rl"]), ck["rl"]["config_sha256"])
            self.assertIsNone(getattr(L, "ctx_head", None))
        recs_p, beta_p, sd_p, rng_p, keys_p, sha_p = runs["pre"]
        for name in ("absent", "null"):
            recs, beta, sd, rng, keys, sha = runs[name]
            self.assertEqual(recs, recs_p, name)
            self.assertEqual((beta, rng, keys, sha), (beta_p, rng_p, keys_p, sha_p), name)
            for k in sd_p:
                self.assertTrue(torch.equal(sd[k], sd_p[k]), (name, k))
        self.assertFalse(any("ctx" in r for r in runs["absent"][0]))

    def test_collate_identical(self):
        for adv in ("match_loo", "gae"):
            Bp, sp = self.P.collate(copy.deepcopy(self.results), 2.0, advantage=adv)
            Bn, sn = RL.collate(copy.deepcopy(self.results), 2.0, advantage=adv)
            self.assertEqual(sorted(Bn), sorted(Bp))
            for k in Bp:
                self.assertEqual(Bn[k].tobytes(), Bp[k].tobytes(), k)
            self.assertEqual(sn, sp)


if __name__ == "__main__":
    unittest.main()
