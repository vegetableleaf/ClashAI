"""The deploy rule viewers and graders apply to a PPO gate -- ONE implementation for sim_view,
policy-stats and the L62 gate_probe, because three greedy copies is how HANDOFF §5cs.46 happened.

`sim.ppo_gate_rule`: "sample" (owner ruling 2026-09-05) draws play ~ Bernoulli(sigmoid(g1-g0)) from a
seeded torch.Generator so a viewing run is reproducible; "threshold" is the old
`sigmoid(g1-g0) > sim.ppo_gate_threshold`. Card and cell are the caller's argmax either way.
"""
import torch


class GateRule:
    def __init__(self, cfg, seed: int = 0):
        self.rule = str(cfg.get("sim", "ppo_gate_rule", default="threshold") or "threshold").lower()
        self.tau = float(cfg.get("sim", "ppo_gate_threshold", default=0.25))
        if self.rule not in ("sample", "threshold"):
            raise ValueError(f"sim.ppo_gate_rule must be sample|threshold, got {self.rule!r}")
        self.gen = torch.Generator().manual_seed(int(seed))

    def describe(self) -> str:
        return ("PPO play ~ Bernoulli(sigmoid(play-wait)), seeded" if self.rule == "sample"
                else f"PPO sigmoid(play-wait) > {self.tau}")

    @staticmethod
    def p_play(gq) -> float:
        return float(torch.sigmoid(gq[1] - gq[0]))

    def play(self, gq) -> bool:
        p = self.p_play(gq)
        if self.rule == "sample":
            return bool(torch.rand(1, generator=self.gen).item() < p)
        return p > self.tau
