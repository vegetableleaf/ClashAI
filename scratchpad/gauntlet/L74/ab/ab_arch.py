"""Live A/B win rates split by opponent archetype (the SIM split of 10-15: F1 gains outside beatdown only -- does live agree?).
Enemy cards seen = live_history.py's rule (raw_bodies of every 10th decision -> catalog names); result = results.jsonl's own.
    python ab_arch.py RUN_ID      (repo root; counted matches only)
beatdown = any tank win condition (weekend/archetypes.TANK) or Three Musketeers -- the SIM split's grouping."""
import collections, json, math, sys
sys.path[:0] = ["C:/Users/benpe/ClashBot", "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/weekend"]
from pipeline.obs_contract import catalog_card_form
import archetypes as A

BEAT = A.TANK | {"threemusketeers"}


def seen_cards(path):
    seen, n = set(), 0
    for line in open(path, encoding="utf-8", errors="replace"):
        if line.startswith('{"event": "decision"'):
            n += 1
            if n % 10 == 1:
                p = json.loads(line)["public"]
                seen |= {catalog_card_form(b["card_id"])[0] for b in p["raw_bodies"]
                         if b["side"] != p["observer_side"] and b["card_id"] != -1}
    return {A.canon(x) for x in seen if x}


def wr(v):
    w, n = sum(v), len(v)
    return f"{w:3d}/{n:<3d} {100 * w / n:5.1f}%" if n else "  -  "


def main(run):
    rows = [json.loads(l) for l in open("scratchpad/gauntlet/L74/ab/results.jsonl") if l.strip()]
    rows = [r for r in rows if r.get("run_id") == run and r.get("counted") and r.get("result") in ("W", "L")]
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        s = seen_cards(r["match_file"])
        win = int(r["result"] == "W")
        by[r["arm"] + " " + r["label"]]["beatdown" if s & BEAT else "rest"].append(win)
        by[r["arm"] + " " + r["label"]][A.classify(s)].append(win)
    keys = ["beatdown", "rest"] + list(A.ORDER) + ["other"]
    print(f"run {run}: {len(rows)} counted W/L matches")
    print(f"{'group':18s} " + " ".join(f"{a:>18s}" for a in sorted(by)))
    for k in keys:
        print(f"{k:18s} " + " ".join(f"{wr(by[a][k]):>18s}" for a in sorted(by)))
    arms = sorted(by)
    if len(arms) == 2:                                  # difference of the two arms' win rates per group, normal approx
        for k in ("beatdown", "rest"):
            a, b = by[arms[0]][k], by[arms[1]][k]
            if a and b:
                pa, pb = sum(a) / len(a), sum(b) / len(b)
                se = math.sqrt(pa * (1 - pa) / len(a) + pb * (1 - pb) / len(b))
                print(f"{k}: {arms[0]} - {arms[1]} = {100 * (pa - pb):+.1f} pp [{100 * (pa - pb - 1.96 * se):+.1f}, "
                      f"{100 * (pa - pb + 1.96 * se):+.1f}]")


if __name__ == "__main__":
    main(sys.argv[1])
