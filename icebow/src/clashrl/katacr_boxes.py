"""Import KataCR's hand-labelled DETECTION frames (`images/part2`) into our training split.

`katacr_segments` imports their cut-out sprites, which feed `synth`. This imports the other half
of their dataset: 6,939 real frames a human boxed by hand. That is the thing our detector was
starving for -- the plateau at mAP50 0.71 was diagnosed as a long tail, 83 of 133 val classes
sitting at <=5 instances, and no amount of synth fixes a class the model has never seen in a real
frame.

FOUR decisions here are load-bearing, and each one is a silent corruption if taken the other way.

1. EVERYTHING GOES TO TRAIN. Their `val_annotation.txt` is not a clean held-out set: all 35 of its
   episodes also appear in their train split, so their val frames are neighbours -- often seconds
   apart -- of their train frames. Folding that into OUR val would import the leak and inflate every
   number we measure afterwards. Our own 401-image val set is left untouched, which is also what
   makes the next detector directly comparable to the current one (see `_load_split`: val is meant
   to grow as a SUPERSET, never to be reshuffled).

2. NO RESCALE. Their frames are an arena-only crop at 568x896; ours are full phone screenshots at
   nine different sizes. That looks like a scale mismatch but is not: measured over the 60 classes
   both sets label at least 20 times, the median ratio of our box height to theirs is 0.929. A unit
   lands within 7% of the same pixel size, so resizing would CREATE the mismatch it looks like it
   is fixing. (Contrast `katacr_segments`, where the sprites really are ~1.6x too large -- there the
   segments are pasted at native size onto OUR arena, so the geometry is genuinely different.)

3. A FRAME CONTAINING A BODY WE CANNOT NAME IS REJECTED WHOLE. `map_name` drops what it cannot
   resolve, which is right for sprites -- a bad sprite forges a wrong synth label. For frames the
   calculus inverts: keeping the frame while dropping the box leaves a visible unit with no label,
   which trains the detector to SUPPRESS it. Towers and UI are safe to drop (we model no tower
   class, so both datasets leave them unlabelled and agree), and so are small effects nobody boxes.
   Real bodies are not. `_REJECT_FRAME` names them.

4. THE FRIEND/ENEMY COLUMN IS KEPT, OUT OF BAND. Their label lines carry twelve fields, not five:
   after the YOLO five comes `bel`, the side the unit belongs to -- ground truth for the one thing
   `TeamTracker` can only ever infer. Ultralytics reads a sixth column as a segmentation polygon and
   dies, so it CANNOT go in the label file; it goes to `katacr_team.json` instead, where it costs
   nothing and stays recoverable. Re-deriving it later would mean re-doing this import.
"""
from __future__ import annotations

import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .katacr_segments import map_name

# Bodies a viewer plainly sees but our taxonomy has no name for. Dropping the BOX would teach
# suppression, so the whole frame goes. Cheap: ~310 frames of 6,939.
_REJECT_FRAME = {
    "goblin-brawler",             # goblin_cage's spawn -- deliberately unmodelled, but very visible
    "royal-recruit-evolution",    # we hold `royal_recruit` (a body) and `royal_recruits_evo` (a
                                  # card); guessing which one their box means is the corruption
    "phoenix-egg",
}

_FRAME_RE = re.compile(r"\s+(\d+):\s*(\S+)")


def _their_names(root: Path) -> Dict[int, str]:
    """Their class index -> their class name, from ClashRoyale_detection.yaml."""
    y = root / "ClashRoyale_detection.yaml"
    if not y.is_file():
        return {}
    out = {}
    for line in y.read_text(encoding="utf-8").splitlines():
        m = _FRAME_RE.match(line)
        if m:
            out[int(m.group(1))] = m.group(2)
    return out


def _find_part2(src: Path) -> Optional[Path]:
    """Accept the repo root, images/, or part2 itself."""
    for c in (src, src / "part2", src / "images" / "part2"):
        if (c / "annotation.txt").is_file():
            return c
    return None


def _stem(rel: str) -> str:
    """'./WTY_20240305/1/00810.jpg' -> 'katacr_WTY_20240305_1_00810'.

    Their frame numbers repeat across episodes, so the episode path has to survive into the name or
    the import silently collapses 41 episodes onto a few hundred stems. The prefix also keeps the
    provenance readable in the labelling tab and makes a re-import idempotent."""
    p = rel.lstrip("./").replace("\\", "/")
    return "katacr_" + p[: p.rfind(".")].replace("/", "_")


