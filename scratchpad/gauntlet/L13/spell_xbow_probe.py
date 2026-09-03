"""Spell-whiff + X-bow-vs-dead-tower probe on a sim checkpoint. Greedy, SEARCH-FREE, NO spell mask
(the greedy path never applies it) -> measures the POLICY's own casts. Same harness as ab_reward_report."""
import collections, json, os, pathlib, sys, time
_ROOT = pathlib.Path(__file__).resolve().parents[3] / "icebow"
sys.path.insert(0, str(_ROOT / "src")); os.chdir(_ROOT)
import numpy as np, torch
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim import rollout_search as RS
from clashrl.sim.engine import tile_dist

def run(ckpt, matches, seed):
    cfg = Config.load(); env = SimMatchEnv(cfg); env.rng.seed(seed); env.reset()
    net = RS.load_net(str(ckpt), env, torch.device("cpu"))
    sr = RS.Searcher(env, net, torch.device("cpu"), 12.0, 0, 4, 1.0, 0.25, cells=3)
    spell_ids = {i for i, s in enumerate(env.specs) if getattr(s, "kind", "") == "spell"}
    casts = collections.Counter(); mask_whiff = collections.Counter(); no_target = collections.Counter()
    plays = 0; bows = []; done = 0; gw = int(env.actions.gw)
    while done < matches:
        act, _ = sr.act(0)
        if act[0] == 1:
            plays += 1; ci = int(act[1]); cell = int(act[2]); key = env.deck_keys[ci]
            if ci in spell_ids:
                casts[key] += 1
                m = env.spell_target_mask(ci)
                if m is None or not m.any(): no_target[key] += 1
                elif not m[cell]: mask_whiff[key] += 1
            if ci in env.xbow_ids:
                cx, cy = env.actions.cell_center(cell % gw, cell // gw)
                tw = env.eng.towers[1]
                alive = [bool(t.alive) for t in tw[:2]]
                d = [tile_dist(cx, cy, t.x, t.y) for t in tw[:2]]
                in_rng_alive = any(a and dd <= env.xbow_range for a, dd in zip(alive, d))
                in_rng_dead = any((not a) and dd <= env.xbow_range for a, dd in zip(alive, d))
                bows.append({"t": round(env.eng.t, 1), "cell": cell, "alive": alive, "d": [round(x, 1) for x in d],
                             "reaches_alive": in_rng_alive, "reaches_dead_only": in_rng_dead and not in_rng_alive,
                             "defensive": bool(env._defensive)})
        _o, _r, d, info = env.step(act)
        if d:
            done += 1; env.reset()
    led = env.rw_stats.run_summary()["terms"]
    t = lambda k: (led[k]["fires"], round(led[k]["total"], 2)) if k in led else (0, 0.0)
    return {"ckpt": str(ckpt), "matches": matches, "seed": seed, "plays": plays,
            "spell_casts": dict(casts), "cast_where_mask_says_nothing_to_hit": dict(mask_whiff),
            "cast_with_no_target_anywhere": dict(no_target),
            "ledger": {k: t(k) for k in ("spell_waste", "nado_bad", "spell_effect", "log_hits", "chip_offence", "wincon_exec", "wincon_mis")},
            "xbow_plays": len(bows), "xbow_with_a_dead_princess": sum(1 for b in bows if not all(b["alive"])),
            "xbow_reaches_dead_only": sum(1 for b in bows if b["reaches_dead_only"]),
            "xbow_reaches_no_tower": sum(1 for b in bows if not b["reaches_alive"] and not b["reaches_dead_only"]),
            "xbow_records_with_dead": [b for b in bows if not all(b["alive"])][:20]}

if __name__ == "__main__":
    ck = sys.argv[1]; n = int(sys.argv[2]); seeds = [int(s) for s in sys.argv[3].split(",")]
    out = []
    for s in seeds:
        t0 = time.time(); r = run(ck, n, s); r["wall_s"] = round(time.time() - t0, 1); out.append(r)
        print(json.dumps({k: v for k, v in r.items() if k != "xbow_records_with_dead"}), flush=True)
    pathlib.Path(sys.argv[4]).write_text(json.dumps(out, indent=1))
