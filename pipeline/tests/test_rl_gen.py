"""Offline tests for the GENERALIST path of the RL trainer (L68 T11): e1_eval's GenPolicy recording, rl_royale's
learner terms on generalist rows, pro agreement / checkpoints for a generalist init, and the condition keys.

    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_rl_gen.py

No engine, no GPU, no royalesim: the fake env of test_e1_eval_gen (the obs-contract fixture board and engine deck, made
to last several decisions here) runs the REAL ``e1_eval.run_batch`` / ``Match`` / ``sample_decide_batch`` with a tiny
random GenModel, so the learner is checked against exactly what an actor hands it.
"""
from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import torch                                                              # noqa: E402

from pipeline import e1_eval as E                                         # noqa: E402
from pipeline import rl_royale as RL                                      # noqa: E402
from pipeline.dataset import PAST_K                                       # noqa: E402
from pipeline.e1_view import Noise                                        # noqa: E402
from pipeline.obs_contract import load_deck                               # noqa: E402
from pipeline.tests.test_e1_eval_gen import VOCAB, _FakeEnv, _tiny_gen    # noqa: E402
from pipeline.tests.test_rl_royale import CFG, _Log, _tiny_model          # noqa: E402

TAU, T = 0.27, 0.5
N_DEC = 12                                          # decisions per fake match


class _LongEnv(_FakeEnv):
    """test_e1_eval_gen's fake env, N_DEC decisions long."""

    def reset(self, entry):
        st = super().reset(entry)
        self.tail_cap = self.tick + 10 * N_DEC
        return st


def _cfg(policy="sample", record=True, **kw):
    c = {"policy": policy, "tau": TAU, "afford_mask": True, "stall_elixir": 9.0, "stall_seconds": 12.0,
         "obs": "clean", "noise": Noise(), "p_random": 0.0, "random_hand_only": False, "grid": "lattice",
         "device": "cpu", "decide_every": 10, "slot": 0, "port": 0, "T": T, "record": record}
    c.update(kw)
    return c


def _wide_cells(model, seed=5):
    """cell_bias widened so cell log-probs are far from uniform 1/2304 (a stricter recompute check)."""
    with torch.no_grad():
        model.cell_bias.copy_(torch.from_numpy(np.random.default_rng(seed).normal(size=E.N_CELLS).astype("float32")))
    return model


