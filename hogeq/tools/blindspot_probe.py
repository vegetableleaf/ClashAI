"""Is the beatdown blind spot actually costing anything?  `python tools/blindspot_probe.py`

WHAT THIS CAN AND CANNOT ANSWER. Changing a reward does not change a FIXED policy's play, so no
amount of policy-stats can show "win rate if the reward could see a Giant" without retraining.
Two things it CAN settle, and both gate the labelling decision:

  1. IS THE BLIND SPOT LIVE? Over real matches, how often is an enemy WIN CONDITION committed on
     our half while the reward's own threat vector (`_threat_id_true`, filtered through
     observation.detector_cards) reads NOTHING? That is a property of the opponent pool and the
     whitelist, not of our policy, so it is measured directly. If it is ~0%, the labelling is not
     worth an afternoon whatever else is true.

  2. IS BEATDOWN WHERE WE LOSE? Win rate against decks containing the four unlabelled cards
     (giant / golem / royal_giant / graveyard) versus everything else, same policy, same run.

Run it against the CURRENT checkpoint -- the old champion predates the per-card cell head and
would load with a random placement head, which would make every number meaningless.
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from clashrl.config import Config          # noqa: E402

BLIND = ("giant", "golem", "royal_giant", "graveyard")


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="data/policy_sim_ppo.pt")
    ap.add_argument("--matches", type=int, default=120)
    ap.add_argument("--envs", type=int, default=24)
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args(argv)

    import torch
    from clashrl import card_threat
    from clashrl.sim.env import SimMatchEnv
    from clashrl.train_rl import _build_net

    cfg = Config.load()
    ck_path = cfg.path(a.ckpt)
    if not ck_path.exists():
        print("no checkpoint at %s" % ck_path)
        return 2
    ck = torch.load(ck_path, map_location="cpu")

    pool = [SimMatchEnv(cfg, seed=a.seed + i) for i in range(a.envs)]
    e0 = pool[0]
    net = _build_net(cfg, "cpu", e0.n_cards, e0.n_cells, e0.threat_dim, int(e0.obs_shape[2]))
    net.policy.load_state_dict(ck["model"])
    if "gate" in ck:
        net.gate.load_state_dict(ck["gate"])
    net.eval()
    gate_tau = float(cfg.get("sim", "ppo_gate_threshold", default=0.25))
    yourhalf = torch.tensor(e0.actions.deployable_mask(False), dtype=torch.bool)
    allcells = torch.ones(e0.n_cells, dtype=torch.bool)
    anywhere = set(e0.anywhere_ids)
    costs = torch.tensor([float(s.elixir) for s in e0.specs])

    def wincon_committed(env):
        """Ground truth: an enemy WIN CONDITION is over the river and on our side."""
        for u in env.eng.units:
            if u.team == 1 and u.hp > 0 and u.y > 0.46 \
                    and card_threat.profile(env.db, u.spec.base).win_condition:
                return u.spec.base
        return None

    seen_lit = collections.Counter()          # base -> steps the reward COULD see something
    seen_blind = collections.Counter()        # base -> steps it read nothing at all
    outcomes = {"blind": [0, 0], "other": [0, 0]}   # [wins, matches]
    played = 0
    obs = [e.reset() for e in pool]

    def deck_is_blind(env):
        return any(b in BLIND for b in (getattr(env.opponent, "cards", None) or []))

    tags = [deck_is_blind(e) for e in pool]

    while played < a.matches:
        with torch.no_grad():
            cq, ceq, gq = net(
                torch.stack([torch.from_numpy(o).float().div(255).permute(2, 0, 1) for o in obs]),
                torch.stack([torch.from_numpy(e.hand_vec).float() for e in pool]),
                torch.stack([torch.from_numpy(e.next_vec).float() for e in pool]),
                torch.stack([torch.from_numpy(e.elixir_vec).float() for e in pool]),
                torch.stack([torch.from_numpy(e.threat_vec).float() for e in pool]))
        for i, env in enumerate(pool):
            # -- the measurement, taken BEFORE acting --------------------------------
            base = wincon_committed(env)
            if base is not None:
                tid = env._threat_id_true
                lit = tid is not None and len(tid) and float(tid[0]) >= 0.5
                (seen_lit if lit else seen_blind)[base] += 1
            # -- greedy action, same rule as policy-stats ---------------------------
            afford = (torch.from_numpy(env.hand_vec).float() > 0.5) & (costs <= env.eng.elixir[0] + 1e-6)
            if not bool(afford.any()) or \
                    float(torch.sigmoid(gq[i, 1] - gq[i, 0])) <= gate_tau:
                act = (0, 0, 0)
            else:
                ci = int(cq[i].masked_fill(~afford, float("-inf")).argmax())
                cm = allcells if ci in anywhere else yourhalf
                act = (1, ci, int(ceq[i, ci].masked_fill(~cm, float("-inf")).argmax()))
            _, _, done, info = env.step(act)
            if done:
                key = "blind" if tags[i] else "other"
                outcomes[key][1] += 1
                outcomes[key][0] += int(info.get("outcome") == "win")
                played += 1
                obs[i] = env.reset()
                tags[i] = deck_is_blind(env)
            else:
                obs[i] = env._last_obs
    for e in pool:
        pass

    lit, blind = sum(seen_lit.values()), sum(seen_blind.values())
    tot = lit + blind
    print("\n== 1. IS THE BLIND SPOT LIVE? ==")
    print("steps with an enemy WIN CONDITION committed on our half: %d" % tot)
    if tot:
        print("   reward saw a threat : %5d  (%.1f%%)" % (lit, 100.0 * lit / tot))
        print("   reward saw NOTHING  : %5d  (%.1f%%)   <- the blind spot" % (blind, 100.0 * blind / tot))
        print("\n   most-committed win conditions the reward could NOT see:")
        for k, n in seen_blind.most_common(8):
            print("      %-16s %5d" % (k, n))
        if seen_lit:
            print("   ...and the ones it could:")
            for k, n in seen_lit.most_common(6):
                print("      %-16s %5d" % (k, n))

    print("\n== 2. IS BEATDOWN WHERE WE LOSE? ==")
    for key, label in (("blind", "vs decks WITH giant/golem/RG/graveyard"),
                       ("other", "vs every other deck")):
        w, m = outcomes[key]
        if m:
            se = (w / m * (1 - w / m) / m) ** 0.5 * 100
            print("   %-38s %3d/%-3d = %5.1f%%  (+/- %.1f)" % (label, w, m, 100.0 * w / m, 1.96 * se))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
