"""L56 TESLA-OUTCOME PROBE (sim only). Does the sim itself reward the corner Tesla?

Greedy policy exactly as play.py (argmax card, argmax cell of that card's own map, own-half mask,
gate thresholded at tau -- NO search, NO exploration), c2r_best, N matches per arm per seed.
Arms force the TESLA cell only (everything else is the policy's own choice):
  own     -> the policy's cell (L55: cell 234 = row 13, col 0, left riverside corner, 63%)
  corner  -> forced 234 on every Tesla play (control for the 37% that go elsewhere)
  lane    -> forced 274 = row 15, col 4  (left lane, ~3 tiles behind our bank)
  centre  -> forced 314 = row 17, col 8  (central, ~4 tiles in front of the king)
Per Tesla: lifetime, died-before-expiry, damage to the unit it was shooting (UPPER BOUND, sampled at
agent_dt like tools/xbow_probe.py), targets that died, time-with-target fraction.
Per match: crowns, our/enemy tower HP lost, enemy river crossings left vs right.
"""
import sys, json, math, collections, argparse
from pathlib import Path
import numpy as np, torch, torch.nn as nn
_ROOT = Path("C:/Users/benpe/ClashBot/icebow")
sys.path.insert(0, str(_ROOT / "src"))
from clashrl.config import Config
from clashrl.model import PolicyNet
from clashrl.sim.env import SimMatchEnv
import clashrl.sim.engine as E

ARMS = {"own": None, "corner": 234, "lane": 274, "centre": 314}


def load(ckpt, e0):
    state = torch.load(ckpt, map_location="cpu", weights_only=False)
    in_ch = int(state.get("in_ch") or 12); thr_dim = int(state.get("threat_dim") or e0.threat_dim)

    class PPONet(nn.Module):
        def __init__(s):
            super().__init__()
            s.policy = PolicyNet(in_ch, e0.n_cards, e0.n_cells, threat_dim=thr_dim)
            s.gate = nn.Linear(s.policy.embed_dim, 2)

        def forward(s, x, hand, nxt, elx, thr):
            z, cards, cells = s.policy.forward_parts(x, hand, nxt, elx, thr)
            return cards, cells, s.gate(z)
    net = PPONet(); net.policy.load_state_dict(state["model"])
    if "gate" in state: net.gate.load_state_dict(state["gate"])
    net.eval()
    return net, in_ch, thr_dim


def run(ckpt, arm, matches, seed, gate_tau):
    cfg = Config.load(_ROOT / "config" / "config.yaml")
    cfg.data.setdefault("action", {})["grid"] = [18, 24]
    env = SimMatchEnv(cfg, seed=seed)
    if getattr(env, "domain_rand", None) is not None:
        env.domain_rand.enabled = False; env.domain_rand.resample()
    net, in_ch, thr_dim = load(ckpt, env)
    names = [str(getattr(sp, "key", i)) for i, sp in enumerate(env.specs)]
    tesla_ids = {i for i, n in enumerate(names) if n in ("tesla", "tesla_evo")}
    own = np.zeros(env.n_cells, bool); own[12 * 18:] = True
    force = ARMS[arm]

    def obs_t(o):
        x = np.asarray(o)
        if x.shape[2] > in_ch: x = x[:, :, :in_ch]
        elif x.shape[2] < in_ch:
            x = np.concatenate([x, np.zeros((x.shape[0], x.shape[1], in_ch - x.shape[2]), dtype=x.dtype)], axis=2)
        return torch.from_numpy(x).float().permute(2, 0, 1) / 255.0

    def thr_t(v):
        t = np.asarray(v, np.float32)
        return torch.from_numpy(t[:thr_dim] if t.shape[0] > thr_dim else np.pad(t, (0, thr_dim - t.shape[0])))

    recs, live, mrows = [], {}, []
    cells_used = collections.Counter()
    obs = env.reset(); done_n = 0
    cross = [0, 0]; crossed = set()
    with torch.no_grad():
        while done_n < matches:
            cq, ceq, gq = net(obs_t(obs)[None], torch.from_numpy(np.asarray(env.hand_vec, np.float32))[None],
                              torch.from_numpy(np.asarray(env.next_vec, np.float32))[None],
                              torch.from_numpy(np.asarray(env.elixir_vec, np.float32))[None], thr_t(env.threat_vec)[None])
            elx = float(env.eng.elixir[0])
            hand = [c for c in env._hand_ids() if 0 <= c < len(env.specs) and elx >= env.specs[c].elixir]
            act = (0, 0, 0)
            if hand:
                pc = torch.softmax(cq, 1)[0].numpy()
                pick = int(max(hand, key=lambda c: pc[c]))
                p_play = float(torch.sigmoid(gq[0, 1] - gq[0, 0]))
                if p_play > gate_tau:
                    m = ceq[0, pick].numpy().copy(); m[~own] = -1e9; cell = int(m.argmax())
                    if pick in tesla_ids:
                        if force is not None: cell = force
                        cells_used[cell] += 1
                    act = (1, pick, cell)
            obs, _r, d, _i = env.step(act)
            eng = env.eng
            # enemy river crossings by lane
            for u in eng.units:
                if u.team == 1 and id(u) not in crossed and u.y >= 0.5:
                    crossed.add(id(u)); cross[0 if u.x < 0.5 else 1] += 1
            seen = set()
            for u in eng.units:
                if u.team != 0 or str(u.spec.key) not in ("tesla", "tesla_evo"): continue
                k = id(u); seen.add(k); r = live.get(k)
                if r is None:
                    r = live[k] = {"x": u.x, "y": u.y, "key": str(u.spec.key), "age": 0.0, "n": 0, "t_tgt": 0,
                                   "dmg": 0.0, "kills": 0, "hp_end": float(u.hp), "prev": None, "hidden": 0}
                r["age"] = float(u.age); r["n"] += 1; r["hp_end"] = float(u.hp)
                if getattr(u, "hidden", False): r["hidden"] += 1
                tgt = u.target
                if tgt is not None: r["t_tgt"] += 1
                prev = r["prev"]
                if prev is not None:
                    pobj, php = prev
                    if pobj is tgt and tgt is not None:
                        r["dmg"] += max(0.0, php - float(getattr(tgt, "hp", php)))
                    elif isinstance(pobj, E.Unit) and float(getattr(pobj, "hp", 1.0)) <= 0.0:
                        r["kills"] += 1
                r["prev"] = (tgt, float(getattr(tgt, "hp", 0.0))) if tgt is not None else None
            for k in [k for k in live if k not in seen]:
                recs.append(live.pop(k))
            if d:
                for k in list(live): recs.append(live.pop(k))
                tw = [t for t in eng.towers[0]]; te = [t for t in eng.towers[1]]
                mrows.append({"our_lost": sum(t.max_hp - max(0.0, t.hp) for t in tw),
                              "enemy_lost": sum(t.max_hp - max(0.0, t.hp) for t in te),
                              "our_crowns": sum(1 for t in te if not t.alive), "enemy_crowns": sum(1 for t in tw if not t.alive),
                              "t": float(eng.t)})
                done_n += 1; obs = env.reset(); crossed = set()
    for r in recs: r.pop("prev", None)
    return {"arm": arm, "seed": seed, "matches": matches, "teslas": recs, "match": mrows,
            "cells": cells_used.most_common(6), "cross_left_right": cross}


