"""L31 VARIANT of tools/gate_prior_probe.py: TRAINING-STYLE opponents (adaptive=True) at PROBE_FLOOR. Original doc:
P(play | elixir bucket, phase) as the POLICY actually samples it, next to the pro table.

The watchdog reads one P(play) mean per checkpoint; the trainer's `GATE PRIOR CE` line reads
pi(play) only on rows where something is affordable, cumulative since start. Neither shows the
SHAPE the gate-prior run (HANDOFF 5bf) is trying to change: how often the gate opens at 1 elixir
vs 4 vs 8. This probe does, with the watchdog's own sampler (6 envs x 400 steps, seeds 4242+i,
card from the card head, gate SAMPLED, plays at the centre cell) so the reading is on the same
instrument as data/ppo_watchdog.log -- plus what the watchdog does not record: whether anything
was affordable on each row, which is exactly the "N% of rows usable" the trainer prints.

    .venv/Scripts/python.exe tools/gate_prior_probe.py data/policy_gate_20260902.pt
    .venv/Scripts/python.exe tools/gate_prior_probe.py data/policy_real_20260901.pt --seed 1

np.random is seeded (the watchdog's is not -- part of its noise floor, HANDOFF 8), so two
checkpoints read on the same --seed face the same coin flips where their gates agree.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(r"C:/Users/benpe/ClashBot/icebow")
sys.path.insert(0, str(_ROOT / "src"))

import numpy as np                                      # noqa: E402
import torch                                            # noqa: E402


def probe(ckpt: Path, envs: int = 6, steps: int = 400, seed: int = 0,
          force_bank: float = 0.0) -> dict:
    import torch.nn as nn
    from clashrl.config import Config
    from clashrl.model import PolicyNet
    from clashrl.sim.env import SimMatchEnv

    np.random.seed(seed)
    cfg = Config.load(_ROOT / "config" / "config.yaml")
    cfg.data.setdefault("action", {})["grid"] = [18, 24]
    # L31 VARIANT: the TRAINING opponent (make_opponent adaptive=True, so sim.bot_attack_floor applies) instead of
    # the env's default non-adaptive bots. Floor from env PROBE_FLOOR (default 0 = the historical training bot).
    import os as _os
    from clashrl.sim.opponents import make_opponent as _mk
    cfg.data.setdefault("sim", {})["bot_attack_floor"] = float(_os.environ.get("PROBE_FLOOR", "0"))
    reg = float(cfg.get("sim", "regulation_s", default=180.0))
    ot = float(cfg.get("sim", "overtime_s", default=120.0))
    dbl, tri = reg - 60.0, reg + max(0.0, ot - 60.0)
    state = torch.load(ckpt, map_location="cpu", weights_only=False)
    pool = [SimMatchEnv(cfg, seed=4242 + i) for i in range(envs)]
    for _e in pool:
        _e.opponent_provider = lambda env: _mk(cfg, env.db, env.rng, env.meta_pool, adaptive=True)
    e0 = pool[0]
    for e in pool:
        if getattr(e, "domain_rand", None) is not None:
            e.domain_rand.enabled = False
            e.domain_rand.resample()
    in_ch = int(state.get("in_ch") or 12)
    thr_dim = int(state.get("threat_dim") or e0.threat_dim)

    class PPONet(nn.Module):
        def __init__(self):
            super().__init__()
            self.policy = PolicyNet(in_ch, e0.n_cards, e0.n_cells, threat_dim=thr_dim)
            self.gate = nn.Linear(self.policy.embed_dim, 2)

        def forward(self, x, hand, nxt, elx, thr):
            z, cards, cells = self.policy.forward_parts(x, hand, nxt, elx, thr)
            return cards, cells, self.gate(z)

    net = PPONet()
    net.policy.load_state_dict(state["model"])
    if "gate" in state:
        net.gate.load_state_dict(state["gate"])
    net.eval()

    def obs_t(o):
        x = np.asarray(o)
        if x.shape[2] > in_ch:
            x = x[:, :, :in_ch]
        elif x.shape[2] < in_ch:
            x = np.concatenate([x, np.zeros((x.shape[0], x.shape[1], in_ch - x.shape[2]),
                                            dtype=x.dtype)], axis=2)
        return torch.from_numpy(x).float().permute(2, 0, 1) / 255.0

    def thr_t(v):
        t = np.asarray(v, np.float32)
        return torch.from_numpy(t[:thr_dim] if t.shape[0] > thr_dim
                                else np.pad(t, (0, thr_dim - t.shape[0])))

    # COUNTERFACTUAL BANK (--force-bank X): suppress every play below X elixir, then let the policy
    # act normally. The gate prior's THEORY OF CHANGE is "if it waits, it will play the expensive
    # win conditions"; that is a claim about the CARD head at an elixir level this policy never
    # reaches, so it cannot be read off the unforced rollout. This forces the states and reads what
    # the card head does there. It is a probe, not a policy: nothing is trained here.
    # rows: (phase, bucket, p_play, affordable, played, elixir)
    rows = []
    picks = []                                          # (bucket, card_id) for rows that played
    obs = [e.reset() for e in pool]
    with torch.no_grad():
        for _ in range(steps):
            xb = torch.stack([obs_t(o) for o in obs])
            hb = torch.stack([torch.from_numpy(np.asarray(e.hand_vec, np.float32)) for e in pool])
            nb = torch.stack([torch.from_numpy(np.asarray(e.next_vec, np.float32)) for e in pool])
            eb = torch.stack([torch.from_numpy(np.asarray(e.elixir_vec, np.float32)) for e in pool])
            tb = torch.stack([thr_t(e.threat_vec) for e in pool])
            cq, _ceq, gq = net(xb, hb, nb, eb, tb)
            pg = torch.softmax(gq, dim=1)[:, 1].numpy()
            pc = torch.softmax(cq, dim=1).numpy()
            for i, e in enumerate(pool):
                elx = float(e.eng.elixir[0])
                t = float(getattr(e.eng, "t", 0.0))
                ph = 2 if t >= tri else (1 if t >= dbl else 0)
                b = int(np.clip(np.floor(elx + 1e-6), 0, 10))
                hand = [c for c in e._hand_ids()
                        if 0 <= c < len(e.specs) and elx >= e.specs[c].elixir]
                if hand:
                    w = np.asarray([pc[i][c] for c in hand], dtype=np.float64)
                    w = w / w.sum() if w.sum() > 0 else None
                    pick = int(np.random.choice(hand, p=w)) if w is not None else int(hand[0])
                else:
                    pick = None
                play = bool(hand) and bool(np.random.random() < pg[i])
                if force_bank > 0.0 and elx < force_bank:
                    play = False
                rows.append((ph, b, float(pg[i]), bool(hand), bool(play), elx))
                if play and pick is not None:
                    picks.append((b, int(pick)))
                act = (1, pick, int(e0.n_cells // 2)) if (play and pick is not None) else (0, 0, 0)
                nobs, _r, done, _i = e.step(act)
                obs[i] = e.reset() if done else nobs
    a = np.asarray(rows, dtype=np.float64)
    ph, b, pg_, aff, pl, ex = a.T
    out = {"ckpt": str(ckpt), "matches": int(state.get("matches") or 0), "rows": int(len(a)),
           "seed": seed, "affordable_frac": float(aff.mean()),
           "p_play_mean_all": float(pg_.mean()),
           "p_play_mean_affordable": float(pg_[aff > 0.5].mean()) if aff.any() else None,
           "played_frac": float(pl.mean()),
           "elixir_mean": float(ex.mean()), "elixir_ge6": float((ex >= 6.0).mean()),
           "phase_rows": [int((ph == k).sum()) for k in range(3)],
           "force_bank": float(force_bank),
           "cost_of_plays": None, "picks_by_bucket": {}, "card_names": [], "by_bucket": {}}
    names = [str(getattr(sp, "key", i)) for i, sp in enumerate(e0.specs)]
    costs = [float(sp.elixir) for sp in e0.specs]
    out["card_names"] = names
    if picks:
        out["cost_of_plays"] = float(np.mean([costs[c] for _b, c in picks]))
        for lo, hi, lab in ((0, 3, "<3"), (3, 6, "3-5"), (6, 11, ">=6")):
            sel = [c for b_, c in picks if lo <= b_ < hi]
            if sel:
                cnt = {}
                for c in sel:
                    cnt[names[c]] = cnt.get(names[c], 0) + 1
                out["picks_by_bucket"][lab] = {
                    "n": len(sel), "mean_cost": float(np.mean([costs[c] for c in sel])),
                    "top": sorted(cnt.items(), key=lambda kv: -kv[1])[:4]}
    for k in range(11):
        m = b == k
        out["by_bucket"][k] = {
            "rows": int(m.sum()),
            "p_play": float(pg_[m].mean()) if m.any() else None,
            "affordable": float(aff[m].mean()) if m.any() else None,
            "played": float(pl[m].mean()) if m.any() else None,
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ckpt")
    ap.add_argument("--envs", type=int, default=6)
    ap.add_argument("--steps", type=int, default=400)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--prior", default="config/gate_prior.json")
    ap.add_argument("--force-bank", type=float, default=0.0,
                    help="counterfactual: suppress plays below this elixir (probe only)")
    ap.add_argument("--json", default=None, help="also dump the full dict here")
    a = ap.parse_args()
    r = probe(Path(a.ckpt), a.envs, a.steps, a.seed, a.force_bank)
    prior = None
    pp = _ROOT / a.prior
    if pp.exists():
        prior = json.loads(pp.read_text(encoding="utf-8"))["p_play"]["single"]
    print("%s  matches=%d  rows=%d  seed=%d%s" % (r["ckpt"], r["matches"], r["rows"], r["seed"],
          "  FORCE-BANK %.0f" % r["force_bank"] if r["force_bank"] else ""))
    print("  affordable on %.1f%% of rows | P(play) mean %.3f (all) %.3f (affordable rows) | "
          "played on %.1f%% of rows | elixir mean %.2f  >=6 %.1f%% | phase rows %s"
          % (100 * r["affordable_frac"], r["p_play_mean_all"],
             r["p_play_mean_affordable"] if r["p_play_mean_affordable"] is not None else float("nan"),
             100 * r["played_frac"], r["elixir_mean"], 100 * r["elixir_ge6"], r["phase_rows"]))
    print("  bucket  rows  P(play)  affordable  played   pro(single)")
    for k in range(11):
        d = r["by_bucket"][k]
        f = lambda v: "  -  " if v is None else "%.3f" % v
        print("  %5d  %5d   %s     %s     %s    %s" % (
            k, d["rows"], f(d["p_play"]), f(d["affordable"]), f(d["played"]),
            "%.3f" % prior[k] if prior else "-"))
    if r["cost_of_plays"] is not None:
        print("  mean cost of the cards actually played: %.2f (deck mean %.2f)"
              % (r["cost_of_plays"], float(np.mean([1, 2, 3, 3, 3, 4, 4, 6, 6, 3]))))
        for lab in ("<3", "3-5", ">=6"):
            d = r["picks_by_bucket"].get(lab)
            if d:
                print("    plays at %-4s n=%-4d mean cost %.2f  %s"
                      % (lab, d["n"], d["mean_cost"],
                         " ".join("%s:%d" % (k, v) for k, v in d["top"])))
    if a.json:
        Path(a.json).write_text(json.dumps(r, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
