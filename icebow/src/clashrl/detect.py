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
import hashlib
import json
import math
import random
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

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
    # If a SYNTHETIC copy-paste set exists (run.py sprites --synth), keep it in the train list so a
    # detect-import (which regenerates this file) never silently drops it. Val stays REAL-only.
    train = "train: images/train\n"
    if (root / "synth" / "images").is_dir() and any((root / "synth" / "images").glob("*.jpg")):
        train = "train:\n  - images/train\n  - synth/images\n"
    (root / "data.yaml").write_text(
        "# Auto-generated by `run.py autolabel`. Edit config/detect_classes.yaml for classes.\n"
        f"path: {root.as_posix()}\n"
        + train +
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


def draw_detections(frame, dets):
    """Return a COPY of ``frame`` with the detector's boxes drawn -- enemy=red, yours=blue, unknown=grey,
    each labelled with the base card + confidence. Boxes are normalized (cx,cy,w,h) so this works at any
    frame size (e.g. a downscaled monitor clip). ``dets`` = a list of clashrl.replay_mine.Detection."""
    out = frame.copy()
    h, w = out.shape[:2]
    colours = {"enemy": (60, 60, 230), "mine": (230, 150, 60), "unknown": (150, 150, 150)}   # BGR
    for d in dets:
        x0, y0 = int((d.cx - d.w / 2) * w), int((d.cy - d.h / 2) * h)
        x1, y1 = int((d.cx + d.w / 2) * w), int((d.cy + d.h / 2) * h)
        c = colours.get(d.team, colours["unknown"])
        cv2.rectangle(out, (x0, y0), (x1, y1), c, 2)
        cv2.putText(out, f"{d.base} {d.conf:.2f}", (x0, max(11, y0 - 3)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, c, 1, cv2.LINE_AA)
    return out


class LivePreview:
    """Side window shown during train-rl: LIVE game frames with the detector's team-coloured boxes
    (:func:`draw_detections`). The env pushes its newest tagged detections at the act cadence
    (~1.5s -- that IS how often the policy perceives); a background REFRESHER THREAD redraws them
    onto fresh frames at ``preview.fps`` so the video is smooth while the boxes update at the
    policy's own rate. The thread owns a private WindowCapture (mss handles are per-thread; the
    env's capture is untouched -- same pattern as the Discord monitor).

    The capture is a SCREEN grab, so this window must NEVER cover the game (it would be captured
    into the next frame): it auto-positions just RIGHT of the capture region (``preview.pos``
    overrides). Closing the window disables it for the session; any GUI failure (headless, no
    HighGUI) degrades to a permanent silent no-op."""

    _TITLE = "clashrl detector"

    def __init__(self, cfg):
        self.enabled = bool(cfg.get("preview", "enabled", default=True))
        self.scale = float(cfg.get("preview", "scale", default=0.5))
        self.pos = cfg.get("preview", "pos", default=None)
        self.fps = min(30.0, max(1.0, float(cfg.get("preview", "fps", default=15.0))))
        self._title_contains = cfg.get("window", "title_contains", default=None)
        self._region_cfg = cfg.get("window", "region", default=None)
        self._dets: list = []
        self._region = None
        self._placed = False
        self._lock = threading.Lock()
        self._thread = None

    def update(self, frame, dets, region=None) -> None:
        """Env-side: cache the newest detections for the refresher (starts it on first use).
        ``frame`` is unused (the thread grabs its own live frames); kept for call-site clarity."""
        if not self.enabled:
            return
        with self._lock:
            self._dets = list(dets or [])
        self._region = region
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="clashrl-preview", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        try:
            from .capture import WindowCapture
            cap = WindowCapture(self._title_contains, self._region_cfg)
        except Exception:
            self.enabled = False
            return
        period = 1.0 / self.fps
        while self.enabled:
            t0 = time.time()
            try:
                frame = cap.grab()
                if frame is None:
                    cap.refresh_region()
                    time.sleep(0.5)
                    continue
                if self._placed and cv2.getWindowProperty(self._TITLE, cv2.WND_PROP_VISIBLE) < 1:
                    self.enabled = False                   # user closed the window -> respect it
                    break
                with self._lock:
                    dets = self._dets
                small = draw_detections(frame, dets)
                if self.scale and self.scale != 1.0:
                    small = cv2.resize(small, None, fx=self.scale, fy=self.scale)
                cv2.imshow(self._TITLE, small)
                if not self._placed:                       # position ONCE (don't fight the user dragging)
                    region = self._region
                    if self.pos:
                        x, y = int(self.pos[0]), int(self.pos[1])
                    elif region is not None:               # beside the game, clear of the screen capture
                        x, y = region.left + region.width + 12, max(0, region.top)
                    else:
                        x, y = 60, 60
                    cv2.moveWindow(self._TITLE, x, y)
                    self._placed = True
                cv2.waitKey(1)                             # pump HighGUI (this thread owns ALL GUI calls)
            except Exception:
                self.enabled = False                       # headless / GUI unavailable -> silent no-op
                break
            time.sleep(max(0.0, period - (time.time() - t0)))


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


def _obb_to_bbox(coords):
    """Fold a Label Studio YOLO label's coords to an axis-aligned ``[cx, cy, w, h]`` (strings).
    Accepts a standard YOLO bbox (``cx cy w h`` = 4 values) AND an OBB / polygon export
    (``x1 y1 x2 y2 ...`` = an even count >= 6 of normalized corner points), which Label Studio
    emits when the rectangle tool allows ROTATION -- those get folded to their bounding box
    (without this, corner coords were misread as w/h, inflating every box). Returns None if the
    coords don't form a bbox or polygon."""
    try:
        v = [float(c) for c in coords]
    except ValueError:
        return None
    if len(v) == 4:                                        # cx cy w h (standard YOLO detection)
        return [f"{x:.6f}" for x in v]
    if len(v) >= 6 and len(v) % 2 == 0:                   # x1 y1 x2 y2 ... (OBB / polygon) -> bbox
        xs, ys = v[0::2], v[1::2]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        return [f"{(x0 + x1) / 2:.6f}", f"{(y0 + y1) / 2:.6f}", f"{x1 - x0:.6f}", f"{y1 - y0:.6f}"]
    return None


def _ls_export_image_name(ref: str) -> str:
    """The on-disk image filename from a Label Studio task image reference. Handles the Windows
    local-files form ``/data/local-files/?d=to_label%5Ctrl_...jpg`` (or with a raw backslash) ->
    ``trl_...jpg`` (drops the ``?d=`` prefix + any subfolder + URL-encoding)."""
    s = unquote(str(ref))                                # %5C -> '\', %20 -> ' ', ...
    if "?d=" in s:
        s = s.split("?d=", 1)[1]
    s = s.split("&", 1)[0].replace("\\", "/")
    return s.rsplit("/", 1)[-1]


def _ls_rect_to_yolo(v: dict):
    """A Label Studio rectangle region (``x, y, width, height`` as PERCENTAGES 0-100, optional
    ``rotation`` in degrees about the top-left corner) -> normalized ``[cx, cy, w, h]`` strings.
    A rotated rectangle is folded to its axis-aligned bounding box."""
    try:
        x, y, w, h = float(v["x"]), float(v["y"]), float(v["width"]), float(v["height"])
    except (KeyError, ValueError, TypeError):
        return None
    rot = float(v.get("rotation", 0) or 0)
    if abs(rot) < 1e-6:
        x0, y0, x1, y1 = x, y, x + w, y + h
    else:
        a = math.radians(rot)
        ca, sa = math.cos(a), math.sin(a)
        corners = ((0, 0), (w, 0), (w, h), (0, h))
        xs = [x + dx * ca - dy * sa for dx, dy in corners]
        ys = [y + dx * sa + dy * ca for dx, dy in corners]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    cx = min(max((x0 + x1) / 200.0, 0.0), 1.0)
    cy = min(max((y0 + y1) / 200.0, 0.0), 1.0)
    bw = min(max((x1 - x0) / 100.0, 0.0), 1.0)
    bh = min(max((y1 - y0) / 100.0, 0.0), 1.0)
    return [f"{cx:.6f}", f"{cy:.6f}", f"{bw:.6f}", f"{bh:.6f}"]


def _ls_task_regions(task: dict):
    """Every rectangle-region ``value`` dict for a Label Studio task, across the FULL JSON
    (``annotations[].result[]``) and the JSON-MIN (a top-level list field) export shapes."""
    regions = []
    for ann in task.get("annotations", []) or []:
        for r in ann.get("result", []) or []:
            v = r.get("value", {})
            if v.get("rectanglelabels"):
                regions.append(v)
    if regions:
        return regions
    for val in task.values():                            # JSON-MIN: a from_name field holds the regions
        if isinstance(val, list):
            for r in val:
                if isinstance(r, dict) and r.get("rectanglelabels") and "width" in r:
                    regions.append(r)
    return regions


def _ls_json_pairs(json_path: Path, root: Path, name_to_idx: dict):
    """Parse a Label Studio JSON / JSON-MIN export into ``(stem, image, [label lines])`` triples --
    the SAME shape the YOLO path produces. Sidesteps the Windows YOLO-export crash (label filenames
    derived from ``?d=...\\...`` URLs contain ``? = \\`` = illegal on Windows). Images are matched by
    basename against the dataset (the labelling queue / any split), so a plain 'JSON' export (no
    image files) is enough."""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("annotations") or data.get("tasks") or [data]
    by_name = {}                                         # basename + stem -> on-disk image path
    imgs_root = root / "images"
    if imgs_root.exists():
        for p in imgs_root.rglob("*"):
            if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
                by_name.setdefault(p.name, p)
                by_name.setdefault(p.stem, p)
    pairs, unmatched, unknown = [], 0, set()
    for task in data:
        d = task.get("data") if isinstance(task.get("data"), dict) else None
        ref = (d or {}).get("image") or task.get("image")
        if not ref:
            continue
        fname = _ls_export_image_name(ref)
        src = by_name.get(fname) or by_name.get(Path(fname).stem)
        if src is None:
            unmatched += 1
            continue
        img = cv2.imread(str(src))
        if img is None:
            unmatched += 1
            continue
        lines = []
        for v in _ls_task_regions(task):
            nm = v["rectanglelabels"][0]
            if nm not in name_to_idx:
                unknown.add(nm)
                continue
            bb = _ls_rect_to_yolo(v)
            if bb is not None:
                lines.append(" ".join([str(name_to_idx[nm])] + bb))
        pairs.append((Path(fname).stem, img, lines))
    return pairs, unmatched, sorted(unknown)


def _yolo_export_pairs(export: Path, root: Path, name_to_idx: dict):
    """Parse a Label Studio YOLO export (``classes.txt`` + ``labels/`` + optional ``images/``) into
    ``(stem, image, [label lines])`` triples, remapping class ids to the taxonomy BY NAME."""
    export_names = [ln.strip() for ln in (export / "classes.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
    remap, unknown = {}, []
    for i, nm in enumerate(export_names):
        if nm in name_to_idx:
            remap[i] = name_to_idx[nm]
        else:
            unknown.append(nm)
    existing = {}                                        # image stem -> path (fallback source)
    for split in ("train", "val"):
        d = root / "images" / split
        if d.exists():
            for p in d.glob("*"):
                if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
                    existing[p.stem] = p
    exp_imgs = export / "images"
    pairs, unmatched = [], 0
    for lf in sorted((export / "labels").glob("*.txt")):
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
            if len(p) < 5:
                continue
            cid = int(float(p[0]))
            if cid not in remap:
                continue
            bb = _obb_to_bbox(p[1:])                     # YOLO bbox OR OBB/polygon export -> cx cy w h
            if bb is not None:
                lines.append(" ".join([str(remap[cid])] + bb))
        pairs.append((stem, img, lines))
    return pairs, unmatched, unknown


def _stable_split(stem: str, val_frac: float) -> str:
    """Assign an image to train/val by a STABLE hash of its filename.

    A positional RNG (``random.Random(0)`` walked down the import list) is deterministic only for an
    UNCHANGED list: adding images shifts every later image's draw, so pictures MIGRATE between train
    and val on each re-import. That silently makes consecutive detector generations incomparable --
    the val set they are scored on is not the same set -- and it means a previous generation's val
    images can become the next one's TRAINING data, so scoring an OLD checkpoint on the NEW val set
    is contaminated. Hashing the stem instead pins each image to one side for its whole lifetime,
    regardless of dataset size or import order. ``hashlib`` (not ``hash()``) because Python
    randomises string hashing per process."""
    h = int(hashlib.md5(stem.encode("utf-8")).hexdigest()[:8], 16)
    return "val" if (h % 10_000) < val_frac * 10_000 else "train"


def detect_import(cfg, export_dir, val_frac=None) -> None:
    """Ingest a Label Studio export into the training dataset. REMAPS classes to the taxonomy by NAME
    (order/compaction-proof) and lays images + labels into the Ultralytics train/val split + rebuilds
    data.yaml -- the export becomes the source of truth, so the previous split is replaced.

    Accepts EITHER a **JSON export** (a .json file, or a folder containing one) OR a **YOLO export**
    (a folder with ``classes.txt`` + ``labels/`` + optionally ``images/``). PREFER JSON on Windows:
    the YOLO export CRASHES when Local Storage serves files via ``?d=...\\...`` URLs -- the per-image
    label filename Label Studio derives then contains ``? = \\`` (illegal on Windows). Images are
    matched by basename to the current dataset (the labelling queue / existing split), so a plain
    'JSON' export (no image files) is enough.
    """
    export = Path(export_dir)
    names = _load_classes(cfg)
    name_to_idx = {n: i for i, n in enumerate(names)}
    root = Path(cfg.path(cfg.get("detect", "dataset_dir", default="data/detect")))

    json_path = None
    if export.is_file() and export.suffix.lower() == ".json":
        json_path = export
    elif export.is_dir() and not ((export / "classes.txt").exists() and (export / "labels").exists()):
        js = sorted(export.glob("*.json"))
        json_path = js[0] if js else None

    if json_path is not None:
        pairs, unmatched, unknown = _ls_json_pairs(json_path, root, name_to_idx)
        src_desc = f"JSON export ({json_path.name})"
    elif export.is_dir() and (export / "classes.txt").exists() and (export / "labels").exists():
        pairs, unmatched, unknown = _yolo_export_pairs(export, root, name_to_idx)
        src_desc = "YOLO export"
    else:
        print(f"[detect-import] {export} is not a Label Studio export -- expected a .json file, OR a "
              "folder with either a *.json (JSON export) or classes.txt + labels/ (YOLO export).")
        return

    if not pairs:
        print(f"[detect-import] matched 0 annotations to images from the {src_desc} -- check the export "
              "and that its images are in the dataset (the labelling queue).")
        return
    # the export is the source of truth -> clear the old split, then write fresh
    for sub in ("images/train", "images/val", "labels/train", "labels/val"):
        d = root / sub
        d.mkdir(parents=True, exist_ok=True)
        for p in d.glob("*"):
            p.unlink()
    vf = float(val_frac if val_frac is not None else cfg.get("detect", "val_frac", default=0.15))
    q = int(cfg.get("detect", "jpeg_quality", default=92))
    n_val = n_box = 0
    for stem, img, lines in pairs:
        split = _stable_split(stem, vf)
        n_val += split == "val"
        n_box += len(lines)
        cv2.imwrite(str(root / "images" / split / f"{stem}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, q])
        (root / "labels" / split / f"{stem}.txt").write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    _write_data_yaml(root, names)
    _write_label_studio_helpers(root, names)

    print(f"[detect-import] imported {len(pairs)} images ({len(pairs) - n_val} train / {n_val} val), "
          f"{n_box} boxes from the {src_desc} -> {root}")
    if unknown:
        print(f"[detect-import] {len(unknown)} export class(es) not in the taxonomy (their boxes were "
              f"skipped): {', '.join(unknown[:12])}")
    if unmatched:
        print(f"[detect-import] {unmatched} task(s)/label(s) had no matching image (skipped)")
    print("[detect-import] ready to train:  python tools/detect/train.py")


def _queue_dir(cfg) -> Path:
    """The flat LABELLING-QUEUE folder (data/detect/images/<detect.label_queue_subdir>, default to_label)
    that the frame extractors drop NEW images into for hand-labelling. Kept FLAT (no train/val subfolders)
    so Label Studio Local Storage can point straight at it -- flat paths dodge the Windows `train\\file`
    backslash bug -- and OUTSIDE the train/val split that detect-import WIPES, so the queue survives an
    import. detect-import still reads the LS EXPORT (not this folder) to build the training split."""
    d = (Path(cfg.path(cfg.get("detect", "dataset_dir", default="data/detect"))) / "images"
         / str(cfg.get("detect", "label_queue_subdir", default="to_label")))
    d.mkdir(parents=True, exist_ok=True)
    return d


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

    qdir = _queue_dir(cfg)                              # flat labelling queue (survives detect-import; LS reads it flat)
    existing = set()                                    # frame indices already queued
    for p in qdir.glob(f"{session.name}_g*.jpg"):
        try:
            existing.add(int(p.stem.rsplit("_g", 1)[1]))
        except (ValueError, IndexError):
            pass

    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    q = int(cfg.get("detect", "jpeg_quality", default=92))
    rng = random.Random()                               # unseeded: fresh frames each call
    added = tries = 0
    while added < count and tries < count * 12:
        tries += 1
        frame, fi = _read_at(cap, frame_times, rng.choice(plays)["t"] + rng.uniform(-2.0, 6.0), total)
        if frame is None or fi in existing:
            continue
        existing.add(fi)
        stem = f"{session.name}_g{fi:06d}"
        cv2.imwrite(str(qdir / f"{stem}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, q])
        added += 1
    cap.release()
    print(f"[detect-frames] {session.name}: added {added} new frames -> {qdir}. "
          f"Point Label Studio Local Storage at this folder + Sync.")


def add_timelapse_frames(cfg, video=None, per_video=12, diff_thresh=5.0, val_frac=None, recent=0,
                         min_sharpness=420.0) -> None:
    """Sample frames from training TIMELAPSE videos into the detect dataset as empty-label images to
    hand-label. Timelapses (``train.timelapse_dir``) are raw game-screen captures -- the SAME rendering
    as the live env -- so they are valid detector data. Unlike sessions they carry NO play log, so
    frames are sampled UNIFORMLY across each clip and consecutive near-duplicates (the fixed-length
    timelapse resampler REPEATS frames when a run was short) are skipped by a mean-abs-diff test.
    ``min_sharpness`` (variance-of-Laplacian at width 480; 0 disables) skips MOTION-BLURRED and
    transition frames -- external replay footage (HunterCR) is full of them and they are useless
    to label (measured: transition garbage < ~420, clean own-capture frames ~750+).
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

    qdir = _queue_dir(cfg)                               # flat labelling queue (survives detect-import; LS reads it flat)
    existing = set(p.stem for p in qdir.glob("tl_*.jpg"))

    def _sharp(img) -> float:
        """Variance of Laplacian at width 480 (comparable across source resolutions)."""
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = g.shape
        if w != 480:
            g = cv2.resize(g, (480, max(1, round(h * 480 / w))), interpolation=cv2.INTER_AREA)
        return float(cv2.Laplacian(g, cv2.CV_64F).var())

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
            # blur gate with a LOCAL SEARCH: replay footage blurs in bursts (action / transitions),
            # so if the sampled frame is soft, walk +-12 frames and keep the SHARPEST one in the
            # window that clears the gate (uniform coverage is preserved; garbage is not).
            best = None                                  # (sharpness, fi, frame)
            for off in (0, 4, -4, 8, -8, 12, -12):
                fj = int(min(max(fi + off, 0), n - 1))
                stem_j = f"tl_{vid.stem}_f{fj:06d}"
                if stem_j in existing:
                    continue
                cap.set(cv2.CAP_PROP_POS_FRAMES, fj)
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                s = _sharp(frame) if min_sharpness > 0 else float("inf")
                if best is None or s > best[0]:
                    best = (s, fj, frame)
                if s >= min_sharpness * 1.3:             # comfortably sharp -> stop searching
                    break
            if best is None or (min_sharpness > 0 and best[0] < min_sharpness):
                continue                                 # the whole window is blurred -> skip this slot
            s, fj, frame = best
            stem = f"tl_{vid.stem}_f{fj:06d}"
            cur = frame.astype(np.int16)
            if last is not None and float(np.abs(cur - last).mean()) < diff_thresh:
                continue                                 # a repeated (resampled) frame -> skip
            last = cur
            cv2.imwrite(str(qdir / f"{stem}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, q])
            existing.add(stem)
            added += 1
            total += 1
        cap.release()
        print(f"[detect-timelapse] {vid.stem}: +{added}")
    print(f"[detect-timelapse] added {total} frames -> {qdir}. "
          f"Point Label Studio Local Storage at this folder + Sync.")


class TrainFrameCollector:
    """Harvest annotation frames DURING a train-rl session: save the live game frame into the flat
    labelling QUEUE (data/detect/images/<detect.label_queue_subdir>) once every ``every_s`` seconds of
    match play, capped ``per_match`` per match and ``session_max`` for the whole run. Writes NEW
    ``trl_<runstamp>_<n>.jpg`` only -- a flat, import-safe folder Label Studio can point straight at, so a
    live training run doubles as data collection and the queue survives detect-import."""

    def __init__(self, cfg, every_s=5.0, per_match=20, session_max=200):
        self.queue = _queue_dir(cfg)
        self.root = self.queue                           # exposed for the train-rl harvest summary print
        self.jpeg_q = int(cfg.get("detect", "jpeg_quality", default=92))
        self.every_s = float(every_s)
        self.per_match = int(per_match)
        self.session_max = int(session_max)
        self.stamp = time.strftime("%Y%m%d_%H%M%S")
        self.session_count = 0
        self._match_count = 0
        self._last_t = None

    def new_match(self) -> None:
        """Call at the START of each match: reset the per-match cap + restart the interval clock."""
        self._match_count = 0
        self._last_t = None

    def maybe_capture(self, frame, now=None) -> bool:
        """Save ``frame`` if the interval has elapsed and neither cap is hit. Returns True if it saved."""
        if frame is None or self.session_count >= self.session_max or self._match_count >= self.per_match:
            return False
        now = time.time() if now is None else now
        if self._last_t is None:                         # first in-match frame -> start the clock (no shot yet)
            self._last_t = now
            return False
        if now - self._last_t < self.every_s:
            return False
        self._last_t = now
        cv2.imwrite(str(self.queue / f"trl_{self.stamp}_{self.session_count:04d}.jpg"),
                    frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_q])
        self.session_count += 1
        self._match_count += 1
        return True


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
