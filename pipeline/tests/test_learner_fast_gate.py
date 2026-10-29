"""LEARNER-SCALE ``gate_baseline`` (rl_royale.gate_baseline_fit + minibatch_loss(gate_bl=)): the joint L_pg's A on
gate-sampled rows becomes A - b(s), b a ridge regression of A on the trunk output [g, 1] cross-fitted by match halves.
Absent / null = byte-identical and the historical config hash; the baseline leaves the policy gradient's expectation
unchanged (Monte Carlo over trajectories sampled from the tiny model's own policy) and the planted in-sample variant
(each half fitted on its own rows, so a row's own A enters its baseline) is detected as biased by the same test.

    icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_learner_fast_gate -v
"""
from __future__ import annotations

import copy
import os
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
from pipeline.tests import test_learner_fast_accum as ACC       # noqa: E402
from pipeline.tests.test_rl_royale import TAU, T               # noqa: E402

BASE, VF = ACC.BASE, ACC.VF
GB = {"weight": "score", "ridge": 0.0}
DRAWS = int(os.environ.get("GATE_MC_DRAWS", "300"))


class TestGateBaseline(unittest.TestCase):
    setUpClass = classmethod(ACC.TestMicroBatch.setUpClass.__func__)
    pbytes = staticmethod(ACC.TestMicroBatch.pbytes)

    def run_update(self, cfg, vf=None):
        model = copy.deepcopy(self.model)
        opt = torch.optim.Adam(model.parameters(), lr=1e-2)
        out = RL.ppo_update(model, opt, self.B, self.R, cfg, 0.0, np.random.default_rng(0), vf=vf)
        return out, model

    def test_off_is_byte_identical(self):
        for vf in (None, VF):
            off, m_off = self.run_update(dict(BASE), vf)
            on, m_on = self.run_update({**BASE, "gate_baseline": None}, vf)
            self.assertEqual(self.pbytes(m_off), self.pbytes(m_on))
            self.assertEqual(off, on)

    def test_on_runs_warmup_untouched(self):
        for gb in (GB, {"weight": "plain", "fit_rows": 20}):
            on, m_on = self.run_update({**BASE, "gate_baseline": gb}, VF)
            off, m_off = self.run_update(dict(BASE), VF)
            self.assertNotEqual(self.pbytes(m_off), self.pbytes(m_on))
            self.assertEqual(len(on["gate_baseline"]["fit_rows"]), 2)
            if gb.get("fit_rows"):
                self.assertTrue(all(n <= 20 for n in on["gate_baseline"]["fit_rows"]))
        warm = {**VF, "policy": False}                        # critic warm-up: no fit, no change
        off, m_off = self.run_update(dict(BASE), warm)
        on, m_on = self.run_update({**BASE, "gate_baseline": GB}, warm)
        self.assertEqual(self.pbytes(m_off), self.pbytes(m_on))
        self.assertNotIn("gate_baseline", on)

    def test_unbiased_monte_carlo(self):
        """Fixed states (the tiny batch's gate-sampled rows, both match halves), fixed weights. Each draw samples a fresh
        joint action (gate, then card and cell if played) from the model's own policy, A = c(s) + played + noise with
        c(s) linear in g, refits the baseline on that draw (gate_baseline_fit), and takes the L_pg gradient at ratio 1
        with the baseline off / on (cross-fit) / in-sample (W flipped: each half's own fit). The per-draw gradients use
        one forward (-sum w A_eff lp); on the first draw they are checked against minibatch_loss(gate_bl=) itself.
        Paired differences on - off and in - off, projected on the mean gradient and 8 random directions:
        on |z| < 4.5 (unbiased), in-sample max |z| > 6 (the test detects a baseline that sees the row's own A)."""
        torch.manual_seed(0)
        model = self.model
        keep = self.B["gate_sampled"]
        B0 = {k: v[keep] for k, v in self.B.items()}
        N = len(B0["A"])
        self.assertGreater(int((B0["match"] % 2 == 0).sum()), 20)
        self.assertGreater(int((B0["match"] % 2 == 1).sum()), 20)
        allr = torch.arange(N)
        with torch.no_grad():
            t0 = RL.policy_terms(model, B0, allr, TAU, T)
            p_play = torch.sigmoid(t0["x"])
            card_lp = t0["card_lp"]
            cell_lp = torch.stack([RL.policy_terms(model, {**B0, "played": torch.ones(N, dtype=torch.bool),
                                                          "slot": torch.full((N,), s, dtype=torch.long),
                                                          "cell": torch.zeros(N, dtype=torch.long)},
                                                   allr, TAU, T)["cell_lp"] for s in range(card_lp.shape[1])], 1)
            u = torch.randn(t0["g"].shape[1], dtype=torch.float64)
            c = t0["g"].double() @ u
            c = 2.0 * (c - c.mean()) / c.std()
        ref = copy.deepcopy(model).eval()
        for q in ref.parameters():
            q.requires_grad_(False)
        params = list(model.parameters())
        cfg = {"tau": TAU, "T": T, "gate_baseline": GB}
        kw = dict(tau=TAU, T=T, clip=0.2, beta=0.0, n_total=N, T_gate=None)
        rng = np.random.default_rng(0)

        flat = (lambda gs: torch.cat([(g if g is not None else torch.zeros_like(q)).reshape(-1).double()
                                      for g, q in zip(gs, params)]))

        def grad_mb(Bd, R, gbl):                              # the real path (first draw only)
            loss, st = RL.minibatch_loss(model, Bd, R, allr, gate_bl=gbl, **kw)
            self.assertLess(st["ratio_maxdev"], 1e-4)          # fp32 forward noise
            return flat(torch.autograd.grad(loss, params, allow_unused=True))

        def grads(Bd, Ws):                                    # = minibatch_loss's L_pg gradient at ratio 1, one forward
            t = RL.policy_terms(model, Bd, allr, TAU, T)
            lp = t["lp_gate"] + t["lp_card"] + t["lp_cell"]
            xg = torch.cat([t["g"].detach().double(), torch.ones(N, 1, dtype=torch.float64)], 1)
            out = []
            for k, W in enumerate(Ws):
                A = Bd["A"] if W is None else Bd["A"] - torch.where(Bd["gate_sampled"], (xg * W[Bd["match"] % 2]).sum(1), 0.0)
                out.append(flat(torch.autograd.grad(-(Bd["w"] * A * lp).sum(), params, allow_unused=True,
                                                    retain_graph=k < len(Ws) - 1)))
            return out

        G = {"off": [], "on": [], "in": []}
        for _ in range(DRAWS):
            played = torch.rand(N, dtype=torch.float64) < p_play
            slot = torch.multinomial(card_lp.exp(), 1).squeeze(1)
            cell = torch.multinomial(cell_lp[allr, slot].exp(), 1).squeeze(1)
            slot = torch.where(played, slot, torch.full_like(slot, -1))
            cell = torch.where(played, cell, torch.full_like(cell, -1))
            lp = torch.where(played, torch.log(p_play), torch.log1p(-p_play))
            lp = lp + torch.where(played, card_lp[allr, slot.clamp(min=0)] + cell_lp[allr, slot.clamp(min=0), cell.clamp(min=0)],
                                  torch.zeros_like(lp))
            A = c + played.double() + 0.5 * torch.randn(N, dtype=torch.float64)
            Bd = {**B0, "played": played, "slot": slot, "cell": cell, "lp_old": lp, "A": A}
            W, _ = RL.gate_baseline_fit(model, Bd, cfg, rng)
            g3 = grads(Bd, (None, W, W.flip(0)))
            if not G["off"]:                                  # the one-forward gradients ARE minibatch_loss's
                R = RL.ref_terms(ref, Bd, TAU, T)
                for gk, wk in zip(g3, (None, W, W.flip(0))):
                    gm = grad_mb(Bd, R, wk)
                    self.assertLess(float((gm - gk).norm() / gm.norm()), 1e-4)
            for k, gk in zip(("off", "on", "in"), g3):
                G[k].append(gk)
        G = {k: torch.stack(v) for k, v in G.items()}
        gbar = G["off"].mean(0)
        dirs = torch.cat([(gbar / gbar.norm())[None], torch.nn.functional.normalize(
            torch.randn(8, len(gbar), generator=torch.Generator().manual_seed(1), dtype=torch.float64), dim=1)])

        def zs(D):
            x = D @ dirs.T                                    # [draws, 9]
            return (x.mean(0) / (x.std(0) / np.sqrt(len(x)))).abs()

        z_on, z_in = zs(G["on"] - G["off"]), zs(G["in"] - G["off"])
        tr = {k: float(((v - v.mean(0)) ** 2).sum(1).mean()) for k, v in G.items()}
        print(f"\n[gate_baseline MC] draws {DRAWS} rows {N}: |z| on {z_on.max():.2f} in-sample {z_in.max():.2f}; "
              f"tr(Sigma) off {tr['off']:.4g} on {tr['on']:.4g} (x{tr['on'] / tr['off']:.3f})", flush=True)
        self.assertLess(float(z_on.max()), 4.5)
        self.assertGreater(float(z_in.max()), 6.0)
        self.assertLess(tr["on"], 0.5 * tr["off"])            # c(s) is linear in g: the baseline removes most of it

    def test_config_validation_and_hash(self):
        import yaml
        cfg = yaml.safe_load((REPO / "pipeline" / "rl_royale.yaml").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as d:
            def load(**kv):
                p = Path(d) / "c.yaml"
                p.write_text(yaml.safe_dump({**cfg, **kv}), encoding="utf-8")
                return RL.load_config(p, [], smoke=False)
            self.assertEqual(RL.config_sha(load()), RL.config_sha(load(gate_baseline=None)))
            self.assertNotEqual(RL.config_sha(load()), RL.config_sha(load(gate_baseline={"weight": "score"})))
            load(gate_baseline={}), load(gate_baseline={"weight": "plain", "ridge": 0, "fit_rows": 4096})
            for bad in (True, "score", 1, {"weight": "x"}, {"ridge": -1}, {"ridge": True}, {"fit_rows": 1},
                        {"fit_rows": 2.5}, {"other": 1}):
                with self.assertRaises(SystemExit, msg=str(bad)):
                    load(gate_baseline=bad)


if __name__ == "__main__":
    unittest.main()
