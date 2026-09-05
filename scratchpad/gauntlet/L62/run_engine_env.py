"""L62 driver / measurement harness for EngineMatchEnv.

Modes:
  map    -- cell <-> engine (x, y) round-trip on real pro plays (no engine needed)
  smoke  -- one match with the greedy policy, verbose
  det    -- N repeats of the same tag with the same policy: final state-hash equality
  bench  -- M matches: wall clock, ghost rejection stats, outcome sanity

    cd icebow && PYTHONHASHSEED=0 ./.venv/Scripts/python.exe ../scratchpad/gauntlet/L62/run_engine_env.py bench \
        --matches 20 --port 38031 --out ../scratchpad/gauntlet/L62/bench_slot0.json
"""
from __future__ import annotations

import argparse, json, statistics, sys, time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from engine_env import EngineMatchEnv, load_pool, V2, key_base   # noqa: E402

ROOT = HERE.parents[2]
CKPT = ROOT / "icebow" / "data" / "bc_pro" / "models" / "bc_bias_native_s0.pt"
_NEG = -1e9


# --------------------------------------------------------------------------------- greedy policy
class GreedyPolicy:
    """The trainer's greedy action, reproduced from train_sim_ppo.masked_logits + choose_greedy:
    card = argmax over cards that are IN HAND and AFFORDABLE; cell = argmax over the DEPLOYABLE cells
    of that card (per-card logit map); play/wait = argmax of the checkpoint's gate head."""

    def __init__(self, env, ckpt=CKPT, device="cpu"):
        from clashrl.model import PolicyNet
        ck = torch.load(str(ckpt), map_location="cpu", weights_only=False)
        self.meta = {k: ck[k] for k in ("in_ch", "n_cards", "n_cells", "threat_dim", "grid", "algo") if k in ck}
        assert int(ck["n_cards"]) == env.n_cards and int(ck["n_cells"]) == env.n_cells \
            and int(ck["threat_dim"]) == env.threat_dim, (self.meta, env.n_cards, env.n_cells, env.threat_dim)
        assert list(ck["deck"]) == list(env.deck_keys), (ck["deck"], env.deck_keys)
        self.dev = torch.device(device)
        self.net = PolicyNet(in_ch=int(ck["in_ch"]), n_cards=int(ck["n_cards"]),
                             n_cells=int(ck["n_cells"]), threat_dim=int(ck["threat_dim"]))
        self.net.load_state_dict(ck["model"])
        self.net = self.net.to(self.dev).eval()
        self.gate = nn.Linear(self.net.embed_dim, 2)
        self.gate.load_state_dict({k: v for k, v in ck["gate"].items()})
        self.gate = self.gate.to(self.dev).eval()
        self.costs = torch.tensor([float(s.elixir) for s in env.sim.specs], dtype=torch.float32, device=self.dev)
        self.anywhere = set(env.anywhere_ids)
        self.env = env
        self._cellmask = {}

    def cellmask(self, card_id, pocket_code):
        key = (card_id in self.anywhere, pocket_code)
        if key not in self._cellmask:
            m = self.env.actions.deployable_mask(key[0], (bool(pocket_code & 2), bool(pocket_code & 1)))
            self._cellmask[key] = torch.tensor(m, dtype=torch.bool, device=self.dev)
        return self._cellmask[key]

    @torch.no_grad()
    def act(self, env, obs):
        x = (torch.as_tensor(obs, device=self.dev).unsqueeze(0)
             .permute(0, 3, 1, 2).contiguous().float() / 255.0)   # HWC -> NCHW, as train_sim_ppo does
        hand = torch.as_tensor(env.hand_vec, device=self.dev).unsqueeze(0)
        nxt = torch.as_tensor(env.next_vec, device=self.dev).unsqueeze(0)
        elx = torch.as_tensor(env.elixir_vec, device=self.dev).unsqueeze(0)
        thr = torch.as_tensor(env.threat_vec, device=self.dev).unsqueeze(0)
        z, cards, cells = self.net.forward_parts(x, hand, nxt, elx, thr)
        gq = self.gate(z)
        elixir = elx * 10.0
        playable = (hand > 0.5) & (self.costs.view(1, -1) <= elixir + 1e-6)
        if not bool(playable.any()):
            return (0, 0, 0)
        if float(gq[0, 1]) <= float(gq[0, 0]):
            return (0, 0, 0)
        card = int(cards.masked_fill(~playable, _NEG).argmax(1))
        pk = env.sim.pocket_state(0)
        cm = self.cellmask(card, (2 if pk[0] else 0) + (1 if pk[1] else 0))
        cell = int(cells[0, card].masked_fill(~cm, _NEG).argmax())
        return (1, card, cell)


