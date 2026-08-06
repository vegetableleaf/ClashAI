r"""Sprite bank: cut ANNOTATED units out of their arena background (`run.py sprites`).

Walks the detect dataset (images/{train,val} + YOLO labels), and for every annotated bounding box
runs a GrabCut segmentation seeded by the box itself: the ring of context AROUND the box is definite
background, the box interior is probable foreground. The result is an RGBA sprite (transparent
background) saved under data/detect/sprites/<class>/ -- a per-class SPRITE BANK.

WHY: the detector's frames all share whatever arenas you happened to record, so arena art leaks into
what YOLO learns (the new-arena repaint measurably dropped recall). Background-free sprites are the
raw material for COPY-PASTE augmentation -- compositing real units onto other arena backgrounds /
solid canvases so the detector learns the UNIT, not the lawn it stood on.

`run.py sprites --verify` gauges the cutout quality BEFORE trusting the bank: it samples random
annotated boxes, runs the same extraction live, and tiles side-by-side panels (source crop with the
box, sprite over a checkerboard, sprite over dark/light canvases -- halos and bleed show instantly)
into montage JPGs under sprites/_verify/, including the REJECTED cases with their reason.

Notes:
- `_aoe` classes are SKIPPED: spell area decals are translucent ground overlays; "removing the
  background" of a semi-transparent circle is meaningless and would poison the bank.
- Cutouts with degenerate masks (almost nothing / almost everything kept) are rejected, not saved.
- data/detect is gitignored: the bank stays local, like the rest of the dataset.
"""
from __future__ import annotations

import random
import shutil
import time
from pathlib import Path

import cv2
import numpy as np

from .detect import _load_classes

_MIN_BOX_PX = 12          # boxes smaller than this per side are too thin to segment usefully
_COV_MIN, _COV_MAX = 0.08, 0.97   # kept-pixel fraction of the box outside this range = failed cut


def _boxes_of(label_path: Path):
    out = []
    if not label_path.exists():
        return out
    for line in label_path.read_text(encoding="utf-8").splitlines():
        p = line.split()
        if len(p) >= 5:
            try:
                out.append((int(float(p[0])), *(float(v) for v in p[1:5])))
            except ValueError:
                continue
    return out


