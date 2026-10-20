"""Step c: per-unit visual-cue inputs (rl_royale ``cue_inputs``; model_gen ``cue_in``; e1_eval ``sim_cue_rows``;
scratchpad/gauntlet/L74/cues/STEP_C_SPEC.md).

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_cue_inputs.py
    # the SIM-cue tests need RoyaleSim >= 0.1.35 (pods: ROYALE_RUNTIME=20261016-linux; laptop: the composite venv in
    # STEP_C_SPEC.md "Laptop runtime"): ROYALE_RUNTIME=unpinned-linux <scratch>/v35/Scripts/python.exe -m pytest ...

Covers: absent = the pre-change code (config hash, GenModel outputs, a whole recorded SIM match + collate, against
PRE); zero-init layer = identical outputs on REAL rows (fv5 pro rows) even with random cues; u250 loads into a model with
the layer (that key zero-filled, every other key strict); graft_generic carries the layer; cue rows aligned to the unit
tokens on a real SIM board; recorded cue rows reach collate and the learner's trunk; search_s0 feeds them.
"""
from __future__ import annotations

import copy
import random
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import torch                                                              # noqa: E402

from pipeline import model_gen as MG                                     # noqa: E402
from pipeline import rl_royale as RL                                      # noqa: E402

PRE = "296e85c"                       # the last commit before step c: the absent-key reference
U250 = REPO / "icebow/data/bench/rl_royale/rlarm_gae/rlarm_gae_u0250_grafted.pt"
U0065 = REPO / "icebow/data/bench/rl_royale/rlarm_gae/rlarm_gae_u0065.pt"
FV5 = REPO / "icebow/data/pipeline/gen_dataset_v32_fv5.npz"
GRAFT = REPO / "scratchpad/gauntlet/L74/weekend/graft_generic.py"
YAML = REPO / "pipeline" / "rl_royale.yaml"

try:
    from pipeline.royale_env import RoyaleSelfPlayEnv
    from pipeline import e1_eval as E
    from pipeline import search_s0 as S
except ImportError:                   # no royalegym in this venv
    RoyaleSelfPlayEnv = None
try:
    E.require_cue_runtime()
    CUE_RT = RoyaleSelfPlayEnv is not None
except Exception:
    CUE_RT = False


def _pre(rel: str, name: str):
    try:
        src = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE}:{rel}"], capture_output=True, text=True,
                             encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise unittest.SkipTest(f"git unavailable: {exc}")
    if src.returncode:
        raise unittest.SkipTest(f"git show {PRE}:{rel} failed: {src.stderr.strip()}")
    mod = types.ModuleType(name)
    mod.__file__ = str(REPO / rel)
    mod.__package__ = "pipeline"
    sys.modules[name] = mod                   # dataclasses / pickling look the module up
    exec(compile(src.stdout, name, "exec"), mod.__dict__)
    return mod


def _need(*paths):
    for p in paths:
        if not p.exists():
            raise unittest.SkipTest(f"{p} not on this machine")


def _real_batch(n=48):
    """n fv5 pro rows (the pro-agreement VAL rows rl_royale reads) as a GenModel batch."""
    from pipeline.eval_gen import GenRows
    arrs, _ = RL.gen_v3val_arrays(FV5, n)
    return GenRows(arrs, np.arange(n), torch.device("cpu")).batch(np.arange(n))


def _outs(model, b):
    with torch.no_grad():
        o = model(b, card=b["card"], form=b["form"])
    return {k: o[k] for k in ("gate", "card", "wait", "value", "g", "cell")}


def _same(tc, a, b):
    for k in a:
        tc.assertTrue(torch.equal(a[k], b[k]), k)