def katacr_boxes(cfg, src: str, dry_run: bool = False, limit: int = 0) -> None:
    from .detect import _load_classes, _write_data_yaml

    ours = _load_classes(cfg)
    idx = {n: i for i, n in enumerate(ours)}
    root = Path(cfg.path(cfg.get("detect", "dataset_dir", default="data/detect")))

    sp = _find_part2(Path(src))
    if sp is None:
        print(f"[katacr-boxes] no annotation.txt under {src} -- point --src at their dataset folder")
        return
    their = _their_names(sp)
    if not their:
        print(f"[katacr-boxes] {sp}/ClashRoyale_detection.yaml missing or unreadable")
        return

    # ---- pass 1: read, map, decide ------------------------------------
    keep: List[Tuple[str, Path, List[Tuple[int, float, float, float, float]], List[int]]] = []
    rejected = Counter()
    gained = Counter()
    unmatched = Counter()
    n_seen = n_empty = 0

    for line in (sp / "annotation.txt").read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        img = sp / parts[0].lstrip("./")
        lab = sp / parts[1].lstrip("./")
        if not img.is_file() or not lab.is_file():
            continue
        n_seen += 1
        boxes, sides, bad = [], [], None
        for row in lab.read_text(encoding="utf-8").splitlines():
            q = row.split()
            if len(q) < 5:
                continue
            name = their.get(int(q[0]))
            if name is None:
                continue
            if name in _REJECT_FRAME:
                bad = name
                break
            m = map_name(name)
            if m is None:
                continue
            if m not in idx:
                unmatched[f"{name} -> {m}"] += 1
                continue
            boxes.append((idx[m], float(q[1]), float(q[2]), float(q[3]), float(q[4])))
            # `bel` is their affiliation column; absent on a malformed row, hence the guard
            sides.append(int(q[5]) if len(q) > 5 and q[5].lstrip("-").isdigit() else -1)
            gained[m] += 1
        if bad:
            rejected[bad] += 1
            continue
        if not boxes:
            n_empty += 1
        keep.append((_stem(parts[0]), img, boxes, sides))
        if limit and len(keep) >= limit:
            break

    # ---- report --------------------------------------------------------
    have = Counter()
    for split in ("train", "val"):
        for lp in (root / "labels" / split).glob("*.txt"):
            for row in lp.read_text(encoding="utf-8").splitlines():
                q = row.split()
                if len(q) >= 5:
                    have[ours[int(q[0])]] += 1

    print(f"[katacr-boxes] {sp}")
    print(f"[katacr-boxes] {n_seen} frame(s) read; keeping {len(keep)}, "
          f"{n_empty} of them with no box (kept ON PURPOSE: an empty arena teaches the detector not "
          f"to fire on one)")
    if rejected:
        print("[katacr-boxes] frames REJECTED WHOLE -- they show a body our taxonomy cannot name, "
              "and an unlabelled body trains suppression:")
        for n, c in rejected.most_common():
            print(f"               {n:<28} {c:>5} frame(s)")
    if unmatched:
        print("[katacr-boxes] mapped to a name we do NOT have (boxes dropped, frames kept):")
        for n, c in unmatched.most_common(10):
            print(f"               {n:<40} {c:>6} box(es)")
    new = [c for c in gained if have.get(c, 0) == 0]
    print(f"[katacr-boxes] {sum(gained.values())} usable box(es) across {len(gained)} class(es); "
          f"{len(new)} class(es) go from ZERO real boxes to some")
    if new:
        print(f"               {', '.join(sorted(new))}")
    print(f"[katacr-boxes] dataset boxes {sum(have.values())} -> "
          f"{sum(have.values()) + sum(gained.values())}")
    print(f"{'':15}{'class':<22}{'now':>8}{'+new':>8}{'after':>8}")
    for c, g in gained.most_common(15):
        print(f"{'':15}{c:<22}{have.get(c, 0):>8}{g:>8}{have.get(c, 0) + g:>8}")

    if dry_run:
        print("[katacr-boxes] --dry-run: nothing written")
        return

    # ---- pass 2: write --------------------------------------------------
    (root / "images" / "train").mkdir(parents=True, exist_ok=True)
    (root / "labels" / "train").mkdir(parents=True, exist_ok=True)
    split_p = root / "split.json"
    split = json.loads(split_p.read_text(encoding="utf-8")) if split_p.is_file() else {}
    team_p = root / "katacr_team.json"
    team = json.loads(team_p.read_text(encoding="utf-8")) if team_p.is_file() else {}

    wrote = 0
    for stem, img, boxes, sides in keep:
        # copy, not re-encode: they are already jpg, and a second lossy pass buys nothing
        shutil.copyfile(img, root / "images" / "train" / f"{stem}.jpg")
        (root / "labels" / "train" / f"{stem}.txt").write_text(
            "".join(f"{c} {x:.6f} {y:.6f} {w:.6f} {h:.6f}\n" for c, x, y, w, h in boxes),
            encoding="utf-8")
        split[stem] = "train"
        if sides:
            team[stem] = sides
        wrote += 1

    split_p.write_text(json.dumps(split, indent=1, sort_keys=True), encoding="utf-8")
    team_p.write_text(json.dumps(team, sort_keys=True), encoding="utf-8")
    _write_data_yaml(root, ours)
    print(f"[katacr-boxes] wrote {wrote} frame(s) into images/train + labels/train")
    print(f"[katacr-boxes] friend/enemy ground truth for {len(team)} frame(s) -> {team_p.name} "
          f"(kept out of the label files: ultralytics reads a 6th column as a polygon)")
    print("[katacr-boxes] val/ untouched -- the next detector stays comparable to the current one")
