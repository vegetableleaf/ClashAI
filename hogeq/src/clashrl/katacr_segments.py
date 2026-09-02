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

2. SCALE. A sprite's pixel size means nothing on its own -- it is only comparable as a fraction of
   the frame it was cut from. `sprites` records that as a `_w<px>` tag and `synth_images` rescales
   each paste by base_width/source_width, so importing here means answering ONE question: what frame
   width are their segments effectively cut from, expressed in our arena's terms?

   `--src-width auto` measures it from the classes both banks share. It compares ALPHA-TIGHT heights
   (the bounding box of the non-transparent pixels), not crop heights: their crops carry far more
   transparent padding than ours (alpha fill 0.53 vs 0.73), so raw crop dimensions measure padding
   convention as much as scale. It also REQUIRES our bank to be width-tagged, because a bank mixing
   392 px and 669 px sources has no single native scale to compare against -- the first attempt at
   this measurement scattered across a 0.41..1.75 range for exactly that reason.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .sprites import _src_width

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
    # kitka's library (2026-09-02, HANDOFF 5bb): its own spellings for cards we DO model. Checked by
    # hand against the taxonomy, not by string distance -- `goblinstein-doctor` and
    # `skeleton-balloon-evolution` are ambiguous against our single classes and stay dropped.
    "dartgoblin-evolution": "dart_goblin_evo", "ghost-evolution": "royal_ghost_evo",
    "megaknight-evolution": "mega_knight_evo", "snowball-evolution": "giant_snowball_evo",
    "skarmy-evolution": "skeleton_army_evo",
    "spirit-empress-air": "spirit_empress", "spirit-empress-ground": "spirit_empress",
    "hog": None, "dirt": None, "axe": None, "bomb": None, "goblin-ball": None,
    "skeleton-king-skill": None, "tesla-evolution-shock": None,
    # one evolved BODY has no home: we hold `royal_recruit` (a body) and `royal_recruits` (the card),
    # and `royal_recruits_evo` means the card. Dropping beats guessing which one their box is.
    "royal-recruit-evolution": None,
}
_UI = {"bar", "bar-level", "clock", "emote", "text", "elixir", "selected", "tower-bar",
       "king-tower-bar", "dagger-duchess-tower-bar", "skeleton-king-bar", "evolution-symbol",
       "ice-spirit-evolution-symbol", "backgrounds", "background-items"}

# CARDS WHOSE IN-GAME ART CHANGED AFTER THIS DATASET WAS CAPTURED. Their segments are pixels of a
# sprite that no longer exists, so importing them teaches the detector an appearance it will never
# see and actively competes with the current art. This is separate from _EXPLICIT (which is about
# NAMING and concepts) because the reason is temporal, and Supercell reworks visuals regularly --
# add to this set whenever a rework lands, with the date.
_STALE_ART = {
    "three-musketeers",     # visual rework, November 2025
}


def map_name(n: str) -> Optional[str]:
    """Their segment folder name -> our class name, or None to drop."""
    n = n.strip().lower()
    if n in _UI or n in _STALE_ART:
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


def _alpha_h(paths, limit: int = 80):
    """Median height of the TIGHT alpha bounding box, and the sample size.

    The sprite itself, not the canvas it sits on: comparing crop heights across two banks with
    different padding conventions measures the padding as much as the unit."""
    hs = []
    for p in list(paths)[:limit]:
        im = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
        if im is None or im.size == 0:
            continue
        if im.ndim == 3 and im.shape[2] == 4:
            ys = np.where((im[:, :, 3] > 16).any(axis=1))[0]
            if ys.size:
                hs.append(float(ys[-1] - ys[0] + 1))
        else:
            hs.append(float(im.shape[0]))
    return (float(np.median(hs)) if hs else 0.0), len(hs)


