"""L29: opponent CADENCE vs `sim.bot_attack_floor` (Path A preparation). Same key and instrument as L22's
quiet_stretches.py (enemy TROOP younger than W=6 s on the board, sampled m10k policy, single elixir), plus
the opponent's own elixir waste (steps at >= 9.9) and troop deploys per single-elixir phase, so a floor
that just parks the bot at 10 elixir is visible. Pro reference (L22, 519 replays): pressure 37%, quiet
median 9.0 s, p90/p95 23.4/28.6, stretches >= 11.2 s 39%, bankable/phase ~2.7.
usage (from icebow/): PYTHONHASHSEED=0 .venv/Scripts/python.exe ../scratchpad/gauntlet/L29/cadence_floor.py <ckpt> <matches> <seed> <floor> <out.json>"""
import sys, json
sys.path.insert(0, "src"); sys.path.insert(0, "tools")
import numpy as np, torch
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim import rollout_search as RS
from clashrl.sim.opponents import make_opponent

W = 6.0
ckpt, matches, seed, floor, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
cfg = Config.load("data/bench/gate05_run.yaml")
cfg.data.setdefault("sim", {})["bot_attack_floor"] = floor
env = SimMatchEnv(cfg); env.rng.seed(seed)
# TRAINING bots (adaptive=True through make_opponent = the gate that reads the floor), as train_sim_ppo does
env.opponent_provider = lambda e: make_opponent(cfg, e.db, e.rng, e.meta_pool, adaptive=True)
env.reset()
assert abs(getattr(env.opponent, "attack_floor", -1.0) - floor) < 1e-9, getattr(env.opponent, "attack_floor", None)
net = RS.load_net(ckpt, env, torch.device("cpu"))
sr = RS.Searcher(env, net, torch.device("cpu"), 12.0, 0, 4, 1.0, 0.25, cells=3)
rng = np.random.RandomState(seed)
flags, waste, deploys, styles = [], [], 0, {}
per_match = []; m_flags = []; m_waste = []; m_dep = 0
done = 0; last_n = None
while done < matches:
    cq_m, ceq, gq_m, playable = sr._forward()
    pp = float(torch.softmax(gq_m, 0)[1]) if bool(playable.any()) else 0.0
    if rng.rand() < pp:
        pc = torch.softmax(cq_m, 0).numpy(); ci = int(rng.choice(len(pc), p=pc / pc.sum()))
        act = (1, ci, sr._cell_for(ceq, ci))
    else:
        act = (0, 0, 0)
    e = env.eng
    single = float(e.t) < 120.0
    if single:
        pres = any(u.team == 1 and u.hp > 0 and u.spec.kind == "troop" and u.age < W for u in e.units)
        flags.append(int(pres)); waste.append(int(e.elixir[1] >= 9.9))
        n = sum(1 for u in e.units if u.team == 1 and u.spec.kind == "troop" and u.age < 0.61)
        deploys += n; m_flags.append(int(pres)); m_waste.append(int(e.elixir[1] >= 9.9)); m_dep += n
    else:
        flags.append(-1)
    _o, _r, d, info = env.step(act)
    if d:
        done += 1; flags.append(-1); st = getattr(env.opponent, "style", "?"); styles[st] = styles.get(st, 0) + 1
        per_match.append({"style": st, "deck": getattr(env.opponent, "deck_name", "?"), "adaptive": bool(env.opponent.adaptive),
                          "flags": m_flags, "waste_steps": int(sum(m_waste)), "troop_units": m_dep})
        m_flags, m_waste, m_dep = [], [], 0
        env.reset()

def stretches(fl):
    o, run = [], 0
    for f in fl:
        if f == 0: run += 1
        else:
            if run: o.append(run)
            run = 0
    if run: o.append(run)
    return o
fl = np.asarray(flags); valid = fl >= 0; st = np.asarray(stretches(flags)); wa = np.asarray(waste)
res = {"ckpt": ckpt, "matches": matches, "seed": seed, "floor": floor, "single_steps": int(valid.sum()),
       "pressure_pct": round(100 * float((fl[valid] == 1).mean()), 1),
       "quiet_n": int(len(st)), "quiet_mean_s": round(float(st.mean() * 0.6), 1), "quiet_median_s": round(float(np.median(st) * 0.6), 1),
       "quiet_p90_s": round(float(np.percentile(st, 90) * 0.6), 1), "quiet_p95_s": round(float(np.percentile(st, 95) * 0.6), 1),
       "stretch_ge_11p2_pct": round(100 * float((st >= 19).mean()), 1),
       "quiet_steps_in_bankable_pct": round(100 * float(st[st >= 19].sum() / max(1, st.sum())), 1),
       "bankable_per_phase": round(float((st >= 19).sum() / matches), 2),
       "opp_elixir_ge9p9_pct": round(100 * float(wa.mean()), 1),
       "opp_troop_units_per_phase": round(deploys / matches, 1), "styles": styles, "per_match": per_match}
print(json.dumps(res)); json.dump(res, open(out, "w"), indent=1)
