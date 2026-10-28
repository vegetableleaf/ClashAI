"""LOOP-LRN ``ent_pair_every`` k (rl_royale): the entropy floor's ref_init baseline is computed on exactly the rows of every
k-th epoch-0 minibatch that steps (minibatch_loss ``ent_ref`` -> st ``ent0_*``), and the guard compares it with the
policy's entropy on those same minibatches (``ent_pair``). Off (absent / null) = the loop and the record unchanged.

    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_ent_pair.py

Real minibatch_loss / ppo_update on test_rl_royale's tiny S1Model rows, and one Learner.one_update on test_rl_gen's
generalist rows (no engine, no GPU).
"""
from __future__ import annotations

import copy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import torch                                                    # noqa: E402

from pipeline import rl_royale as RL                            # noqa: E402
from pipeline.tests.test_rl_royale import TAU, T, _results, _tiny_model   # noqa: E402

BASE = {"minibatch": 16, "ppo_epochs": 2, "tau": TAU, "T": T, "clip": 0.2, "grad_clip": 0.5}
HEADS = ("gate", "card", "cell")


def _frozen(m):
    r = copy.deepcopy(m).eval()
    for p in r.parameters():
        p.requires_grad_(False)
    return r


def _ent(model, B, idx):
    """The init's per-head entropy on rows idx with the policy monitor's masks (minibatch_loss), computed directly."""
    with torch.no_grad():
        t = RL.policy_terms(model, B, idx, TAU, T)
    gs, pl, cl = B["gate_sampled"][idx], B["played"][idx], t["cell_lp"]
    if "cf" in B:
        real = ~B["cf"][idx]
        cl = cl[real[pl]]
        gs, pl = gs & real, pl & real
    return {"gate": float(RL.bern_ent(t["x"][gs]).mean()), "card": float(RL.cat_ent(t["card_lp"][pl]).mean()),
            "cell": float(RL.cat_ent(cl).mean())}


