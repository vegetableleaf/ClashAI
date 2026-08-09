"""Import KataCR's segment library into our sprite bank.

Their dataset (github.com/wty-yy/Clash-Royale-Detection-Dataset, MIT) is ~4,654 hand-cut RGBA
segments across 154 classes. That is exactly what our own bank cannot manufacture: `sprites` cuts
crops from OUR frames, so it multiplies CONTEXTS but never creates new POSES -- which is the
diagnosed reason valkyrie sat at 0.33 recall for four generations despite synth.

TWO CONVERSIONS ARE REQUIRED, and both are silent failures if skipped.

1. NAMES. Theirs are hyphenated and mostly SINGULAR because they box individual bodies and name the
   body ('spear-goblin'); ours are underscored and sometimes name the CARD ('spear_goblins'). Pure
   mechanical normalisation gets 71%; the singular->plural rule and a short explicit table take it
   to ~90%. The subtle case is the two rules COMPOUNDING: 'archer-evolution' must become
   'archers_evo', not 'archer_evo', so the plural rule has to be applied to the STEM BEFORE the
   suffix is re-attached. Six classes were being lost to exactly that ordering bug.

   Anything that does not resolve is DROPPED, never guessed. `detect-import` remaps by name and
   skips unknown classes, so the failure mode of a bad mapping is LOST DATA rather than a corrupted
   label -- worth preserving deliberately.

2. SCALE. `sprites.synth_images` pastes at NATIVE size (only +-15% jitter; "native scale is real"),
   so a segment cut from their 1080x2400 phone frames lands roughly 1.6x too large on our 668x1182
   arena. The factor is NOT assumed: `--scale auto` measures it from the classes both banks share,
   comparing median sprite heights, which is robust to their arena-crop geometry being unknown.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

# they box the BODY, we sometimes name the CARD
_PLURAL = {
    "archer": "archers", "barbarian": "barbarians", "bat": "bats",
    "elite-barbarian": "elite_barbarians", "goblin": "goblins", "guard": "guards",
    "lava-pup": "lava_pups", "minion": "minions", "royal-hog": "royal_hogs",
    "skeleton": "skeletons", "skeleton-dragon": "skeleton_dragons",
    "spear-goblin": "spear_goblins", "wall-breaker": "wall_breakers", "zappy": "zappies",
}
# different concepts, sub-parts, or things we deliberately do not model. None = drop.
_EXPLICIT = {
    "king-tower": None, "queen-tower": None, "cannoneer-tower": None,
    "dagger-duchess-tower": None,          # towers are rendered, never detected
    "elixir-golem-big": "elixir_golem", "elixir-golem-mid": "elixir_golemite",
    "elixir-golem-small": "elixir_blob",
    "phoenix-big": "phoenix", "phoenix-small": "phoenix", "phoenix-egg": None,
    "royal-guardian": "royal_ghost", "rascal-boy": "rascals", "rascal-girl": "rascals",
    "goblin-brawler": None,                # goblin_cage's spawn: not a card, deliberately unmodelled
    "hog": None, "dirt": None, "axe": None, "bomb": None, "goblin-ball": None,
    "skeleton-king-skill": None, "tesla-evolution-shock": None,
    # one evolved BODY has no home: we hold `royal_recruit` (a body) and `royal_recruits` (the card),
    # and `royal_recruits_evo` means the card. Dropping beats guessing which one their box is.
    "royal-recruit-evolution": None,
}
_UI = {"bar", "bar-level", "clock", "emote", "text", "elixir", "selected", "tower-bar",
       "king-tower-bar", "dagger-duchess-tower-bar", "skeleton-king-bar", "evolution-symbol",
       "ice-spirit-evolution-symbol", "backgrounds", "background-items"}


def map_name(n: str) -> Optional[str]:
    """Their segment folder name -> our class name, or None to drop."""
    n = n.strip().lower()
    if n in _UI:
        return None
    if n in _EXPLICIT:
        return _EXPLICIT[n]
    if n in _PLURAL:
        return _PLURAL[n]
    if n.endswith("-evolution"):
        # THE ORDERING THAT MATTERS: pluralise the STEM, then re-attach the suffix.
        stem = n[: -len("-evolution")]
        if stem in _EXPLICIT and _EXPLICIT[stem] is None:
            return None
        base = _PLURAL.get(stem) or _EXPLICIT.get(stem) or stem.replace("-", "_")
        return f"{base}_evo"
    return n.replace("-", "_")


def _median_h(paths, limit=60) -> float:
    hs = []
    for p in list(paths)[:limit]:
        im = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
        if im is not None and im.size:
            hs.append(im.shape[0])
    return float(np.median(hs)) if hs else 0.0


def katacr_segments(cfg, src: str, scale: str = "auto", dry_run: bool = False,
                    min_per_class: int = 1) -> None:
    from .detect import _load_classes

    ours = set(_load_classes(cfg))
    root = Path(cfg.path(cfg.get("detect", "dataset_dir", default="data/detect")))
    bank = root / "sprites"
    sp = Path(src)
    if not sp.exists():
        print(f"[katacr] no segment folder at {sp}")
        return
    # accept either .../images/segment or a folder that CONTAINS it
    if (sp / "images" / "segment").is_dir():
        sp = sp / "images" / "segment"
    elif (sp / "segment").is_dir():
        sp = sp / "segment"

    dirs = [d for d in sp.iterdir() if d.is_dir()]
    if not dirs:
        print(f"[katacr] {sp} has no class folders")
        return

    mapped, dropped, unmatched = {}, [], []
    for d in dirs:
        m = map_name(d.name)
        pngs = sorted(d.glob("*.png"))
        if not pngs:
            continue
        if m is None:
            dropped.append((d.name, len(pngs)))
        elif m in ours:
            mapped.setdefault(m, []).extend(pngs)
        else:
            unmatched.append((d.name, m, len(pngs)))

    n_src = sum(len(v) for v in mapped.values())
    print(f"[katacr] {len(dirs)} class folder(s) at {sp}")
    print(f"[katacr] mapped {len(mapped)} class(es) / {n_src} segment(s); "
          f"dropped {len(dropped)}; UNMATCHED {len(unmatched)}")
    if unmatched:
        print("[katacr] unmatched (DROPPED, never guessed -- add to _EXPLICIT if wanted):")
        for a, b, c in sorted(unmatched, key=lambda r: -r[2])[:12]:
            print(f"           {a:<28} -> '{b}' not in taxonomy   ({c} segs)")

    # ---- scale factor, MEASURED on the classes both banks share ----
    if scale == "auto":
        ratios = []
        for cls, pngs in mapped.items():
            mine = list((bank / cls).glob("*.png")) if (bank / cls).is_dir() else []
            if len(mine) >= 5 and len(pngs) >= 5:
                a, b = _median_h(mine), _median_h(pngs)
                if a > 0 and b > 0:
                    ratios.append(a / b)
        if ratios:
            f = float(np.median(ratios))
            print(f"[katacr] scale AUTO = {f:.3f} (median over {len(ratios)} shared class(es); "
                  f"their frames are larger, so <1 is expected)")
        else:
            f = 1.0
            print("[katacr] scale AUTO found no shared class with enough samples -> 1.0 (NO rescale). "
                  "Check this: synth pastes at NATIVE size, so a wrong factor trains on wrong-sized units.")
    else:
        f = float(scale)
        print(f"[katacr] scale FIXED = {f:.3f}")

    if dry_run:
        print("[katacr] --dry-run: nothing written")
        return

    written = 0
    for cls, pngs in mapped.items():
        if len(pngs) < min_per_class:
            continue
        out = bank / cls
        out.mkdir(parents=True, exist_ok=True)
        for i, p in enumerate(pngs):
            im = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
            if im is None or im.size == 0:
                continue
            if abs(f - 1.0) > 0.02:
                h, w = im.shape[:2]
                im = cv2.resize(im, (max(2, int(round(w * f))), max(2, int(round(h * f)))),
                                interpolation=cv2.INTER_AREA if f < 1 else cv2.INTER_LINEAR)
            # katacr_ prefix keeps provenance visible and makes a re-import idempotent
            cv2.imwrite(str(out / f"katacr_{p.stem}_{i:05d}.png"), im)
            written += 1
    print(f"[katacr] wrote {written} segment(s) into {bank}")
    print("[katacr] NEXT: `run.py sprites --synth N` -- do NOT re-run `run.py sprites`, it CLEARS "
          "the bank and would delete everything just imported.")