# ------------------------------------------------------------------------------------------------------
class TestModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _need(U0065, FV5)
        cls.model = MG.load_model(U0065, torch.device("cpu"))[0].eval()
        cls.b = _real_batch()

    def test_zero_init_identical_on_real_rows(self):
        ref = _outs(self.model, self.b)
        m = copy.deepcopy(self.model)
        m.add_cue_in()
        self.assertTrue(torch.equal(m.cue_in.weight, torch.zeros(m.d, MG.CUE_N)))
        cue = torch.randn(*self.b["tok"].shape[:2], MG.CUE_N)
        _same(self, _outs(m, {**self.b, "cue": cue}), ref)          # random cues, zero layer: byte-identical
        _same(self, _outs(m, self.b), ref)                          # pro rows without cues (imitation path)
        with torch.no_grad():
            m.cue_in.weight.normal_()
        self.assertFalse(torch.equal(_outs(m, {**self.b, "cue": cue})["g"], ref["g"]))   # the layer is wired in
        _same(self, _outs(m, {**self.b, "cue": torch.zeros_like(cue)}), ref)            # cue_known 0 rows: no bias

    def test_absent_model_is_pre(self):
        P = _pre("pipeline/model_gen.py", "pipeline._model_gen_pre_cue")
        old = P.GenModel(d=128, layers=4, d_c=int(self.model.d_c), n_cards=self.model.n_cards,
                         feature_version=self.model.feature_version).eval()
        old.load_state_dict(self.model.state_dict())
        _same(self, _outs(self.model, self.b), _outs(old, self.b))
        self.assertNotIn("cue_in.weight", self.model.state_dict())

    def test_u250_loads_with_the_layer(self):
        _need(U250)
        st = torch.load(U250, map_location="cpu", weights_only=False)
        a = st["args"]
        m = MG.GenModel(d=int(a["d"]), layers=int(a["layers"]), d_c=int(st["d_c"]), n_cards=len(st["card_vocab"]),
                        feature_version=int(a["feature_version"]))
        m.add_cue_in()
        with torch.no_grad():
            m.cue_in.weight.fill_(1.0)
        m.load_state_dict(st["model"])                                # strict; cue_in zero-filled
        self.assertTrue(torch.equal(m.cue_in.weight, torch.zeros_like(m.cue_in.weight)))
        sd = m.state_dict()
        from pipeline import vocab
        for k, v in st["model"].items():
            if k == "cls_emb.weight":                                 # an older vocab grows on load (W9 10-20)
                v = v[vocab.grown_rows(v.shape[0] - 1)]
            self.assertTrue(torch.equal(sd[k], v), k)
        missing = dict(st["model"])
        missing.pop("gate_head.weight")
        with self.assertRaises(RuntimeError):
            m.load_state_dict(missing)
        with self.assertRaises(RuntimeError):
            m.load_state_dict({**st["model"], "bogus.weight": torch.zeros(1)})
        fresh = MG.GenModel(d=int(a["d"]), layers=int(a["layers"]), d_c=int(st["d_c"]), n_cards=len(st["card_vocab"]),
                            feature_version=int(a["feature_version"]))
        w = torch.randn(int(a["d"]), MG.CUE_N)
        fresh.load_state_dict({**st["model"], "cue_in.weight": w})    # a cue checkpoint builds the layer
        self.assertTrue(torch.equal(fresh.cue_in.weight, w))

    def test_graft_carries_the_layer(self):
        _need(U250)
        tmp = Path(tempfile.mkdtemp(prefix="cue_graft_"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        st = torch.load(U0065, map_location="cpu", weights_only=False)
        w = torch.randn(int(st["args"]["d"]), MG.CUE_N)
        st["model"] = {**st["model"], "cue_in.weight": w}
        torch.save(st, tmp / "arm.pt")
        r = subprocess.run([sys.executable, str(GRAFT), str(tmp / "arm.pt"), str(U250), str(tmp / "out.pt")],
                           capture_output=True, text=True, cwd=REPO, timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("cue_in carried: True", r.stdout)
        out = torch.load(tmp / "out.pt", map_location="cpu", weights_only=False)["model"]
        self.assertTrue(torch.equal(out["cue_in.weight"], w))
        live = torch.load(U250, map_location="cpu", weights_only=False)["model"]
        self.assertTrue(torch.equal(out["cell_refine.out.weight"], live["cell_refine.out.weight"]))
        m = MG.GenModel(d=int(st["args"]["d"]), layers=int(st["args"]["layers"]), d_c=int(st["d_c"]),
                        n_cards=len(st["card_vocab"]), feature_version=int(st["args"]["feature_version"]))
        m.load_state_dict(out)                                        # builds cue_in + refinements, strict
        self.assertTrue(torch.equal(m.cue_in.weight, w))

    def test_cue_vector_layout(self):
        u = {"state": "engaged", "charging": True, "hide": "hidden",
             "attack": {"target": 7, "phase": "hit", "frac": 0.25},
             "status": dict(stunned=False, frozen=True, slowed=True, raged=False, taunted=False, invisible=False,
                            shielded=True, slow_frac=0.5)}
        v = MG.cue_vector(u, True)
        self.assertEqual(len(v), MG.CUE_N)
        self.assertEqual(v, [1.0, 0, 0, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 1, 0.25, 1, 1, 0, 0, 1, 0.5])
        self.assertEqual(MG.CUE_N, 22)                                  # S6: no stunned / taunted


# ------------------------------------------------------------------------------------------------------
class TestConfig(unittest.TestCase):
    def test_hash_absent_is_pre(self):
        cfg = RL.load_config(YAML, [], False)
        self.assertNotIn("cue_inputs", cfg)
        P = _pre("pipeline/rl_royale.py", "rl_royale_pre_cue")
        self.assertEqual(RL.config_sha(cfg), P.config_sha(cfg))
        for off in (None, False):
            self.assertEqual(RL.config_sha(cfg), RL.config_sha(dict(cfg, cue_inputs=off)))
        self.assertNotEqual(RL.config_sha(cfg), RL.config_sha(dict(cfg, cue_inputs=True)))

    def test_override(self):
        self.assertIs(RL.load_config(YAML, ["cue_inputs=on"], False)["cue_inputs"], True)
        self.assertIs(RL.load_config(YAML, ["cue_inputs=off"], False)["cue_inputs"], False)
        with self.assertRaises(SystemExit):
            RL.load_config(YAML, ["cue_inputs=maybe"], False)


# ------------------------------------------------------------------------------------------------------
ICEBOW = ["Tornado", "Tesla@evolution", "IceWizard", "Xbow", "Rocket", "Knight@evolution", "Log", "Skeletons"]
HOGEQ = ["HogRider", "Earthquake", "Log", "Cannon", "Musketeer", "IceSpirits", "Skeletons", "Valkyrie"]


def _vocab():
    from pipeline.dataset_gen import card_key
    return ["<pad>"] + sorted({card_key(n) for n in ICEBOW + HOGEQ})


def _tiny(cue: bool, seed=0):
    torch.manual_seed(seed)
    net = MG.GenModel(d=16, layers=1, heads=2, d_c=8, n_cards=len(_vocab())).eval()
    if cue:
        net.add_cue_in()
        with torch.no_grad():
            net.cue_in.weight.normal_()
    return net


def _spec(seed=3):
    return {"tag": f"cue:{seed}", "opp": {"id": "gen"}, "learner_deck": list(E.ICEBOW_ENGINE_DECK),
            "opp_deck": list(HOGEQ), "learner_side": seed % 2, "seed": seed}


def _record_cfg():
    return dict(S.live_cfg(S.TAU_PLAIN, "lattice"), policy="sample", record=True)


def _opp_cfg():
    return S.live_cfg(S.TAU_OPP, "lattice")


@unittest.skipIf(RoyaleSelfPlayEnv is None, "royalegym not importable")
class TestAbsentRowsArePre(unittest.TestCase):
    def test_recorded_match_and_collate(self):
        """No cue layer: a whole recorded self-play match (traj bytes, result) and its collate = the PRE code's."""
        P = _pre("pipeline/e1_eval.py", "pipeline._e1_eval_pre_cue")
        PR = _pre("pipeline/rl_royale.py", "rl_royale_pre_cue2")
        outs = []
        for mod in (E, P):
            pol = mod.GenPolicy(_tiny(False), _vocab())
            opp = mod.GenPolicy(_tiny(False, seed=1), _vocab())
            got = []
            mod.run_selfplay_batch(lambda: RoyaleSelfPlayEnv(tail_cap=600), pol, {"gen": (opp, _opp_cfg())},
                                   [(0, _spec(), 0)], _record_cfg(), 1, on_result=got.append)
            got[0].pop("wall_s", None)
            outs.append(got[0])
        new, old = outs
        self.assertNotIn("cue", new["traj"])
        self.assertGreater(len(new["traj"]["tok"]), 10)                  # a real recorded match, not an empty one
        self.assertEqual(sorted(new["traj"]), sorted(old["traj"]))
        for k in old["traj"]:
            self.assertEqual(new["traj"][k].tobytes(), old["traj"][k].tobytes(), k)
        self.assertEqual({k: v for k, v in new.items() if k != "traj"}, {k: v for k, v in old.items() if k != "traj"})
        res = [dict(new, entry_index=0, outcome=new["outcome"])]
        Bn, _ = RL.collate(copy.deepcopy(res), 2.0, advantage="gae")
        Bp, _ = PR.collate(copy.deepcopy(res), 2.0, advantage="gae")
        self.assertEqual(sorted(Bn), sorted(Bp))
        for k in Bp:
            self.assertEqual(Bn[k].tobytes(), Bp[k].tobytes(), k)


@unittest.skipUnless(CUE_RT, "needs RoyaleSim >= 0.1.35 (STEP_C_SPEC.md 'Laptop runtime')")
class TestSimCues(unittest.TestCase):
    def _root(self, cfg, after=600, need=3):
        """A self-play match advanced (plain rule, both sides) until our side is due with >= need unit tokens."""
        pol = E.GenPolicy(_tiny(True), _vocab())
        opp = E.GenPolicy(_tiny(False, seed=1), _vocab())
        run = S.Runner(pol, {"gen": (opp, S.live_cfg(S.TAU_OPP, "lattice"))}, cfg,
                       lambda: RoyaleSelfPlayEnv(tail_cap=7200), horizon_s=4.0)
        m = run.setup("gen", 3, HOGEQ)
        st = {k: 0 for k in ("eligible", "searched", "unsearched", "gate_skipped", "overrides", "chose_wait",
                             "plain_wait_overridden", "moved_cell", "n_cands")}
        st["search_s"] = 0.0
        rng = random.Random(0)
        while True:
            ds = m.due()
            self.assertTrue(ds, f"match ended before >= {need} unit tokens were on the board")
            if m.learner in ds and m.env.tick >= after:
                m.learner.prepare()
                tok, mask = m.learner._obs[:2]
                if int((mask & (tok[:, 13] == 0)).sum()) >= need:
                    for s in ds:
                        s.prepare()
                    return run, m
            run.round(m, ds, "plain", st, rng)                         # both sides keep playing (plain rule)

    def test_rows_aligned_to_tokens(self):
        from pipeline.sim_unit_state import extract
        cfg = dict(S.live_cfg(S.TAU_PLAIN, "lattice"), extrapolate_ticks=0)     # exact positions: every body matches
        _, m = self._root(cfg)
        s = m.learner
        row = s.gen_row(s.model)
        tok, mask, cue = row["tok"], row["mask"], row["cue"]
        self.assertEqual(cue.shape, (len(tok), MG.CUE_N))
        unit = mask & (tok[:, 13] == 0) & ((tok[:, 1] > 0) | (tok[:, 2] > 0))
        self.assertTrue((cue[~unit] == 0).all())                       # spells / pads / unknown side: cue_known 0
        self.assertTrue((cue[unit, 0] == 1).all(), (int(unit.sum()), int(cue[:, 0].sum())))
        c = extract(s.env.core._battle, copy.deepcopy(s._cue_memo), hit_window_ms=100)
        towers = {u["uid"] for u in c["units"] if u["kind"].endswith("_tower")}

        def dist(u, i):                                                # tiles, in this side's board frame
            bx, by = u["x"] / 18, 1 - u["y"] / 32
            if s.side == 1:
                bx, by = 1 - bx, 1 - by
            return np.hypot((bx - tok[i, 4]) * 18, (by - tok[i, 5]) * 32)
        for i in np.flatnonzero(unit):
            here = [u for u in c["units"] if u["uid"] not in towers and (u["team"] == s.side) == (tok[i, 1] > 0)
                    and dist(u, i) < 0.05]                             # the token's own body (same tick, exact view)
            self.assertTrue(here, i)
            self.assertTrue(any(np.allclose(cue[i], MG.cue_vector(u, u["attack"]["target"] in towers)) for u in here), i)
            self.assertEqual(cue[i, 1:8].sum(), 1.0)                   # one state

    def test_search_s0_feeds_cues(self):
        run, m = self._root(S.live_cfg(S.TAU_PLAIN, "lattice"), after=0, need=1)
        p, enc, heads, hand = S.forward(m.learner)
        self.assertIn("cue", m.learner._gen_row)
        cue = m.learner._gen_row["cue"]
        self.assertGreater(cue[:, 0].sum(), 0)
        b = {k: torch.as_tensor(np.stack([m.learner._gen_row[k]])) for k in E.gen_row_keys(m.learner.model.model)}
        with torch.no_grad():
            g1 = m.learner.model.model.encode_gen(b)["g"]
            g0 = m.learner.model.model.encode_gen({**b, "cue": torch.zeros_like(b["cue"])})["g"]
        self.assertFalse(torch.equal(g0, g1))                          # the cues reached the forward search uses

    def test_record_collate_learner(self):
        pol = E.GenPolicy(_tiny(True), _vocab())
        opp = E.GenPolicy(_tiny(False, seed=1), _vocab())
        got = []
        E.run_selfplay_batch(lambda: RoyaleSelfPlayEnv(tail_cap=900), pol, {"gen": (opp, _opp_cfg())},
                             [(0, _spec(), 0)], _record_cfg(), 1, on_result=got.append)
        tj = got[0]["traj"]
        self.assertEqual(tj["cue"].shape, (len(tj["tok"]), E.MAX_U, MG.CUE_N))
        self.assertGreater(tj["cue"][..., 0].sum(), 0)
        unit = tj["mask"] & (tj["tok"][..., 13] == 0) & ((tj["tok"][..., 1] > 0) | (tj["tok"][..., 2] > 0))
        self.assertTrue((tj["cue"][~unit] == 0).all())                  # aligned: cues only on unit tokens
        B, _ = RL.collate([dict(got[0], entry_index=0)], 2.0, advantage="gae")
        self.assertIn("cue", B)
        self.assertEqual(len(B["cue"]), len(B["tok"]))
        Bt = RL.to_device(B, "cpu")
        idx = torch.arange(len(B["tok"]))
        g = RL.trunk_g(pol.model, Bt, idx)
        g0 = RL.trunk_g(pol.model, {**Bt, "cue": torch.zeros_like(Bt["cue"])}, idx)
        self.assertFalse(torch.equal(g, g0))                            # the learner feeds the recorded cues


if __name__ == "__main__":
    unittest.main()
