"""LEARNER-SPEED ticket B first cut (pipeline/learner_graph.py ``trunk_graph``): the trunk forward + backward replayed as
CUDA graphs = the eager trunk. CUDA only (skipped without a GPU); the learner's settings (deterministic, TF32 off).

    PY -m unittest pipeline.tests.test_learner_graph -v

Tiny GenModel with both refine modules (test_lazy_refine's fixture, lazy_refine on as in the pilot), real-sampler rows:
1. minibatch_loss + backward on one graphed minibatch: loss, monitors and gradients vs eager (prints the bitwise status and
   the worst relative gradient difference; asserts <= 1e-6 relative per tensor, the summation-order bound);
2. ppo_update with kl_stop_prev (Adam, an N that leaves an eager tail minibatch): the same stop (epoch, minibatch, steps);
3. the overlap stack: ppo_decoupled on stale rows + micro_batch + split_attn + trunk_graph = the plain eager learner;
4. the critic warm-up (trunk frozen) and no-grad forwards run eager; validation + hash.
"""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

from pipeline import e1_eval as E
from pipeline import rl_royale as RL
from pipeline.tests.test_e1_eval_gen import VOCAB
from pipeline.tests.test_lazy_refine import _frozen, _refine_model
from pipeline.tests.test_rl_gen import TAU, T, _batch, _rollouts

REPO = Path(__file__).resolve().parents[2]


def _cuda(x):
    return {k: (v.cuda() if torch.is_tensor(v) else v) for k, v in x.items()}