def _our_rel_h(paths, limit: int = 80):
    """Median of height/source_width over OUR cutouts -- the scale-free size of this class.

    Untagged cutouts are skipped rather than assumed: their source width is genuinely unknown."""
    rel = []
    for p in list(paths)[:limit]:
        w_src = _src_width(p)
        if not w_src:
            continue
        im = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
        if im is None or im.size == 0:
            continue
        if im.ndim == 3 and im.shape[2] == 4:
            ys = np.where((im[:, :, 3] > 16).any(axis=1))[0]
            if ys.size:
                rel.append(float(ys[-1] - ys[0] + 1) / w_src)
        else:
            rel.append(float(im.shape[0]) / w_src)
    return (float(np.median(rel)) if rel else 0.0), len(rel)


def katacr_segments(cfg, src: str, src_width: str = "auto", dry_run: bool = False,
                    min_per_class: int = 1, bank_dir: Optional[str] = None,
                    prefix: str = "katacr") -> None:
    """`bank_dir` (default data/detect/sprites) lets a HELD-OUT slice of a segment library go into
    a separate bank that only a synthetic VAL set is composed from -- the training bank never sees
    it. `prefix` is the provenance tag on every written file (kitka_ vs katacr_), so two libraries
    from the same upstream can coexist and each re-import stays idempotent."""
    from .detect import _load_classes

    ours = set(_load_classes(cfg))
    root = Path(cfg.path(cfg.get("detect", "dataset_dir", default="data/detect")))
    bank = Path(cfg.path(bank_dir)) if bank_dir else root / "sprites"
    ref_bank = root / "sprites"          # width is always measured against the TRAINING bank
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

    # ---- effective SOURCE FRAME WIDTH, measured on the classes both banks share ----
    # Per shared class: their alpha height / our height-per-source-pixel = the frame width their
    # segments behave as if cut from. Median across classes; the spread is printed because a wide
    # one means the two banks disagree and no single number is right.
    if src_width == "auto":
        ests, untagged = [], 0
        for cls, pngs in sorted(mapped.items()):
            mine = list((ref_bank / cls).glob("*.png")) if (ref_bank / cls).is_dir() else []
            if len(mine) < 5 or len(pngs) < 5:
                continue
            rel, n_rel = _our_rel_h(mine)
            theirs, n_th = _alpha_h(pngs)
            if n_rel < 5:
                untagged += 1
                continue
            if rel > 0 and theirs > 0 and n_th >= 5:
                ests.append(theirs / rel)
        if not ests:
            print("[katacr] cannot MEASURE the source width: "
                  + (f"{untagged} shared class(es) have no width-tagged cutouts. "
                     "Rebuild the bank first (`run.py sprites`) so every cutout records the frame "
                     "it came from, then re-run." if untagged else
                     "no shared class has enough samples on both sides."))
            print("[katacr] refusing to guess -- pass an explicit --src-width <px> to override.")
            return
        e = np.array(ests)
        w_k = float(np.median(e))
        cv_ = float(e.std() / max(1e-9, e.mean()))
        print(f"[katacr] source width AUTO = {w_k:.0f} px  (median over {len(e)} shared class(es); "
              f"p10 {np.percentile(e, 10):.0f}, p90 {np.percentile(e, 90):.0f}, CV {cv_:.2f})")
        if untagged:
            print(f"[katacr] note: {untagged} shared class(es) skipped -- no width-tagged cutouts")
        if cv_ > 0.20:
            print("[katacr] WARNING: the shared classes DISAGREE (CV > 0.20). One width will be "
                  "wrong for some classes -- inspect before trusting this import.")
    else:
        w_k = float(src_width)
        print(f"[katacr] source width FIXED = {w_k:.0f} px")
    w_tag = max(1, int(round(w_k)))

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
            # NO resampling here: the segments keep their full resolution and carry the measured
            # source width instead, so synth_images scales each paste to ITS base frame. Baking one
            # global factor in would throw away detail and re-freeze the same mixed-scale mistake.
            # katacr_ prefix keeps provenance visible and makes a re-import idempotent
            cv2.imwrite(str(out / f"{prefix}_{p.stem}_{i:05d}_w{w_tag}.png"), im)
            written += 1
    print(f"[katacr] wrote {written} segment(s) into {bank}, tagged _w{w_tag}")
    print("[katacr] NEXT: `run.py sprites --synth N` -- do NOT re-run `run.py sprites`, it CLEARS "
          "the bank and would delete everything just imported.")