class RandomPolicy:
    def __init__(self, env, seed=0):
        import random
        self.r = random.Random(seed)
        self.env = env

    def act(self, env, obs):
        if self.r.random() < 0.5:
            return (0, 0, 0)
        ids = [i for i, v in enumerate(env.hand_vec) if v > 0.5]
        if not ids:
            return (0, 0, 0)
        return (1, self.r.choice(ids), self.r.randrange(env.n_cells))


# --------------------------------------------------------------------------------- modes
def mode_map(args):
    """Round-trip a real pro play through BOTH directions and report the error in TILES (1 tile = 1000
    engine units).  The only error is the placement grid's own quantisation (cell centres)."""
    env = object.__new__(EngineMatchEnv)          # no engine connection needed for the mapping
    if not V2._W:
        V2.init_worker()
    env.sim = V2._W["env"]; env.actions = env.sim.actions; env.gw = env.actions.gw
    env._mirror = True
    pool = load_pool()
    errs, exact, rows = [], [], []
    n = 0
    for e in pool[: args.matches or 40]:
        for c in e["icebow_commands"]:
            if c.get("ability") or c["x"] is None:
                continue
            cell, snap = env.engine_to_cell(c["x"], c["y"])
            x2, y2 = env.cell_to_engine(cell)
            dx, dy = abs(x2 - c["x"]) / 1000.0, abs(y2 - c["y"]) / 1000.0
            errs.append((dx * dx + dy * dy) ** 0.5)
            # exactness of the inverse ITSELF: cell centre -> engine -> cell centre
            nx, ny = env.actions.cell_center(cell % env.gw, cell // env.gw)
            xc, yc = env.cell_to_engine(cell)
            c2, d2 = env.engine_to_cell(xc, yc)
            exact.append((c2 == cell, d2))
            if n < 8:
                rows.append({"tag": e["tag"], "card": c["card"], "engine_xy": [c["x"], c["y"]], "cell": cell,
                             "back_xy": [x2, y2], "err_tiles": round(errs[-1], 4),
                             "snap_tiles": round(snap, 4)})
            n += 1
    out = {"n_plays": len(errs),
           "roundtrip_err_tiles": {"mean": round(float(np.mean(errs)), 4), "median": round(float(np.median(errs)), 4),
                                   "p90": round(float(np.percentile(errs, 90)), 4), "max": round(float(np.max(errs)), 4)},
           "inverse_is_exact": {"cell_recovered": int(sum(1 for ok, _ in exact if ok)), "of": len(exact),
                                "max_residual_tiles": round(float(max(d for _, d in exact)), 6)},
           "examples": rows}
    print(json.dumps(out, indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")


def _run_match(env, policy, index=None, entry=None, max_steps=100000):
    t0 = time.perf_counter()
    obs = env.reset(index=index, entry=entry)
    t_reset = time.perf_counter() - t0
    t_pol = 0.0
    done = False
    steps = 0
    while not done and steps < max_steps:
        ta = time.perf_counter()
        a = policy.act(env, obs)
        t_pol += time.perf_counter() - ta
        obs, r, done, info = env.step(a)
        steps += 1
    s = env.episode_summary()
    s["wall_s"] = round(time.perf_counter() - t0, 3)
    s["reset_s"] = round(t_reset, 3)
    s["policy_s"] = round(t_pol, 3)
    s["deal_s"] = round(env.deal_seconds, 3)
    s["deal_cache_hit"] = env.deal_cache_hit
    return s


def mode_smoke(args):
    env = EngineMatchEnv(port=args.port, decision_ticks=args.decision_ticks)
    pol = GreedyPolicy(env, device=args.device) if not args.random else RandomPolicy(env)
    print("policy meta:", getattr(pol, "meta", "random"))
    print("reward:", env.reward_spec())
    s = _run_match(env, pol, index=args.index)
    print(json.dumps({k: v for k, v in s.items() if k != "ghost_events"}, indent=1))
    env.close()


def mode_det(args):
    env = EngineMatchEnv(port=args.port, decision_ticks=args.decision_ticks)
    pol = GreedyPolicy(env, device=args.device)
    runs = []
    for i in range(args.repeats):
        s = _run_match(env, pol, index=args.index)
        runs.append(s)
        print(f"run {i+1}: hash {s['state_hash']} tick {s['tick']} crowns {s['crowns']} "
              f"reward {s['reward']} ghost {s['ghost_ok']}/{s['ghost_ok']+s['ghost_rejected']} "
              f"our {s['our_plays']} wall {s['wall_s']}s")
    hashes = {r["state_hash"] for r in runs}
    rewards = {r["reward"] for r in runs}
    out = {"tag": runs[0]["tag"], "repeats": args.repeats, "hashes": sorted(hashes),
           "deterministic": len(hashes) == 1 and len(rewards) == 1,
           "rewards": sorted(rewards), "ticks": sorted({r["tick"] for r in runs}),
           "runs": [{k: v for k, v in r.items() if k != "ghost_events"} for r in runs]}
    print(json.dumps({k: v for k, v in out.items() if k != "runs"}, indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    env.close()


def mode_bench(args):
    env = EngineMatchEnv(port=args.port, decision_ticks=args.decision_ticks)
    pol = GreedyPolicy(env, device=args.device) if not args.random else RandomPolicy(env)
    rows = []
    t0 = time.perf_counter()
    for i in range(args.matches):
        s = _run_match(env, pol, index=args.start + i)
        rows.append(s)
        print(f"[{i+1}/{args.matches}] {s['tag']} {s['wall_s']}s tick {s['tick']} "
              f"term={s['terminated']} {s['outcome']} crowns {s['crowns']} "
              f"ghost {s['ghost_ok']}ok/{s['ghost_rejected']}rej of {s['ghost_total']} "
              f"our {s['our_plays']}p/{s['our_rejected']}rej", flush=True)
    total = time.perf_counter() - t0
    walls = [r["wall_s"] for r in rows]
    rej = [r["ghost_rejected"] / max(1, r["ghost_ok"] + r["ghost_rejected"]) for r in rows]
    out = {"port": args.port, "matches": len(rows), "device": args.device,
           "decision_ticks": args.decision_ticks,
           "total_s": round(total, 1), "s_per_match": round(total / len(rows), 3),
           "matches_per_hour": round(3600.0 * len(rows) / total, 1),
           "wall_s": {"min": min(walls), "median": statistics.median(walls), "max": max(walls)},
           "policy_s_frac": round(sum(r["policy_s"] for r in rows) / total, 3),
           "reset_s_median": statistics.median(r["reset_s"] for r in rows),
           "terminated_frac": round(sum(r["terminated"] for r in rows) / len(rows), 3),
           "outcomes": {o: sum(1 for r in rows if r["outcome"] == o) for o in ("win", "loss", "draw")},
           "mean_crowns_for": round(statistics.mean(r["crowns"][0] for r in rows), 3),
           "mean_crowns_against": round(statistics.mean(r["crowns"][1] for r in rows), 3),
           "mean_match_seconds": round(statistics.mean(r["seconds"] for r in rows), 1),
           "median_match_seconds": statistics.median(r["seconds"] for r in rows),
           "mean_reward": round(statistics.mean(r["reward"] for r in rows), 3),
           "ghost": {"total": sum(r["ghost_total"] for r in rows), "ok": sum(r["ghost_ok"] for r in rows),
                     "rejected": sum(r["ghost_rejected"] for r in rows),
                     "undelivered": sum(r["ghost_undelivered"] for r in rows),
                     "reject_rate_overall": round(sum(r["ghost_rejected"] for r in rows)
                                                  / max(1, sum(r["ghost_ok"] + r["ghost_rejected"] for r in rows)), 4),
                     "per_match_rate": {"mean": round(statistics.mean(rej), 4),
                                        "median": round(statistics.median(rej), 4),
                                        "min": round(min(rej), 4), "max": round(max(rej), 4)},
                     "reasons": dict(sum((__import__("collections").Counter(r["ghost_reject_reasons"])
                                          for r in rows), __import__("collections").Counter()))},
           "our": {"plays": sum(r["our_plays"] for r in rows), "rejected": sum(r["our_rejected"] for r in rows),
                   "reasons": dict(sum((__import__("collections").Counter(r["our_reject_reasons"])
                                        for r in rows), __import__("collections").Counter()))},
           "unmapped_entities": sum(r["unmapped_entities"] for r in rows),
           "rows": rows}
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    env.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["map", "smoke", "det", "bench"])
    ap.add_argument("--port", type=int, default=38031)
    ap.add_argument("--matches", type=int, default=20)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--index", type=int, default=0)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--decision-ticks", type=int, default=10)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--random", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    torch.manual_seed(0)
    torch.set_num_threads(2)
    globals()[f"mode_{args.mode}"](args)


if __name__ == "__main__":
    main()
