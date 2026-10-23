"""rl_royale ``tau_phase`` (owner 10-23): learner rollouts gate at live's per-phase threshold [1x, 2x, OT] and the PPO
recompute uses the very threshold each row was sampled with (rows record it as ``gate_tau``).

    icebow/.venv/Scripts/python.exe -m pytest pipeline/tests/test_tau_phase.py -q
"""
from __future__ import annotations

import copy
import os
import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import torch                                                    # noqa: E402

from pipeline import e1_eval as E                               # noqa: E402
from pipeline import rl_royale as RL                            # noqa: E402
from pipeline.dataset import PAST_K                             # noqa: E402
from pipeline.decision_options import options_from_config      # noqa: E402
from pipeline.obs_contract import F as TOK_F, S as SC_S         # noqa: E402

PRE = "6e83cc8"                         # HEAD before tau_phase: the absent-key reference
PHASE, TAU, T, TG = [0.35, 0.45, 0.55], 0.35, 0.5, 0.1
DTAU = [0.10, 0.0, -0.10]
D_G = 1 + E.N_SLOTS                     # g = [gate logit, 8 card logits]


class _Net(torch.nn.Module):
    """S1Model's decide surface with every output an ELEMENTWISE function of the row's own first token (no reduction
    over rows or features): the sampler's batched forward and the learner's recompute agree bit for bit, so only the
    gate threshold / log-prob formulas are under test."""

    def __init__(self):
        super().__init__()
        self.w = torch.nn.Parameter(torch.linspace(-3.0, 3.0, E.N_SLOTS * E.N_CELLS).reshape(E.N_SLOTS, E.N_CELLS))

    def encode(self, tok, mask, sc, past):
        return {"g": tok[:, 0, :D_G]}

    def heads(self, enc, hand_mask):
        return {"gate": enc["g"][:, 0], "card": enc["g"][:, 1:]}

    def cell_logits(self, enc, slot):
        return enc["g"][:, :1] * self.w[slot]


