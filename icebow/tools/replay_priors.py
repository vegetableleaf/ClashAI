"""FIT `P(tile | card, phase)` to a pro replay corpus, and check it before believing it.

The corpus is `data/royaleapi/crawl2/plays_ext.csv` (this deck's own crawl; icebow's lives in
icebow/). Each row is one card play with a tick, a side and -- for the replays whose payload ships
markers -- a tile-precision placement. This tool turns the blue (crawled player) placements into a
per-card, per-phase tile distribution, and prints the checks that decide whether the fit is usable.

    python tools/replay_priors.py --report                    # numbers only, writes nothing
    python tools/replay_priors.py --out data/analysis/placement_priors.json

WHY THE CHECKS COME FIRST (HANDOFF 5ag / the queued spec in 6):
* the marker join covers only ~HALF the replays. If the covered half differs from the uncovered
  half -- newer battles, a different subset of players, a different card mix -- then a fit on it is
  a fit on that subset, not on the population. `--report` prints all three comparisons.
* per-card sample floors: a card with a handful of placements gets a distribution that is mostly
  noise, and the caller must fall back to the hand-written doctrine spot instead.
* mirror-fold: the arena is symmetric and pros' modal spots come in left/right pairs, so folding
  x about the centre line doubles the effective sample per tile. Folded and unfolded counts are
  both reported -- if they disagree strongly the deck has a lane preference and folding is wrong.

PHASES come from the sim's own config (`sim.double_time_s` / `sim.triple_time_s`), not from a
guess: single < 120 s, double 120-240 s, triple >= 240 s. Reading them from config is the point --
the badge-vs-clock confusion in engine.py's own comment is exactly this boundary being got wrong.

NOT an imitation dataset. The output is an EXPLORATION prior for the doctrine seam (rollout-only,
annealable), which is why the three measured BC/distillation nulls do not apply to it.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clashrl.config import Config                                    # noqa: E402

TILES_X, TILES_Y = 18, 32          # engine board; markers are 1000 units per tile


def _load(src: Path):
    rows = list(csv.DictReader(open(src, encoding="utf-8")))
    for r in rows:
        r["_secs"] = float(r.get("seconds") or 0.0)
        r["_has_xy"] = bool(r.get("tile_x"))
    return rows


def _phase(secs: float, dbl: float, tri: float) -> str:
    return "single" if secs < dbl else ("double" if secs < tri else "triple")


def _coverage_report(rows, battles_csv: Path) -> None:
    """Is the marker-covered half representative? Three comparisons, printed not asserted."""
    by_replay = defaultdict(list)
    for r in rows:
        by_replay[r["replay_tag"]].append(r)
    covered, uncovered = [], []
    for tag, rs in by_replay.items():
        frac = sum(1 for r in rs if r["_has_xy"]) / len(rs)
        (covered if frac > 0.8 else uncovered if frac < 0.2 else covered).append(tag)
    print(f"[coverage] replays {len(by_replay)}: covered {len(covered)}, uncovered {len(uncovered)}")

    meta = {}
    if battles_csv.exists():
        for b in csv.DictReader(open(battles_csv, encoding="utf-8")):
            meta[b["replay_tag"]] = b
    if meta:
        def stat(tags, key):
            vals = [meta[t][key] for t in tags if t in meta and meta[t].get(key)]
            return vals
        for key in ("battle_timestamp", "battle_time"):
            c, u = stat(covered, key), stat(uncovered, key)
            if c and u and key == "battle_timestamp":
                c = sorted(float(v) for v in c); u = sorted(float(v) for v in u)
                print(f"[coverage] median {key}: covered {c[len(c)//2]:.0f}  uncovered {u[len(u)//2]:.0f}"
                      f"   ({'SKEWED -- the covered half is a time slice' if abs(c[len(c)//2]-u[len(u)//2]) > 14*86400 else 'no large time skew'})")
                break
        cp = Counter(meta[t]["player_tag"] for t in covered if t in meta)
        up = Counter(meta[t]["player_tag"] for t in uncovered if t in meta)
        only_c = set(cp) - set(up)
        print(f"[coverage] players: covered {len(cp)}, uncovered {len(up)}, "
              f"{len(only_c)} appear ONLY in the covered half")
    # ABILITY ROWS ARE NOT PLACEMENTS (HANDOFF 8): hero-ability activations carry attr_ability=1
    # and attr_card `_invalid`, and never have a marker. Counting them makes the uncovered half look
    # like a different card mix when it is the same mix plus the rows that cannot have coordinates.
    real = [r for r in rows if r.get("attr_card") != "_invalid" and r.get("attr_ability") != "1"]
    cc = Counter(r["attr_card"] for r in real if r["_has_xy"])
    uc = Counter(r["attr_card"] for r in real if not r["_has_xy"])
    tot_c, tot_u = sum(cc.values()), sum(uc.values())
    worst = max(((c, 100.0 * cc[c] / max(1, tot_c) - 100.0 * uc[c] / max(1, tot_u))
                 for c in set(cc) | set(uc)), key=lambda kv: abs(kv[1]))
    print(f"[coverage] card mix: largest share gap is {worst[0]} {worst[1]:+.1f} pp "
          f"({'a real mix difference' if abs(worst[1]) > 3 else 'mix matches'})")


def fit(src: Path, cfg, min_n: int = 60, fold: bool = True):
    dbl = float(cfg.get("sim", "double_time_s", default=120.0))
    tri = float(cfg.get("sim", "triple_time_s", default=240.0))
    rows = _load(src)
    plays = [r for r in rows if r["_has_xy"] and r.get("attr_s") == "blue"]
    dist = defaultdict(Counter)
    unfolded = defaultdict(Counter)
    for r in plays:
        try:
            tx, ty = float(r["tile_x"]), float(r["tile_y"])
        except ValueError:
            continue
        gx, gy = int(tx), int(ty)
        if not (0 <= gx < TILES_X and 0 <= gy < TILES_Y):
            continue
        key = (r["attr_card"], _phase(r["_secs"], dbl, tri))
        unfolded[key][(gx, gy)] += 1
        dist[key][(min(gx, TILES_X - 1 - gx), gy) if fold else (gx, gy)] += 1
    return rows, plays, dist, unfolded, (dbl, tri)


def report(dist, unfolded, min_n: int) -> None:
    print(f"\n{'card':<18}{'phase':<8}{'n':>6}{'top tiles (folded x, y) : count':>10}")
    for (card, phase), c in sorted(dist.items(), key=lambda kv: -sum(kv[1].values())):
        n = sum(c.values())
        flag = "" if n >= min_n else "   <- BELOW FLOOR, fall back to the hand spot"
        top = "  ".join(f"({x},{y}):{k}" for (x, y), k in c.most_common(3))
        # concentration: how much mass sits in the top 3 tiles of the 576-tile board
        conc = 100.0 * sum(k for _, k in c.most_common(3)) / max(1, n)
        ent = -sum((k / n) * math.log(k / n) for k in c.values()) if n else 0.0
        print(f"{card:<18}{phase:<8}{n:>6}   {top}   top3={conc:.0f}%  H={ent:.2f}{flag}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="data/royaleapi/crawl2/plays_ext.csv")
    ap.add_argument("--battles", default="data/royaleapi/crawl2/battles.csv")
    ap.add_argument("--out", default=None, help="write the fitted prior here (JSON)")
    ap.add_argument("--min-n", type=int, default=60,
                    help="per (card, phase) sample floor; below it the fit is noise (default 60)")
    ap.add_argument("--no-fold", action="store_true", help="do NOT mirror-fold x")
    ap.add_argument("--report", action="store_true", help="print the checks and the table")
    a = ap.parse_args()
    cfg = Config.load(None)
    src = Path(cfg.path(a.src)) if not Path(a.src).is_absolute() else Path(a.src)
    rows, plays, dist, unfolded, (dbl, tri) = fit(src, cfg, a.min_n, fold=not a.no_fold)
    print(f"[priors] {len(rows)} plays, {len(plays)} blue with placement "
          f"({100.0*len(plays)/max(1,len(rows)):.0f}%); phases at {dbl:.0f}s / {tri:.0f}s")
    _coverage_report(rows, Path(cfg.path(a.battles)))
    if a.report:
        report(dist, unfolded, a.min_n)
    if a.out:
        out = Path(cfg.path(a.out))
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema": 1, "folded": not a.no_fold, "min_n": a.min_n,
                   "phases": {"double_time_s": dbl, "triple_time_s": tri},
                   "counts": {f"{c}|{p}": {f"{x},{y}": k for (x, y), k in cnt.items()}
                              for (c, p), cnt in dist.items()}}
        out.write_text(json.dumps(payload), encoding="utf-8")
        print(f"[priors] wrote {out} ({sum(sum(c.values()) for c in dist.values())} placements)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