def _rollouts(policy, n_matches=6, spy=None, cfg=None) -> list[dict]:
    """``n_matches`` recorded sample-policy matches through the real run_batch (2 in flight), outcomes alternating."""
    out = []
    jobs = [(i // 2, {"tag": f"e{i // 2}"}, i % 2, {"rollout_index": i % 2, "update": 0}) for i in range(n_matches)]
    orig = E.sample_decide_batch
    if spy is not None:
        def spying(model, enc, heads, p, allowed, stalled, matches, c):
            ds = orig(model, enc, heads, p, allowed, stalled, matches, c)
            for r, m in enumerate(matches):
                spy.setdefault((m.tag, m.k), []).append(
                    {"gate": float(heads["gate"][r]), "card": heads["card"][r].clone(), "d": ds[r]})
            return ds
        E.sample_decide_batch = spying
    try:
        E.run_batch(lambda: _LongEnv(), policy, load_deck("icebow"), jobs, cfg or _cfg(), 2, on_result=out.append)
    finally:
        E.sample_decide_batch = orig
    for j, r in enumerate(out):
        r["outcome"] = ("win", "loss", "draw")[j % 3]
    return out


def _batch(results):
    Bn, st = RL.collate(results)
    return RL.to_device(Bn, "cpu"), st


# ------------------------------------------------------------------------------------------------------
class TestGenRecording(unittest.TestCase):
    """The recorded generalist rows reproduce the logits the sampler used, and the learner's log-probs."""

    @classmethod
    def setUpClass(cls):
        cls.model = _wide_cells(_tiny_gen(3))
        cls.spy: dict = {}
        cls.res = _rollouts(E.GenPolicy(cls.model, VOCAB), spy=cls.spy)

    def test_rows_are_the_generalist_input(self):
        for r in self.res:
            t = r["traj"]
            n = len(t["played"])
            self.assertEqual(n, N_DEC)
            for k in E.GEN_ROW_KEYS:
                self.assertIn(k, t)
                self.assertEqual(len(t[k]), n, k)
            self.assertEqual(t["past"].shape[1:], (PAST_K, 5))                                 # (card, form, x, y, dt)
            self.assertFalse(t["sc"][:, 7:52].any())                                           # slot columns zeroed
            for k in E.GEN_IDENT_KEYS:
                self.assertEqual(t[k].dtype, np.int64, k)

    def test_recorded_rows_reproduce_sampler_logits(self):
        pol = E.GenPolicy(self.model, VOCAB)
        n_played = 0
        for r in self.res:
            t, seen = r["traj"], self.spy[(r["tag"], r["k"])]
            self.assertEqual(len(seen), len(t["played"]))
            b = {k: torch.from_numpy(np.ascontiguousarray(t[k])) for k in E.GEN_ROW_KEYS}
            with torch.no_grad():
                _, heads = pol.heads_t(b)
            for i, s in enumerate(seen):
                self.assertAlmostEqual(float(heads["gate"][i]), s["gate"], places=5)
                fin = torch.isfinite(s["card"])
                self.assertTrue(torch.equal(fin, torch.isfinite(heads["card"][i])))
                self.assertLess(float((heads["card"][i][fin] - s["card"][fin]).abs().max()), 1e-5)
                d = s["d"]
                self.assertEqual((bool(t["played"][i]), int(t["slot"][i]), int(t["cell"][i])),
                                 (d["play"], d["slot"], d["cell"]))
                self.assertEqual(float(t["lp_card"][i]), d["lp_card"])
                n_played += int(d["play"])
        self.assertGreater(n_played, 10)

    def test_learner_recomputes_recorded_logprobs(self):
        B, st = _batch(self.res)
        self.assertGreater(st["rows_played"], 10)
        self.assertGreater(st["rows_gate"], 10)
        for k in E.GEN_IDENT_KEYS:
            self.assertIn(k, B)
        with torch.no_grad():
            t = RL.policy_terms(self.model, B, torch.arange(len(B["A"])), TAU, T)
        for k in ("lp_gate", "lp_card", "lp_cell"):
            self.assertLess(float((t[k] - B[k]).abs().max()), 1e-5, k)
        # the card support is the allowed deck slots = the allowed hand positions: probs sum to 1 over allowed only
        pl = B["played"]
        p = t["card_lp"][pl].exp()
        self.assertLess(float((p.sum(-1) - 1).abs().max()), 1e-9)
        self.assertEqual(float(p[~B["allowed"][pl]].sum()), 0.0)


# ------------------------------------------------------------------------------------------------------
class TestGenOnPolicy(unittest.TestCase):
    """Unchanged weights: PPO ratio == 1 at the first minibatch, KL(pi || init) == 0, gradients finite."""

    @classmethod
    def setUpClass(cls):
        cls.model = _wide_cells(_tiny_gen(4))
        cls.B, _ = _batch(_rollouts(E.GenPolicy(cls.model, VOCAB), n_matches=8))

    def _ref(self):
        ref = copy.deepcopy(self.model).eval()
        for p in ref.parameters():
            p.requires_grad_(False)
        return ref

    def test_ratio_one_and_kl_zero(self):
        model = copy.deepcopy(self.model)
        R = RL.ref_terms(self._ref(), self.B, TAU, T)
        N = len(self.B["A"])
        loss, st = RL.minibatch_loss(model, self.B, R, torch.arange(N), tau=TAU, T=T, clip=0.2, beta=0.3, n_total=N)
        self.assertLess(st["ratio_maxdev"], 1e-4)
        for k in ("kl_gate", "kl_card", "kl_cell"):
            self.assertLess(abs(st[k]), 1e-8, k)
        self.assertTrue(torch.isfinite(loss))
        loss.backward()
        grads = [p.grad for p in model.parameters() if p.grad is not None]
        self.assertTrue(grads and all(torch.isfinite(g).all() for g in grads))
        self.assertTrue(any(float(g.abs().sum()) > 0 for g in grads))

    def test_ppo_update_first_minibatch_is_on_policy(self):
        model = copy.deepcopy(self.model)
        R = RL.ref_terms(self._ref(), self.B, TAU, T)
        opt = torch.optim.Adam(model.parameters(), lr=1e-3)
        cfg = {"minibatch": 32, "ppo_epochs": 2, "tau": TAU, "T": T, "clip": 0.2, "grad_clip": 0.5}
        out = RL.ppo_update(model, opt, self.B, R, cfg, 0.3, np.random.default_rng(0))
        self.assertIsNone(out["nonfinite"])
        self.assertLess(out["first"]["ratio_maxdev"], 1e-4)
        for k in ("kl_gate", "kl_card", "kl_cell"):
            self.assertLess(out["first"][k], 1e-8, k)
        self.assertGreater(out["kl_cell"], 0.0)               # it moved after steps at lr 1e-3


# ------------------------------------------------------------------------------------------------------
class TestS1PathUnchanged(unittest.TestCase):
    """S1 recording keeps exactly its old keys / shapes and the learner still recomputes it; the S1 actor cfg is the old
    inline dict plus the three neutral condition keys (e1_eval.Match treats them exactly like unset)."""

    OLD_TRAJ = {"tok", "mask", "sc", "past", "allowed", "stalled", "gate_sampled", "played", "slot", "cell", "lp_gate",
                "lp_card", "lp_cell", "p_gate", "T"}

    def test_s1_recording_and_recompute(self):
        model = _wide_cells(_tiny_model(7))
        res = _rollouts(model)
        for r in res:
            self.assertEqual(set(r["traj"]), self.OLD_TRAJ)
            self.assertEqual(r["traj"]["past"].shape[1:], (PAST_K, 4))
            self.assertTrue(r["traj"]["sc"][:, 7:52].any())                                  # S1 keeps its slot columns
        B, st = _batch(res)
        self.assertEqual(set(B), set(RL.TRAJ_KEYS) | {"lp_gate", "lp_card", "lp_cell", "lp_old", "A", "w", "match"})
        with torch.no_grad():
            t = RL.policy_terms(model, B, torch.arange(len(B["A"])), TAU, T)
        for k in ("lp_gate", "lp_card", "lp_cell"):
            self.assertLess(float((t[k] - B[k]).abs().max()), 1e-5, k)

    def test_s1_default_actor_cfg_is_the_old_one(self):
        base = {"tau": 0.27, "afford_mask": True, "stall_elixir": 9, "stall_seconds": 12, "obs": "live",
                "grid": "lattice", "decide_every": 10, "T": 0.5, "noise_off": [], "opp_elixir": None,
                "action_delay_ticks": 0, "extrapolate_ticks": 0}
        for kind in ("rollout", "screen"):
            old = {"policy": "sample" if kind == "rollout" else "live", "tau": 0.27, "afford_mask": True,
                   "stall_elixir": 9, "stall_seconds": 12.0, "obs": "live", "noise": Noise(), "p_random": 0.0,
                   "random_hand_only": False, "grid": "lattice", "device": "cpu", "decide_every": 10, "slot": 1,
                   "port": 0, "T": 0.5, "record": kind == "rollout"}
            new = RL.actor_cfg(base, kind, 1, "cpu")
            self.assertEqual({k: v for k, v in new.items() if k not in RL.COND_KEYS[1:]}, old)
            self.assertEqual((new["opp_elixir"], new["action_delay_ticks"], new["extrapolate_ticks"]), (None, 0, 0))
        self.assertEqual(RL.actor_cfg({**base, **{k: None for k in RL.COND_KEYS}}, "screen", 1, "cpu"),
                         RL.actor_cfg(base, "screen", 1, "cpu"))                                  # missing = default


# ------------------------------------------------------------------------------------------------------
def _stub_learner(cfg: dict, gen: dict | None, model, tmp: Path) -> "RL.Learner":
    L = RL.Learner.__new__(RL.Learner)
    L.cfg, L.gen, L.grid, L.model = cfg, gen, "lattice", model
    L.run, L.dev, L.pool_sha = "unit", torch.device("cpu"), "sha"
    L.init_meta = {"args": {"d": 16, "layers": 1, "grid": "lattice"}, "deck": "generalist", "epoch": 4, "n_params": 1}
    L.opt = torch.optim.Adam(model.parameters(), lr=1e-4)
    L.update, L.beta, L.rng, L.visits, L.train = 0, 0.3, np.random.default_rng(0), [0, 0, 0], [None] * 3
    L.base, L.guards, L.latest_pa, L._rows = {"init_screen": {}}, RL.Guards(cfg), None, None
    L.run_dir, L.ck_dir = tmp / "run", tmp / "ck" / "unit"
    L.run_dir.mkdir(parents=True, exist_ok=True)
    L.ck_dir.mkdir(parents=True, exist_ok=True)
    L.log = _Log()
    return L


class TestConditions(unittest.TestCase):
    """The condition keys reach BOTH the rollout and the screen match cfg, and the matches themselves."""

    LIVE = {"noise_off": "all", "opp_elixir": "counter", "action_delay_ticks": 26, "extrapolate_ticks": 26}

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rl_gen_cond_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_yaml_defaults_are_neutral(self):
        import yaml
        y = yaml.safe_load((REPO / "pipeline" / "rl_royale.yaml").read_text(encoding="utf-8"))
        self.assertEqual({k: y[k] for k in RL.COND_KEYS},
                         {"noise_off": [], "opp_elixir": None, "action_delay_ticks": 0, "extrapolate_ticks": 0})
        self.assertEqual(RL.condition_cfg(y), {"noise": Noise(), "opp_elixir": None, "action_delay_ticks": 0,
                                               "extrapolate_ticks": 0})

    def test_keys_reach_rollout_and_screen_cfg(self):
        cfg = dict(CFG, actor_threads=1, actor_device="cpu", tau=TAU, T=T, afford_mask=True, stall_elixir=9,
                   stall_seconds=12, obs="live", decide_every=10, in_flight=2, **self.LIVE)
        for gen in (None, {"d_c": 8, "card_vocab": VOCAB}):
            L = _stub_learner(cfg, gen, _tiny_gen(0), self.tmp)
            base = L.actor_base()
            self.assertEqual(base["gen"], gen)
            clean = Noise(**{n: False for n in E.NOISE_NAMES})
            for kind, policy in (("rollout", "sample"), ("screen", "live")):
                c = RL.actor_cfg(base, kind, 0, "cpu")
                self.assertEqual(c["policy"], policy)
                self.assertEqual(c["noise"], clean)
                self.assertEqual((c["opp_elixir"], c["action_delay_ticks"], c["extrapolate_ticks"]), ("counter", 26, 26))

    def test_noise_off_spellings_and_validation(self):
        self.assertEqual(RL.condition_cfg({"noise_off": ["recall", "position"]})["noise"],
                         RL.condition_cfg({"noise_off": "recall, position"})["noise"])
        self.assertEqual(RL.condition_cfg({"noise_off": ["all"]})["noise"], RL.condition_cfg({"noise_off": "all"})["noise"])
        for bad in ({"noise_off": ["nope"]}, {"opp_elixir": "truth"}, {"action_delay_ticks": -1},
                    {"extrapolate_ticks": -2}):
            with self.assertRaises(SystemExit, msg=bad):
                RL.condition_cfg(bad)

    def test_delay_and_extrapolation_reach_the_match(self):
        """An actor cfg with the live condition (minus the opp counter, which needs a ghost-delivering env) drives the
        real run_batch: every match -- rollout and screen, gen and S1 -- reports the delay and extrapolation."""
        base = {"tau": TAU, "afford_mask": True, "stall_elixir": 9, "stall_seconds": 12, "obs": "clean",
                "grid": "lattice", "decide_every": 10, "T": T, "noise_off": "all", "opp_elixir": None,
                "action_delay_ticks": 26, "extrapolate_ticks": 26}
        for pol in (E.GenPolicy(_tiny_gen(1), VOCAB), _tiny_model(1)):
            for kind in ("rollout", "screen"):
                out = []
                E.run_batch(lambda: _LongEnv(), pol, load_deck("icebow"), [(0, {"tag": "t"}, 0)],
                            RL.actor_cfg(base, kind, 0, "cpu"), 1, on_result=out.append)
                self.assertEqual((out[0]["action_delay_ticks"], out[0]["extrapolate_ticks"]), (26, 26))
                self.assertEqual("traj" in out[0], kind == "rollout")


# ------------------------------------------------------------------------------------------------------
class TestGenLearner(unittest.TestCase):
    """Checkpoint, update and pro agreement for a generalist init."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rl_gen_learner_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        orig = RL.CKPT_ROOT
        RL.CKPT_ROOT = self.tmp / "ck"
        self.addCleanup(setattr, RL, "CKPT_ROOT", orig)

    def _learner(self, model):
        cfg = dict(CFG, init="x.pt", lr=1e-4, tau=TAU, T=T, adv_clip=2.0, minibatch=64, ppo_epochs=2, clip=0.2,
                   grad_clip=0.5, kl_target=0.1, beta_min=0.03, beta_max=3.0, screen_every=1000, proagree_every=1000,
                   save_every=1, max_updates=1)
        L = _stub_learner(cfg, {"d_c": 8, "card_vocab": list(VOCAB)}, model, self.tmp)
        L.ref = copy.deepcopy(model).eval()
        for p in L.ref.parameters():
            p.requires_grad_(False)
        return L

    def test_checkpoint_loads_as_generalist(self):
        from pipeline.eval_gen import load_model
        model = _tiny_gen(2)
        L = self._learner(model)
        L.update = 3
        path = self.tmp / "ck" / "unit" / "unit_latest.pt"
        L._atomic_save(L._payload({"cell_half_top1": np.float64(0.2)}), path)
        ck = torch.load(path, map_location="cpu", weights_only=True)
        self.assertEqual((ck["gen"], ck["d_c"], ck["card_vocab"]), (True, 8, list(VOCAB)))
        pol, info = E.load_policy(path, "cpu")                     # what e1_eval / rl_gate / run_screen use
        self.assertIsInstance(pol, E.GenPolicy)
        self.assertEqual(info["grid"], "lattice")
        m2 = load_model(path, torch.device("cpu"))[0]
        for (k, a), b in zip(model.state_dict().items(), m2.state_dict().values()):
            self.assertTrue(torch.equal(a, b), k)
        L2 = self._learner(_tiny_gen(9))
        L2._restore(path)
        self.assertEqual(L2.update, 3)
        for a, b in zip(model.state_dict().values(), L2.model.state_dict().values()):
            self.assertTrue(torch.equal(a, b))

    def test_one_update_generalist(self):
        model = _wide_cells(_tiny_gen(6))
        res = _rollouts(E.GenPolicy(model, VOCAB), n_matches=6)
        L = self._learner(model)
        L.rollout = lambda u: (list(res), {"picked": [0, 1, 2], "actors": {}, "skipped": 0})
        rec, reasons, crash = L.one_update(0)                      # includes the update-0 on-policy assertion
        self.assertFalse(crash)
        self.assertEqual(L.update, 1)
        self.assertLess(rec["first_minibatch"]["ratio_maxdev"], RL.ASSERT_RATIO)
        ck = torch.load(L.ck_dir / "unit_u0001.pt", map_location="cpu", weights_only=True)
        self.assertTrue(ck["gen"])
        moved = any(not torch.equal(a, b) for a, b in zip(ck["model"].values(), L.ref.state_dict().values()))
        self.assertTrue(moved)

    def _synthetic_gen_npz(self, path: Path, n=40, seed=0) -> dict:
        from pipeline.obs_contract import F as TOK_F, S as SC_S
        from pipeline.dataset import PAST_K
        rng = np.random.default_rng(seed)
        units = rng.integers(0, 70, size=n)
        off = np.concatenate([[0], np.cumsum(units)]).astype(np.int64)
        tok = rng.normal(size=(int(off[-1]), TOK_F)).astype(np.float32)
        tok[:, 0] = rng.integers(0, 50, size=len(tok))
        tok[:, 4:6] = rng.uniform(0, 1, size=(len(tok), 2))
        deck = np.stack([np.sort(rng.choice(np.arange(1, len(VOCAB)), 8, replace=False)) for _ in range(n)])
        hp = np.stack([rng.choice(8, 4, replace=False) for _ in range(n)])
        hand = np.take_along_axis(deck, hp, 1)
        gate = (rng.random(n) < 0.5).astype(np.int8)
        a = {"off": off, "tok": tok, "sc": rng.normal(size=(n, SC_S)).astype(np.float32),
             "past": np.tile(np.array([0, 3, -1, -1, -1], np.float32), (n, PAST_K, 1)),
             "y_xy": rng.uniform(0, 1, size=(n, 2)).astype(np.float32),
             "y_hand_pos": np.where(gate == 1, rng.integers(0, 4, size=n), -1).astype(np.int8), "y_gate": gate,
             "y_wait_card": deck[np.arange(n), rng.integers(0, 8, size=n)].astype(np.int16),
             "y_crowns": rng.integers(0, 3, size=(n, 2)).astype(np.int8),
             "hand_card": hand.astype(np.int16), "hand_form": np.zeros((n, 4), np.int8),
             "next_card": deck[:, 0].astype(np.int16), "next_form": np.zeros(n, np.int8),
             "deck_card": deck.astype(np.int16), "deck_form": np.zeros((n, 8), np.int8),
             "v3val": (rng.random(n) < 0.5).astype(np.int8), "split": np.ones(n, np.int8)}
        a["y_card"] = np.where(gate == 1, hand[np.arange(n), np.maximum(a["y_hand_pos"], 0)], 0).astype(np.int16)
        a["sc"][:, 7:52] = 0.0
        np.savez(path, meta=np.array(json.dumps({"card_vocab": list(VOCAB)})), **a)
        return a

    def test_gen_proagree_is_eval_gen_on_the_v3val_rows(self):
        from pipeline.eval_gen import GenRows, evaluate
        npz = self.tmp / "gen_ds.npz"
        a = self._synthetic_gen_npz(npz)
        v3 = np.where(a["v3val"] == 1)[0]
        sub, meta = RL.gen_v3val_arrays(npz, 0)
        self.assertEqual(len(sub["y_gate"]), len(v3))
        for j, i in enumerate(v3):                                  # tok re-packed row by row
            np.testing.assert_array_equal(sub["tok"][sub["off"][j]:sub["off"][j + 1]], a["tok"][a["off"][i]:a["off"][i + 1]])
        model = _wide_cells(_tiny_gen(8))
        L = self._learner(model)
        L.cfg.update(proagree_data_gen=str(npz), proagree_rows=0)
        got = L.proagree(model)
        want = evaluate(model, GenRows(a, v3, torch.device("cpu")), grid="lattice")
        self.assertGreater(want["n_play"], 3)
        for k in RL.PA_KEYS + ("cell_tile_top1", "n", "n_play"):
            self.assertEqual(got[k], want[k], k)
        L._rows = None
        L.cfg.update(proagree_rows=5)
        self.assertEqual(L.proagree(model)["n"], 5)                 # first proagree_rows v3val rows


if __name__ == "__main__":
    unittest.main()