def summarize(o):
    rs = o["teslas"]; m = o["match"]
    n = len(rs)
    if n == 0:
        return f"{o['arm']:7s} s{o['seed']} NO TESLA in {o['matches']} matches"
    age = np.array([r["age"] for r in rs]); died = sum(1 for r in rs if r["hp_end"] <= 0.0)
    life = np.array([30.0 if r["key"] == "tesla" else 25.0 for r in rs])
    full = int((age >= life - 1.0).sum())
    dmg = np.array([r["dmg"] for r in rs]); kills = sum(r["kills"] for r in rs)
    tgt = np.array([r["t_tgt"] / max(1, r["n"]) for r in rs])
    ol = np.mean([x["our_lost"] for x in m]); el = np.mean([x["enemy_lost"] for x in m])
    oc = sum(x["our_crowns"] for x in m); ec = sum(x["enemy_crowns"] for x in m)
    wins = sum(1 for x in m if x["our_crowns"] > x["enemy_crowns"]); losses = sum(1 for x in m if x["our_crowns"] < x["enemy_crowns"])
    return (f"{o['arm']:7s} s{o['seed']} teslas {n} ({n/len(m):.2f}/match) cells {o['cells'][:3]} | life mean {age.mean():.1f}s "
            f"full {full}/{n} died {died}/{n} | with-target {100*tgt.mean():.0f}% | unit dmg/tesla mean {dmg.mean():.0f} "
            f"median {np.median(dmg):.0f} kills {kills} ({kills/n:.2f}/tesla) | match: W{wins}-L{losses}-D{len(m)-wins-losses} "
            f"crowns {oc}-{ec} our tower HP lost {ol:.0f} enemy {el:.0f} | enemy crossings L/R {o['cross_left_right']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ckpt"); ap.add_argument("--arms", default="own,corner,lane,centre")
    ap.add_argument("--matches", type=int, default=24); ap.add_argument("--seeds", default="1234,5678")
    ap.add_argument("--tau", type=float, default=0.5); ap.add_argument("--out", default=None)
    a = ap.parse_args()
    outs = []
    for s in [int(x) for x in a.seeds.split(",")]:
        for arm in a.arms.split(","):
            np.random.seed(s); torch.manual_seed(s)
            o = run(a.ckpt, arm, a.matches, s, a.tau); outs.append(o)
            print(summarize(o), flush=True)
    if a.out:
        json.dump(outs, open(a.out, "w"))
