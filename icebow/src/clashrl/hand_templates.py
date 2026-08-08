"""Build hand-card templates from a recording, for identity-based recognition.

Your deck's cards cycle through the 4 tray slots over a match, so this samples
in-match frames, crops each tray slot, and keeps the visually DISTINCT crops --
one per card face (an evolved card counts as its own face). By default it only
surfaces cards **not already covered by your existing templates**, so you can
record more and re-run to fill in the ones you're still missing without wading
through cards you've already done (`--include-known` re-dumps everything). It
saves crops as `_cand_<i>.png` plus a labelled `_candidates.png` montage under
`hand.templates_dir`; you rename each to its identity: `<key>.png` (or
`<key>_evo.png` for the evolved face). Then `verify --hand` confirms recognition.

Naming is left to you on purpose: you know your deck, and renaming off the montage
is quick and reliable -- more so than guessing card identities from art. Existing
renamed templates are never touched.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .vision import Vision

_STD = (64, 80)     # normalized candidate size (w, h) for dedup + montage


def _latest_session(root: Path):
    found = [p for p in root.glob("*") if (p / "meta.json").exists()]
    return max(found, key=lambda p: p.name) if found else None


def build_hand_templates(cfg, session_arg=None, only_new: bool = True,
                         distinct: float = 0.8, samples: int = 500) -> None:
    root = cfg.path(cfg.get("record", "out_dir", default="data/sessions"))
    from .label import _resolve_session
    session = _resolve_session(root, session_arg) if session_arg else _latest_session(root)
    if session is None or not Path(session).exists():
        print(f"[hand-templates] no session found under {root}")
        return
    session = Path(session)
    video = next((session / n for n in ("video.mp4", "video.avi") if (session / n).exists()), None)
    if video is None:
        print(f"[hand-templates] no video in {session}")
        return

    vision = Vision(cfg)
    out_dir = cfg.path(cfg.get("hand", "templates_dir", default="templates/cards"))
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    kept: list = []                                  # distinct normalized crops of NEW cards
    for fi in np.linspace(0, max(total - 1, 0), samples).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(fi))
        ok, frame = cap.read()
        if not ok:
            continue
        if vision.detect_state(frame).name != "IN_MATCH":   # only frames where the hand is shown
            continue
        for cx, cy in vision.hand_slots:
            crop = vision.hand_crop(frame, cx, cy)
            if crop.size == 0:
                continue
            if only_new and vision.match_card(crop)[0] >= 0:    # already covered by a template
                continue
            std = cv2.resize(crop, _STD, interpolation=cv2.INTER_AREA)
            if all(float(cv2.matchTemplate(std, k, cv2.TM_CCOEFF_NORMED).max()) < distinct for k in kept):
                kept.append(std)
    cap.release()

    if only_new and not kept:
        print(f"[hand-templates] {session.name}: no new HAND cards -- your existing templates "
              "already cover every tray card in this recording.")
    else:
        for i, k in enumerate(kept):
            cv2.imwrite(str(out_dir / f"_cand_{i}.png"), k)
        _montage(kept, out_dir / "_candidates.png")

        scope = "new " if only_new else ""
        skipped = " (cards already covered by your templates were skipped)" if only_new else ""
        print(f"[hand-templates] {session.name}: {len(kept)} distinct {scope}card crops -> {out_dir}{skipped}")
        print(f"[hand-templates] card identities: {', '.join(vision.deck_keys) or '(none - check cards.yaml deck)'}")
        print("[hand-templates] open _candidates.png, then rename each _cand_<i>.png to one of the "
              "identities above, e.g. musketeer.png. An EVOLVED card is a SEPARATE identity -- name "
              "those crops <key>_evo.png. Multiple crops of one identity are fine and help -- add "
              "_2/_3 (e.g. tesla_2.png, tesla_evo_2.png). Any file starting with an identity counts; "
              "delete leftover _cand_*.png. Then run `verify --hand` to check recognition.")

    _build_next_templates(cfg, vision, video, total, only_new, distinct, samples)


def _build_next_templates(cfg, vision, video, total, only_new, distinct, samples) -> None:
    """Dump 'next card' preview candidates for labeling under templates/next/.

    The next preview is a smaller, blue-tinted rendering that does NOT match the in-hand
    templates, so it needs its own set. Same workflow: rename each crop to its identity.
    """
    if not vision.next_slot:
        return
    out_dir = cfg.path(cfg.get("hand", "next_templates_dir", default="templates/next"))
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video))
    kept: list = []
    for fi in np.linspace(0, max(total - 1, 0), samples).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(fi))
        ok, frame = cap.read()
        if not ok or vision.detect_state(frame).name != "IN_MATCH":
            continue
        crop = vision.next_crop(frame)
        if crop.size == 0:
            continue
        if only_new and vision.recognize_next(frame) >= 0:       # already covered by a next template
            continue
        std = cv2.resize(crop, _STD, interpolation=cv2.INTER_AREA)
        if all(float(cv2.matchTemplate(std, k, cv2.TM_CCOEFF_NORMED).max()) < distinct for k in kept):
            kept.append(std)
    cap.release()

    if only_new and not kept:
        print("[hand-templates] next preview: no new cards -- templates/next already covers this "
              "recording. (Re-run with --include-known to re-dump.)")
        return
    for i, k in enumerate(kept):
        cv2.imwrite(str(out_dir / f"_cand_{i}.png"), k)
    _montage(kept, out_dir / "_candidates.png")
    print(f"[hand-templates] NEXT preview: {len(kept)} distinct crops -> {out_dir}")
    print("[hand-templates] rename each templates/next/_cand_<i>.png to its identity (SAME names as "
          "the hand: <key>.png, <key>_evo.png, extra crops <key>_2.png). These are the smaller 'next' "
          "rendering, kept separate. Some crops may show a '1sec' cycle timer -- delete those. Then "
          "`verify --hand` shows the next-card match.")


def _montage(crops: list, path: Path) -> None:
    if not crops:
        return
    w, h = _STD
    cols = min(6, len(crops))
    rows = (len(crops) + cols - 1) // cols
    pad = 18
    canvas = np.full((rows * (h + pad), cols * w, 3), 40, np.uint8)
    for i, c in enumerate(crops):
        r, col = divmod(i, cols)
        y0, x0 = r * (h + pad), col * w
        canvas[y0:y0 + h, x0:x0 + w] = c
        cv2.putText(canvas, str(i), (x0 + 2, y0 + h + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.imwrite(str(path), canvas)
