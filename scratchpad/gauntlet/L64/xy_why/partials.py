import csv, json, sys
from collections import Counter, defaultdict
from pathlib import Path
deck = sys.argv[1]
D = Path("C:/Users/benpe/ClashBot") / deck / "data/royaleapi/crawl2"
plays = list(csv.DictReader(open(D / "plays_ext.csv", encoding="utf-8")))
frac = json.load(open(f"C:/Users/benpe/ClashBot/scratchpad/gauntlet/L64/xy_why/{deck}_frac.json"))
by = defaultdict(list)
for r in plays: by[r["replay_tag"]].append(r)
def hasxy(r): return bool(r["tile_x"]) and r["tile_x"] != "None"
# attr_s values by coverage
for lab, sel in (("covered", lambda f: f >= 0.8), ("uncovered", lambda f: f == 0)):
    tags = [t for t, f in frac.items() if sel(f)]
    rows = [r for t in tags for r in by[t]]
    print(lab, len(tags), "replays", len(rows), "rows; attr_s:", Counter(r["attr_s"] for r in rows).most_common(),
          "| attr_ability:", Counter(r["attr_ability"] for r in rows).most_common(),
          "| tick==attr_t:", sum(r["tick"] == r["attr_t"] for r in rows),
          "| tick%20==0 share:", round(sum(int(r["tick"]) % 20 == 0 for r in rows) / len(rows), 3),
          "| tick parity even share:", round(sum(int(r["tick"]) % 2 == 0 for r in rows) / len(rows), 3),
          "| max tick:", max(int(r["tick"]) for r in rows),
          "| mean plays/replay:", round(len(rows)/len(tags),1))
    # blue share
    print("   blue share", round(sum(r["attr_s"]=="blue" for r in rows)/len(rows),3),
          " first tick median", sorted(int(by[t][0]["tick"]) for t in tags)[len(tags)//2],
          " tick last-digit dist", Counter(int(r["tick"]) % 10 for r in rows).most_common(10))
    # duplicate (tick,card) within replay
    dup = 0
    for t in tags:
        c = Counter((r["tick"], r["attr_card"]) for r in by[t]); dup += sum(v-1 for v in c.values())
    print("   duplicate (tick,card) pairs:", dup)
    # x/y in covered: side split
    if lab == "covered":
        print("   covered rows with xy by side:", Counter(r["attr_s"] for r in rows if hasxy(r)).most_common())
        print("   covered rows without xy by side/card:", Counter((r["attr_s"], r["attr_card"]) for r in rows if not hasxy(r)).most_common(5))
# partials
print("\nPARTIAL replays (0<frac<0.8):")
for t, f in frac.items():
    if 0 < f < 0.8:
        rs = by[t]
        hx = [r for r in rs if hasxy(r)]
        print(f"  {t} frac={f:.3f} n={len(rs)} xy_rows={len(hx)}:",
              [(r["tick"], r["attr_card"], r["attr_s"], r["tile_x"], r["tile_y"]) for r in hx][:8])
        # show ticks/cards near those
        for r in hx[:2]:
            near = [(q["tick"], q["attr_card"], q["attr_s"]) for q in rs if abs(int(q["tick"]) - int(r["tick"])) <= 40]
            print("      neighbours:", near)
