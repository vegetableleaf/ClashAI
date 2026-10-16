"""How many logged matches (main account, 10-15/10-16 frame logs) had a given card on the opponent side. ents only (cid, side)."""
import collections
import glob
import json

import measure as m

WATCH = ["Wizard", "LavaHound", "MinionGiant", "Ronin", "MiniZapMachine", "MegaKnight", "Golem", "SkeletonBalloon", "Prince", "MiniPekka"]

def main():
    from pipeline.obs_contract import _catalog_names
    cat = _catalog_names()
    seen, total = collections.defaultdict(int), 0
    for f in sorted(glob.glob(str(m.LOGS / "live_play_2026101[56]_*.jsonl"))):
        names, ms, first, n = set(), None, None, 0
        for line in open(f, encoding="utf-8"):
            if '"event": "frame"' not in line:
                continue
            e = json.loads(line)
            n += 1
            if first is None:
                ms = e["my_side"]
                pr = [x[4] for x in e["ents"] if x[3] == -1 and x[0] == ms and x[1] in (3500, 14500)]
                first = pr[0] if pr else None
                if first not in m.MAIN_PRINCESS_HP:
                    break
            if n % 5 == 0:
                names |= {cat.get(x[3]) for x in e["ents"] if x[0] != ms and x[3] != -1}
        if first in m.MAIN_PRINCESS_HP and n > 400:
            total += 1
            for w in names:
                seen[w] += 1
    print("main-account matches", total)
    for w, c in sorted(seen.items(), key=lambda kv: -kv[1]):
        if any(k.lower() in (w or "").lower().replace(" ", "").replace("-", "") for k in ("wizard", "lavahound", "minion", "ronin", "zap", "knight", "golem", "balloon", "prince", "pekka", "sparky")):
            print(f"  {w}: {c}")


if __name__ == "__main__":
    main()
