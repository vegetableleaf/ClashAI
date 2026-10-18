"""SIM promotion eval (fork36 + troops + live levels, D3, 960 paired) per opponent archetype: Mark CXXXVIII (ref_cxxxviii) vs
Mark CXXIV (ref_u250). Opponent decks classified with live_eval.classify (same rule as the live review); paired by seed tag."""
import glob, json, sys, collections
sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/live_eval"); sys.path.insert(0, "C:/Users/benpe/ClashBot/")
from live_eval import classify
from scratchpad.gauntlet.L74.livecal.census import unfavorable
B = "C:/Users/benpe/pod_backup_weekend/pod1017_factorial/"
def rows(ref):
    out = {}
    for f in glob.glob(B + ref + "/eval/*/D3/*/matches.jsonl"):
        for l in open(f):
            r = json.loads(l); deck = [c.split("@")[0] for c in r["opp_deck"]]
            out[(f.split("_")[-1].split("/")[0] if False else f.replace(ref, ""), r["tag"], r["learner_side"], r.get("opp_deck_name"))] = (r["outcome"] == "win", classify(deck), unfavorable(deck))
    return out
a, b = rows("ref_cxxxviii"), rows("ref_u250")
keys = sorted(set(a) & set(b)); print(len(a), len(b), "paired", len(keys))
g = collections.defaultdict(list)
for k in keys: g[a[k][1]].append((a[k][0], b[k][0])); g["unfavourable six" if a[k][2] else "other (not six)"].append((a[k][0], b[k][0]))
g["ALL"] = [(a[k][0], b[k][0]) for k in keys]
for c, v in sorted(g.items(), key=lambda kv: -len(kv[1])):
    n = len(v); wa = sum(x for x, _ in v); wb = sum(y for _, y in v)
    d = [x - y for x, y in v]; m = sum(d) / n; sd = (sum((e - m) ** 2 for e in d) / max(1, n - 1)) ** .5; se = sd / n ** .5
    print(f"  {c[:28]:28s} n {n:4d}  CXXXVIII {wa / n:6.1%}  CXXIV {wb / n:6.1%}  diff {m:+.1%} +- {1.96 * se:.1%}")
# overtime in SIM (end_tick > 3600 = past 180 s), per ref, all and Hog
def ot_rows(ref):
    out = []
    for f in glob.glob(B + ref + "/eval/*/D3/*/matches.jsonl"):
        for l in open(f):
            r = json.loads(l); deck = [c.split("@")[0] for c in r["opp_deck"]]
            out.append((r["end_tick"] > 3600, r["outcome"] == "win", classify(deck), r.get("habits") or {}))
    return out
for ref in ("ref_cxxxviii", "ref_u250"):
    v = ot_rows(ref); ot = [x for x in v if x[0]]; h = [x for x in ot if x[2].startswith("Hog")]
    print(f"{ref}: OT share {len(ot) / len(v):.0%}, OT win {sum(x[1] for x in ot) / len(ot):.1%} (n {len(ot)}); Hog OT win {sum(x[1] for x in h) / max(1, len(h)):.1%} (n {len(h)}); "
          f"Rockets/game {sum(x[3].get('rocket', 0) for x in v) / len(v):.2f}, princess Rockets {sum(x[3].get('rocket_princess', 0) for x in v) / len(v):.2f}")
