"""Audit the EVOLUTION every meta deck's scripted opponent actually fields.

Why this exists: `build_spec` used to FABRICATE a spec for any `<x>_evo` key -- with no evo row the
overlay merged nothing and it returned the BASE card wearing the evo name. `ScriptedBot` picked its
evolution as "the first deck card whose `<key>_evo` builds", and since nothing ever raised, that was
ALWAYS deck index 0. Every deck therefore fielded a PHANTOM evolution: base stats, evo label.

Three verdicts per deck:
  REAL     -- the fielded evo resolves to an actual KB `<base>_evo` row (or a curated `evolution:`
              block), so the spec carries the evolution's own stats.
  PHANTOM  -- an evo was fielded for a card the KB has no evolution for. Must be 0.
  NONE     -- the deck declares no evolution (or its declared one has no KB row yet). Correct
              behaviour, not a defect: fielding nothing beats fielding a fake.

Run:  PYTHONPATH=src python tools/evo_audit.py [--verbose]
Exit code 1 if ANY phantom is found, so this can gate a commit.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import random  # noqa: E402

from clashrl.cards import CardDB  # noqa: E402
from clashrl.sim.engine import build_spec  # noqa: E402
from clashrl.sim.meta_decks import load_meta_decks  # noqa: E402
from clashrl.sim.opponents import ScriptedBot  # noqa: E402


class _Cfg:
    """Minimal cfg: ScriptedBot only reads sim.* scalars, and the defaults are the shipped ones."""

    def __init__(self, root: Path):
        self._root = root

    def get(self, *keys, default=None):
        if keys[:2] == ("sim", "meta_decks_file"):
            return "config/meta_decks.yaml"
        if keys[:2] == ("cards", "file"):
            return "config/cards.yaml"
        return default

    def path(self, p):
        return self._root / p


def _has_real_evo(db, base: str) -> bool:
    """True when the KB can actually build `<base>_evo` -- an imported row or a curated block."""
    if db.get(base + "_evo"):
        return True
    return isinstance((db.get(base) or {}).get("evolution"), dict)


def main(argv) -> int:
    verbose = "--verbose" in argv
    cfg = _Cfg(ROOT)
    db = CardDB(path=ROOT / "config" / "cards.yaml")
    pool = load_meta_decks(cfg, db)

    verdicts: Counter = Counter()
    fielded: Counter = Counter()
    phantoms: list = []
    declared_no_row: Counter = Counter()

    declared_decks = 0
    unmodelled_extra = 0
    for deck in pool:
        # `evo=` is what makes this an audit of the REAL picker rather than of a default: the bot
        # fields the deck's DECLARED slot, so passing it is not optional here.
        bot = ScriptedBot(cfg, db, random.Random(0), deck["cards"], deck["style"],
                          [11] * len(deck["cards"]), evo=deck.get("evo"))
        declared = list(deck.get("evo") or [])
        if declared:
            declared_decks += 1
        # A slot the meta DECLARES but the KB cannot build is a missing KB row, not a modelling
        # choice -- counted for every deck, including ones where a different slot did build.
        for k in declared:
            if not _has_real_evo(db, k):
                declared_no_row[k] += 1
        # The engine models ONE evolution slot; top-ladder decks field 2-3 (R4). Count what the
        # declaration asked for and the bot could not carry.
        unmodelled_extra += max(0, sum(1 for k in declared if _has_real_evo(db, k)) - 1)
        idx = getattr(bot, "evo_idx", -1)
        if idx < 0 or getattr(bot, "evo_spec", None) is None:
            verdicts["NONE"] += 1
            continue
        base = deck["cards"][idx]
        if _has_real_evo(db, base):
            verdicts["REAL"] += 1
            fielded[base] += 1
        else:
            verdicts["PHANTOM"] += 1
            phantoms.append((deck["name"], base))

    total = sum(verdicts.values())
    print(f"decks audited: {total}   (declaring a slot: {declared_decks})")
    for v in ("REAL", "PHANTOM", "NONE"):
        print(f"  {v:<8} {verdicts[v]:>4}  ({100.0 * verdicts[v] / max(1, total):.1f}%)")
    if unmodelled_extra:
        print(f"buildable slots the single-slot engine could not carry: {unmodelled_extra}")
    if fielded:
        print("fielded evolutions (top 15):")
        for k, n in fielded.most_common(15):
            print(f"  {k:<24} x{n}")
    if declared_no_row:
        print("DECLARED by the meta but absent from the KB (no `_evo` row -> nothing fielded):")
        for k, n in declared_no_row.most_common():
            print(f"  {k:<24} x{n} decks")
    if phantoms:
        print(f"PHANTOMS ({len(phantoms)}):")
        shown = phantoms if verbose else phantoms[:20]
        for name, base in shown:
            print(f"  {name}: {base}_evo has no KB row")
        if len(shown) < len(phantoms):
            print(f"  ... {len(phantoms) - len(shown)} more (--verbose)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
