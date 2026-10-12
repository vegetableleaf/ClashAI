"""Win rate per opponent archetype from the live logs (laptop; read-only).  python live_history.py OUT.txt
Archetype = archetypes.classify over the enemy card names seen in the match (raw_bodies card ids -> live_card_catalog display names, every
10th decision).  Result = INFERRED from the LAST decision's model_towers: crowns (enemy towers dead) then total tower hp_frac; there is no
win/loss event in the logs.  Only logs with an end/stop event and >= 20 decisions."""
import collections, glob, json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, "C:/Users/benpe/ClashBot"); sys.path.insert(0, HERE)
from pipeline.obs_contract import catalog_card_form
import archetypes as A
LOGS = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/"
rows = []
for f in sorted(glob.glob(LOGS + "live_play_2026*.jsonl")):
    seen, last, n, ended = set(), None, 0, False
    for l in open(f, encoding="utf-8", errors="replace"):
        if l.startswith('{"event": "decision"'):
            n += 1
            if n % 10 == 1:
                d = json.loads(l); p = d["public"]
                for b in p["raw_bodies"]:
                    if b["side"] != p["observer_side"] and b["card_id"] != -1:
                        nm = catalog_card_form(b["card_id"])[0]
                        if nm: seen.add(nm)
            last = l
        elif l.startswith('{"event": "end"') or l.startswith('{"event": "stop"'):
            ended = True
    if not ended or n < 20 or last is None:
        continue
    t = json.loads(last)["public"]["model_towers"]
    mine = [x for x in t if x["side"] == 0]; theirs = [x for x in t if x["side"] == 1]
    cm, ct = sum(not x["alive"] for x in theirs), sum(not x["alive"] for x in mine)
    hm, ht = sum(x["hp_frac"] if x["alive"] else 0 for x in mine), sum(x["hp_frac"] if x["alive"] else 0 for x in theirs)
    res = 1 if (cm, hm - ht) > (ct, 0) else 0 if (cm, hm - ht) < (ct, 0) else (1 if hm > ht else 0)
    rows.append((os.path.basename(f), A.classify(seen), res, sorted(seen)))
by = collections.defaultdict(list)
for _, a, r, _ in rows: by[a].append(r)
L = [f"live history: {len(rows)} matches with an end/stop event; result inferred from the last decision's towers (crowns, then tower hp)"]
for a, v in sorted(by.items(), key=lambda kv: -len(kv[1])):
    n, w = len(v), sum(v); p = w / n; hw = 1.96 * math.sqrt(p * (1 - p) / n) if n else 0
    L.append(f"{a:18s} n {n:4d} win {100 * p:5.1f}% [{100 * max(0, p - hw):.1f}, {100 * min(1, p + hw):.1f}]")
# other archetypes: single signature cards with n >= 15 and win < 45%
card_n = collections.defaultdict(list)
for _, a, r, s in rows:
    for c in {A.canon(x) for x in s}: card_n[c].append(r)
L.append("other signature cards (n >= 15, win < 45%):")
for c, v in sorted(card_n.items(), key=lambda kv: sum(kv[1]) / len(kv[1])):
    if len(v) >= 15 and sum(v) / len(v) < 0.45:
        L.append(f"  {c:18s} n {len(v):4d} win {100 * sum(v) / len(v):5.1f}%")
open(sys.argv[1], "w").write("\n".join(L) + "\n"); json.dump(rows, open(sys.argv[1] + ".json", "w"))
print("\n".join(L))
