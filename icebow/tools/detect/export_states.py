"""Rescue KataCR's per-unit STATE columns before the 1.2 GB source goes away.

Their label lines are 12 columns, not 5. `katacr_boxes.py` keeps column 5 (`bel`, the side)
in `katacr_team.json` and throws the rest away. Columns 6-11 are seven state flags, and this
writes them to `katacr_states.json`, aligned BOX FOR BOX with `katacr_team.json` so the two
sidecars index the same detections.

WHAT THE COLUMNS MEAN -- confirmed, not guessed. Their own annotation spec ("Clash Royale
dataset annotation.md", section "Detail state") names nine states, seven of them per-box:

    col 5   belong      0 / 1                                    -> already in katacr_team.json
    col 6   movement    0 norm  1 attack  2 deploy  3 freeze  4 dash/destroy
    col 7   shield      0 bare/charge     1 shield/over
    col 8   visible     0 visible         1 invisible
    col 9   rage        0 norm            1 rage
    col 10  slow        0 norm            1 slow
    col 11  heal/clone  0 norm            1 heal   2 clone

The measured distribution matches that reading exactly, including the one anomaly: 2,995
`king-tower` boxes carry movement=3 (freeze), which looks absurd until their spec's line
"king-tower_freeze # means king tower hasn't been activated" -- for towers the same column
means something else.

HOW THIN THIS ACTUALLY IS, measured over all 117,026 boxes:

    movement    9,261 non-zero (attack 4,462, freeze 4,194, deploy 605; no dash at all)
    shield      2,221 -- every single one is `royal-recruit`
    slow          132
    visible / rage / heal-clone   ZERO. Not rare -- absent.

So this is ARCHIVAL, not a training set. 4,462 attack examples spread across dozens of
classes will not train a state head, and three of the seven flags have no positive example
to learn from. It is written down because it is ground truth we already paid for, and
because re-deriving it later means re-downloading the whole dataset.

    python icebow/tools/detect/export_states.py [--src <katacr_source>] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parents[2]          # icebow/
sys.path.insert(0, str(HERE / "src"))

from clashrl.katacr_boxes import _REJECT_FRAME, _stem       # noqa: E402
from clashrl.katacr_segments import map_name                # noqa: E402

_STATE_NAMES = ["movement", "shield", "visible", "rage", "slow", "heal_clone"]


def _sources(src: Path) -> tuple[Path, Path, dict[int, str]]:
    ann = next((p for p in (src / "annotation.txt", src / "part2" / "annotation.txt")
                if p.is_file()), None) or next(iter(src.rglob("annotation.txt")), None)
    if ann is None:
        raise SystemExit(f"no annotation.txt under {src}")
    first = ann.read_text(encoding="utf-8").split("\n", 1)[0].split()[0].lstrip("./")
    base = next((c for c in (ann.parent, *src.rglob("part2")) if (c / first).is_file()), None)
    if base is None:
        raise SystemExit(f"annotation.txt found but its frames are not beside it, under {src}")
    y = next(iter([src / "ClashRoyale_detection.yaml"]
                  if (src / "ClashRoyale_detection.yaml").is_file()
                  else src.rglob("ClashRoyale_detection.yaml")), None)
    n = yaml.safe_load(y.read_text(encoding="utf-8"))["names"]
    return ann, base, (n if isinstance(n, dict) else dict(enumerate(n)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=r"C:\Users\Maxi\Desktop\katacr_source")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    ann, base, their = _sources(Path(a.src))
    det = HERE / "data" / "detect"
    ours = [ln.strip() for ln in (det / "classes.txt").read_text(encoding="utf-8").splitlines()
            if ln.strip()]
    idx = {n: i for i, n in enumerate(ours)}

    out: dict[str, list[list[int]]] = {}
    hist = [Counter() for _ in _STATE_NAMES]
    n_boxes = 0

    for line in ann.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        lab = base / parts[1].lstrip("./")
        if not lab.is_file():
            continue

        # THE FILTER HAS TO MATCH katacr_boxes.py EXACTLY, in the same order, or the box
        # index this file stores points at a different detection than katacr_team.json's.
        rows, bad, i = [], False, 0
        for row in lab.read_text(encoding="utf-8").splitlines():
            q = row.split()
            if len(q) < 5:
                continue
            name = their.get(int(q[0]))
            if name is None:
                continue
            if name in _REJECT_FRAME:
                bad = True
                break
            m = map_name(name)
            if m is None or m not in idx:
                continue
            st = [int(q[j]) if len(q) > j and q[j].lstrip("-").isdigit() else 0
                  for j in range(6, 12)]
            for k, v in enumerate(st):
                hist[k][v] += 1
            if any(st):
                rows.append([i] + st)
            i += 1
        if bad:
            continue
        n_boxes += i
        if rows:
            out[_stem(parts[0])] = rows

    print(f"[states] {n_boxes} box(es) kept by the same filter katacr_boxes.py uses; "
          f"{sum(len(v) for v in out.values())} carry a non-default state, "
          f"across {len(out)} frame(s)")
    for k, n in enumerate(_STATE_NAMES):
        nz = {v: c for v, c in sorted(hist[k].items()) if v}
        print(f"[states]   {n:<11} {'-- no positive example' if not nz else nz}")

    if a.dry_run:
        print("[states] --dry-run: nothing written")
        return

    p = det / "katacr_states.json"
    p.write_text(json.dumps({"columns": _STATE_NAMES, "frames": out}, sort_keys=True),
                 encoding="utf-8")
    print(f"[states] -> {p} ({p.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    main()
