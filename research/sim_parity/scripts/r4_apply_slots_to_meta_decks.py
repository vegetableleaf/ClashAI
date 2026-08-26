"""I3 -- retro-fit the R4 evolution / tower-troop slots onto the EXISTING meta_decks.yaml.

One-off. The pool in config/meta_decks.yaml was imported 2026-08-07 and carries no slot info; the
R4 ledger (2026-08-26) carries the slots but a slightly different set of decks. This joins them on
the 8-card set and rewrites each deck line with `evo:` / `support:`, leaving the deck list, the
weights and the ordering untouched -- the training distribution must not move in a commit whose
subject is evolution slots.

Decks with no exact card-set match keep NO slots: the conditional P(evolved | card in deck) is not
bimodal (36 of 109 cards sit between 0.15 and 0.85), so inferring a slot would be a guess wearing
measured clothes. `run.py decks-import` writes both together from now on (deck_import.py), so the
gap closes on the next re-import rather than needing this script again.

Run:  python research/sim_parity/scripts/r4_apply_slots_to_meta_decks.py
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
LEDGER = ROOT / "research" / "sim_parity" / "ledger" / "meta_evo_slots.json"
TARGETS = [ROOT / "icebow" / "config" / "meta_decks.yaml",
           ROOT / "hogeq" / "config" / "meta_decks.yaml"]


def main() -> int:
    led = json.loads(LEDGER.read_text(encoding="utf-8"))
    evo_by: dict = defaultdict(Counter)
    sup_by: dict = defaultdict(Counter)
    for row in led["decks"]:
        ck = tuple(sorted(row["cards"]))
        evo_by[ck][tuple(row["evo"])] += row["sightings"]
        sup_by[ck][tuple(row["support"])] += row["sightings"]

    def modal(counter: Counter):
        # deterministic: most sightings first, then lexicographic, so a re-run cannot reshuffle ties
        return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if counter else ()

    matched = 0
    text = TARGETS[0].read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    head = [ln for ln in text.splitlines() if ln.startswith("#")]

    lines = list(head)
    lines.append("# EVOLUTION + TOWER-TROOP SLOTS (2026-08-26, R4): `evo` = the evolution(s) this "
                 "exact 8-card deck was")
    lines.append("# SEEN fielding on top ladder, `support` = its tower troop -- "
                 "research/sim_parity/ledger/meta_evo_slots.json")
    lines.append("# (7173 battlelog sightings, 120 path-of-legends players). A deck with no `evo` "
                 "was never seen in that")
    lines.append("# sample: the sim then fields NO evolution for it rather than guessing one. "
                 "`evo` records what the META")
    lines.append("# does, so keys the KB has no `_evo` row for (berserker, giant, ...) stay listed "
                 "and light up on import.")
    lines.append("decks:")
    for d in (data.get("decks") or []):
        cards = list(d.get("cards") or [])
        ck = tuple(sorted(cards))
        evo = [k for k in modal(evo_by.get(ck, Counter())) if k in cards]
        sup = list(modal(sup_by.get(ck, Counter())))
        if ck in evo_by:
            matched += 1
        bits = [f"name: {d['name']}", f"weight: {d['weight']}", f"cards: [{', '.join(cards)}]"]
        if evo:
            bits.append(f"evo: [{', '.join(evo)}]")
        if sup:
            bits.append(f"support: {sup[0]}")
        lines.append("  - {" + ", ".join(bits) + "}")

    out = "\n".join(lines) + "\n"
    for p in TARGETS:
        p.write_text(out, encoding="utf-8")
    n = len(data.get("decks") or [])
    with_evo = sum(1 for ln in lines if "evo: [" in ln and ln.startswith("  - {"))
    with_sup = sum(1 for ln in lines if "support: " in ln and ln.startswith("  - {"))
    print(f"decks: {n}; card-set matched in the ledger: {matched}; "
          f"with an evo slot: {with_evo}; with a tower troop: {with_sup}")
    print("wrote " + " and ".join(str(p) for p in TARGETS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