class TestEntPair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.init = _tiny_model(1)
        res = _results(cls.init, [(0, 0, 40, "win"), (0, 1, 35, "loss"), (1, 0, 30, "draw"), (1, 1, 25, "win")], seed=3)
        Bn, _ = RL.collate(res)
        cls.B = RL.to_device(Bn, "cpu")
        cls.ref_init = _frozen(cls.init)
        cls.R = RL.ref_terms(cls.ref_init, cls.B, TAU, T)

    def run_update(self, cfg, B=None, ent_ref=True):
        """-> (summary, params bytes, [(epoch, minibatch, idx, st)] of every minibatch_loss call in order)."""
        B = self.B if B is None else B
        model = copy.deepcopy(self.init)
        opt = torch.optim.Adam(model.parameters(), lr=1e-2)
        calls, real = [], RL.minibatch_loss
        mb = int(cfg["minibatch"])
        n_mb = -(-len(B["A"]) // mb)

        def spy(m, B_, R_, idx, **k):
            loss, st = real(m, B_, R_, idx, **k)
            i = len(calls)
            calls.append((i // n_mb, i % n_mb, idx.clone(), st))
            return loss, st
        RL.minibatch_loss = spy
        try:
            out = RL.ppo_update(model, opt, B, self.R, cfg, 0.0, np.random.default_rng(0),
                                **({"ent_ref": self.ref_init} if ent_ref else {}))
        finally:
            RL.minibatch_loss = real
        return out, b"".join(p.detach().numpy().tobytes() for p in model.parameters()), calls

    def check_paired(self, out, calls, k, stepped):
        paired = [c for c in calls[:stepped] if c[0] == 0 and c[1] % k == 0]
        self.assertTrue(paired)
        for ep, j, idx, st in calls:                          # ent0 exactly on the k-th epoch-0 minibatches
            self.assertEqual("ent0_gate" in st, ep == 0 and j % k == 0, (ep, j))
        for h in HEADS:
            self.assertAlmostEqual(out["ent_pair"][h], float(np.mean([c[3][f"ent_{h}"] for c in paired])), places=12)
            self.assertAlmostEqual(out["ent_pair_init"][h], float(np.mean([c[3][f"ent0_{h}"] for c in paired])),
                                   places=12)
        self.assertEqual(out["ent_pair_rows"], sum(len(c[2]) for c in paired))
        return paired

    def test_off_is_unchanged_and_on_does_not_move_the_steps(self):
        off, p_off, c_off = self.run_update(dict(BASE), ent_ref=False)
        self.assertNotIn("ent_pair", off)
        self.assertTrue(all("ent0_gate" not in c[3] for c in c_off))
        null, p_null, _ = self.run_update({**BASE, "ent_pair_every": None})   # ent_ref given, key null: off
        self.assertNotIn("ent_pair", null)
        self.assertEqual(p_off, p_null)
        for k in (1, 2, 4):
            out, p, calls = self.run_update({**BASE, "ent_pair_every": k})
            self.assertEqual(p, p_off, k)                     # no_grad, no RNG: the same steps, bit for bit
            self.assertEqual({h: out["ent"][h] for h in HEADS}, {h: off["ent"][h] for h in HEADS})
            paired = self.check_paired(out, calls, k, len(calls))
            for ep, j, idx, st in paired:
                want = _ent(self.ref_init, self.B, idx)
                for h in HEADS:
                    self.assertAlmostEqual(st[f"ent0_{h}"], want[h], places=12)
            if k == 1:                                        # every epoch-0 minibatch: the policy side IS upd["ent"]
                self.assertEqual(out["ent_pair"], out["ent"])
        st0 = calls[0][3]                                     # minibatch 0: the policy is still the init (its grad-mode
        for h in HEADS:                                       # forward vs the frozen no-grad one: ~1e-8 float noise)
            self.assertAlmostEqual(st0[f"ent_{h}"], st0[f"ent0_{h}"], places=6)

    def test_kl_stopped_minibatch_is_not_paired(self):
        _, _, c_off = self.run_update(dict(BASE), ent_ref=False)
        kls = [c[3]["kl_gate"] + c[3]["kl_card"] + c[3]["kl_cell"] for c in c_off]
        n_mb = -(-len(self.B["A"]) // BASE["minibatch"])
        stop_at = 2                                           # a minibatch of epoch 0 with j % 2 == 0
        lim = 0.5 * (kls[stop_at] + max(kls[:stop_at]))
        self.assertTrue(kls[stop_at] > lim > max(kls[:stop_at]) and stop_at < n_mb)
        out, _, calls = self.run_update({**BASE, "ent_pair_every": 2, "kl_stop_prev": lim})
        self.assertEqual(out["kl_stop"]["minibatch"], stop_at)
        self.assertIn("ent0_gate", calls[stop_at][3])       # computed for the over-limit minibatch ...
        paired = self.check_paired(out, calls, 2, stop_at)   # ... but only the stepped ones are averaged
        self.assertEqual([c[1] for c in paired], [0])

    def test_cf_rows_use_the_real_rows_masks(self):
        B = dict(self.B)
        B["cf"] = torch.from_numpy(np.random.default_rng(4).random(len(B["A"])) < 0.3)
        out, _, calls = self.run_update({**BASE, "ent_pair_every": 3}, B=B)
        for ep, j, idx, st in calls:
            if "ent0_gate" in st:
                want = _ent(self.ref_init, B, idx)
                for h in HEADS:
                    self.assertAlmostEqual(st[f"ent0_{h}"], want[h], places=12)

    def test_config_validation_and_hash(self):
        import yaml
        cfg = yaml.safe_load((REPO / "pipeline" / "rl_royale.yaml").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as d:
            def load(**kv):
                p = Path(d) / "c.yaml"
                p.write_text(yaml.safe_dump({**cfg, **kv}), encoding="utf-8")
                return RL.load_config(p, [], smoke=False)
            base = RL.config_sha(load())
            self.assertEqual(base, RL.config_sha(load(ent_pair_every=None)))   # absent == null: the historical hash
            self.assertNotEqual(base, RL.config_sha(load(ent_pair_every=4)))
            self.assertNotEqual(RL.config_sha(load(ent_pair_every=4)), RL.config_sha(load(ent_pair_every=2)))
            for bad in ({"ent_pair_every": 0}, {"ent_pair_every": True}, {"ent_pair_every": 2.0},
                        {"ent_pair_every": "4"}, {"ent_pair_every": 4, "ent_init_rows": 20000}):
                with self.assertRaises(SystemExit, msg=str(bad)):
                    load(**bad)


class TestEntPairLearner(unittest.TestCase):
    """Learner.one_update with ent_pair_every: no ref_init pass, the guard gets the PAIRED entropies, the record has them."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rl_ent_pair_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        orig = RL.CKPT_ROOT
        RL.CKPT_ROOT = self.tmp / "ck"
        self.addCleanup(setattr, RL, "CKPT_ROOT", orig)

    def test_one_update_guard_is_paired(self):
        from pipeline import e1_eval as E
        from pipeline.tests.test_e1_eval_gen import VOCAB, _tiny_gen
        from pipeline.tests.test_rl_gen import TestGenLearner, _rollouts, _wide_cells
        model = _wide_cells(_tiny_gen(6))
        res = _rollouts(E.GenPolicy(model, VOCAB), n_matches=6)
        recs = {}
        for pe in (None, 2):
            helper = TestGenLearner()
            helper.tmp = self.tmp / f"pe{pe}"
            RL.CKPT_ROOT = helper.tmp / "ck"                  # (setUp restores it)
            L = helper._learner(copy.deepcopy(model))
            L.cfg = {**L.cfg, "minibatch": 8, **({"ent_pair_every": pe} if pe else {})}
            L.ref_init = _frozen(model)                       # a moved anchor (W16): ref is not ref_init
            L.rollout = lambda u: (list(res), {"picked": [0, 1, 2], "actors": {}, "skipped": 0})
            seen, real_after, real_rt = {}, L.guards.after_update, RL.ref_terms
            n_rt = []

            def after(*a, ent=None, ent_init=None, **k):
                seen.update(ent=ent, ent_init=ent_init)
                return real_after(*a, ent=ent, ent_init=ent_init, **k)
            L.guards.after_update = after

            def rt(*a, **k):
                n_rt.append(1)
                return real_rt(*a, **k)
            RL.ref_terms = rt
            try:
                rec, reasons, crash = L.one_update(0)
            finally:
                RL.ref_terms = real_rt
            self.assertFalse(crash)
            self.assertEqual(len(n_rt), 2 if pe is None else 1)   # paired: no separate ref_init pass
            recs[pe] = rec
            if pe:
                self.assertEqual(seen["ent"], rec["entropy_pair"])
                self.assertEqual(seen["ent_init"], rec["entropy_init"])
                self.assertGreater(rec["ent_pair_rows"], 0)
                self.assertNotEqual(rec["entropy_pair"], rec["entropy"])   # a subset of the epoch-0 minibatches
            else:
                self.assertNotIn("entropy_pair", rec)
                self.assertEqual(seen["ent"], rec["entropy"])
        for h in HEADS:
            self.assertGreater(recs[2]["entropy_init"][h], 0.0, h)


if __name__ == "__main__":
    unittest.main()
