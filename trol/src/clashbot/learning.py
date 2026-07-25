"""Adaptive learning for transition timing.

Goal (from the spec): "maximize the speed at which it can transition from the
end of one match to the start of another." Each menu/queue button press is
followed by a wait before the bot checks whether the expected state was
reached. Waiting too long is slow; waiting too little makes the click land
before the UI is ready (a failure that forces a costly retry).

`TimingLearner` treats each named transition as a multi-armed bandit whose
arms are candidate wait durations. It learns the fastest wait that still
succeeds reliably, and persists what it has learned across sessions.
"""
from __future__ import annotations

import json
import random
from typing import Dict, List, Tuple


class TimingLearner:
    def __init__(self, cfg):
        self.cfg = cfg
        self.epsilon = float(cfg.get("learning", "epsilon", default=0.15))
        self.candidates: List[float] = list(
            cfg.get("learning", "candidate_delays", default=[0.3, 0.5, 0.8, 1.2, 1.8, 2.5])
        )
        self.state_path = cfg.path(cfg.get("learning", "state_file", default="learning_state.json"))
        # stats[name] -> list of {"n": count, "q": value estimate} per candidate
        self.stats: Dict[str, List[dict]] = {}
        self._load()

    def _arms(self, name: str) -> List[dict]:
        if name not in self.stats or len(self.stats[name]) != len(self.candidates):
            self.stats[name] = [{"n": 0, "q": 0.0} for _ in self.candidates]
        return self.stats[name]

    def choose(self, name: str) -> Tuple[int, float]:
        arms = self._arms(name)
        if random.random() < self.epsilon or all(a["n"] == 0 for a in arms):
            i = random.randrange(len(self.candidates))
        else:
            i = max(range(len(arms)), key=lambda k: arms[k]["q"])
        return i, self.candidates[i]

    def update(self, name: str, arm_index: int, success: bool, waited: float) -> None:
        # Reward: successful + fast is best; failure is heavily penalized.
        reward = (1.0 - min(waited, 3.0) / 3.0) if success else -1.0
        arm = self._arms(name)[arm_index]
        arm["n"] += 1
        arm["q"] += (reward - arm["q"]) / arm["n"]
        self._save()

    def _load(self) -> None:
        try:
            if self.state_path.exists():
                self.stats = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            self.stats = {}

    def _save(self) -> None:
        try:
            self.state_path.write_text(json.dumps(self.stats, indent=2), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass


def make_learner(cfg):
    """Factory: return the configured learning backend (falls back to bandit)."""
    if cfg.get("learning", "backend", default="bandit") == "dqn":
        try:
            from .dqn import DQNTimingPolicy
            return DQNTimingPolicy(cfg)
        except Exception as exc:  # noqa: BLE001
            print(f"[learning] DQN backend unavailable ({exc}); using bandit.")
    return TimingLearner(cfg)
