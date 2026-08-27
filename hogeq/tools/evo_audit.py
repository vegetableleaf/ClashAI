"""Audit the EVOLUTION every meta deck's scripted opponent actually fields.

Why this exists: `build_spec` used to FABRICATE a spec for any `<x>_evo` key -- with no evo row the
overlay merged nothing and it returned the BASE card wearing the evo name. `ScriptedBot` picked its
evolution as "the first deck card whose `<key>_evo` builds", and since nothing ever raised, that was
ALWAYS deck index 0. Every deck therefore fielded a PHANTOM evolution: base stats, evo label.

What replaced it (I3): the deck's `evo_candidates` -- its cards that really HAVE an evolution,
derived from the KB's 42 `_evo` rows, which match the 42 wiki-verified evolutions in
research/sim_parity/ledger/r1a_evolutions.json exactly. No source says which of them a player
actually slotted, so ScriptedBot draws ONE uniformly per match rather than naming one.

Three verdicts per deck:
  REAL     -- the fielded evo resolves to an actual KB `<base>_evo` row (or a curated `evolution:`
              block), so the spec carries the evolution's own stats.
  PHANTOM  -- an evo was fielded for a card the KB has no evolution for. Must be 0.
  NONE     -- the deck holds no evolvable card at all, so it fields nothing. Correct behaviour.

I8 EXTENDED IT TO THE WHOLE LOADOUT, because the same phantom question now has three places to go
wrong instead of one. The 16/3/2026 update made the format "one Evolution, one Hero and one Wild",
so this also audits:
  * the HERO slot -- the same three verdicts against the 16 LIVE heroes (`has_hero`), plus the
    rule that a deck holding a candidate ALWAYS fields one (owner ruling, 2026-08-26);
  * the WILD slot -- second evo / second hero / neither, whose 1/3 split is an UNMEASURED choice
    and is reported as a distribution rather than asserted;
  * the CAPS -- no deck card may occupy two slots, and neither category may exceed two.

Run:  PYTHONPATH=src python tools/evo_audit.py [--verbose] [--draws N]
Exit code 1 if ANY phantom is found (evolution or hero), if any candidate fails to resolve through
`build_spec`, or if a slot cap is violated -- so this can gate a commit.
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
from clashrl.sim.meta_decks import has_evolution, has_hero, load_meta_decks  # noqa: E402
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


def _arg_int(argv, flag: str, default: int) -> int:
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv):
            return int(argv[i + 1])
    return default


def main(argv) -> int:
    verbose = "--verbose" in argv
    draws = _arg_int(argv, "--draws", 20)
    cfg = _Cfg(ROOT)
    db = CardDB(path=ROOT / "config" / "cards.yaml")
    pool = load_meta_decks(cfg, db)

    verdicts: Counter = Counter()
    hero_verdicts: Counter = Counter()
    phantoms: list = []
    hero_phantoms: list = []
    unbuildable: list = []
    cand_hist: Counter = Counter()
    hero_hist: Counter = Counter()
    declared_no_row: Counter = Counter()
    cap_breaks: list = []

    n_cands = n_hero_cands = 0
    declared_decks = 0
    for deck in pool:
        cands = list(deck.get("evo_candidates") or [])
        hcands = list(deck.get("hero_candidates") or [])
        hero_hist[len(hcands)] += 1
        n_hero_cands += len(hcands)
        # Every HERO candidate must resolve too, and for the same reason: a broken row would
        # otherwise only surface on the run that happened to draw it.
        for k in hcands:
            if not has_hero(db, k):
                unbuildable.append((deck["name"], k + "_hero", "not a live hero / no KB row"))
                continue
            try:
                build_spec(db, k + "_hero", 11)
            except Exception as exc:                                      # noqa: BLE001
                unbuildable.append((deck["name"], k + "_hero", repr(exc)))
        cand_hist[len(cands)] += 1
        n_cands += len(cands)
        # EVERY candidate must resolve, not just the one this seed happened to draw -- otherwise a
        # broken row would only surface on the run that sampled it.
        for k in cands:
            if not has_evolution(db, k):
                unbuildable.append((deck["name"], k, "no KB evolution"))
                continue
            try:
                build_spec(db, k + "_evo", 11)
            except Exception as exc:                                      # noqa: BLE001
                unbuildable.append((deck["name"], k, repr(exc)))
        declared = list(deck.get("evo") or [])
        if declared:
            declared_decks += 1
            for k in declared:
                if not has_evolution(db, k):
                    declared_no_row[k] += 1
        # `evo_candidates=` is what makes this an audit of the REAL picker rather than of a
        # default: the bot draws from the deck's own legal set, so passing it is not optional.
        bot = ScriptedBot(cfg, db, random.Random(0), deck["cards"], deck["style"],
                          [11] * len(deck["cards"]), evo=declared, evo_candidates=cands,
                          hero_candidates=hcands, support=list(deck.get("support") or []))
        # THE HERO SLOT, by the same three verdicts.
        hidx = getattr(bot, "hero_idx", -1)
        if hidx < 0 or getattr(bot, "hero_spec", None) is None:
            hero_verdicts["NONE" if not hcands else "UNFILLED"] += 1
        elif has_hero(db, deck["cards"][hidx]):
            hero_verdicts["REAL"] += 1
        else:
            hero_verdicts["PHANTOM"] += 1
            hero_phantoms.append((deck["name"], deck["cards"][hidx]))
        # THE CAPS. One deck card cannot be in two slots, and neither category may exceed two.
        slots = [i for i in (bot.evo_idx, hidx, bot.wild_evo_idx, bot.wild_hero_idx) if i >= 0]
        if len(slots) != len(set(slots)):
            cap_breaks.append((deck["name"], "one card in two slots", slots))
        if sum(1 for i in (bot.evo_idx, bot.wild_evo_idx) if i >= 0) > 2:
            cap_breaks.append((deck["name"], "more than two evolutions", slots))
        if sum(1 for i in (hidx, bot.wild_hero_idx) if i >= 0) > 2:
            cap_breaks.append((deck["name"], "more than two heroes", slots))
        idx = getattr(bot, "evo_idx", -1)
        if idx < 0 or getattr(bot, "evo_spec", None) is None:
            verdicts["NONE"] += 1
            continue
        base = deck["cards"][idx]
        if has_evolution(db, base):
            verdicts["REAL"] += 1
        else:
            verdicts["PHANTOM"] += 1
            phantoms.append((deck["name"], base))

    total = sum(verdicts.values())
    print(f"decks audited: {total}   (declaring a fixed slot: {declared_decks})")
    for v in ("REAL", "PHANTOM", "NONE"):
        print(f"  {v:<8} {verdicts[v]:>4}  ({100.0 * verdicts[v] / max(1, total):.1f}%)")
    with_cands = sum(n for k, n in cand_hist.items() if k)
    print(f"decks with >=1 evolution candidate: {with_cands}/{total} "
          f"({100.0 * with_cands / max(1, total):.1f}%)")
    print(f"mean candidates/deck: {n_cands / max(1, total):.3f}")
    print("candidates-per-deck: " + "  ".join(f"{k}:{n}" for k, n in sorted(cand_hist.items())))
    print(f"candidates failing build_spec: {len(unbuildable)}")

    print("--- HERO SLOT (I8) " + "-" * 55)
    h_total = sum(hero_verdicts.values())
    for v in ("REAL", "PHANTOM", "NONE", "UNFILLED"):
        print(f"  {v:<9} {hero_verdicts[v]:>4}  ({100.0 * hero_verdicts[v] / max(1, h_total):.1f}%)")
    h_with = sum(n for k, n in hero_hist.items() if k)
    print(f"decks with >=1 hero candidate: {h_with}/{h_total} "
          f"({100.0 * h_with / max(1, h_total):.1f}%)")
    print(f"mean hero candidates/deck: {n_hero_cands / max(1, h_total):.3f}")
    print("hero-candidates-per-deck: " + "  ".join(f"{k}:{n}" for k, n in sorted(hero_hist.items())))
    print("UNFILLED = the deck HAS a candidate and fielded none. The owner ruling is that the "
          "hero slot always fills;")
    print("  the residue is decks whose ONE card is the sole candidate for the Evolution slot too, "
          "where the two")
    print("  'always' rulings cannot both hold and the Evolution keeps the card.")

    # THE SAMPLED DISTRIBUTION, not the seed-0 one above: the bot draws per match, so what the
    # policy actually trains against is this spread over many draws.
    sampled: Counter = Counter()
    n_none = 0
    for s in range(draws):
        for deck in pool:
            bot = ScriptedBot(cfg, db, random.Random(1000 + s), deck["cards"], deck["style"],
                              [11] * len(deck["cards"]), evo=list(deck.get("evo") or []),
                              evo_candidates=list(deck.get("evo_candidates") or []))
            if bot.evo_idx < 0 or bot.evo_spec is None:
                n_none += 1
            else:
                sampled[deck["cards"][bot.evo_idx]] += 1
    n_draws = total * max(1, draws)
    print(f"sampled evolutions over {draws} draws x {total} decks = {n_draws} matches "
          f"({n_none} fielded none, {len(sampled)} distinct evolutions fielded):")
    for k, n in sampled.most_common(None if verbose else 15):
        print(f"  {k + '_evo':<26} x{n:<6} ({100.0 * n / max(1, n_draws):.2f}%)")
    if not verbose and len(sampled) > 15:
        print(f"  ... {len(sampled) - 15} more (--verbose)")

    # THE SAMPLED HERO + WILD DISTRIBUTION, over the same draws.
    h_sampled: Counter = Counter()
    wild: Counter = Counter()
    wild_both = Counter()
    # ONE RNG ACROSS THE WHOLE SWEEP, unlike the evolution loop above, and the difference is
    # load-bearing: re-seeding per deck makes every deck in a pass draw from the SAME position in
    # the same stream, so the wild slot's three-way split came out 43.9/30.0/26.1 -- an artefact of
    # the seeding, not of the model. Sharing the stream makes the draws independent and it lands on
    # the 1/3 the knobs ask for. The evolution loop keeps its per-deck seeding because it is
    # sampling DECKS rather than measuring a probability.
    _rng = random.Random(2000)
    for s in range(draws):
        for deck in pool:
            bot = ScriptedBot(cfg, db, _rng, deck["cards"], deck["style"],
                              [11] * len(deck["cards"]), evo=list(deck.get("evo") or []),
                              evo_candidates=list(deck.get("evo_candidates") or []),
                              hero_candidates=list(deck.get("hero_candidates") or []),
                              support=list(deck.get("support") or []))
            if bot.hero_idx >= 0:
                h_sampled[deck["cards"][bot.hero_idx]] += 1
            wild[bot.wild_kind or "(none)"] += 1
            if bot.wild_choices[0] > 0 and bot.wild_choices[1] > 0:
                wild_both[bot.wild_kind or "(none)"] += 1
    print(f"sampled heroes over {draws} draws x {total} decks "
          f"({len(h_sampled)} distinct heroes fielded):")
    for k, n in h_sampled.most_common(None if verbose else 16):
        print(f"  {k + '_hero':<26} x{n:<6} ({100.0 * n / max(1, n_draws):.2f}%)")
    wb = sum(wild_both.values())
    print("wild slot, all decks: " + "  ".join(f"{k}:{n} ({100.0 * n / max(1, sum(wild.values())):.1f}%)"
                                               for k, n in wild.most_common()))
    print("wild slot, decks where BOTH categories were legal (the 1/3 split, UNMEASURED choice): "
          + "  ".join(f"{k}:{100.0 * n / max(1, wb):.1f}%" for k, n in wild_both.most_common())
          + f"   n={wb}")

    if declared_no_row:
        print("DECLARED by the meta but absent from the KB (no `_evo` row -> nothing fielded):")
        for k, n in declared_no_row.most_common():
            print(f"  {k:<24} x{n} decks")
    rc = 0
    if unbuildable:
        print(f"CANDIDATES THAT DO NOT RESOLVE ({len(unbuildable)}):")
        for name, k, why in (unbuildable if verbose else unbuildable[:20]):
            print(f"  {name}: {k}_evo -> {why}")
        rc = 1
    if cap_breaks:
        print(f"SLOT CAP VIOLATIONS ({len(cap_breaks)}):")
        for name, why, slots in (cap_breaks if verbose else cap_breaks[:20]):
            print(f"  {name}: {why} {slots}")
        rc = 1
    if hero_phantoms:
        print(f"HERO PHANTOMS ({len(hero_phantoms)}):")
        for name, base in (hero_phantoms if verbose else hero_phantoms[:20]):
            print(f"  {name}: {base}_hero has no live hero row")
        rc = 1
    if phantoms:
        print(f"PHANTOMS ({len(phantoms)}):")
        shown = phantoms if verbose else phantoms[:20]
        for name, base in shown:
            print(f"  {name}: {base}_evo has no KB row")
        if len(shown) < len(phantoms):
            print(f"  ... {len(phantoms) - len(shown)} more (--verbose)")
        rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
