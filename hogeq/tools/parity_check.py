"""SIM PARITY GATE: what the two decks share must stay shared, and what differs must be declared.

icebow/ and hogeq/ are two checkouts of one agent with two decks. Everything below the deck --
the engine, the card knowledge base, the level table, the meta-deck pool -- is supposed to be ONE
thing, and repeatedly was not: a fix would land in whichever deck the session was working in and
the other would keep the bug for weeks. Measured examples, all real:

  * `Engine._recoil` existed only in hogeq, so icebow's copy of the shared geometry test had the
    Firecracker recoil class deleted with the note "this engine has no self-recoil mechanic".
  * `CardDB.deck()` scaled by `1.1 ** (level - 11)` in BOTH decks while `build_spec` had long
    since moved to `levels.PERCENT` -- the same card, two answers.
  * `evo_cycles()` was gated so that 6 of 42 evolutions reported a cycle count.

This is the gate that makes such drift LOUD. It compares the two trees and fails on any divergence
that is not on the allow-list below. It is byte-identical in both decks and runs from either.

    PYTHONPATH=src python tools/parity_check.py [--verbose] [--strict]

Exit 1 on unexpected divergence (or, with --strict, also on a stale allow-list entry).

THE ALLOW-LIST IS TWO LISTS, and the distinction is the point:

  DECK    -- genuinely deck-specific. These SHOULD differ forever; converging them would be wrong.
  DRIFT   -- divergence that is not deliberate, recorded as today's baseline. Each entry is a
             fix or feature that landed in one deck and never reached the other. This list is
             meant to SHRINK; nothing here has been blessed, only measured.

Adding an entry is a decision to be made deliberately, in a commit that says why.
"""
from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAIR = ROOT.parent
DECKS = ("icebow", "hogeq")

# --- CONFIG: must be byte-identical. No allow-list, deliberately. -----------------------------
# Pure DATA about the game and the detector, shared wholesale. A difference here is never a deck
# opinion -- it means one deck's import, generator run or hand-edit did not reach the other.
# import_allowlist.json + import_pins.json joined 2026-08-26 (I4): the generated evolution/hero
# import gate and the curated-value pin registry.
QUARTET = ("cards_stats.json", "card_mechanics.json", "detect_classes.yaml", "meta_decks.yaml",
           "import_allowlist.json", "import_pins.json")

# cards.yaml is the one config file that legitimately differs, and ONLY in its `deck:` block: the
# eight cards and their levels. Everything else in it is a card fact. Checked by stripping that
# block from both and requiring the remainder to match, rather than by allow-listing the file --
# a blanket allow would have hidden the Earthquake / Firecracker / Mighty Miner rows that were
# sitting in one KB and not the other.
DECK_BLOCK = re.compile(r"(?m)^deck:\n(?:[ \t][^\n]*\n|\n(?=[ \t]))*")

# --- src/clashrl: the allow-list ---------------------------------------------------------------
DECK_SPECIFIC = {
    "sim/drills_*.py": "the deck's own drill curriculum -- one file per deck by construction",
    "sim/doctrine.py": "card doctrine: X-Bow/Rocket/Tornado rules vs Hog/Earthquake rules, keyed "
                       "on cards only one deck holds",
    "sim/env.py": "the deck's action space and reward wiring. hogeq exposes the Mighty Miner's "
                  "ability as its own identity (11 outputs); icebow has no champion and must stay "
                  "at 10 or every checkpoint refuses to load. Also icebow-only pocket-lane "
                  "deployment and deck-PFSP plumbing",
    "sim/opponents.py": "icebow-only pocket pressure + deck PFSP; the evolution and cycle "
                        "machinery IS shared and is pinned by tests/test_no_phantom_evos.py",
    "train_sim_ppo.py": "per-deck training wiring: drill mix, deck-PFSP aggregation, worker "
                        "plumbing",
    "vision.py": "live deck identities. hogeq must publish policy_identities() (card head 11) so "
                 "a sim checkpoint loads; icebow publishes deck_identities()",
    "policy_stats.py": "which ids count as win conditions -- deck-driven",
    "llm_advisor.py": "the prompt names the deck's cards; icebow also carries the async advisor",
    "play.py": "live aim assists for cards only one deck holds (Log corridor, Tornado king pull)",
    "actions.py": "icebow-only pocket deployment mask (`deployable_mask(anywhere, pocket=...)`)",
    "cli.py": "per-deck training flags (--drill-only, --workers default, drill-mix banner)",
}

DRIFT = {
    "sim/remote_pool.py": "icebow-only deck-record channel for deck PFSP across workers. Only "
                          "useful once hogeq has deck PFSP, so it moves with sim/opponents.py",
    "train_rl.py": "icebow-only async LLM advisor; hogeq-only policy_identities() for the live "
                   "deck. Two separate one-way ports",
    "env.py": "comment wording only on the air_bases fix; the code agrees",
}

ALLOW = dict(DECK_SPECIFIC)
ALLOW.update(DRIFT)


def _match(rel: str):
    """The allow-list entry covering `rel`, or None. Exact path first, then glob."""
    if rel in ALLOW:
        return rel
    for pat in ALLOW:
        if "*" in pat and fnmatch.fnmatch(rel, pat):
            return pat
    return None


def _read(p: Path) -> bytes:
    return p.read_bytes()


def _same(a: Path, b: Path) -> bool:
    return a.exists() and b.exists() and _read(a) == _read(b)


