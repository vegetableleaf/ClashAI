"""Import tray-crop card templates from a Roboflow CLASSIFICATION export into templates/cards.

    python tools/import_card_templates.py <extracted_export_dir> [--per-card 40] [--dry-run]

WHICH FOLDER, AND WHY IT MATTERS. This project has two template libraries and they hold different
kinds of picture:

  templates/cards/    64x80 TRAY CROPS -- the zoomed sub-window the game draws in a hand slot,
                      named <card_key>_<n>.png. What `hand-templates` builds and what deck-detect
                      is benchmarked against.
  templates/cardart/  one full CARD ILLUSTRATION per card (gold frame and all), named <key>.png.
                      What `cards-art` downloads from the wiki, and what deck-detect matches
                      crops against.

A detection dataset of gold-framed card art is cardart material, NOT cards -- dropping it into
templates/cards would break the 64x80 convention and pollute the labelled crop set. This importer
is for a dataset of TRAY-STYLE crops only.

GEOMETRY. Sources are commonly square (100x100) while a tray slot is 4:5, so a straight resize
squashes the art by 20% and every template stops matching real crops. Each image is centre-cropped
to 4:5 first, then resized to the exact 64x80 the existing templates use.
"""
from __future__ import annotations

import argparse
import collections
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

#: Cards whose art was REWORKED recently, so a template from an older export is stale and would
#: actively mislead the matcher (user, 2026-08-17).
SKIP = {"bandit", "musketeer", "three_musketeers", "3_musketeers"}

#: Misspellings in the source exports. Kept as an explicit table rather than fuzzy-matched: a
#: near-miss on card names silently files Mini P.E.K.K.A art under P.E.K.K.A, and a wrong template
#: is worse than a missing one.
ALIASES = {
    "lighhning": "lightning",        # sic, in evgeny-9crvq/cards-clash-royale
    "royale_giant": "royal_giant",   # sic
}

TPL_W, TPL_H = 64, 80


def norm(name: str) -> str:
    s = name.strip().lower().replace("-", " ").replace(".", "")
    s = re.sub(r"[^a-z0-9 _]", "", s)
    return re.sub(r"\s+", "_", s).strip("_")


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("export_dir")
    ap.add_argument("--per-card", type=int, default=40,
                    help="cap per card; the existing set averages ~17, so this stays comparable")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    import cv2
    from clashrl.cards import CardDB
    from clashrl.config import Config

    cfg = Config.load()
    db = CardDB(cfg)
    known = set(db.cards)
    out_dir = Path(cfg.path(cfg.get("hand", "templates_dir", default="templates/cards")))
    out_dir.mkdir(parents=True, exist_ok=True)

    # continue each card's existing numbering rather than restarting at 1
    used = collections.Counter()
    for p in out_dir.glob("*.png"):
        m = re.match(r"^(.*)_(\d+)\.png$", p.name)
        if m:
            used[m.group(1)] = max(used[m.group(1)], int(m.group(2)))

    src = Path(a.export_dir)
    by_card: dict[str, list[Path]] = collections.defaultdict(list)
    for split in sorted(p for p in src.iterdir() if p.is_dir()):
        for cls in sorted(p for p in split.iterdir() if p.is_dir()):
            key = norm(cls.name)
            key = ALIASES.get(key, key)
            by_card[key].extend(sorted(cls.glob("*.jpg")) + sorted(cls.glob("*.png")))

    written, skipped_stale, unknown = 0, [], []
    for key, files in sorted(by_card.items()):
        if key in SKIP:
            skipped_stale.append(key)
            continue
        if key not in known:
            unknown.append((key, len(files)))
            continue
        step = max(1, len(files) // a.per_card)          # spread across the class, not the first N
        picked = files[::step][:a.per_card]
        for f in picked:
            used[key] += 1
            dst = out_dir / ("%s_%d.png" % (key, used[key]))
            if a.dry_run:
                written += 1
                continue
            img = cv2.imread(str(f))
            if img is None:
                used[key] -= 1
                continue
            h, w = img.shape[:2]
            tw = int(round(h * TPL_W / TPL_H))           # 4:5 window, full height
            if tw <= w:
                x0 = (w - tw) // 2
                img = img[:, x0:x0 + tw]
            else:                                        # source is TALLER than 4:5 -> crop height
                th = int(round(w * TPL_H / TPL_W))
                y0 = max(0, (h - th) // 2)
                img = img[y0:y0 + th, :]
            cv2.imwrite(str(dst), cv2.resize(img, (TPL_W, TPL_H), interpolation=cv2.INTER_AREA))
            written += 1

    print("wrote %d template(s) into %s%s" % (written, out_dir, " (DRY RUN)" if a.dry_run else ""))
    print("cards covered: %d" % sum(1 for k in by_card if k in known and k not in SKIP))
    if skipped_stale:
        print("skipped as STALE art (reworked recently): %s" % ", ".join(sorted(skipped_stale)))
    if unknown:
        print("unmatched source classes (%d) -- not in the card DB, left out:" % len(unknown))
        for k, n in sorted(unknown)[:15]:
            print("   %-28s %d image(s)" % (k, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
