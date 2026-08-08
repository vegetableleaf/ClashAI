r"""Recognise the deck from a recording instead of renaming crops by hand.

The tray shows every deck card sooner or later, and its four slots are already
calibrated (`hand.slots`), so this samples in-match frames, groups the crops into
distinct card faces, and IDENTIFIES each face against the reference pictures in
`templates/cardart/` (see `card_art.py`) instead of asking you to name them.

How the matching works, and why: a tray crop is a strongly zoomed sub-window of the
card illustration, and an unaffordable card is drawn greyed out. So each crop is
searched INSIDE the reference picture at several scales with a normalised
correlation on contrast-equalised grayscale, which ignores brightness and colour
shifts. One crop alone is not reliable enough; averaging the scores over several
frames of the same face is. Measured against the 190 hand-labelled crops in
`templates/cards/` with all 181 reference pictures competing: 83 % correct from a
single crop, 12 of 12 cards correct when 6 crops of a face are averaged.

An evolved face (`<key>_evo`) is folded back onto its base card and only sets the
`evolved` flag, because both faces are the same deck slot.

Card LEVELS are not visible in the tray. With an official-API token and your player
tag they are read from your account; otherwise the levels already in cards.yaml are
kept and reported as unchanged.

    .\\.venv\\Scripts\\python.exe run.py deck-detect
    .\\.venv\\Scripts\\python.exe run.py deck-detect --session <name> --player-tag "#ABC123"
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

_STD = (64, 80)                     # normalised crop size (w, h), same as hand_templates
_SCALES = [56, 72, 90, 112, 140]    # reference widths the crop is searched in
_CLAHE = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
_MIN_SAT = 45.0                     # mean HSV saturation below this = card greyed out (unaffordable)


# --- image helpers ----------------------------------------------------------------
def _flatten(img: np.ndarray) -> np.ndarray:
    """Reference pictures carry transparency; put them on a neutral background."""
    if img.ndim == 3 and img.shape[2] == 4:
        a = img[:, :, 3:4].astype(np.float32) / 255.0
        return (img[:, :, :3].astype(np.float32) * a + 30 * (1 - a)).astype(np.uint8)
    return img


def _prep_reference(img: np.ndarray) -> np.ndarray:
    im = _flatten(img)
    h, w = im.shape[:2]
    im = im[int(0.05 * h):int(0.97 * h), int(0.07 * w):int(0.93 * w)]   # inside the card frame
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    return _CLAHE.apply(cv2.GaussianBlur(g, (3, 3), 0))


def _prep_crop(img: np.ndarray, width: int = 40) -> np.ndarray:
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = g.shape[:2]
    g = cv2.resize(g, (width, max(8, int(round(h * width / w)))), interpolation=cv2.INTER_AREA)
    return _CLAHE.apply(cv2.GaussianBlur(g, (3, 3), 0))


def _score(crop_g: np.ndarray, ref_g: np.ndarray) -> float:
    best = -1.0
    ch, cw = crop_g.shape
    for W in _SCALES:
        H = max(8, int(round(ref_g.shape[0] * W / ref_g.shape[1])))
        if H < ch or W < cw:
            continue
        r = cv2.matchTemplate(cv2.resize(ref_g, (W, H), interpolation=cv2.INTER_AREA),
                              crop_g, cv2.TM_CCOEFF_NORMED)
        best = max(best, float(r.max()))
    return best


def load_reference_bank(cfg) -> Dict[str, np.ndarray]:
    from .card_art import art_dir
    d = art_dir(cfg)
    bank: Dict[str, np.ndarray] = {}
    for p in sorted(d.glob("*.png")):
        img = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
        if img is not None:
            bank[p.stem] = _prep_reference(img)
    return bank


# --- levels from the official API (optional) ---------------------------------------
def _fetch_levels(cfg, player_tag: str) -> Dict[str, int]:
    """{card key -> in-game level} from the official API. {} if it is not usable."""
    token_env = cfg.get("sim", "api_token_env", default="CLASHRL_CR_API_TOKEN")
    token = os.environ.get(token_env, "").strip()
    if not token:
        print(f"[deck-detect] no API token in {token_env}: levels stay as they are in cards.yaml.")
        return {}
    base = cfg.get("sim", "api_base", default="https://api.clashroyale.com/v1")
    tag = player_tag.strip()
    if not tag.startswith("#"):
        tag = "#" + tag
    url = f"{base}/players/{urllib.parse.quote(tag, safe='')}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}",
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as exc:                                # noqa: BLE001
        print(f"[deck-detect] could not query the account ({exc!r}); levels left unchanged.")
        return {}
    deck = data.get("currentDeck") or []
    if not deck:
        print("[deck-detect] the account returns no current deck; levels left unchanged.")
        return {}
    # The API counts levels within a rarity. The number shown in the game is
    # level + (highest maxLevel in the deck - this card's maxLevel).
    top = max(int(c.get("maxLevel", 14)) for c in deck)
    out: Dict[str, int] = {}
    for c in deck:
        key = re.sub(r"[ \-]+", "_", str(c.get("name", "")).lower().replace(".", "").replace("'", ""))
        try:
            out[key] = int(c["level"]) + (top - int(c.get("maxLevel", top)))
        except (KeyError, TypeError, ValueError):
            continue
    print(f"[deck-detect] levels read from the account: "
          + ", ".join(f"{k} {v}" for k, v in out.items()))
    return out


# --- main -------------------------------------------------------------------------
def _latest_session(root: Path):
    found = [p for p in root.glob("*") if (p / "meta.json").exists()]
    return max(found, key=lambda p: p.name) if found else None


def _write_templates(cfg, faces, detections, min_score: float, min_margin: float,
                     overwrite: bool) -> None:
    """Save the confidently identified faces as hand templates under their real name.

    This is the step that used to be manual: `hand-templates` dumps `_cand_*.png` and you
    rename them. Once a face has been identified there is nothing left to rename, so the
    crop is written straight to `<key>.png`. Only confident faces are written -- a wrong
    name here would silently poison hand recognition for every later run.
    """
    out_dir = cfg.path(cfg.get("hand", "templates_dir", default="templates/cards"))
    out_dir.mkdir(parents=True, exist_ok=True)
    written, skipped, existing = [], [], []
    for face, det in zip(faces, detections):
        best = det["candidates"][0]
        if best["score"] < min_score or det["margin"] < min_margin:
            skipped.append(f"{best['display']} ({best['score']:.2f}/{det['margin']:.2f})")
            continue
        dst = out_dir / f"{best['key']}.png"
        if dst.name in written:
            continue                      # several views of the same card: one template is enough
        if dst.exists() and not overwrite:
            existing.append(dst.name)
            continue
        cv2.imwrite(str(dst), face["key"])
        written.append(dst.name)
    if written:
        print(f"[deck-detect] {len(written)} hand templates written: {', '.join(sorted(set(written)))}")
    if existing:
        print(f"[deck-detect] left alone because they already exist: {', '.join(sorted(set(existing)))}. "
              "Use --overwrite-templates to replace them.")
    if skipped:
        print(f"[deck-detect] {len(skipped)} card images were too uncertain to write a template for.")


def detect_deck(cfg, session_arg: Optional[str] = None, samples: int = 400,
                distinct: float = 0.8, per_face: int = 6, top: int = 5,
                player_tag: Optional[str] = None, out: Optional[str] = None,
                write_templates: bool = False, overwrite_templates: bool = False,
                tpl_min_score: float = 0.65, tpl_min_margin: float = 0.08) -> None:
    from .cards import CardDB
    from .vision import Vision

    bank = load_reference_bank(cfg)
    if not bank:
        print("[deck-detect] no reference pictures found. Run `run.py cards-art` once.")
        return
    db = CardDB(cfg)

    root = cfg.path(cfg.get("record", "out_dir", default="data/sessions"))
    from .label import _resolve_session
    session = _resolve_session(root, session_arg) if session_arg else _latest_session(root)
    if session is None or not Path(session).exists():
        print(f"[deck-detect] no recording found under {root}. Run `record` first.")
        return
    session = Path(session)
    video = next((session / n for n in ("video.mp4", "video.avi") if (session / n).exists()), None)
    if video is None:
        print(f"[deck-detect] no video in {session}")
        return

    vision = Vision(cfg)
    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    faces: List[Dict[str, Any]] = []                 # {"key": std crop, "members": [crops]}
    frames_seen = 0
    for fi in np.linspace(0, max(total - 1, 0), samples).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(fi))
        ok, frame = cap.read()
        if not ok or vision.detect_state(frame).name != "IN_MATCH":
            continue
        frames_seen += 1
        for cx, cy in vision.hand_slots:
            crop = vision.hand_crop(frame, cx, cy)
            if crop.size == 0:
                continue
            # The game DESATURATES a card you can't currently afford. Measured on a real
            # recording: mean HSV saturation ~100-155 while affordable, ~18-25 while greyed
            # out. Both versions of the SAME card then cluster as two different faces (117
            # "distinct" faces for an 8-card deck), and the grey one has to be identified
            # against colour reference art, which is what left half the deck at a
            # coin-flip margin. Keep only the affordable, full-colour views.
            if float(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[..., 1].mean()) < _MIN_SAT:
                continue
            std = cv2.resize(crop, _STD, interpolation=cv2.INTER_AREA)
            hit = None
            for f in faces:
                if float(cv2.matchTemplate(std, f["key"], cv2.TM_CCOEFF_NORMED).max()) >= distinct:
                    hit = f
                    break
            if hit is None:
                faces.append({"key": std, "members": [std]})
            elif len(hit["members"]) < per_face:
                hit["members"].append(std)
    cap.release()

    if not faces:
        print(f"[deck-detect] in {session.name} no hand cards were found. "
              "Does the recording contain match footage, and is the window calibrated?")
        return
    print(f"[deck-detect] {session.name}: {frames_seen} match frames, {len(faces)} "
          f"distinct card images, matched against {len(bank)} reference cards ...", flush=True)

    keys = list(bank)
    detections: List[Dict[str, Any]] = []
    for i, f in enumerate(faces):
        acc = np.zeros(len(keys))
        for m in f["members"]:
            cg = _prep_crop(m)
            acc += np.array([_score(cg, bank[k]) for k in keys])
        acc /= len(f["members"])
        order = np.argsort(-acc)
        cands = [{"key": keys[j], "score": round(float(acc[j]), 4),
                  "display": (db.get(keys[j].replace("_evo", "")) or {}).get(
                      "display", keys[j]) + (" (Evo)" if keys[j].endswith("_evo") else "")}
                 for j in order[:top]]
        detections.append({"face": i, "samples": len(f["members"]),
                           "candidates": cands,
                           "margin": round(float(acc[order[0]] - acc[order[1]]), 4)})
        print(f"[deck-detect]   image {i + 1}: {cands[0]['display']} ({cands[0]['score']:.3f}, "
              f"distance to runner-up {detections[-1]['margin']:.3f})", flush=True)

    # An evolved face is the same deck slot as its base card, so fold it back and
    # keep the better score of the two.
    slots: Dict[str, Dict[str, Any]] = {}
    for d in detections:
        best = d["candidates"][0]
        base = best["key"][:-4] if best["key"].endswith("_evo") else best["key"]
        s = slots.setdefault(base, {"card": base, "score": 0.0, "evolved": False,
                                    "margin": 0.0, "faces": [], "alternatives": []})
        s["faces"].append(d["face"])
        if best["key"].endswith("_evo"):
            s["evolved"] = True
        if best["score"] > s["score"]:
            s["score"] = best["score"]
            s["margin"] = d["margin"]
            s["alternatives"] = d["candidates"]

    ranked = sorted(slots.values(), key=lambda s: -s["score"])
    chosen = ranked[:8]
    for s in chosen:
        c = db.get(s["card"]) or {}
        s["display"] = c.get("display", s["card"])
        s["elixir"] = c.get("elixir")
        s["level"] = db.level(s["card"]) or 11
        s["known"] = bool(c)

    levels = _fetch_levels(cfg, player_tag) if player_tag else {}
    for s in chosen:
        if s["card"] in levels:
            s["level"] = levels[s["card"]]
            s["level_source"] = "account"
        else:
            s["level_source"] = "cards.yaml"

    # What separates a safe call from a coin flip is the DISTANCE to the runner-up, not the
    # absolute score: correct matches land anywhere between 0.43 and 0.70 depending on how
    # much of the illustration the tray shows. Measured on the labelled crops, every wrong
    # candidate sat within 0.05 of the winner, and every clear winner was further away.
    unsure = [s for s in chosen if s["margin"] < 0.05 or s["score"] < 0.35]
    for s in chosen:
        s["unsure"] = s in unsure
    print("")
    print(f"[deck-detect] deck recognised ({len(chosen)} of 8 slots):")
    for s in chosen:
        evo = " (Evo)" if s["evolved"] else ""
        flag = "  UNCERTAIN" if s in unsure else ""
        print(f"[deck-detect]   {s['display']}{evo:<6} level {s['level']:<3} "
              f"confidence {s['score']:.3f}, margin {s['margin']:.3f}{flag}")
    if len(chosen) < 8:
        print(f"[deck-detect] only {len(chosen)} cards were seen. A longer recording "
              "shows all eight; expensive cards come up less often.")
    if unsure:
        print("[deck-detect] For the uncertain cards, pick from the candidate list in the panel "
              "instead of accepting the result unchecked.")

    if write_templates:
        _write_templates(cfg, faces, detections, tpl_min_score, tpl_min_margin, overwrite_templates)

    payload = {
        "generated": time.time(),
        "session": session.name,
        "frames": frames_seen,
        "faces": len(faces),
        "reference_cards": len(bank),
        "deck": chosen,
        "detections": detections,
        "levels_from_account": bool(levels),
        "current_deck": db.deck_names(),
    }
    out_path = Path(out) if out else cfg.path("data/deck_detect.json")
    if not out_path.is_absolute():
        out_path = cfg.path(str(out_path))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"[deck-detect] proposal written to {out_path}. Review and apply it in the panel under Deck.")