def _cut_sprite(img, box_px, margin: float = 0.25):
    """GrabCut one annotated box out of its background.

    box_px = (x0, y0, x1, y1) pixel corners of the ANNOTATION. Returns (sprite_bgra, crop, rect,
    reason): sprite is the tight RGBA cutout or None, crop is the margin-expanded context (for the
    verify panels), rect the box within that crop, reason a reject string or "" on success."""
    H, W = img.shape[:2]
    x0, y0, x1, y1 = (int(round(v)) for v in box_px)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(W, x1), min(H, y1)
    bw, bh = x1 - x0, y1 - y0
    if bw < _MIN_BOX_PX or bh < _MIN_BOX_PX:
        return None, None, None, "too-small"
    mx, my = max(8, int(bw * margin)), max(8, int(bh * margin))
    cx0, cy0, cx1, cy1 = x0 - mx, y0 - my, x1 + mx, y1 + my
    # pad with replicated border where the margin runs off the frame, so GrabCut always has a
    # definite-background ring around the rect (it needs one to model the background colours)
    pl, pt = max(0, -cx0), max(0, -cy0)
    pr, pb = max(0, cx1 - W), max(0, cy1 - H)
    crop = img[max(0, cy0):min(H, cy1), max(0, cx0):min(W, cx1)]
    if pl or pt or pr or pb:
        crop = cv2.copyMakeBorder(crop, pt, pb, pl, pr, cv2.BORDER_REPLICATE)
    rect = (mx, my, bw, bh)                       # the annotation box inside the crop
    mask = np.zeros(crop.shape[:2], np.uint8)
    try:
        cv2.grabCut(crop, mask, rect, np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64),
                    5, cv2.GC_INIT_WITH_RECT)
    except cv2.error:
        return None, crop, rect, "grabcut-error"
    fg = ((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)).astype(np.uint8)
    if float(fg[my:my + bh, mx:mx + bw].sum()) / float(bw * bh) < _COV_MIN:
        # RETRY for low-contrast cases (blue unit on blue arena, purple deploy-tile overlay): the
        # rect init let the background model swallow everything. Seed a mask init instead -- ring =
        # definite background, box = probable foreground, the CENTRAL CORE of the box = definite
        # foreground -- so the unit's body anchors the foreground colour model.
        mask = np.full(crop.shape[:2], cv2.GC_BGD, np.uint8)
        mask[my:my + bh, mx:mx + bw] = cv2.GC_PR_FGD
        core = (my + bh // 4, my + (3 * bh) // 4, mx + bw // 4, mx + (3 * bw) // 4)
        mask[core[0]:core[1], core[2]:core[3]] = cv2.GC_FGD
        try:
            cv2.grabCut(crop, mask, None, np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64),
                        5, cv2.GC_INIT_WITH_MASK)
        except cv2.error:
            return None, crop, rect, "grabcut-error"
        fg = ((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)).astype(np.uint8)
        # the forced core ALWAYS survives a mask init -- only accept the retry if the model actually
        # grew beyond it (a bare rectangular core = a failed cut, not a sprite)
        beyond = fg[my:my + bh, mx:mx + bw].copy()
        beyond[bh // 4:(3 * bh) // 4, bw // 4:(3 * bw) // 4] = 0
        if float(beyond.sum()) / float(bw * bh) < 0.06:
            return None, crop, rect, "empty-mask (retry stayed at the core)"
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    # keep only components that touch the CENTRAL half of the box (stray background blobs out)
    n, lab = cv2.connectedComponents(fg)
    if n > 1:
        cx_lo, cx_hi = mx + bw // 4, mx + (3 * bw) // 4
        cy_lo, cy_hi = my + bh // 4, my + (3 * bh) // 4
        centre = lab[cy_lo:cy_hi, cx_lo:cx_hi]
        keep = {int(v) for v in np.unique(centre) if v != 0}
        fg = np.isin(lab, list(keep)).astype(np.uint8) if keep else np.zeros_like(fg)
    box_fg = fg[my:my + bh, mx:mx + bw]
    cov = float(box_fg.sum()) / float(bw * bh)
    if cov < _COV_MIN:
        return None, crop, rect, f"empty-mask ({cov:.0%})"
    if cov > _COV_MAX:
        return None, crop, rect, f"kept-everything ({cov:.0%})"
    alpha = cv2.GaussianBlur(box_fg * 255, (3, 3), 0)          # 1px feather vs hard halos
    sprite = cv2.cvtColor(crop[my:my + bh, mx:mx + bw], cv2.COLOR_BGR2BGRA)
    sprite[:, :, 3] = alpha
    ys, xs = np.where(alpha > 8)                               # tight-crop to the visible pixels
    if ys.size == 0:
        return None, crop, rect, "empty-mask (0%)"
    sprite = sprite[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return sprite, crop, rect, ""


def _iter_annotations(cfg, split: str):
    root = Path(cfg.path(cfg.get("detect", "dataset_dir", default="data/detect")))
    splits = ["train", "val"] if split == "all" else [split]
    for s in splits:
        for ip in sorted((root / "images" / s).glob("*.jpg")):
            lp = root / "labels" / s / (ip.stem + ".txt")
            boxes = _boxes_of(lp)
            if boxes:
                yield ip, boxes


def extract_sprites(cfg, split: str = "all", margin: float = 0.25, limit: int | None = None,
                    append: bool = False) -> None:
    """Build the sprite bank: every annotated box -> an RGBA cutout under sprites/<class>/.

    A FULL rebuild (default: split=all, no --limit) first CLEARS the existing per-class sprite dirs
    so the bank always reflects the CURRENT annotations -- otherwise a detect-import re-hashes +
    re-splits the images (new stems) and re-annotations move boxes, leaving stale orphan cutouts
    that --synth would paste back into training. `append` (or a --limit trial / a single --split)
    skips the clear so you can accumulate on purpose. The `_verify` montages are never touched."""
    classes = _load_classes(cfg)
    root = Path(cfg.path(cfg.get("detect", "dataset_dir", default="data/detect")))
    out_root = root / "sprites"
    full_rebuild = split == "all" and not limit and not append
    if full_rebuild and out_root.is_dir():
        wiped = 0
        for d in out_root.iterdir():                  # clear class dirs; keep _verify (starts with _)
            if d.is_dir() and not d.name.startswith("_"):
                shutil.rmtree(d, ignore_errors=True); wiped += 1
        if wiped:
            print(f"[sprites] reset: cleared {wiped} class dir(s) for a fresh rebuild (--append to keep)")
    kept = rejected = aoe = 0
    per_class: dict[str, int] = {}
    reasons: dict[str, int] = {}
    t0 = time.time()
    for ip, boxes in _iter_annotations(cfg, split):
        img = cv2.imread(str(ip))
        if img is None:
            continue
        H, W = img.shape[:2]
        for bi, (cid, cx, cy, w, h) in enumerate(boxes):
            if not (0 <= cid < len(classes)):
                continue
            name = classes[cid]
            if name.endswith("_aoe"):                     # translucent ground decals: skip (see module doc)
                aoe += 1
                continue
            box = ((cx - w / 2) * W, (cy - h / 2) * H, (cx + w / 2) * W, (cy + h / 2) * H)
            sprite, _crop, _rect, reason = _cut_sprite(img, box, margin)
            if sprite is None:
                rejected += 1
                reasons[reason.split(" (")[0]] = reasons.get(reason.split(" (")[0], 0) + 1
                continue
            d = out_root / name
            d.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(d / f"{ip.stem}_b{bi}.png"), sprite)
            kept += 1
            per_class[name] = per_class.get(name, 0) + 1
            if limit and kept >= limit:
                break
        if limit and kept >= limit:
            break
    top = sorted(per_class.items(), key=lambda kv: -kv[1])[:12]
    print(f"[sprites] {kept} sprite(s) kept, {rejected} rejected, {aoe} _aoe skipped "
          f"({time.time() - t0:.0f}s) -> {out_root}")
    if reasons:
        print("[sprites] rejects: " + ", ".join(f"{k} x{v}" for k, v in sorted(reasons.items())))
    if top:
        print("[sprites] top classes: " + ", ".join(f"{k} {v}" for k, v in top))
    print("[sprites] gauge the quality with: run.py sprites --verify")


def _checker(h, w, cell=8):
    """The classic alpha-transparency checkerboard."""
    yy, xx = np.mgrid[0:h, 0:w]
    board = (((yy // cell) + (xx // cell)) % 2) * 55 + 170
    return cv2.merge([board.astype(np.uint8)] * 3)


def _over(bg, sprite):
    """Alpha-composite the sprite centred onto a copy of bg (both BGR; sprite BGRA)."""
    out = bg.copy()
    sh, sw = sprite.shape[:2]
    H, W = out.shape[:2]
    scale = min(1.0, (H - 4) / max(1, sh), (W - 4) / max(1, sw))
    if scale < 1.0:
        sprite = cv2.resize(sprite, (max(1, int(sw * scale)), max(1, int(sh * scale))))
        sh, sw = sprite.shape[:2]
    y0, x0 = (H - sh) // 2, (W - sw) // 2
    a = sprite[:, :, 3:4].astype(np.float32) / 255.0
    roi = out[y0:y0 + sh, x0:x0 + sw].astype(np.float32)
    out[y0:y0 + sh, x0:x0 + sw] = (a * sprite[:, :, :3] + (1 - a) * roi).astype(np.uint8)
    return out


def verify_sprites(cfg, count: int = 24, margin: float = 0.25) -> None:
    """Sample random annotated boxes, cut them LIVE, and tile verification panels: source crop with
    the box | sprite on a checkerboard | sprite on dark | sprite on light. Rejects included, with
    their reason -- the honest read on whether the background removal works."""
    classes = _load_classes(cfg)
    all_boxes = []
    for ip, boxes in _iter_annotations(cfg, "all"):
        for bi, b in enumerate(boxes):
            if 0 <= b[0] < len(classes) and not classes[b[0]].endswith("_aoe"):
                all_boxes.append((ip, bi, b))
    if not all_boxes:
        print("[sprites] no annotated boxes found under data/detect -- run detect-import first.")
        return
    sample = random.sample(all_boxes, min(count, len(all_boxes)))
    PH = 108                                                    # panel height
    panels, ok_n = [], 0
    for ip, bi, (cid, cx, cy, w, h) in sample:
        img = cv2.imread(str(ip))
        if img is None:
            continue
        H, W = img.shape[:2]
        box = ((cx - w / 2) * W, (cy - h / 2) * H, (cx + w / 2) * W, (cy + h / 2) * H)
        sprite, crop, rect, reason = _cut_sprite(img, box, margin)
        if crop is None:
            continue
        src = crop.copy()
        if rect is not None:
            cv2.rectangle(src, (rect[0], rect[1]), (rect[0] + rect[2], rect[1] + rect[3]),
                          (0, 255, 0), 1)
        def _fit(p):
            return cv2.resize(p, (max(1, int(p.shape[1] * PH / p.shape[0])), PH))
        cells = [_fit(src)]
        if sprite is not None:
            ok_n += 1
            sq = max(sprite.shape[0], sprite.shape[1]) + 8
            cells += [_fit(_over(_checker(sq, sq), sprite)),
                      _fit(_over(np.full((sq, sq, 3), 40, np.uint8), sprite)),
                      _fit(_over(np.full((sq, sq, 3), 215, np.uint8), sprite))]
            label, colour = classes[cid], (80, 220, 80)
        else:
            label, colour = f"{classes[cid]} REJECT: {reason}", (60, 60, 235)
        panel = np.full((PH + 18, sum(c.shape[1] for c in cells) + 4 * len(cells), 3), 24, np.uint8)
        x = 2
        for c in cells:
            panel[18:18 + PH, x:x + c.shape[1]] = c
            x += c.shape[1] + 4
        cv2.putText(panel, label[:60], (4, 13), cv2.FONT_HERSHEY_SIMPLEX, 0.42, colour, 1, cv2.LINE_AA)
        panels.append(panel)
    if not panels:
        print("[sprites] nothing to verify (no readable images).")
        return
    out_dir = Path(cfg.path(cfg.get("detect", "dataset_dir", default="data/detect"))) / "sprites" / "_verify"
    out_dir.mkdir(parents=True, exist_ok=True)
    per, stamp = 8, time.strftime("%H%M%S")
    written = []
    for pi in range(0, len(panels), per):
        chunk = panels[pi:pi + per]
        wmax = max(p.shape[1] for p in chunk)
        chunk = [cv2.copyMakeBorder(p, 0, 0, 0, wmax - p.shape[1], cv2.BORDER_CONSTANT, value=(24, 24, 24))
                 for p in chunk]
        out = out_dir / f"verify_{stamp}_{pi // per}.jpg"
        cv2.imwrite(str(out), cv2.vconcat(chunk), [cv2.IMWRITE_JPEG_QUALITY, 92])
        written.append(out)
    print(f"[sprites] verified {len(panels)} sample(s): {ok_n} cut cleanly, {len(panels) - ok_n} rejected")
    print("[sprites] panels: source+box | checkerboard | dark | light  (halos/bleed show on the canvases)")
    for p in written:
        print(f"[sprites]   -> {p}")


# ---------------------------------------------------------------------------------------------
# Copy-paste COMPOSITOR: synthesize labeled training frames from the sprite bank.
# ---------------------------------------------------------------------------------------------

def _rect_iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def _paste(img, sprite, x0, y0):
    """Alpha-composite the BGRA sprite onto img at (x0, y0), clipped to the frame."""
    H, W = img.shape[:2]
    sh, sw = sprite.shape[:2]
    sx0, sy0 = max(0, -x0), max(0, -y0)
    dx0, dy0 = max(0, x0), max(0, y0)
    dx1, dy1 = min(W, x0 + sw), min(H, y0 + sh)
    if dx1 <= dx0 or dy1 <= dy0:
        return
    part = sprite[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0)]
    a = part[:, :, 3:4].astype(np.float32) / 255.0
    roi = img[dy0:dy1, dx0:dx1].astype(np.float32)
    img[dy0:dy1, dx0:dx1] = (a * part[:, :, :3] + (1 - a) * roi).astype(np.uint8)


def synth_images(cfg, count: int = 300, paste_max: int = 4, classes_filter: str | None = None,
                 seed: int | None = None) -> None:
    """COPY-PASTE augmentation: paste bank sprites onto ALREADY-LABELED train images and emit the
    merged labels -> data/detect/synth/{images,labels}. Using labeled bases is what makes this safe:
    every real unit in the frame keeps its box (no unlabeled-unit poison), and the pasted sprites
    add fully-known instances on top. Class sampling is weighted 1/sqrt(bank size), so THIN classes
    (the presence-recall gap: skeletons / ice_spirit / guards ...) get boosted hardest; --classes
    restricts pasting to an explicit list. Val is NEVER synthesized -- metrics stay real.

    The synth set lives OUTSIDE images/train so detect-import's wipe never eats it; data.yaml lists
    both dirs (and detect.py's writer re-adds synth/ after every import). Each run REGENERATES the
    whole set (old synth images are cleared) so `--count` is the set size, not a growth increment."""
    import math

    rng = random.Random(seed)
    classes = _load_classes(cfg)
    name_to_id = {n: i for i, n in enumerate(classes)}
    root = Path(cfg.path(cfg.get("detect", "dataset_dir", default="data/detect")))
    quality = int(cfg.get("detect", "jpeg_quality", default=92))
    ax0, ay0, ax1, ay1 = cfg.get("env", "arena_region", default=[0.03, 0.10, 0.97, 0.86])

    want = {c.strip() for c in classes_filter.split(",")} if classes_filter else None
    bank: dict[str, list[Path]] = {}
    sp_root = root / "sprites"
    if sp_root.is_dir():
        for d in sorted(sp_root.iterdir()):
            if d.is_dir() and not d.name.startswith("_") and d.name in name_to_id \
                    and (want is None or d.name in want):
                files = list(d.glob("*.png"))
                if files:
                    bank[d.name] = files
    if not bank:
        print("[sprites] no sprite bank found -- run `run.py sprites` (extraction) first.")
        return
    names = sorted(bank)
    # thin classes get boosted hardest, but CLAMP the skew: a singleton-sprite class at a raw
    # 1/sqrt(1) would out-sample a 400-sprite class ~20:1 and the SAME lone cutout pasted dozens
    # of times just teaches that exact pixel pattern. Flooring the count at 4 caps the ratio ~10:1.
    weights = [1.0 / math.sqrt(max(len(bank[n]), 4)) for n in names]

    # bases = TRAIN images that HAVE a label file (empty = a labeled negative, a fine canvas);
    # their existing boxes ride along into the synthetic labels.
    bases = []
    for ip in sorted((root / "images" / "train").glob("*.jpg")):
        lp = root / "labels" / "train" / (ip.stem + ".txt")
        if lp.exists():
            bases.append((ip, _boxes_of(lp)))
    if not bases:
        print("[sprites] no labeled train images under data/detect -- run detect-import first.")
        return

    out_i, out_l = root / "synth" / "images", root / "synth" / "labels"
    dbg = root / "synth" / "_debug"
    for d in (out_i, out_l, dbg):
        d.mkdir(parents=True, exist_ok=True)
        for f in d.glob("*.*"):
            f.unlink()

    made = pasted = 0
    per_class: dict[str, int] = {}
    t0 = time.time()
    for k in range(count):
        ip, gt = bases[rng.randrange(len(bases))]
        img = cv2.imread(str(ip))
        if img is None:
            continue
        H, W = img.shape[:2]
        lines = [f"{cid} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}" for cid, cx, cy, w, h in gt]
        placed = [((cx - w / 2) * W, (cy - h / 2) * H, (cx + w / 2) * W, (cy + h / 2) * H)
                  for _cid, cx, cy, w, h in gt]
        for _ in range(rng.randint(1, max(1, paste_max))):
            name = rng.choices(names, weights=weights, k=1)[0]
            sp = cv2.imread(str(bank[name][rng.randrange(len(bank[name]))]), cv2.IMREAD_UNCHANGED)
            if sp is None or sp.ndim != 3 or sp.shape[2] != 4:
                continue
            s = rng.uniform(0.85, 1.15)                        # mild size jitter (native scale is real)
            sp = cv2.resize(sp, (max(2, int(sp.shape[1] * s)), max(2, int(sp.shape[0] * s))))
            if rng.random() < 0.5:                             # CR units face both ways -> hflip is realistic
                sp = sp[:, ::-1].copy()
            b = rng.uniform(0.88, 1.12)                        # independent lighting jitter per sprite
            sp[:, :, :3] = np.clip(sp[:, :, :3].astype(np.float32) * b, 0, 255).astype(np.uint8)
            sh, sw = sp.shape[:2]
            if sw >= (ax1 - ax0) * W or sh >= (ay1 - ay0) * H:
                continue
            for _try in range(12):                             # find a spot that doesn't bury anyone
                x0 = int(rng.uniform(ax0 * W, ax1 * W - sw))
                y0 = int(rng.uniform(ay0 * H, ay1 * H - sh))
                rect = (x0, y0, x0 + sw, y0 + sh)
                if all(_rect_iou(rect, r) < 0.30 for r in placed):   # <=30% overlap = healthy occlusion
                    _paste(img, sp, x0, y0)
                    placed.append(rect)
                    lines.append(f"{name_to_id[name]} {(x0 + sw / 2) / W:.6f} {(y0 + sh / 2) / H:.6f} "
                                 f"{sw / W:.6f} {sh / H:.6f}")
                    pasted += 1
                    per_class[name] = per_class.get(name, 0) + 1
                    break
        stem = f"syn_{k:05d}"
        cv2.imwrite(str(out_i / f"{stem}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        (out_l / f"{stem}.txt").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        made += 1
        if made <= 6:                                          # label-alignment eyeball copies
            dbg_img = img.copy()
            for ln in lines:
                p = ln.split()
                cid, cx, cy, w, h = int(p[0]), *(float(v) for v in p[1:5])
                x0b, y0b = int((cx - w / 2) * W), int((cy - h / 2) * H)
                x1b, y1b = int((cx + w / 2) * W), int((cy + h / 2) * H)
                cv2.rectangle(dbg_img, (x0b, y0b), (x1b, y1b), (0, 255, 0), 1)
                cv2.putText(dbg_img, classes[cid][:14], (x0b, max(10, y0b - 3)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1, cv2.LINE_AA)
            cv2.imwrite(str(dbg / f"{stem}.jpg"), dbg_img, [cv2.IMWRITE_JPEG_QUALITY, quality])

    # keep data.yaml pointing at BOTH train dirs (detect-import's writer re-adds synth/ too)
    from .detect import _write_data_yaml
    _write_data_yaml(root, classes)
    top = sorted(per_class.items(), key=lambda kv: -kv[1])[:12]
    print(f"[sprites] synthesized {made} image(s), {pasted} sprite paste(s) "
          f"({time.time() - t0:.0f}s) -> {out_i.parent}")
    if top:
        print("[sprites] pasted classes: " + ", ".join(f"{k} {v}" for k, v in top))
    print(f"[sprites] data.yaml train now includes synth/images; label-check copies in {dbg}")
    print("[sprites] regenerate after every detect-import (the import wipes only images/train, "
          "but its base frames change).")