class _M:
    """What sample_decide_batch / posture_dtau read of a match: rng_behave, _cur (tick, board with t_sec), a ctx row."""

    def __init__(self, seed):
        self.rng_behave = np.random.default_rng(seed)

    def at(self, t_sec):
        self._cur = (int(round(t_sec * 20)), SimpleNamespace(t_sec=float(t_sec)), None)
        return self

    def _ctx_row(self, tick):
        return [tick % 9, int(tick >= 2400), min(2, tick // 2400), 0, 0]


def _rows(rng, n, p=None):
    toks, scs = [], []
    for r in range(n):
        t = np.zeros((E.MAX_U, TOK_F), np.float32)
        q = rng.uniform(0.25, 0.65) if p is None else p
        t[0, 0] = np.log(q / (1 - q))                         # the gate logit
        t[0, 1:D_G] = rng.normal(size=E.N_SLOTS)              # card logits (cell logits = gate logit x w[slot])
        toks.append(t)
        s = np.zeros(SC_S, np.float32)
        for g, slot in enumerate(rng.choice(E.N_SLOTS, size=4, replace=False)):
            s[7 + g * 9 + slot] = 1.0
        scs.append(s)
    return toks, [np.ones(E.MAX_U, bool)] * n, scs, [np.full((PAST_K, 4), -1.0, np.float32)] * n


def _head(z=None):
    with torch.random.fork_rng():
        torch.manual_seed(3)
        h = RL.PostureHead(D_G)
        with torch.no_grad():
            h.net[2].weight.normal_(0.0, 0.5)
            if z is not None:                                 # forced: always posture z
                h.net[2].bias.copy_(torch.tensor([100.0 if i == z else 0.0 for i in range(3)]))
    return h.eval()


def _cfg(tau_phase=PHASE, head=None, **kw):
    c = {"tau": TAU, "T": T, "T_gate": TG, **kw}
    if tau_phase is not None:
        c["tau_phase"] = tau_phase
    if head is not None:
        c["posture"] = {"head": head, "every": 200, "dtau": DTAU, "mode": "sample"}
    return c


def _results(net, cfg, n_match=6, n_dec=40, seed=0, mod=E):
    """n_match fake matches decided TOGETHER (one batched sample_decide_batch per round, as run_batch), each row at a
    random board time in [0, 300) s, recorded by the real Match._record / _traj_arrays (of ``mod``)."""
    rng = np.random.default_rng(seed)
    ms = [_M(100 + j) for j in range(n_match)]
    ns = [SimpleNamespace(cfg={"record": True}, _cur=None, n_dec=0, p_gates=[], _obs=None, _gen_row=None, traj=[],
                          n_noaff=0) for _ in ms]
    for _ in range(n_dec):
        toks, masks, scs, pasts = _rows(rng, n_match)
        enc, heads, p, hand = mod.model_forward_batch(net, toks, masks, scs, pasts)
        allowed = hand & (rng.random(hand.shape) < 0.8)
        for m in ms:
            m.at(rng.uniform(0.0, 300.0))
        ds = mod.sample_decide_batch(net, enc, heads, p, allowed, np.zeros(n_match, bool), ms, cfg)
        for j, d in enumerate(ds):
            ns[j]._cur, ns[j]._obs = ms[j]._cur, (toks[j], masks[j], scs[j], pasts[j])
            mod.Match._record(ns[j], p[j], d)
    return [{"entry_index": j // 2, "k": j % 2, "outcome": ("win", "loss")[j % 2], "traj": mod.Match._traj_arrays(x)}
            for j, x in enumerate(ns)]


def _pre(rel, name):
    """The pre-tau_phase module: git ``PRE`` here, or env TAU_PHASE_PRE_TREE's file (a pod's unpatched tree, no git)."""
    if os.environ.get("TAU_PHASE_PRE_TREE"):
        code = (Path(os.environ["TAU_PHASE_PRE_TREE"]) / rel).read_text(encoding="utf-8")
    else:
        try:
            src = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE}:{rel}"], capture_output=True, text=True,
                                 encoding="utf-8", timeout=60)
        except (OSError, subprocess.TimeoutExpired) as exc:
            pytest.skip(f"git unavailable: {exc}")
        if src.returncode:
            pytest.skip(f"git show {PRE}:{rel} failed: {src.stderr.strip()}")
        code = src.stdout
    mod = types.ModuleType(name)
    mod.__file__, mod.__package__ = str(REPO / rel), "pipeline"
    sys.modules[name] = mod
    exec(compile(code, name, "exec"), mod.__dict__)
    return mod


# ---- (i) the row's phase sets its threshold ---------------------------------------------------------------------
@pytest.mark.parametrize("z", [None, 0, 2])
def test_threshold_by_phase(z):
    times = [60.0, 119.99, 120.0, 150.0, 179.99, 180.0, 200.0, 290.0]
    want = np.array([.35, .35, .45, .45, .45, .55, .55, .55]) + (0.0 if z is None else DTAU[z])
    net, rng = _Net(), np.random.default_rng(1)
    toks, masks, scs, pasts = _rows(rng, len(times), p=0.40)
    enc, heads, p, hand = E.model_forward_batch(net, toks, masks, scs, pasts)
    ms = [_M(j).at(t) for j, t in enumerate(times)]
    ds = E.sample_decide_batch(net, enc, heads, p, hand, np.zeros(len(times), bool), ms,
                               _cfg(head=None if z is None else _head(z)))
    np.testing.assert_allclose([d["gate_tau"] for d in ds], want, rtol=0, atol=1e-15)
    lt = np.log(want / (1 - want))                            # the sampled gate's log-prob is at that threshold
    pb = 1 / (1 + np.exp(-(float(np.float32(np.log(0.4 / 0.6))) - lt) / TG))
    np.testing.assert_allclose([d["lp_gate"] for d in ds], np.log(np.where([d["play"] for d in ds], pb, 1 - pb)),
                               rtol=0, atol=1e-9)
    ms = [_M(j).at(t) for j, t in enumerate(times)]          # the greedy gate (eval decomposition) uses it too
    g = E.sample_decide_batch(net, enc, heads, p, hand, np.zeros(len(times), bool), ms,
                              _cfg(head=None if z is None else _head(z), sample_heads=("card", "cell")))
    assert [d["play"] for d in g] == list(0.4 > want)


# ---- (ii) THE RATIO TEST: recompute == behaviour at the unchanged policy -------------------------------------------
@pytest.mark.parametrize("posture", [False, True])
def test_ratio_is_one(posture):
    net = _Net()
    res = _results(net, _cfg(head=_head() if posture else None))
    B = RL.to_device(RL.collate(res)[0], "cpu")
    assert "gate_tau" in B and ("posture_dtau" in B) == posture
    assert len(np.unique(np.round(B["gate_tau"].numpy(), 9))) >= (4 if posture else 3)   # every phase (x posture)
    if posture:
        assert len(np.unique(B["posture_dtau"].numpy())) >= 2
    idx = torch.arange(len(B["A"]))
    assert int(B["gate_sampled"].sum()) > 50 and int(B["played"].sum()) > 20
    with torch.no_grad():
        t = RL.policy_terms(net, B, idx, TAU, T, T_gate=TG)
    for k in ("lp_gate", "lp_card", "lp_cell"):
        assert float((t[k] - B[k]).abs().max()) < 1e-9, k
    R = RL.ref_terms(copy.deepcopy(net), B, TAU, T, T_gate=TG)
    _, st = RL.minibatch_loss(net, B, R, idx, tau=TAU, T=T, clip=0.2, beta=0.3, n_total=len(idx), T_gate=TG)
    assert st["ratio_maxdev"] < 1e-9 and st["clip_frac"] == 0.0 and abs(st["kl_gate"]) < 1e-12
    B0 = {k: v for k, v in B.items() if k != "gate_tau"}     # control: the scalar tau (+ dtau) would be off-policy
    with torch.no_grad():
        t0 = RL.policy_terms(net, B0, idx, TAU, T, T_gate=TG)
    assert float((t0["lp_gate"] - B["lp_gate"]).abs().max()) > 1e-2


def test_monitors_use_row_threshold():
    res = _results(_Net(), _cfg(), n_match=2, n_dec=30)
    for r in res:
        r.update(seconds=180.0, plays_attempted=1, plays_accepted=1, card_mix_attempted={}, refuse_reasons={},
                 play_elixir=[], stall_fired=0, ghost_delivered=0, ghost_refused=0, ghost_undelivered=0,
                 won_after_script=False)
    pg = np.concatenate([r["traj"]["p_gate"] for r in res])
    gt = np.concatenate([r["traj"]["gate_tau"] for r in res])
    assert RL.rollout_monitors(res, TAU, TG)["p_gate_frac_gt_tau"] == float((pg > gt).mean())


# ---- (iii) absent key = today's config hash and rows -----------------------------------------------------------
def test_absent_key_hash():
    cfg = RL.load_config(REPO / "pipeline" / "rl_royale.yaml", [], False)
    assert "tau_phase" not in cfg
    h = RL.config_sha(cfg)
    assert h == RL.config_sha({**cfg, "tau_phase": None})
    on = RL.config_sha({**cfg, "tau_phase": PHASE})
    assert on != h and on == RL.config_sha({**cfg, "tau_phase": (0.35, 0.45, 0.55)})
    assert _pre("pipeline/rl_royale.py", "rl_royale_pre_tau_phase").config_sha(cfg) == h


@pytest.mark.parametrize("posture", [False, True])
def test_absent_key_rows_identical(posture):
    P = _pre("pipeline/e1_eval.py", "pipeline._e1_eval_pre_tau_phase")
    cfg = _cfg(tau_phase=None, head=_head() if posture else None)

    a, b = (_results(_Net(), cfg, n_match=3, n_dec=25, seed=4, mod=m) for m in (E, P))
    for x, y in zip(a, b):
        assert sorted(x["traj"]) == sorted(y["traj"]) and "gate_tau" not in x["traj"]
        for k in x["traj"]:
            np.testing.assert_array_equal(x["traj"][k], y["traj"][k], err_msg=k)


def test_actor_cfg():
    base = {"tau": TAU, "afford_mask": True, "stall_elixir": None, "stall_seconds": 12.0, "obs": "live", "grid": "lattice",
            "decide_every": 10, "T": T, "T_gate": TG}
    for kind in ("rollout", "screen"):
        assert "tau_phase" not in RL.actor_cfg(base, kind, 0, "cpu")
        on = RL.actor_cfg({**base, "tau_phase": PHASE}, kind, 0, "cpu")
        assert on["tau_phase"] == PHASE and on["tau"] == TAU
    o = options_from_config(on)                               # the screen: live's DecisionOptions tau_phase
    assert o.active and o.tau_phase == tuple(PHASE)
    P = _pre("pipeline/rl_royale.py", "rl_royale_pre_tau_phase_ac")
    for kind in ("rollout", "screen"):
        assert RL.actor_cfg(base, kind, 0, "cpu") == P.actor_cfg(base, kind, 0, "cpu")


# ---- (iv) validation --------------------------------------------------------------------------------------------
@pytest.mark.parametrize("bad", [
    {"tau_phase": [.35, .45]}, {"tau_phase": [.35, .45, 1.0]}, {"tau_phase": [0, .45, .55]},
    {"tau_phase": [.35, float("nan"), .55]}, {"tau_phase": [True, .45, .55]}, {"tau_phase": ".35 .45 .55"},
    {"tau_phase": PHASE, "branch_gate": True},
    {"tau_phase": [.35, .45, .95], "posture_head": True},                              # .95 + .10 >= 1
    {"tau_phase": PHASE, "posture_head": True, "posture_dtau": [.1, 0, -.4]}])         # .35 - .40 <= 0
def test_validation(bad):
    with pytest.raises(SystemExit, match="tau_phase"):
        RL.tau_phase_cfg(bad)


def test_validation_ok_and_load_config():
    assert RL.tau_phase_cfg({}) is None and RL.tau_phase_cfg({"tau_phase": None}) is None
    assert RL.tau_phase_cfg({"tau_phase": (.35, .45, .55), "posture_head": True}) == PHASE
    y = REPO / "pipeline" / "rl_royale.yaml"
    assert RL.load_config(y, ["tau_phase=[0.35, 0.45, 0.55]"], False)["tau_phase"] == PHASE
    with pytest.raises(SystemExit, match="tau_phase"):
        RL.load_config(y, ["tau_phase=[0.35, 0.45, 1.5]"], False)
