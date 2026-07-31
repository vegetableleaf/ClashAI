"""Bootstrap a YOLO (Ultralytics) object-detection dataset from your recordings.

Per-unit object detection gives the policy a robust read of the board -- WHAT troop /
building / spell is WHERE -- instead of the coarse red-blob proxies in ``threats``. The
bottleneck is labelled data, so this seeds it two ways from footage you already have:

* AUTO labels for YOUR OWN troops: every card you play is a KNOWN class at a KNOWN spot
  (the labeller in ``label.py`` already pairs the select+placement clicks), so the unit that
  appears at the tap a moment later is localised by a frame diff and boxed automatically.
* FRAMES to hand-label for the ENEMY: a sample of active in-match frames is exported with
  EMPTY label files, ready to annotate in a tool (Label Studio / Roboflow / CVAT).

Output is a ready-to-train Ultralytics dataset under ``detect.dataset_dir`` (images/ +
labels/ + data.yaml). IMPORTANT: the auto (own-troop) labels are a STARTING POINT -- a frame
usually also holds enemy units and other own units the auto-pass can't identify. Open each
frame in your labeller and add those boxes before training, or the detector learns to treat
them as background. Taxonomy: ``detect.classes_file`` (config/detect_classes.yaml).

Then: ``pip install ultralytics`` and ``python tools/detect/train.py``.
"""
from __future__ import annotations

import bisect
import json
import random
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import yaml

from .label import _extract_plays, _latest_session
from .vision import Vision


def _load_classes(cfg) -> list[str]:
    f = Path(cfg.path(cfg.get("detect", "classes_file", default="config/detect_classes.yaml")))
    data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    names = [str(c) for c in (data.get("classes") or [])]
    if not names:
        raise ValueError(f"no classes listed in {f}")
    return names


def _read_at(cap, frame_times, t, total):
    """Read the recorded frame nearest capture time ``t``; returns (frame|None, frame_index)."""
    fi = bisect.bisect_left(frame_times, t)
    fi = max(0, min(fi, max(total - 1, 0)))
    cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
    ok, frame = cap.read()
    return (frame if ok else None), fi


