"""X-Bow placement classes in states with an enemy princess down: live (live_matches.jsonl from live_measure.py) vs pros
(L70/gen_v31/native_xbows_2020/xbows.jsonl). Model board frame, tiles: enemy K (9,3), L (3.5,6.5), R (14.5,6.5);
forward = decreasing y. REACH = decision_options.XBOW_REACH_TILES (lead-approved 13.0384, centre to centre).

  KONLY     reaches an alive enemy tower but no alive princess (the king only)            <- ticket definition
  OFF_P     reaches an alive enemy princess (locks the remaining tower)
  DL_LOCK   in the dead lane, within reach of the DEAD princess's position, reaches nothing alive (the lane-lock cell)
  DL_BACK   in the dead lane, beyond reach of the dead princess's position, reaches nothing alive
  DEF       other lane (alive princess), reaches nothing alive
Also: threat = an enemy unit (live: public raw bodies) on my half in the X-Bow's lane at placement (live only)."""
import collections, json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
REACH = 13.0384 + 1e-4
TW = {"K": (9.0, 3.0), "L": (3.5, 6.5), "R": (14.5, 6.5)}


def cls(x, y, alive):
    """alive: dict K/L/R -> bool (my frame)."""
    reach = {k: math.hypot(x - TW[k][0], y - TW[k][1]) <= REACH for k in TW}
    if any(reach[k] and alive[k] for k in "LR"):
        return "OFF_P"
    if reach["K"] and alive["K"]:
        return "KONLY"
    lane = "L" if x < 9 else "R"
    if not alive[lane]:
        return "DL_LOCK" if reach[lane] else "DL_BACK"
    return "DEF"


def live():
    out = []
    for l in open(os.path.join(HERE, "live_matches.jsonl")):
        m = json.loads(l)
        for p in m["plays"]:
            if p["card"] != "Xbow" or not p["down"]:
                continue
            alive = {"K": True, "L": "eL" not in p["down"], "R": "eR" not in p["down"]}
            out.append(dict(src=m["ckpt"], ph=p["ph"], c=cls(p["X"], 32 - p["Y"], alive), y=32 - p["Y"],
                            crowns=tuple(p["crowns"]), file=m["file"]))
    return out


def pros():
    out = []
    PH = {"single": "1x", "double": "2x", "overtime": "OT"}
    for l in open("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L70/gen_v31/native_xbows_2020/xbows.jsonl"):
        r = json.loads(l)
        h = r["tower_hp"]
        if h.get("enemy_left") is None or h.get("enemy_right") is None or (h["enemy_left"] > 0 and h["enemy_right"] > 0):
            continue
        alive = {"K": True, "L": h["enemy_left"] > 0, "R": h["enemy_right"] > 0}
        x, y = r["xy"][0] * 18, r["xy"][1] * 32
        out.append(dict(src="pros", ph=PH.get(r["phase"], r["phase"]), c=cls(x, y, alive), y=y,
                        crowns=tuple(r["crowns_ours_enemy"]), file=r["tag"]))
    return out


def main():
    rows = live() + pros()
    C = ("KONLY", "OFF_P", "DL_LOCK", "DL_BACK", "DEF")
    for src in ("towerref_w2", "stack2k", "R1e", "other", "pros"):
        q = [r for r in rows if r["src"] == src]
        if not q:
            continue
        print(f"\n{src}: {len(q)} X-Bows with an enemy princess down")
        for ph in ("1x", "2x", "OT", "all"):
            s = [r for r in q if ph == "all" or r["ph"] == ph]
            if not s:
                continue
            c = collections.Counter(r["c"] for r in s)
            print(f"  {ph:3s} n={len(s):4d} " + " ".join(f"{k}={c[k]:3d} ({c[k] / len(s):.0%})" for k in C))
        ys = collections.Counter(round(r["y"], 1) for r in q if r["c"] in ("DL_LOCK", "DL_BACK"))
        print("  dead-lane rows (board y):", sorted(ys.items()))


if __name__ == "__main__":
    main()
