"""How do human pros place OFFENSIVE X-Bows across lanes, and does concentrating go with winning?

    icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/loss_review/pro_xbow_lanes.py [--rebuild]

Source: scratchpad/gauntlet/L67/hf/replays/part-*.parquet (52 parts), one 1v1 replay per row, payload_json holds
battle.{team,opponent}.players[0].deck and events[] (kind=play_card, side=team|opponent, replay_tick_20hz,
coordinates.native_world_units = 1/1000 tile, arena 18 x 32 tiles, team side at LOW y, opponent at HIGH y, both
already in ONE absolute frame -- 'inversion_applied' is true on every event).
Own frame: team side as-is; opponent side rotated 180 deg (x -> 18-x, y -> 32-y), so every side has its king at low y.
OFFENSIVE = own-frame y in [12, 16) (within 4 tiles of the river, own half). Lane = x<8 left, x>10 right, |x-9|<1 centre.
Left/right is only a consistent label within one side (rotation does not change pairing within a side-match), so
pooled win rate / switch rate do not depend on which physical flank 'left' is.
Cache of per-side records: %TEMP%/pro_xbow_sides.jsonl (delete or --rebuild to refresh).
Output tables go to stdout and %TEMP%/pro_xbow_tables.md.
"""
import glob
import json
import math
import sys
import tempfile
from collections import Counter
from pathlib import Path

import polars as pl

REPO = Path(__file__).resolve().parents[4]
CACHE = Path(tempfile.gettempdir()) / "pro_xbow_sides.jsonl"
ICEBOW8 = {"tornado", "tesla", "ice-wizard", "x-bow", "rocket", "knight", "the-log", "skeletons"}


def base(k):
    for s in ("-ev1", "-ev2", "-hero"):
        if k.endswith(s):
            return k[: -len(s)]
    return k


def build():
    out = open(CACHE, "w")
    n = 0
    for f in sorted(glob.glob(str(REPO / "scratchpad/gauntlet/L67/hf/replays/part-*.parquet"))):
        df = pl.read_parquet(f, columns=["replay_tag", "battle_type", "game_mode", "payload_json"])
        for tag, bt, gm, pj in df.iter_rows():
            p = json.loads(pj)
            n += 1
            b = p["battle"]
            if len(b["team"]["players"]) != 1 or len(b["opponent"]["players"]) != 1:
                continue
            dur = p.get("replay", {}).get("duration", {}).get("timeline_seconds")
            for side, oth in (("team", "opponent"), ("opponent", "team")):
                pl_ = b[side]["players"][0]
                keys = [c["card_key"] for c in pl_["deck"]]
                if not any(base(k) == "x-bow" for k in keys):
                    continue
                res = b["result"]  # result is from the team side's view
                if res == "draw":
                    win = 0.5
                else:
                    win = 1.0 if (res == "victory") == (side == "team") else 0.0
                xb = []
                for e in p["events"]:
                    if e.get("kind") != "play_card" or e.get("side") != side or base(e["card_key"]) != "x-bow":
                        continue
                    nw = e["coordinates"]["native_world_units"]
                    x, y = nw["x"] / 1000, nw["y"] / 1000
                    if side == "opponent":
                        x, y = 18 - x, 32 - y
                    xb.append((e["replay_tick_20hz"], round(x, 3), round(y, 3)))
                xb.sort()
                out.write(json.dumps({
                    "tag": tag, "side": side, "mode": f"{bt}/{gm}", "win": win,
                    "crowns": b[side]["crowns"], "opp_crowns": b[oth]["crowns"], "dur": dur,
                    "deck": sorted(base(k) for k in keys), "xb": xb}) + "\n")
        print("built", f[-18:], n, flush=True)
    out.close()


def wilson(w, n):
    if n == 0:
        return float("nan"), float("nan")
    p = w / n
    z = 1.96
    d = 1 + z * z / n
    c = (p + z * z / 2 / n) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / 4 / n / n) / d
    return c - h, c + h


def lane(x):
    return None if abs(x - 9) < 1 else ("L" if x < 9 else "R")


def feats(r):
    off = [(t, x, y) for t, x, y in r["xb"] if 12 <= y < 16]
    laned = [l for l in (lane(x) for _, x, _ in off) if l]
    r["n_off"] = len(off)
    r["n_all"] = len(r["xb"])
    r["seq"] = laned
    s = set(laned)
    r["pat"] = "both" if len(s) == 2 else ("one" if len(s) == 1 else "none")
    r["minority"] = (min(laned.count("L"), laned.count("R")) / len(laned)) if laned else None
    return r