@unittest.skipUnless(torch.cuda.is_available(), "no CUDA")
class TestTrunkGraph(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = (torch.are_deterministic_algorithms_enabled(), torch.backends.cuda.matmul.allow_tf32,
                   torch.backends.cudnn.allow_tf32)
        torch.use_deterministic_algorithms(True)
        torch.backends.cuda.matmul.allow_tf32 = torch.backends.cudnn.allow_tf32 = False
        m = _refine_model()
        B, _ = _batch(_rollouts(E.GenPolicy(m, VOCAB), n_matches=8))
        cls.model = m.cuda()
        cls.model.lazy_refine = True
        cls.B = _cuda(B)
        cls.N = len(cls.B["A"])
        g = torch.Generator().manual_seed(5)                  # value targets (test_learner_fast_accum's recipe)
        cls.B["v_old"] = (torch.randn(cls.N, generator=g, dtype=torch.float64) * 0.1).cuda()
        cls.B["ret"] = (torch.randn(cls.N, generator=g, dtype=torch.float64) * 0.5).cuda()
        cls.mb = 32 if cls.N % 32 else 30                     # an N that leaves an eager tail minibatch
        cls.R = RL.ref_terms(_frozen(cls.model), cls.B, TAU, T)

    @classmethod
    def tearDownClass(cls):
        torch.use_deterministic_algorithms(cls.old[0])
        torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32 = cls.old[1], cls.old[2]

    def _copy(self, graph):
        m = copy.deepcopy(self.model)
        if graph:
            m.trunk_graph = self.mb
        return m

    def _loss_grads(self, m, idx):
        m.zero_grad(set_to_none=True)
        loss, st = RL.minibatch_loss(m, self.B, self.R, idx, tau=TAU, T=T, clip=0.2, beta=0.3, n_total=self.N,
                                     vf={"coef": 0.5, "clip": 0.2, "policy": True, "trunk_grad": True})
        loss.backward()
        return loss.detach(), st, {n: p.grad.detach().clone() for n, p in m.named_parameters() if p.grad is not None}

    def test_one_minibatch(self):
        idx = torch.randperm(self.N, generator=torch.Generator().manual_seed(1))[:self.mb].cuda()
        e_loss, e_st, e_g = self._loss_grads(self._copy(False), idx)
        m = self._copy(True)
        for _ in range(2):                                    # capture, then a replay
            g_loss, g_st, g_g = self._loss_grads(m, idx)
        from pipeline.learner_graph import _CACHE
        self.assertEqual(len(_CACHE.get(m, {})), 1)           # the graph path really ran
        self.assertEqual(set(e_g), set(g_g))
        rel = {n: float((e_g[n] - g_g[n]).norm() / e_g[n].norm().clamp(min=1e-30)) for n in e_g}
        worst = max(rel, key=rel.get)
        print(f"\n[graph] loss bitwise {torch.equal(e_loss, g_loss)}; grads bitwise "
              f"{sum(torch.equal(e_g[n], g_g[n]) for n in e_g)}/{len(e_g)}; worst rel {rel[worst]:.2e} ({worst})")
        self.assertLessEqual(rel[worst], 1e-6)
        self.assertLessEqual(float((e_loss - g_loss).abs() / e_loss.abs().clamp(min=1e-30)), 1e-6)
        for k in ("kl_gate", "kl_card", "kl_cell", "ratio_maxdev", "l_v"):
            self.assertAlmostEqual(e_st[k], g_st[k], delta=1e-6 * max(1.0, abs(e_st[k])), msg=k)

    def test_kl_stop_same_step(self):
        cfg = {"minibatch": self.mb, "ppo_epochs": 3, "tau": TAU, "T": T, "clip": 0.2, "grad_clip": 0.5}
        vf = {"coef": 0.5, "clip": 0.2, "policy": True, "trunk_grad": True}

        def run(graph, extra):
            m = self._copy(graph)
            opt = torch.optim.Adam(m.parameters(), lr=3e-3)
            return RL.ppo_update(m, opt, self.B, self.R, {**cfg, **extra}, 0.0, np.random.default_rng(0), vf=vf), m
        free, _ = run(False, {})
        steps = []
        for f in (0.5, 1.0, 2.0, 4.0):                        # stops early and late (graph replays + the eager tail)
            lim = f * (free["kl_gate"] + free["kl_card"] + free["kl_cell"])
            e, me = run(False, {"kl_stop_prev": lim})
            g, mg = run(True, {"kl_stop_prev": lim})
            self.assertEqual(g["kl_stop"] is None, e["kl_stop"] is None)
            self.assertEqual(g["steps"], e["steps"])
            if e["kl_stop"] is not None:
                self.assertEqual((g["kl_stop"]["epoch"], g["kl_stop"]["minibatch"]), (e["kl_stop"]["epoch"], e["kl_stop"]["minibatch"]))
                self.assertAlmostEqual(g["kl_stop"]["kl"], e["kl_stop"]["kl"], delta=1e-6)
            dw = max(float((a - b).abs().max()) for a, b in zip(me.parameters(), mg.parameters()))
            print(f"\n[graph] limit {lim:.4f}: kl_stop {e['kl_stop']} steps {e['steps']}; weights max |diff| {dw:.2e}")
            steps.append(e["steps"])
        self.assertGreaterEqual(max(steps), 2 * (self.N // self.mb))   # some run crossed an epoch boundary

    def test_composes_with_decoupled_micro_and_split_attn(self):
        """The overlap stack (lead 10-30): ppo_decoupled 2.0 on one-version-stale rows + micro_batch (graph rows = the
        micro-batch) + split_attn + trunk_graph vs the plain eager learner: same steps / stop, same first monitors."""
        from pipeline.learner_attn import use_split_attn
        g = torch.Generator().manual_seed(7)
        lpp = RL.prox_lp(self.R, self.B, torch.arange(self.N, device="cuda"))
        Bst = {**self.B, "lp_old": lpp + (torch.randn(self.N, generator=g, dtype=torch.float64) * 0.6).cuda()}
        vf = {"coef": 0.5, "clip": 0.2, "policy": True, "trunk_grad": True}
        cfg = {"minibatch": 2 * self.mb, "micro_batch": self.mb, "ppo_epochs": 3, "tau": TAU, "T": T, "clip": 0.2,
               "grad_clip": 0.5, "ppo_decoupled": 2.0}

        def run(fast, extra):
            m = self._copy(fast)
            if fast:
                use_split_attn(m)
            opt = torch.optim.Adam(m.parameters(), lr=3e-4)
            return RL.ppo_update(m, opt, Bst, self.R, {**cfg, **extra}, 0.0, np.random.default_rng(0), vf=vf), m
        grads = []                                            # one accumulated minibatch: every gradient
        idx = torch.randperm(self.N, generator=torch.Generator().manual_seed(2))[:2 * self.mb].cuda()
        for fast in (False, True):
            m = self._copy(fast)
            if fast:
                use_split_attn(m)
            for _ in range(2):                                # graph: capture, then a replay
                m.zero_grad(set_to_none=True)
                RL.accum_backward(m, Bst, self.R, idx, self.mb, self.N, dict(tau=TAU, T=T, clip=0.2, beta=0.0, vf=vf,
                                                                             decoupled=2.0))
            grads.append({n: p.grad.clone() for n, p in m.named_parameters() if p.grad is not None})
        rel = max(float((grads[0][n] - grads[1][n]).norm() / grads[0][n].norm().clamp(min=1e-30)) for n in grads[0])
        self.assertEqual(set(grads[0]), set(grads[1]))
        self.assertLessEqual(rel, 1e-6)
        free, _ = run(False, {})
        self.assertGreater(free["first"]["is_maxdev"], 0.1)  # the rows really are stale
        for f in (0.5, 2.0):
            lim = f * (free["kl_gate"] + free["kl_card"] + free["kl_cell"])
            if f > 1 and free["steps"] <= 1:
                continue
            e, me = run(False, {"kl_stop_prev": lim})
            z, mz = run(True, {"kl_stop_prev": lim})
            self.assertEqual((z["steps"], z["kl_stop"] and (z["kl_stop"]["epoch"], z["kl_stop"]["minibatch"])),
                             (e["steps"], e["kl_stop"] and (e["kl_stop"]["epoch"], e["kl_stop"]["minibatch"])))
            for k in ("l_pg", "kl_gate", "kl_card", "kl_cell", "is_maxdev", "is_trunc_frac", "ratio_maxdev", "l_v"):
                self.assertAlmostEqual(z["first"][k], e["first"][k], delta=1e-6 * max(1.0, abs(e["first"][k])), msg=k)
            from pipeline.learner_graph import _CACHE
            self.assertEqual(len(_CACHE.get(mz, {})), 1)      # the micro-batches ran through the graph
            dw = max(float((a - b).abs().max()) for a, b in zip(me.parameters(), mz.parameters()))
            print(f"\n[graph] decoupled + micro + split_attn + graph: worst grad rel {rel:.2e}; limit {lim:.4f}: steps {e['steps']} stop "
                  f"{e['kl_stop']}; first is_maxdev {e['first']['is_maxdev']:.3f}; weights max |diff| {dw:.2e}")

    def test_warmup_and_no_grad_run_eager(self):
        from pipeline.learner_graph import _CACHE
        m = self._copy(True)
        idx = torch.arange(self.mb).cuda()
        with torch.no_grad():
            RL.policy_terms(m, self.B, idx, TAU, T)
        for n, p in m.named_parameters():                     # the critic warm-up's freeze
            p.requires_grad_(n.startswith("value_head."))
        RL.policy_terms(m, self.B, idx, TAU, T, value=True)["v"].sum().backward()
        self.assertEqual(len(_CACHE.get(m, {})), 0)

    def test_config_validation_and_hash(self):
        import yaml
        cfg = yaml.safe_load((REPO / "pipeline" / "rl_royale.yaml").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as d:
            def load(**kv):
                p = Path(d) / "c.yaml"
                p.write_text(yaml.safe_dump({**cfg, **kv}), encoding="utf-8")
                return RL.load_config(p, [], smoke=False)
            self.assertEqual(RL.config_sha(load()), RL.config_sha(load(trunk_graph=None)))
            self.assertNotEqual(RL.config_sha(load()), RL.config_sha(load(trunk_graph=256)))
            for bad in (0, -1, 1.5, True, "256"):
                with self.assertRaises(SystemExit, msg=str(bad)):
                    load(trunk_graph=bad)


if __name__ == "__main__":
    unittest.main()
