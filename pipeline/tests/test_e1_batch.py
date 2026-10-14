"""Offline tests for e1_eval's batched decide (``run_batch``'s ``live_decide_batch`` / ``sample_decide_batch``) and
the tempered SAMPLE behaviour policy (L68e; design: scratchpad/gauntlet/L68/rl_plan.md "Behaviour policy",
scratchpad/gauntlet/L67/e1_engine_rl_design.md 3.3).

    icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_e1_batch -v

No engine, no GPU, no royalesim -- a tiny random S1Model stands in for the checkpoint, same pattern as
test_e1_baseline.TestLiveRuleParity. The (tok, mask, sc, past) rows are random (not real game states): these
tests are about the DECIDE step on precomputed heads, not the encoder, so the forward's inputs only need the
right shapes -- ``allowed``/``stalled`` are supplied directly, exactly as ``run_batch`` supplies them.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import e1_eval as E                              # noqa: E402
from pipeline.dataset import PAST_K                             # noqa: E402
from pipeline.obs_contract import F as TOK_F, S as SC_S         # noqa: E402

MAX_U, N_SLOTS, N_CELLS, TAU = E.MAX_U, E.N_SLOTS, E.N_CELLS, E.TAU_LIVE


class _FakeMatch:
    """Stands in for a ``Match`` in ``sample_decide_batch``: only ``.rng_behave`` is read."""

    def __init__(self, seed: int):
        self.rng_behave = np.random.default_rng(seed)


def _rows(rng: np.random.Generator, model, b: int, device: str = "cpu"):
    """``b`` random (tok, mask, sc, past) rows -> their ``model_forward_batch`` outputs (enc, heads, p, hand)."""
    toks = []
    for _ in range(b):
        t = rng.normal(size=(MAX_U, TOK_F)).astype(np.float32)
        t[:, 0] = rng.integers(0, 50, size=MAX_U)               # a plausible cls id column
        t[:, 4:6] = rng.uniform(0, 1, size=(MAX_U, 2))          # xy in [0, 1] (encode's fourier features)
        toks.append(t)
    masks = [rng.random(MAX_U) < 0.5 for _ in range(b)]
    scs = []
    for _ in range(b):
        s = rng.normal(size=SC_S).astype(np.float32)
        s[7:43] = 0.0
        for g, slot in enumerate(rng.choice(N_SLOTS, size=4, replace=False)):   # a 4-card hand, 4 distinct slots
            s[7 + g * 9 + slot] = 1.0                           # model_v3.hand_mask_from_sc's 4x9 one-hot layout
        scs.append(s)
    pasts = [np.full((PAST_K, 4), -1.0, np.float32) for _ in range(b)]
    enc, heads, p, hand = E.model_forward_batch(model, toks, masks, scs, pasts, device)
    return toks, masks, scs, pasts, enc, heads, p, hand


def _tiny_model(seed: int):
    import torch
    from pipeline.model_v3 import S1Model
    torch.manual_seed(seed)
    return S1Model(d=16, layers=1, heads=2).eval()


# ------------------------------------------------------------------------------------------------------
class TestLiveDecideBatch(unittest.TestCase):
    """``live_decide_batch`` (run_batch's batched decide) vs today's per-row ``live_decide``."""

    @classmethod
    def setUpClass(cls):
        cls.model = _tiny_model(0)

    def test_matches_per_row_live_decide_on_random_heads(self):
        rng = np.random.default_rng(1)
        b = 11
        *_, enc, heads, p, hand = _rows(rng, self.model, b)
        allowed = np.stack([rng.random(N_SLOTS) < 0.6 for _ in range(b)])
        stalled = rng.random(b) < 0.3
        batched = E.live_decide_batch(self.model, enc, heads, p, allowed, stalled, tau=TAU)
        for r in range(b):
            enc_r = {k: v[r:r + 1] for k, v in enc.items()}
            heads_r = {k: v[r:r + 1] for k, v in heads.items()}
            want = E.live_decide(self.model, enc_r, heads_r, p[r], allowed[r], tau=TAU, stalled=bool(stalled[r]))
            self.assertEqual(batched[r], want, r)

    def test_no_allowed_rows_are_wait_no_afford(self):
        rng = np.random.default_rng(2)
        b = 4
        *_, enc, heads, p, hand = _rows(rng, self.model, b)
        allowed = np.zeros((b, N_SLOTS), dtype=bool)
        stalled = np.array([False, True, False, True])
        out = E.live_decide_batch(self.model, enc, heads, p, allowed, stalled, tau=TAU)
        for d in out:
            self.assertEqual(d, {"play": False, "slot": -1, "cell": -1, "why": "no_affordable"})


# ------------------------------------------------------------------------------------------------------
class TestSampleAtLowTMatchesLive(unittest.TestCase):
    """T -> 0 reproduces the greedy live rule on tie-free rows (rl_plan.md: 'that is the unit test of the sampler')."""

    @classmethod
    def setUpClass(cls):
        import torch
        cls.model = _tiny_model(2)
        # a fresh random tiny model's raw cell logits cluster within ~1e-3 of each other (untrained cell_key/
        # cell_emb) -- a real near-tie no finite T resolves cleanly. Widen cell_bias (a fixed per-cell additive
        # term, model_v3.py:102/146) with a well-separated permutation so THIS test's argmax is unambiguous;
        # it is the sampler's tie-free behaviour under test here, not the untrained model's cell resolution.
        with torch.no_grad():
            cls.model.cell_bias.copy_(torch.from_numpy(
                np.random.default_rng(99).permutation(N_CELLS).astype("float32")) * 5.0)

    def test_T_1e4_reproduces_live_decisions(self):
        rng = np.random.default_rng(7)
        b = 16
        *_, enc, heads, p, hand = _rows(rng, self.model, b)
        allowed = np.stack([rng.random(N_SLOTS) < 0.7 for _ in range(b)])
        stalled = rng.random(b) < 0.3
        live = E.live_decide_batch(self.model, enc, heads, p, allowed, stalled, tau=TAU)
        matches = [_FakeMatch(1000 + i) for i in range(b)]
        sample = E.sample_decide_batch(self.model, enc, heads, p, allowed, stalled, matches, {"tau": TAU, "T": 1e-4})
        n_play = 0
        for r in range(b):
            self.assertEqual(sample[r]["play"], live[r]["play"], r)
            if live[r]["play"]:
                n_play += 1
                self.assertEqual(sample[r]["slot"], live[r]["slot"], r)
                self.assertEqual(sample[r]["cell"], live[r]["cell"], r)
        self.assertGreater(n_play, 0)                            # the comparison is non-trivial

    def test_sample_heads_greedy_heads_equal_live(self):
        """10-13 GAP decomposition: a head left out of ``sample_heads`` is the live greedy choice at ANY T."""
        rng = np.random.default_rng(11)
        b = 16
        *_, enc, heads, p, hand = _rows(rng, self.model, b)
        allowed = np.stack([rng.random(N_SLOTS) < 0.7 for _ in range(b)])
        stalled = rng.random(b) < 0.3
        live = E.live_decide_batch(self.model, enc, heads, p, allowed, stalled, tau=TAU)
        cfg = {"tau": TAU, "T": 0.5}
        none = E.sample_decide_batch(self.model, enc, heads, p, allowed, stalled,
                                     [_FakeMatch(i) for i in range(b)], dict(cfg, sample_heads=()))
        cell = E.sample_decide_batch(self.model, enc, heads, p, allowed, stalled,
                                     [_FakeMatch(i) for i in range(b)], dict(cfg, sample_heads=("cell",)))
        for r in range(b):
            self.assertEqual((none[r]["play"], none[r]["slot"] if live[r]["play"] else -9, none[r]["cell"]),
                             (live[r]["play"], live[r]["slot"] if live[r]["play"] else -9, live[r]["cell"]), r)
            self.assertEqual((none[r]["lp_gate"], none[r]["lp_card"], none[r]["lp_cell"]), (0.0, 0.0, 0.0))
            self.assertEqual(cell[r]["play"], live[r]["play"], r)
            if live[r]["play"]:
                self.assertEqual(cell[r]["slot"], live[r]["slot"], r)
        self.assertTrue(any(c["lp_cell"] != 0.0 for c in cell if c["play"]))   # the cell really was drawn
        cold = E.sample_decide_batch(self.model, enc, heads, p, allowed, stalled,       # T_gate -> 0: live's play/wait
                                     [_FakeMatch(i) for i in range(b)], dict(cfg, T_gate=1e-4))
        self.assertEqual([c["play"] for c in cold], [x["play"] for x in live])


# ------------------------------------------------------------------------------------------------------
class TestLogProbRecompute(unittest.TestCase):
    """lp_gate / lp_card / lp_cell equal an independent recomputation from the SAME recorded logits."""

    @classmethod
    def setUpClass(cls):
        cls.model = _tiny_model(3)

    def test_components_match_independent_computation(self):
        import torch
        rng = np.random.default_rng(11)
        b = 20
        T = 0.5
        *_, enc, heads, p, hand = _rows(rng, self.model, b)
        allowed = np.stack([rng.random(N_SLOTS) < 0.7 for _ in range(b)])
        stalled = np.zeros(b, dtype=bool)                        # force the "else gate" branch every row
        matches = [_FakeMatch(2000 + i) for i in range(b)]
        out = E.sample_decide_batch(self.model, enc, heads, p, allowed, stalled, matches, {"tau": TAU, "T": T})
        logit_tau = math.log(TAU / (1.0 - TAU))
        z_gate = heads["gate"].detach().cpu().numpy().astype(np.float64)
        n_checked = 0
        for r in range(b):
            if not allowed[r].any():
                continue
            d = out[r]
            self.assertTrue(d["gate_sampled"])
            p_b = 1.0 / (1.0 + math.exp(-(z_gate[r] - logit_tau) / T))
            want_lp_gate = math.log(p_b) if d["play"] else math.log(1.0 - p_b)
            self.assertAlmostEqual(d["lp_gate"], want_lp_gate, places=8, msg=r)
            if not d["play"]:
                self.assertEqual(d["lp_card"], 0.0); self.assertEqual(d["lp_cell"], 0.0)
                continue
            with torch.no_grad():
                card_logits = heads["card"][r].clone()
                card_logits = card_logits.masked_fill(~torch.from_numpy(allowed[r]), float("-inf"))
                card_probs = torch.softmax(card_logits.double() / T, dim=-1).numpy()
                enc_r = {k: v[r:r + 1] for k, v in enc.items()}
                cell_logits = self.model.cell_logits(enc_r, torch.tensor([d["slot"]]))[0]
                cell_probs = torch.softmax(cell_logits.double() / T, dim=-1).numpy()
            self.assertAlmostEqual(d["lp_card"], math.log(card_probs[d["slot"]]), places=6, msg=r)
            self.assertAlmostEqual(d["lp_cell"], math.log(cell_probs[d["cell"]]), places=5, msg=r)
            n_checked += 1
        self.assertGreater(n_checked, 0)


# ------------------------------------------------------------------------------------------------------
class TestStalledForcesPlayGateNotSampled(unittest.TestCase):
    """stalled -> play forced: gate NOT sampled (gate_sampled False, lp_gate 0)."""

    @classmethod
    def setUpClass(cls):
        cls.model = _tiny_model(4)

    def test_stalled_rows(self):
        rng = np.random.default_rng(21)
        b = 5
        *_, enc, heads, p, hand = _rows(rng, self.model, b)
        allowed = np.ones((b, N_SLOTS), dtype=bool)
        stalled = np.ones(b, dtype=bool)
        matches = [_FakeMatch(3000 + i) for i in range(b)]
        out = E.sample_decide_batch(self.model, enc, heads, p, allowed, stalled, matches, {"tau": TAU, "T": 0.5})
        for d in out:
            self.assertTrue(d["play"])
            self.assertEqual(d["why"], "stall")
            self.assertFalse(d["gate_sampled"])
            self.assertEqual(d["lp_gate"], 0.0)
            self.assertGreaterEqual(d["slot"], 0)
            self.assertGreaterEqual(d["cell"], 0)


# ------------------------------------------------------------------------------------------------------
class TestNoAllowedIsWaitNoLogProb(unittest.TestCase):
    """none allowed -> WAIT, why 'no_affordable', no log-prob -- but the row IS recorded (all components 0)."""

    @classmethod
    def setUpClass(cls):
        cls.model = _tiny_model(5)

    def test_no_allowed_rows(self):
        rng = np.random.default_rng(31)
        b = 6
        *_, enc, heads, p, hand = _rows(rng, self.model, b)
        allowed = np.zeros((b, N_SLOTS), dtype=bool)
        stalled = np.array([False, True, False, True, False, True])   # stalled must not matter when nothing's allowed
        matches = [_FakeMatch(4000 + i) for i in range(b)]
        out = E.sample_decide_batch(self.model, enc, heads, p, allowed, stalled, matches, {"tau": TAU, "T": 0.5})
        for d in out:
            self.assertFalse(d["play"])
            self.assertEqual(d["why"], "no_affordable")
            self.assertFalse(d["gate_sampled"])
            self.assertEqual(d["slot"], -1)
            self.assertEqual(d["cell"], -1)
            for k in ("lp_gate", "lp_card", "lp_cell"):
                self.assertEqual(d[k], 0.0, k)


if __name__ == "__main__":
    unittest.main()
