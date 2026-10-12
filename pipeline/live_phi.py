"""Offline-fitted state potential. No policy, live-loop or actor dependencies.

The 35 inputs are a fixed projection of the policy's public observation encoding:
25 clock/elixir/tower scalars and count/HP/x/y/deploying sums of its body tokens
for each side. No actions, labels, match IDs or opponent private state enter Phi.
"""
from pathlib import Path

import torch
from torch import nn

SC_COLS = tuple(range(7)) + tuple(range(52, 70))
FEATURE_DIM = 35
SCHEMA = "livephi-public-board-v1"
DEFAULT_CHECKPOINT = "scratchpad/gauntlet/L74/livephi/phi_live.pt"


def features(batch):
    sc, tok, mask = batch["sc"], batch["tok"], batch["mask"]
    parts = [sc[:, SC_COLS]]
    for side in (1, 2):
        w = mask.to(tok.dtype) * tok[..., side] * (1 - tok[..., 13])
        parts.append(torch.stack([w.sum(1), (w * tok[..., 6]).sum(1),
                                  (w * tok[..., 4]).sum(1), (w * tok[..., 5]).sum(1),
                                  (w * tok[..., 8]).sum(1)], 1))
    return torch.cat(parts, 1)


class LivePhi(nn.Module):
    def __init__(self, hidden=32):
        super().__init__()
        self.hidden = int(hidden)
        self.register_buffer("mean", torch.zeros(FEATURE_DIM))
        self.register_buffer("scale", torch.ones(FEATURE_DIM))
        self.register_buffer("calibration", torch.tensor([1.0, 0.0]))
        self.net = nn.Sequential(nn.Linear(FEATURE_DIM, hidden), nn.Tanh(), nn.Linear(hidden, 1))

    def logits(self, x):
        return self.net((x - self.mean) / self.scale).squeeze(-1)

    def probability(self, x):
        return torch.sigmoid(self.calibration[0] * self.logits(x) + self.calibration[1])

    def forward(self, batch):
        return 2.0 * self.probability(features(batch)) - 1.0


def load(path, device="cpu", feature_version=None):
    ck = torch.load(Path(path), map_location="cpu", weights_only=True)
    if ck.get("schema") != SCHEMA or ck.get("feature_dim") != FEATURE_DIM:
        raise ValueError("incompatible live_phi public feature schema")
    if feature_version is not None and int(feature_version) not in ck["feature_versions"]:
        raise ValueError("live_phi feature_version differs from the fitted public encoding")
    model = LivePhi(ck["hidden"])
    model.load_state_dict(ck["state_dict"])
    model.to(device).eval().requires_grad_(False)
    return model
