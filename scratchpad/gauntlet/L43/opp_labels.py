"""Rebuild the ladder opponent for each rollout_search seed and join to base/teacher records."""
import json, sys, collections
sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim import meta_decks
cfg = Config.load()
env = SimMatchEnv(cfg, seed=12345); env.opponent_provider = None
out = {}
for tag in ("base", "teacher"):
    try: d = json.load(open(f"C:/Users/benpe/ClashBot/scratchpad/gauntlet/L43/{tag}.json"))
    except FileNotFoundError: continue
    rows = collections.defaultdict(lambda: [0, 0, 0.0])
    for r in d["records"]:
        env.rng.seed(r["seed"]); env.reset()
        opp = env.opponent; cards = list(getattr(opp, "cards", []))
        style = getattr(opp, "style", None) or meta_decks.classify_style(env.db, cards)
        name = getattr(opp, "name", None) or getattr(opp, "deck_name", None) or "?"
        k = f"{style}"
        rows[k][0] += 1; rows[k][1] += (r["outcome"] == "win")
        rows[k][2] += float(r["tower_delta"])
        out.setdefault(str(r["seed"]), {})[tag] = [style, name, r["outcome"]]
    print(f"== {tag}  n={d['matches']}")
    for k, (n, w, td) in sorted(rows.items()):
        print(f"  {k:10s} n={n:2d}  wr={100*w/n:5.1f}%  towerdelta={td/n:+.3f}")
json.dump(out, open("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L43/opp_labels.json", "w"), indent=1)
