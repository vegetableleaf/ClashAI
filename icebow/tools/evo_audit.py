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

Run:  PYTHONPATH=src python tools/evo_audit.py [--verbose] [--draws N]
Exit code 1 if ANY phantom is found, or if any candidate fails to resolve through `build_spec`,
so this can gate a commit.
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
from clashrl.sim.meta_decks import has_evolution, load_meta_decks  # noqa: E402
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
    phantoms: list = []
    unbuildable: list = []
    cand_hist: Counter = Counter()
    declared_no_row: Counter = Counter()

    n_cands = 0
    declared_decks = 0
    for deck in pool:
        cands = list(deck.get("evo_candidates") or [])
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
                          [11] * len(deck["cards"]), evo=declared, evo_candidates=cands)
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
