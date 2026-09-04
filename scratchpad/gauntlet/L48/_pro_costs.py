"""Card-cost distribution of the crawled (blue) side's plays in hogeq's pro corpus, restricted to
the 8 cards of the hogeq deck so it is the same card space the policy's probe reports on."""
import csv, sys, collections
sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.cards import CardDB
cfg = Config.load()
db = CardDB(cfg)
deck = ["earthquake", "firecracker", "hog_rider", "ice_spirit", "mighty_miner", "skeletons", "tesla", "the_log"]
cost = {}
for k in deck:
    c = db.get(k) or {}
    cost[k] = float(c.get("elixir", c.get("cost", 0)))
print("costs", cost)
plays = collections.Counter(); total = 0; abil = 0; other = collections.Counter()
with open("data/royaleapi/crawl2/plays_ext.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["attr_s"] != "blue":
            continue
        if r["attr_ability"] not in ("0", "", None):
            abil += 1; continue
        k = r["attr_card"].replace("-", "_")
        total += 1
        if k in cost:
            plays[k] += 1
        else:
            other[k] += 1
n = sum(plays.values())
print("blue plays %d, of which in-deck %d (%.0f%%), abilities %d" % (total, n, 100.0 * n / max(1, total), abil))
print("top off-deck:", other.most_common(6))
mean = sum(cost[k] * v for k, v in plays.items()) / max(1, n)
print("PRO mean cost of an in-deck play: %.3f" % mean)
for k, v in sorted(plays.items(), key=lambda kv: -kv[1]):
    print("  %-13s cost %d  share %.1f%%" % (k, cost[k], 100.0 * v / n))
cheap = sum(v for k, v in plays.items() if cost[k] <= 2) / max(1, n)
print("share of plays costing <=2: %.1f%%   costing 4: %.1f%%" % (100 * cheap, 100 * sum(v for k, v in plays.items() if cost[k] == 4) / max(1, n)))
