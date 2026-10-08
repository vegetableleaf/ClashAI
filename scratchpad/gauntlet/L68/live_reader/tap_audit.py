"""Intended vs executed placement on recorded live logs (owner 2026-10-07: "one tile too far left or right").

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L68/live_reader/tap_audit.py [--logs DIR]

Per own play with a public audit (decision raw_bodies, 2026-10-05 on) and a single-body card: INTENDED = the decision
xy, EXECUTED = the confirmed event's spawn (first new own entity of the card), both in my-frame tiles. Prints the
x/y error by card type, side and lattice parity (odd cell = tile centre), the tap-formula check (logged tap ==
Layout.board), and replays pipeline.live_gen.legal_cells on the logged board: plays the legal guard would re-aim
vs plays the game actually moved >= 1 tile.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3]))
sys.path.insert(0, str(HERE))
from pipeline import obs_contract  # noqa: E402
from pipeline.live_gen import legal_cells  # noqa: E402
from pipeline.obs_contract import _catalog_names  # noqa: E402
if not (obs_contract.REPO / "research/ext").is_dir() and obs_contract.REPO.parent.name == "worktrees":
    obs_contract.REPO = obs_contract.REPO.parents[2]     # a worktree has no untracked catalog: read the main checkout's
from live_play import EVEN_BUILDINGS, Layout  # noqa: E402

SINGLE = {"Knight", "Tesla", "Xbow", "MiniPekka", "Bomber", "Giant", "Musketeer", "Valkyrie", "Wizard", "BattleRam"}


def rows(log_dir: Path):
    base = {}
    for i, n in _catalog_names().items():
        if i // 1_000_000 in (26, 27, 28):
            base.setdefault(n, i)
    lay = Layout(900, 1600)
    for fn in sorted(glob.glob(str(log_dir / "live_play_2026*.jsonl"))):
        dec = play = scr = None
        for line in open(fn, encoding="utf-8"):
            if not ('"event": "play"' in line or '"event": "confirmed"' in line or '"event": "start"' in line
                    or ('"event": "decision"' in line and '"play": true' in line)):
                continue
            e = json.loads(line)
            if e["event"] == "start":
                scr = e.get("screen")
            elif e["event"] == "decision":
                dec = e
            elif e["event"] == "play":
                play = e if dec and dec["tick"] == e["tick"] else None
            elif (play and play["name"] == e["name"] and scr == [900, 1600] and dec.get("public")
                  and e["name"] in SINGLE and e["spawn"]):
                side = dec["public"]["observer_side"]
                cx, cy = round(e["intended"][0] * 36), round(e["intended"][1] * 64)
                xy = (cx / 36, cy / 64)
                ok = legal_cells(dec["public"]["raw_bodies"], side, base[e["name"]], e["name"])
                yield dict(file=Path(fn).name, tick=play["tick"], name=e["name"], side=side,
                           type="tesla2x2" if e["name"] in EVEN_BUILDINGS else
                           ("building3x3" if base[e["name"]] // 1_000_000 == 27 else "troop"),
                           parity=("C" if cx % 2 else "E") + ("C" if cy % 2 else "E"),
                           tap_ok=play["tap_board"] == list(lay.board(xy, side, even=e["name"] in EVEN_BUILDINGS)),
                           dx=round((e["spawn"][0][0] - xy[0]) * 18, 1), dy=round((xy[1] - e["spawn"][0][1]) * 32, 1),
                           guard=ok is not None and not ok[cy * 36 + cx])
                play = dec = None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", type=Path, default=HERE)
    ap.add_argument("--show", action="store_true", help="list the plays where re-aim and moved disagree")
    a = ap.parse_args()
    R = list(rows(a.logs))
    moved = lambda r: abs(r["dx"]) >= 0.9 or abs(r["dy"]) >= 0.9  # noqa: E731
    print(f"plays: {len(R)}   logged tap == Layout.board(intended): {sum(r['tap_ok'] for r in R)}/{len(R)}")
    g = collections.defaultdict(list)
    for r in R:
        g[(r["type"], r["side"], r["parity"])].append(r)
    print("type, side, parity(x,y)        n   |dx|>=1   |dy|>=1")
    for k in sorted(g):
        v = g[k]
        print(f"  {str(k):30} {len(v):5d} {sum(abs(r['dx']) >= .9 for r in v):6d} {sum(abs(r['dy']) >= .9 for r in v):8d}")
    c = collections.Counter((r["guard"], moved(r)) for r in R)
    print("legal guard replay (would re-aim, game moved the card >= 1 tile):")
    for k in ((True, True), (True, False), (False, True), (False, False)):
        print(f"  re-aim={k[0]!s:5} moved={k[1]!s:5} {c[k]:5d}")
    for r in R if a.show else ():
        if r["guard"] != moved(r):
            print("  ", r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
