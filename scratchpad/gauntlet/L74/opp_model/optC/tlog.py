"""Per-update summary of an rl_royale train_log.jsonl: win rate vs each opp type, seconds, kl, beta, plays/min.
usage: python tlog.py train_log.jsonl"""
import json, sys
for line in open(sys.argv[1], encoding="utf-8"):
    r = json.loads(line)
    if r.get("type") != "update":
        continue
    bo = {k: f"{v['winrate']:.2f}/{v['n']}" for k, v in r.get("league", {}).get("by_opp", {}).items() if v["n"]}
    print(r["update"], r["time"][11:], f"win {r['winrate']:.3f}", f"sec {r['seconds_mean']:.0f}",
          f"kl {r.get('kl_leash', 0):.4f} ({r.get('kl_driver')})", f"beta {r.get('beta_used', 0):.3f}",
          f"ppm {r['plays_per_min']:.1f}/{r['league'].get('opp_plays_per_min', 0):.1f}", bo)