def fmt(rows, label):
    lines = [f"\n### {label}", "",
             "| n_off | pattern | matches | share of stratum | win % [95% CI] | mean crowns | mean dur s |",
             "|---|---|---|---|---|---|---|"]

    def row(name, g, tot):
        if not g:
            return
        w = sum(r["win"] for r in g)
        n = len(g)
        lo, hi = wilson(w, n)
        dur = [r["dur"] for r in g if r["dur"]]
        lines.append(f"| {name[0]} | {name[1]} | {n} | {n/tot:.1%} | {w/n:.1%} [{lo:.1%},{hi:.1%}] | "
                     f"{sum(r['crowns'] for r in g)/n:.2f} | {sum(dur)/max(len(dur),1):.0f} |")

    base_rows = [r for r in rows if r["n_off"] >= 1 and r["pat"] != "none"]
    for lab, lo_, hi_ in (("1+", 1, 99), ("2", 2, 2), ("3", 3, 3), ("4", 4, 4), ("5+", 5, 99), ("2+", 2, 99)):
        grp = [r for r in base_rows if lo_ <= r["n_off"] <= hi_]
        for pat in ("both", "one"):
            row((lab, pat), [r for r in grp if r["pat"] == pat], max(len(grp), 1))
    mean = lambda g, k: sum(r[k] for r in g) / max(len(g), 1)
    lines.append(f"\nmean offensive X-Bows: both-lane {mean([r for r in base_rows if r['pat']=='both'], 'n_off'):.2f}, "
                 f"one-lane {mean([r for r in base_rows if r['pat']=='one'], 'n_off'):.2f}")
    return lines


def switch(rows, label):
    c = Counter()
    exp = 0.0
    for r in rows:
        s = r["seq"]
        for i, (a, b) in enumerate(zip(s, s[1:])):
            k = min(i, 2)
            c["pairs"] += 1
            c["sw"] += a != b
            c[f"p{k}"] += 1
            c[f"s{k}"] += a != b
        if len(s) >= 2:
            m, k = len(s), s.count("L")
            exp += (m - 1) * 2 * k * (m - k) / (m * (m - 1))  # unbiased 2q(1-q) given the m draws
    n = c["pairs"]
    lo, hi = wilson(c["sw"], n)
    return [f"| {label} | {n} | {c['sw']/max(n,1):.1%} [{lo:.1%},{hi:.1%}] | " +
            " / ".join(f"{c[f's{k}']/max(c[f'p{k}'],1):.0%} (n={c[f'p{k}']})" for k in range(3)) +
            f" | {exp/max(n,1):.1%} |"]


def main():
    if "--rebuild" in sys.argv or not CACHE.exists():
        build()
    rows = [feats(json.loads(l)) for l in open(CACHE)]
    groups = [("ALL x-bow decks, both sides pooled", rows),
              ("team side only (the tracked top player)", [r for r in rows if r["side"] == "team"]),
              ("opponent side only", [r for r in rows if r["side"] == "opponent"]),
              ("Ranked (pathOfLegend) only", [r for r in rows if r["mode"].startswith("pathOfLegend")]),
              ("Tesla + Ice Wizard decks", [r for r in rows if "tesla" in r["deck"] and "ice-wizard" in r["deck"]]),
              ("exact icebow-8 deck", [r for r in rows if set(r["deck"]) == ICEBOW8])]
    md = ["Offensive = own-frame y in [12,16); lane by x vs 9 (|x-9|<1 = centre, dropped from lane sets).", "",
          f"X-Bow deck-sides: {len(rows)}; with >=1 offensive X-Bow: {sum(r['n_off']>=1 for r in rows)}; "
          f"with >=1 laned offensive X-Bow: {sum(r['pat']!='none' for r in rows)}.", "",
          "All-X-Bow placements per side-match (8 = 8+): " +
          ", ".join(f"{k}:{v}" for k, v in sorted(Counter(min(r['n_all'], 8) for r in rows).items())),
          "Offensive count per side-match (8 = 8+): " +
          ", ".join(f"{k}:{v}" for k, v in sorted(Counter(min(r['n_off'], 8) for r in rows).items())), ""]
    sw = ["", "### Lane switch rate per consecutive pair of laned offensive X-Bows", "",
          "| group | pairs | P(next in other lane) [95% CI] | by pair index 1st->2nd / 2nd->3rd / later | expected if each X-Bow picks lane independently at that side's own L/R mix |",
          "|---|---|---|---|---|"]
    for lab, g in groups:
        md += fmt(g, lab)
        sw += switch(g, lab)
    md += sw
    md += ["", "### Both-lane matches, lopsidedness (>=3 laned offensive X-Bows), all pooled", "",
           "| minority-lane share | matches | win % |", "|---|---|---|"]
    g = [r for r in rows if r["pat"] == "both" and len(r["seq"]) >= 3]
    for lab, f in (("<=1/3 (mostly one lane)", lambda m: m <= 1 / 3 + 1e-9), (">1/3 (balanced)", lambda m: m > 1 / 3 + 1e-9)):
        h = [r for r in g if f(r["minority"])]
        md.append(f"| {lab} | {len(h)} | {sum(r['win'] for r in h)/max(len(h),1):.1%} |")
    text = "\n".join(md)
    print(text)
    Path(tempfile.gettempdir(), "pro_xbow_tables.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