def _localize(pre, post, tap, search_r, dth, min_area, pad):
    """Box (cx, cy, w, h -- all normalized) of the unit that APPEARED near the tap between the
    pre and post frames, via a frame diff restricted to a search window around the tap. Unions
    all near-tap diff blobs (so a spawned Skeletons group boxes as one cluster). None if nothing
    clear appeared (caller then tries a later frame or gives up on that play)."""
    h, w = post.shape[:2]
    x0 = max(0, int((tap[0] - search_r) * w))
    x1 = min(w, int((tap[0] + search_r) * w))
    y0 = max(0, int((tap[1] - search_r) * h))
    y1 = min(h, int((tap[1] + search_r) * h))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    a = cv2.cvtColor(pre[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    b = cv2.cvtColor(post[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    m = cv2.threshold(cv2.absdiff(a, b), dth, 255, cv2.THRESH_BINARY)[1]
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, _, stats, cents = cv2.connectedComponentsWithStats(m, connectivity=8)
    tapx, tapy = tap[0] * w, tap[1] * h
    boxes = []
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < min_area:
            continue
        cx, cy = x0 + cents[i][0], y0 + cents[i][1]
        if abs(cx - tapx) > search_r * w or abs(cy - tapy) > search_r * h:
            continue
        bx, by = x0 + stats[i, cv2.CC_STAT_LEFT], y0 + stats[i, cv2.CC_STAT_TOP]
        boxes.append((bx, by, bx + stats[i, cv2.CC_STAT_WIDTH], by + stats[i, cv2.CC_STAT_HEIGHT]))
    if not boxes:
        return None
    bx0 = min(b[0] for b in boxes)
    by0 = min(b[1] for b in boxes)
    bx1 = max(b[2] for b in boxes)
    by1 = max(b[3] for b in boxes)
    cx = (bx0 + bx1) / 2.0 / w
    cy = (by0 + by1) / 2.0 / h
    bw = min((bx1 - bx0) / w + 2 * pad, 0.9)
    bh = min((by1 - by0) / h + 2 * pad, 0.9)
    if bw < 0.01 or bh < 0.01:
        return None
    return (cx, cy, bw, bh)


class _Writer:
    """Writes images + YOLO label files into an Ultralytics dataset tree, with a train/val split."""

    def __init__(self, root: Path, val_frac: float, jpeg_q: int, seed: int = 0):
        self.root = root
        self.val_frac = val_frac
        self.jpeg_q = int(jpeg_q)
        self.rng = random.Random(seed)
        for sub in ("images/train", "images/val", "labels/train", "labels/val"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        self.n_img = 0
        self.n_box = 0
        self.n_seed = 0        # images that got >=1 auto box

    def add(self, stem: str, frame, boxes):
        """boxes: list of (class_idx, cx, cy, w, h) normalized. Empty -> a frame to hand-label."""
        split = "val" if self.rng.random() < self.val_frac else "train"
        cv2.imwrite(str(self.root / "images" / split / f"{stem}.jpg"), frame,
                    [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_q])
        lines = [f"{c} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}" for c, cx, cy, w, h in boxes]
        (self.root / "labels" / split / f"{stem}.txt").write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        self.n_img += 1
        self.n_box += len(boxes)
        self.n_seed += 1 if boxes else 0


def _write_data_yaml(root: Path, names: list[str]) -> None:
    (root / "data.yaml").write_text(
        "# Auto-generated by `run.py autolabel`. Edit config/detect_classes.yaml for classes.\n"
        f"path: {root.as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n"
        f"nc: {len(names)}\n"
        "names:\n" + "".join(f"  {i}: {n}\n" for i, n in enumerate(names)),
        encoding="utf-8")


def _write_label_studio_helpers(root: Path, names: list[str]) -> None:
    """Helpers for hand-labelling in Label Studio: a ``classes.txt`` (newline-separated names,
    which ``label-studio-converter import yolo`` needs to pull the auto boxes in as
    pre-annotations) and a ready-to-paste labelling-config XML with every class as a box label
    (so you don't hand-type the taxonomy into the project)."""
    (root / "classes.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
    labels = "\n".join(f'    <Label value="{n}"/>' for n in names)
    (root / "label_studio_config.xml").write_text(
        '<View>\n'
        '  <Image name="image" value="$image" zoom="true" zoomControl="true"/>\n'
        '  <RectangleLabels name="label" toName="image">\n'
        f'{labels}\n'
        '  </RectangleLabels>\n'
        '</View>\n', encoding="utf-8")


def _autolabel_session(cfg, session: Path, vision: Vision, names, card_class,
                       writer: _Writer, params, preview_dir):
    meta = json.loads((session / "meta.json").read_text(encoding="utf-8"))
    events = [json.loads(ln) for ln in
              (session / "events.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    video = next((session / n for n in ("video.mp4", "video.avi") if (session / n).exists()), None)
    if video is None:
        print(f"[autolabel] {session.name}: no video")
        return 0, 0
    region = meta["region"]
    frame_times = meta["frame_times"]
    slots = cfg.get("hand", "slots", default=[])
    click_r = float(cfg.get("hand", "click_radius", default=0.06))
    pair_timeout = float(cfg.get("label", "pair_timeout", default=3.0))
    a_top = float(cfg.get("label", "arena_top", default=0.10))
    a_bot = float(cfg.get("label", "arena_bottom", default=0.86))
    plays = _extract_plays(events, region, slots, click_r, pair_timeout, a_top, a_bot)

    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    seeded = 0
    for k, p in enumerate(plays):
        sel_frame, _ = _read_at(cap, frame_times, p["t"], total)
        if sel_frame is None:
            continue
        card = -1
        hand_ids = vision.recognize_hand(sel_frame)
        if 0 <= p["slot"] < len(hand_ids):
            card = hand_ids[p["slot"]]
        cls = card_class.get(card)
        if cls is None:                       # spell / unrecognised / not a mappable troop -> skip
            continue
        tap = (p["nx"], p["ny"])
        box = None
        post_frame = None
        for off in [params["spawn_delay"]] + list(params["extra_offsets"]):
            f, _ = _read_at(cap, frame_times, p["t"] + off, total)
            if f is None:
                continue
            box = _localize(sel_frame, f, tap, params["search_r"], params["dth"],
                            params["min_area"], params["pad"])
            if box is not None:
                post_frame = f
                break
        if box is None or post_frame is None:
            continue
        stem = f"{session.name}_p{k:03d}_{names[cls]}"
        writer.add(stem, post_frame, [(cls, *box)])
        seeded += 1
        if preview_dir is not None:
            _save_preview(preview_dir / f"{stem}.jpg", post_frame, [(names[cls], box)])

    # extra active in-match frames (no auto labels) to hand-label the enemy on. Sample them
    # AROUND your plays -- those moments are guaranteed in-match and busy -- rather than via the
    # menu/in-match template detector, which is a weak positive (it reads most in-match frames as
    # UNKNOWN, so filtering on it exports nothing).
    generals = 0
    want = int(params["general"])
    if want > 0 and plays and total > 0:
        rng = random.Random(hash(session.name) & 0xFFFFFFFF)
        seen = set()
        tries = 0
        while generals < want and tries < want * 8:
            tries += 1
            p = rng.choice(plays)
            frame, fi = _read_at(cap, frame_times, p["t"] + rng.uniform(-1.0, 4.0), total)
            if frame is None or fi in seen:
                continue
            seen.add(fi)
            writer.add(f"{session.name}_g{fi:06d}", frame, [])
            generals += 1
    cap.release()
    print(f"[autolabel] {session.name}: {len(plays)} plays -> {seeded} auto-boxed own troops, "
          f"{generals} frames to hand-label")
    return seeded, generals


def _save_preview(path: Path, frame, named_boxes):
    h, w = frame.shape[:2]
    out = frame.copy()
    for name, (cx, cy, bw, bh) in named_boxes:
        x0, y0 = int((cx - bw / 2) * w), int((cy - bh / 2) * h)
        x1, y1 = int((cx + bw / 2) * w), int((cy + bh / 2) * h)
        cv2.rectangle(out, (x0, y0), (x1, y1), (0, 255, 0), 2)
        cv2.putText(out, name, (x0, max(12, y0 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    cv2.imwrite(str(path), out)


def autolabel(cfg, session_arg=None, do_all=False, preview=False) -> None:
    names = _load_classes(cfg)
    name_to_idx = {n: i for i, n in enumerate(names)}
    vision = Vision(cfg)
    # map deck card index -> detection class index. Prefer the EXACT deck key so an evolved
    # card (e.g. tesla_evo) auto-labels as its own class when that class exists, falling back to
    # the base key otherwise. Spells (rocket/tornado/royal_delivery) don't spawn a trackable unit
    # at the tap, so they simply won't have a mappable troop class and are skipped.
    card_class = {}
    for i, key in enumerate(vision.deck_keys):
        base = key[:-4] if key.endswith("_evo") else key
        cls = name_to_idx.get(key, name_to_idx.get(base))
        if cls is not None:
            card_class[i] = cls

    root = cfg.path(cfg.get("record", "out_dir", default="data/sessions"))
    if do_all:
        sessions = sorted(p for p in root.glob("*") if (p / "meta.json").exists())
    else:
        one = Path(session_arg) if session_arg else _latest_session(root)
        sessions = [one] if one else []
    if not sessions:
        print(f"[autolabel] no sessions under {root}")
        return

    out_root = Path(cfg.path(cfg.get("detect", "dataset_dir", default="data/detect")))
    writer = _Writer(out_root, float(cfg.get("detect", "val_frac", default=0.15)),
                     int(cfg.get("detect", "jpeg_quality", default=92)))
    params = {
        "spawn_delay": float(cfg.get("detect", "spawn_delay_s", default=0.5)),
        "extra_offsets": cfg.get("detect", "spawn_extra_offsets", default=[0.3, 0.8]),
        "search_r": float(cfg.get("detect", "search_radius", default=0.10)),
        "dth": int(cfg.get("detect", "diff_thresh", default=22)),
        "min_area": int(cfg.get("detect", "min_blob_px", default=30)),
        "pad": float(cfg.get("detect", "box_pad", default=0.008)),
        "general": int(cfg.get("detect", "general_per_session", default=40)),
    }
    preview_dir = None
    if preview:
        preview_dir = out_root / "preview"
        preview_dir.mkdir(parents=True, exist_ok=True)

    seeded = generals = 0
    for s in sessions:
        a, g = _autolabel_session(cfg, Path(s), vision, names, card_class, writer, params, preview_dir)
        seeded += a
        generals += g
    _write_data_yaml(out_root, names)
    _write_label_studio_helpers(out_root, names)

    print(f"[autolabel] wrote {writer.n_img} images ({writer.n_seed} with auto boxes, "
          f"{writer.n_box} boxes) to {out_root}")
    print(f"[autolabel] {len(names)} classes -> {out_root / 'data.yaml'}")
    print("[autolabel] NEXT: hand-label the ENEMY units (+ any own units the auto-pass missed) on "
          "every frame, then train. Label Studio:")
    print(f"[autolabel]   1) import the images/ folder as tasks (Settings -> Cloud Storage -> Local files)")
    print(f"[autolabel]   2) paste {out_root / 'label_studio_config.xml'} as the labelling config")
    print(f"[autolabel]   3) (optional) bring the auto boxes in as pre-annotations with "
          "label-studio-converter (uses classes.txt)")
    print("[autolabel]   then: pip install ultralytics && python tools/detect/train.py")
    if preview:
        print(f"[autolabel] auto-box previews (sanity check the own-troop boxes): {preview_dir}")


def detect_import(cfg, export_dir, val_frac=None) -> None:
    """Ingest a Label Studio **YOLO export** into the training dataset. Fixes the two things that
    otherwise bite you: (1) it REMAPS the export's class ids to the taxonomy by NAME (so it doesn't
    matter if Label Studio reordered or compacted the class list), and (2) it lays the images +
    labels into the Ultralytics train/val split the trainer expects and rebuilds data.yaml. The
    export becomes the source of truth, so the previous (auto-labelled) split is replaced.

    Point ``export_dir`` at the unzipped export (a folder with ``classes.txt`` + ``labels/`` and,
    for a 'YOLO with images' export, ``images/``). If the export has no images/, the images are
    taken from the current dataset by matching label filenames to image stems.
    """
    export = Path(export_dir)
    names = _load_classes(cfg)
    name_to_idx = {n: i for i, n in enumerate(names)}
    cls_file = export / "classes.txt"
    lbl_dir = export / "labels"
    if not cls_file.exists() or not lbl_dir.exists():
        print(f"[detect-import] expected {cls_file.name} + labels/ under {export} "
              "(export from Label Studio as YOLO).")
        return
    export_names = [ln.strip() for ln in cls_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    remap, unknown = {}, []
    for i, nm in enumerate(export_names):
        if nm in name_to_idx:
            remap[i] = name_to_idx[nm]
        else:
            unknown.append(nm)

    root = Path(cfg.path(cfg.get("detect", "dataset_dir", default="data/detect")))
    existing = {}                                        # image stem -> path (fallback source)
    for split in ("train", "val"):
        d = root / "images" / split
        if d.exists():
            for p in d.glob("*"):
                if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
                    existing[p.stem] = p
    exp_imgs = export / "images"

    pairs, unmatched = [], 0                             # (stem, image_ndarray, [remapped label lines])
    for lf in sorted(lbl_dir.glob("*.txt")):
        stem = lf.stem
        src = None
        if exp_imgs.exists():
            cands = list(exp_imgs.glob(stem + ".*"))
            src = cands[0] if cands else None
        if src is None:                                  # match to a current dataset image by stem
            src = existing.get(stem) or next(
                (existing[s] for s in existing if s == stem or stem.endswith("_" + s) or s in stem), None)
        if src is None:
            unmatched += 1
            continue
        img = cv2.imread(str(src))
        if img is None:
            unmatched += 1
            continue
        lines = []
        for ln in lf.read_text(encoding="utf-8").splitlines():
            p = ln.split()
            if len(p) >= 5 and int(float(p[0])) in remap:
                lines.append(" ".join([str(remap[int(float(p[0]))])] + p[1:5]))
        pairs.append((stem, img, lines))

    if not pairs:
        print("[detect-import] matched 0 label files to images -- check the export layout / filenames.")
        return
    # the export is now the source of truth -> clear the old auto-labelled split, then write fresh
    for sub in ("images/train", "images/val", "labels/train", "labels/val"):
        d = root / sub
        d.mkdir(parents=True, exist_ok=True)
        for p in d.glob("*"):
            p.unlink()
    vf = float(val_frac if val_frac is not None else cfg.get("detect", "val_frac", default=0.15))
    q = int(cfg.get("detect", "jpeg_quality", default=92))
    rng = random.Random(0)
    n_val = n_box = 0
    for stem, img, lines in pairs:
        split = "val" if rng.random() < vf else "train"
        n_val += split == "val"
        n_box += len(lines)
        cv2.imwrite(str(root / "images" / split / f"{stem}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, q])
        (root / "labels" / split / f"{stem}.txt").write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    _write_data_yaml(root, names)
    _write_label_studio_helpers(root, names)

    print(f"[detect-import] imported {len(pairs)} images ({len(pairs) - n_val} train / {n_val} val), "
          f"{n_box} boxes -> {root}")
    if unknown:
        print(f"[detect-import] {len(unknown)} export class(es) not in the taxonomy (their boxes were "
              f"skipped): {', '.join(unknown[:12])}")
    if unmatched:
        print(f"[detect-import] {unmatched} label file(s) had no matching image (skipped)")
    print("[detect-import] ready to train:  python tools/detect/train.py")


def add_frames(cfg, session_arg=None, count=120, val_frac=None) -> None:
    """Extract COUNT extra in-match frames from a recording into the detect dataset, as empty-label
    images to hand-label. ADDITIVE + NON-DESTRUCTIVE: it only writes NEW frame indices (skipping any
    already in data/detect) into images/train, so existing images -- and any Label Studio project
    pointing at them -- are left untouched. Frames are sampled around your plays (guaranteed in-match).
    """
    root_sessions = cfg.path(cfg.get("record", "out_dir", default="data/sessions"))
    if session_arg and Path(session_arg).exists():
        session = Path(session_arg)
    elif session_arg:
        session = Path(root_sessions) / session_arg
    else:
        session = _latest_session(Path(root_sessions))
    if session is None or not (session / "meta.json").exists():
        print(f"[detect-frames] no such session: {session_arg}")
        return
    meta = json.loads((session / "meta.json").read_text(encoding="utf-8"))
    events = [json.loads(ln) for ln in
              (session / "events.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    video = next((session / n for n in ("video.mp4", "video.avi") if (session / n).exists()), None)
    if video is None:
        print(f"[detect-frames] {session.name}: no video")
        return
    region, frame_times = meta["region"], meta["frame_times"]
    plays = _extract_plays(events, region, cfg.get("hand", "slots", default=[]),
                           float(cfg.get("hand", "click_radius", default=0.06)),
                           float(cfg.get("label", "pair_timeout", default=3.0)),
                           float(cfg.get("label", "arena_top", default=0.10)),
                           float(cfg.get("label", "arena_bottom", default=0.86)))
    if not plays:
        print(f"[detect-frames] {session.name}: no plays found (can't locate in-match frames)")
        return

    root = Path(cfg.path(cfg.get("detect", "dataset_dir", default="data/detect")))
    vf = float(val_frac if val_frac is not None else cfg.get("detect", "val_frac", default=0.15))
    for sub in ("images/train", "images/val", "labels/train", "labels/val"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    existing = set()                                    # frame indices already in the dataset (any split)
    for split in ("train", "val"):
        for p in (root / "images" / split).glob(f"{session.name}_g*.jpg"):
            try:
                existing.add(int(p.stem.rsplit("_g", 1)[1]))
            except (ValueError, IndexError):
                pass

    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    q = int(cfg.get("detect", "jpeg_quality", default=92))
    rng = random.Random()                               # unseeded: fresh frames each call
    added = tries = nval = 0
    while added < count and tries < count * 12:
        tries += 1
        frame, fi = _read_at(cap, frame_times, rng.choice(plays)["t"] + rng.uniform(-2.0, 6.0), total)
        if frame is None or fi in existing:
            continue
        existing.add(fi)
        stem = f"{session.name}_g{fi:06d}"
        split = "val" if rng.random() < vf else "train"
        cv2.imwrite(str(root / "images" / split / f"{stem}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, q])
        (root / "labels" / split / f"{stem}.txt").write_text("", encoding="utf-8")
        nval += split == "val"
        added += 1
    cap.release()
    print(f"[detect-frames] {session.name}: added {added} new frames ({added - nval} train / {nval} val, "
          f"empty labels) -> {root / 'images'}. Existing images + splits untouched -- re-sync Local Storage in Label Studio.")


def add_timelapse_frames(cfg, video=None, per_video=12, diff_thresh=5.0, val_frac=None, recent=0) -> None:
    """Sample frames from training TIMELAPSE videos into the detect dataset as empty-label images to
    hand-label. Timelapses (``train.timelapse_dir``) are raw game-screen captures -- the SAME rendering
    as the live env -- so they are valid detector data. Unlike sessions they carry NO play log, so
    frames are sampled UNIFORMLY across each clip and consecutive near-duplicates (the fixed-length
    timelapse resampler REPEATS frames when a run was short) are skipped by a mean-abs-diff test.
    ADDITIVE + NON-DESTRUCTIVE: only writes NEW `tl_*` stems into images/train, so existing images --
    and any Label Studio project pointing at them -- are left untouched.
    """
    if video:
        vids = [Path(video)]
    else:
        tl_dir = Path(cfg.path(cfg.get("train", "timelapse_dir", default="data/timelapses")))
        vids = sorted(tl_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
        if recent and recent > 0:
            vids = vids[-recent:]                             # only the N most-recent timelapses
    if not vids:
        print("[detect-timelapse] no timelapse videos found (train.timelapse_dir)")
        return

    root = Path(cfg.path(cfg.get("detect", "dataset_dir", default="data/detect")))
    vf = float(val_frac if val_frac is not None else cfg.get("detect", "val_frac", default=0.15))
    _split_rng = random.Random()
    for sub in ("images/train", "images/val", "labels/train", "labels/val"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    existing = set()                                     # tl_* stems already in the dataset (any split)
    for split in ("train", "val"):
        existing.update(p.stem for p in (root / "images" / split).glob("tl_*.jpg"))

    q = int(cfg.get("detect", "jpeg_quality", default=92))
    total = 0
    for vid in vids:
        cap = cv2.VideoCapture(str(vid))
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if n <= 0:
            cap.release()
            continue
        cand = np.linspace(0, n - 1, min(n, per_video * 3)).astype(int)  # oversample; dedupe trims it
        added, last = 0, None
        for fi in cand:
            if added >= per_video:
                break
            stem = f"tl_{vid.stem}_f{int(fi):06d}"
            if stem in existing:
                continue
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(fi))
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            cur = frame.astype(np.int16)
            if last is not None and float(np.abs(cur - last).mean()) < diff_thresh:
                continue                                 # a repeated (resampled) frame -> skip
            last = cur
            split = "val" if _split_rng.random() < vf else "train"
            cv2.imwrite(str(root / "images" / split / f"{stem}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, q])
            (root / "labels" / split / f"{stem}.txt").write_text("", encoding="utf-8")
            existing.add(stem)
            added += 1
            total += 1
        cap.release()
        print(f"[detect-timelapse] {vid.stem}: +{added}")
    print(f"[detect-timelapse] added {total} frames (~{int((1 - vf) * 100)}% train / ~{int(vf * 100)}% val, "
          f"empty labels) -> {root / 'images'}. Re-sync Local Storage in Label Studio to pick them up.")


def _resolve_weights(cfg, weights):
    """Return the detector weights path: the given --weights, else the most recently trained
    runs/detect/*/weights/best.pt."""
    runs = Path(cfg.path("runs/detect"))
    if weights:
        return Path(weights), runs
    cands = sorted(runs.glob("*/weights/best.pt"), key=lambda p: p.stat().st_mtime)
    return (cands[-1] if cands else None), runs


def detect_preview(cfg, session_arg=None, count=24, weights=None, conf=0.25) -> None:
    """Run the trained detector on RANDOM in-match frames and save annotated images so you can gauge
    detection quality on frames it never trained on.

    UNBIASED sampling: frames are drawn uniformly at random from the pooled match window of EVERY
    session (first->last play, padded) -- not clustered around plays (unlike autolabel/detect-frames)
    and not weighted by session beyond its real share of playtime. Read-only: touches nothing in the
    dataset. Unseeded, so each run is a fresh random draw.
    """
    wpath, runs = _resolve_weights(cfg, weights)
    if wpath is None:
        print("[detect-preview] no weights found under runs/detect/*/weights/best.pt -- train first: "
              "python tools/detect/train.py")
        return
    if not wpath.exists():
        print(f"[detect-preview] no such weights: {wpath}")
        return
    try:                                                 # a best.pt loads for its own family
        from ultralytics import YOLO
        model = YOLO(str(wpath))
    except Exception:
        from ultralytics import RTDETR
        model = RTDETR(str(wpath))

    root_sessions = Path(cfg.path(cfg.get("record", "out_dir", default="data/sessions")))
    if session_arg and Path(session_arg).exists():
        sessions = [Path(session_arg)]
    elif session_arg:
        sessions = [root_sessions / session_arg]
    else:
        sessions = sorted(d for d in root_sessions.iterdir() if (d / "meta.json").exists())

    pre = float(cfg.get("detect", "preview_pre_s", default=8.0))
    post = float(cfg.get("detect", "preview_post_s", default=10.0))
    info: dict[str, Path] = {}                            # session name -> video path
    pool: list[tuple[str, int]] = []                     # every in-match (session, frame index)
    for s in sessions:
        if not (s / "meta.json").exists():
            print(f"[detect-preview] skip {s.name}: no meta.json")
            continue
        meta = json.loads((s / "meta.json").read_text(encoding="utf-8"))
        ev = s / "events.jsonl"
        events = [json.loads(ln) for ln in ev.read_text(encoding="utf-8").splitlines()
                  if ln.strip()] if ev.exists() else []
        video = next((s / n for n in ("video.mp4", "video.avi") if (s / n).exists()), None)
        if video is None:
            print(f"[detect-preview] skip {s.name}: no video")
            continue
        region, frame_times = meta["region"], meta["frame_times"]
        plays = _extract_plays(events, region, cfg.get("hand", "slots", default=[]),
                               float(cfg.get("hand", "click_radius", default=0.06)),
                               float(cfg.get("label", "pair_timeout", default=3.0)),
                               float(cfg.get("label", "arena_top", default=0.10)),
                               float(cfg.get("label", "arena_bottom", default=0.86)))
        if not plays:
            print(f"[detect-preview] skip {s.name}: no plays (can't bound the match)")
            continue
        t0 = min(p["t"] for p in plays) - pre
        t1 = max(p["t"] for p in plays) + post
        lo = max(0, bisect.bisect_left(frame_times, t0))
        hi = min(len(frame_times), bisect.bisect_right(frame_times, t1))
        if hi <= lo:
            continue
        info[s.name] = video
        pool.extend((s.name, fi) for fi in range(lo, hi))

    if not pool:
        print("[detect-preview] no in-match frames found across the selected session(s).")
        return
    rng = random.Random()                                # unseeded: a fresh random draw each run
    picks = rng.sample(pool, min(count, len(pool)))

    out_dir = runs / "preview" / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    by_session: dict[str, list[int]] = defaultdict(list)
    for name, fi in picks:
        by_session[name].append(fi)

    saved = total_dets = 0
    class_counts: Counter = Counter()
    for name, fis in by_session.items():
        cap = cv2.VideoCapture(str(info[name]))
        for fi in sorted(fis):
            cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            res = model.predict(frame, conf=conf, verbose=False)[0]
            cv2.imwrite(str(out_dir / f"{name}_g{fi:06d}.jpg"), res.plot())
            saved += 1
            total_dets += len(res.boxes)
            for c in res.boxes.cls.tolist():
                class_counts[model.names[int(c)]] += 1
        cap.release()

    top = ", ".join(f"{k}:{v}" for k, v in class_counts.most_common(12)) or "(none)"
    print(f"[detect-preview] {saved} random frames from {len(by_session)} session(s), "
          f"{total_dets} detections (avg {total_dets / max(saved, 1):.1f}/frame) @conf>={conf}, "
          f"weights={wpath.parent.parent.name}")
    print(f"[detect-preview] classes seen: {top}")
    print(f"[detect-preview] annotated images -> {out_dir}")