def _tree(root: Path, sub: str, pattern: str = "*.py"):
    base = root / sub
    if not base.exists():
        return {}
    return {str(p.relative_to(base)).replace("\\", "/"): p
            for p in base.rglob(pattern) if "__pycache__" not in p.parts}


def main(argv) -> int:
    verbose = "--verbose" in argv
    strict = "--strict" in argv
    roots = {d: PAIR / d for d in DECKS}
    missing = [d for d, p in roots.items() if not p.exists()]
    if missing:
        print(f"parity_check: cannot find deck root(s) {missing} beside {ROOT} -- "
              "both decks must be checked out as siblings.")
        return 2
    a, b = roots[DECKS[0]], roots[DECKS[1]]
    print(f"parity: {DECKS[0]} <-> {DECKS[1]}   ({PAIR})")

    fails: list = []

    # 1. the config quartet -------------------------------------------------------------------
    print("\nconfig (must be byte-identical):")
    for f in QUARTET:
        pa, pb = a / "config" / f, b / "config" / f
        if not pa.exists() or not pb.exists():
            fails.append((f"config/{f}", "missing in one deck"))
            print(f"  MISSING  config/{f}")
        elif _same(pa, pb):
            print(f"  ok       config/{f}   ({pa.stat().st_size:,} bytes)")
        else:
            fails.append((f"config/{f}", "bytes differ"))
            print(f"  DIFFERS  config/{f}")

    # 2. cards.yaml, minus the deck block ------------------------------------------------------
    ta = (a / "config" / "cards.yaml").read_text(encoding="utf-8")
    tb = (b / "config" / "cards.yaml").read_text(encoding="utf-8")
    ka, kb = DECK_BLOCK.sub("", ta), DECK_BLOCK.sub("", tb)
    if DECK_BLOCK.search(ta) is None or DECK_BLOCK.search(tb) is None:
        fails.append(("config/cards.yaml", "no `deck:` block found -- the stripper is stale"))
        print("  BROKEN   config/cards.yaml: no `deck:` block found")
    elif ka == kb:
        print(f"  ok       config/cards.yaml   (identical apart from the {len(ta) - len(ka):,}-byte "
              f"deck block)")
    else:
        fails.append(("config/cards.yaml", "differs OUTSIDE the deck block -- a card fact is in "
                                           "one KB and not the other"))
        print("  DIFFERS  config/cards.yaml OUTSIDE its deck block")
        if verbose:
            import difflib
            for line in list(difflib.unified_diff(ka.splitlines(), kb.splitlines(),
                                                  DECKS[0], DECKS[1], lineterm=""))[:60]:
                print("           " + line)

    # 3. src/clashrl ---------------------------------------------------------------------------
    fa, fb = _tree(a, "src/clashrl"), _tree(b, "src/clashrl")
    rels = sorted(set(fa) | set(fb))
    shared, declared, unexpected, converged = [], [], [], []
    for rel in rels:
        pa, pb = fa.get(rel), fb.get(rel)
        both = pa is not None and pb is not None
        identical = both and _same(pa, pb)
        hit = _match(rel)
        if identical:
            (converged if hit else shared).append((rel, hit))
        elif hit:
            declared.append((rel, hit))
        else:
            unexpected.append((rel, "only in " + (DECKS[0] if pa else DECKS[1])
                               if not both else "contents differ"))

    print(f"\nsrc/clashrl: {len(rels)} files")
    print(f"  shared, identical : {len(shared)}")
    print(f"  declared different: {len(declared)}")
    print(f"  UNEXPECTED        : {len(unexpected)}")
    if converged:
        print(f"  allow-listed but now IDENTICAL (delete the entry): {len(converged)}")
        for rel, hit in converged:
            print(f"      {rel}   [{hit}]")

    for rel, hit in declared:
        if verbose:
            print(f"  declared  {rel}\n              {ALLOW[hit]}")
    if unexpected:
        print("\nUNEXPECTED DIVERGENCE -- shared code drifted, or a new deck-specific file needs "
              "an allow-list entry:")
        for rel, why in unexpected:
            print(f"  {rel}   ({why})")
            fails.append((f"src/clashrl/{rel}", why))

    # 4. tests + tools: informational only ------------------------------------------------------
    # NOT a gate. Deck doctrine legitimately owns whole test files, and a count is enough to see
    # the reconciliation state at a glance without inventing a rule nobody agreed to.
    for sub in ("tests", "tools"):
        ga, gb = _tree(a, sub), _tree(b, sub)
        both = set(ga) & set(gb)
        same = sum(1 for r in both if _same(ga[r], gb[r]))
        print(f"\n{sub}/ (informational): {len(both)} in both ({same} identical, "
              f"{len(both) - same} differ), {len(set(ga) - set(gb))} only in {DECKS[0]}, "
              f"{len(set(gb) - set(ga))} only in {DECKS[1]}")
        if verbose:
            for r in sorted(set(ga) ^ set(gb)):
                print(f"    only in {DECKS[0] if r in ga else DECKS[1]}: {r}")

    if converged and strict:
        for rel, hit in converged:
            fails.append((f"src/clashrl/{rel}", f"allow-list entry '{hit}' is stale"))

    print()
    if fails:
        print(f"PARITY FAIL: {len(fails)} problem(s)")
        for path, why in fails:
            print(f"  {path}: {why}")
        return 1
    print("PARITY OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
