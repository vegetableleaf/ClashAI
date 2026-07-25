"""Optional deep-learning backend for transition timing (requires PyTorch).

A minimal DQN that maps a one-hot transition id to Q-values over the candidate
wait durations. It exposes the same choose()/update() interface as
`TimingLearner`, so it is a drop-in replacement when
``learning.backend: "dqn"`` is set in config.yaml.

This is intentionally small: each timing decision is treated as an independent
(bandit-style) bootstrap-free step, which is stable and easy to reason about
while still being a real neural policy you can extend toward full deep RL.
"""
from __future__ import annotations

import random
from typing import List, Tuple

import torch
import torch.nn as nn


class _Net(nn.Module):
    def __init__(self, n_in: int, n_out: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_in, 32), nn.ReLU(),
            nn.Linear(32, 32), nn.ReLU(),
            nn.Linear(32, n_out),
        )

    def forward(self, x):  # noqa: D401
        return self.net(x)


class DQNTimingPolicy:
    def __init__(self, cfg):
        self.cfg = cfg
        self.candidates: List[float] = list(
            cfg.get("learning", "candidate_delays", default=[0.3, 0.5, 0.8, 1.2, 1.8, 2.5])
        )
        self.names: List[str] = list(
            cfg.get("learning", "transitions", default=["home_to_party", "party_to_queue", "results_to_home"])
        )
        self.epsilon = float(cfg.get("learning", "epsilon", default=0.15))
        self.lr = float(cfg.get("learning", "lr", default=1e-3))
        self.path = cfg.path("dqn_state.pt")
        self.net = _Net(len(self.names), len(self.candidates))
        self.opt = torch.optim.Adam(self.net.parameters(), lr=self.lr)
        self.loss_fn = nn.MSELoss()
        self._load()

    def _state(self, name: str) -> torch.Tensor:
        v = torch.zeros(len(self.names))
        if name in self.names:
            v[self.names.index(name)] = 1.0
        return v

    def choose(self, name: str) -> Tuple[int, float]:
        if random.random() < self.epsilon:
            i = random.randrange(len(self.candidates))
        else:
            with torch.no_grad():
                i = int(torch.argmax(self.net(self._state(name))).item())
        return i, self.candidates[i]

    def update(self, name: str, arm_index: int, success: bool, waited: float) -> None:
        reward = (1.0 - min(waited, 3.0) / 3.0) if success else -1.0
        q = self.net(self._state(name))
        target = q.detach().clone()
        target[arm_index] = reward
        loss = self.loss_fn(q, target)
        self.opt.zero_grad()
        loss.backward()
        self.opt.step()
        self._save()

    def _load(self) -> None:
        try:
            if self.path.exists():
                self.net.load_state_dict(torch.load(self.path))
        except Exception:  # noqa: BLE001
            pass

    def _save(self) -> None:
        try:
            torch.save(self.net.state_dict(), self.path)
        except Exception:  # noqa: BLE001
            pass
