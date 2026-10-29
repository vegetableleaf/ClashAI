"""OPP-LEARN-C: curve.py TRAIN_LOG.jsonl -> markdown per update of a calibration run: learner win rate vs the bot partner
(exploiter_league = CLXIII in the sampled decode) and vs the frozen init, plays/min, KL card / cell to the init, and the frozen
heads' drift (th_drift: hazard mean p init -> now, mean / max |dp|, tick KL; ability hazard mean |dp|)."""
import json
import sys

print("| u | wr vs bot (n) | wr vs init (n) | plays/min | KL card | KL cell | hazard p init -> now | mad | max | tick KL | ab mad |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for line in open(sys.argv[1], encoding="utf-8"):
    r = json.loads(line)
    if r.get("type") != "update":
        continue
    bo = (r.get("league") or {}).get("by_opp", {})
    f = lambda t: (f"{bo[t]['winrate']:.3f} ({bo[t]['n']})" if bo.get(t, {}).get("n") else "-")   # noqa: E731
    d = r.get("th_drift") or {}
    h, a = d.get("hazard", {}), d.get("ab_hazard", {})
    print(f"| {r['update']} | {f('exploiter_league')} | {f('init')} | {r.get('plays_per_min', float('nan')):.2f} | "
          f"{r['kl_card']:.4f} | {r['kl_cell']:.4f} | {h.get('p_init', float('nan')):.4f} -> {h.get('p_now', float('nan')):.4f} | "
          f"{h.get('mad', float('nan')):.2e} | {h.get('max', float('nan')):.2e} | {h.get('tick_kl', float('nan')):.1e} | "
          f"{a.get('mad', float('nan')):.1e} |")
