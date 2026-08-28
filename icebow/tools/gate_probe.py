"""Diagnostic probe: measure the PPO gate's play-probability distribution and the
elixir trajectory it produces. Read-only -- writes nothing, trains nothing.

Answers: has the gate collapsed to always-play, and does elixir ever reach the
6 needed for X-Bow / Rocket?
"""
from __future__ import annotations

from pathlib import Path
import sys

# Allow direct execution via `python tools/gate_probe.py` from the icebow root.
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import numpy as np
import torch
import torch.nn as nn

from clashrl.config import Config
from clashrl.model import PolicyNet
from clashrl.sim.env import SimMatchEnv
from clashrl.train_rl import _pick_device


def main(ckpt="data/policy_sim_ppo.pt", matches=8, envs=4, size="432"):
    cfg_path = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
    cfg = Config.load(cfg_path)
    if size == "432":
        cfg.data.setdefault("action", {})["grid"] = [18, 24]

    pool = [SimMatchEnv(cfg, seed=4242 + i) for i in range(envs)]
    e0 = pool[0]
    for e in pool:
        if getattr(e, "domain_rand", None) is not None:
            e.domain_rand.enabled = False
            e.domain_rand.resample()

    device = _pick_device(cfg)

    ck_path = Path(ckpt)
    if not ck_path.is_absolute():
        ck_path = cfg.path(str(ck_path))
    state = torch.load(ck_path, map_location="cpu", weights_only=True)
    model_sd = state.get("model") or {}
    conv0_w = model_sd.get("features.0.weight")
    ck_in_ch = int(state.get("in_ch", 0) or 0)
    if ck_in_ch <= 0:
        ck_in_ch = int(conv0_w.shape[1]) if conv0_w is not None and hasattr(conv0_w, "shape") else 3
    thr_w = model_sd.get("threat_fc.0.weight")
    ck_threat_dim = int(state.get("threat_dim", 0) or 0)
    if ck_threat_dim <= 0:
        ck_threat_dim = int(thr_w.shape[1]) if thr_w is not None and hasattr(thr_w, "shape") else int(e0.threat_dim)

    class PPONet(nn.Module):
        def __init__(self):
            super().__init__()
            self.policy = PolicyNet(ck_in_ch, e0.n_cards, e0.n_cells, threat_dim=ck_threat_dim)
            self.gate = nn.Linear(self.policy.embed_dim, 2)
            self.value = nn.Linear(self.policy.embed_dim, 1)

        def forward(self, x, hand, nxt=None, elx=None, thr=None):
            # `cell_head` HAS NOT EXISTED since the spatial-cell refactor, and `features_vec`
            # discards the pre-pool feature map that head needs -- PolicyNet.forward_parts says so
            # in its own docstring. This probe kept calling both and raised AttributeError on every
            # invocation, so the gate diagnostic has been dead for as long as that refactor is old.
            z, cards, cells = self.policy.forward_parts(x, hand, nxt, elx, thr)
            return cards, cells, self.gate(z), self.value(z).squeeze(-1)

    net = PPONet().to(device)
    net.policy.load_state_dict(state["model"])
    if "gate" in state:
        net.gate.load_state_dict(state["gate"])
    net.eval()

    costs = np.asarray([float(s.elixir) for s in e0.specs], np.float32)
    wincon = [i for i, k in enumerate(e0.deck_keys) if k in ("x_bow", "rocket")]

    def obs_t(o):
        x = np.asarray(o)
        if x.shape[2] > ck_in_ch:
            x = x[:, :, :ck_in_ch]
        elif x.shape[2] < ck_in_ch:
            pad = np.zeros((x.shape[0], x.shape[1], ck_in_ch - x.shape[2]), dtype=x.dtype)
            x = np.concatenate([x, pad], axis=2)
        return torch.from_numpy(x).float().permute(2, 0, 1).to(device) / 255.0

    def vec_t(v):
        return torch.from_numpy(np.asarray(v, np.float32)).to(device)

    def thr_t(v):
        t = np.asarray(v, np.float32)
        if t.shape[0] > ck_threat_dim:
            t = t[:ck_threat_dim]
        elif t.shape[0] < ck_threat_dim:
            t = np.pad(t, (0, ck_threat_dim - t.shape[0]))
        return torch.from_numpy(t).to(device)

    obs = [e.reset() for e in pool]
    p_play, elixir_trace = [], []
    wincon_affordable = 0
    wincon_in_hand = 0
    steps = 0
    done_n = 0

    while done_n < matches:
        with torch.no_grad():
            _, _, gq, _ = net(
                torch.stack([obs_t(o) for o in obs]),
                torch.stack([vec_t(e.hand_vec) for e in pool]),
                torch.stack([vec_t(e.next_vec) for e in pool]),
                torch.stack([vec_t(e.elixir_vec) for e in pool]),
                torch.stack([thr_t(e.threat_vec) for e in pool]),
            )
            probs = torch.sigmoid(gq[:, 1] - gq[:, 0]).cpu().numpy()

        for i, e in enumerate(pool):
            steps += 1
            p_play.append(float(probs[i]))
            elixir_trace.append(float(e.elixir))
            hand = [c for c in range(e0.n_cards) if e.hand_vec[c] > 0.5]
            held = [c for c in wincon if c in hand]
            if held:
                wincon_in_hand += 1
                if any(costs[c] <= e.elixir + 1e-6 for c in held):
                    wincon_affordable += 1

            # follow the policy's own greedy behaviour to advance the state
            aff = [c for c in hand if costs[c] <= e.elixir + 1e-6]
            if aff and probs[i] > 0.25:
                act = (1, int(aff[0]), int(e0.n_cells // 2))
            else:
                act = (0, 0, 0)
            nobs, _, done, _ = e.step(act)
            obs[i] = e.reset() if done else nobs
            done_n += int(done)

    p = np.asarray(p_play)
    x = np.asarray(elixir_trace)
    print(f"steps={steps} matches={done_n}")
    print("P(play) percentiles: "
          + " ".join(f"p{q}={np.percentile(p, q):.3f}" for q in (5, 25, 50, 75, 95)))
    print(f"P(play) mean={p.mean():.3f}  min={p.min():.3f}  max={p.max():.3f}")
    print(f"share of steps with P(play)>0.25: {(p > 0.25).mean():.1%}")
    print(f"share of steps with P(play)>0.60: {(p > 0.60).mean():.1%}")
    print(f"share of steps with P(play)>0.95: {(p > 0.95).mean():.1%}")
    print()
    print("elixir percentiles: "
          + " ".join(f"p{q}={np.percentile(x, q):.2f}" for q in (5, 25, 50, 75, 95)))
    print(f"elixir mean={x.mean():.2f}  max={x.max():.2f}")
    print(f"share of steps elixir>=6 (X-Bow/Rocket affordable): {(x >= 6).mean():.2%}")
    print()
    print(f"steps with x_bow/rocket IN HAND: {wincon_in_hand} "
          f"({wincon_in_hand / max(1, steps):.1%})")
    print(f"steps with x_bow/rocket IN HAND *and affordable*: {wincon_affordable} "
          f"({wincon_affordable / max(1, steps):.2%})")


if __name__ == "__main__":
    main()
