"""Turn researched counter rows into config/counters.yaml -- with a LOCAL re-validation.

    python tools/counters_build.py <research.json> [--deck icebow] [--out config/counters.yaml]

The research fleet audits itself, but a self-audit is a claim, not a verification. Every row is
re-checked HERE against this repo's own card database before it can ship:

  * every respond[].card must be in THIS deck (a table row naming a card we do not hold is dead
    weight at best and a wasted decision at worst);
  * threat_value.pick_invalid must pass -- the same veto the live advisor and the sim prior use,
    so the table can never propose what the pipeline would immediately reject (knight on a
    balloon, rocket on wall breakers);
  * when/where must be in the closed vocabulary the wheels can actually execute;
  * unknown card names are dropped rather than guessed at.

Dropped rows are printed with the reason, so a research gap is visible instead of silent.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl import threat_value                      # noqa: E402
from clashrl.cards import CardDB                      # noqa: E402
from clashrl.config import Config                     # noqa: E402
from clashrl.counters import WHEN_VALUES, WHERE_VALUES  # noqa: E402


def build(rows, deck_bases, db, log=print):
    """Return (clean_rows, dropped[(threat, why)])."""
    known = set(deck_bases)
    out, dropped = [], []
    seen_keys = set()
    for row in rows or []:
        threat = str(row.get("threat") or "")
        cards = [str(c) for c in (row.get("threat_cards") or []) if c]
        if not cards:
            dropped.append((threat, "no threat_cards"))
            continue
        unknown = [c for c in cards if db.get(c) is None]
        if unknown:
            dropped.append((threat, "unknown threat card(s): %s" % ", ".join(unknown)))
            continue
        key = frozenset(cards)
        if key in seen_keys:
            dropped.append((threat, "duplicate of an earlier row"))
            continue
        keep = []
        for r in (row.get("respond") or []):
            card = str(r.get("card") or "")
            when = str(r.get("when") or "")
            where = str(r.get("where") or "")
            if card not in known:
                dropped.append((threat, "response %r is not in this deck" % card))
                continue
            if when not in WHEN_VALUES or where not in WHERE_VALUES:
                dropped.append((threat, "response %r has bad when/where (%s/%s)"
                                % (card, when, where)))
                continue
            why = threat_value.pick_invalid(db, card, cards)
            if why:
                dropped.append((threat, "response %r vetoed: %s" % (card, why)))
                continue
            entry = {"card": card, "when": when, "where": where}
            if r.get("note"):
                entry["note"] = str(r["note"])[:90]
            keep.append(entry)
        if not keep:
            dropped.append((threat, "no response survived validation"))
            continue
        clean = {"threat": threat or "+".join(cards), "threat_cards": cards, "respond": keep}
        if row.get("mitigation"):
            clean["mitigation"] = True
        out.append(clean)
        seen_keys.add(key)
    return out, dropped


def dump_yaml(rows, path, deck, source_note=""):
    """Hand-written YAML: ordering is meaningful here (first row for a threat key wins, so a
    manual override belongs ABOVE the generated rows) and a dumper would not preserve it."""
    L = []
    L.append("# COUNTER TABLE -- %s. What this deck plays against what, WHEN, and WHERE.\n" % deck)
    L.append("#\n")
    L.append("# Researched from counter guides, then re-validated against this repo's own card\n")
    L.append("# database by tools/counters_build.py: every response is in this deck, passes\n")
    L.append("# threat_value.pick_invalid (so it can physically touch the threat and the trade is\n")
    L.append("# sane), and uses only when/where words the wheels can execute.\n")
    L.append("#\n")
    L.append("# Consumed by the live advisor path (vetoed pick / silent advisor) and the sim's\n")
    L.append("# doctrine prior, so both sides answer a push the same way. THE FIRST ROW FOR A\n")
    L.append("# THREAT KEY WINS: put hand-written overrides ABOVE the generated rows and they\n")
    L.append("# survive a regenerate.\n")
    if source_note:
        L.append("#\n# %s\n" % source_note)
    L.append("counters:\n")
    for r in rows:
        L.append("  - threat: %s\n" % json.dumps(r["threat"]))
        L.append("    threat_cards: [%s]\n" % ", ".join(r["threat_cards"]))
        if r.get("mitigation"):
            L.append("    mitigation: true\n")
        L.append("    respond:\n")
        for e in r["respond"]:
            line = "      - {card: %s, when: %s, where: %s" % (e["card"], e["when"], e["where"])
            if e.get("note"):
                line += ", note: %s" % json.dumps(e["note"])
            L.append(line + "}\n")
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("".join(L))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("research", help="JSON with {<deck>: {table: [...]}} or a bare row list")
    ap.add_argument("--deck", default=None, help="key to read from the JSON (default: this deck)")
    ap.add_argument("--out", default=None, help="output path (default: config/counters.yaml)")
    a = ap.parse_args(argv)

    cfg = Config.load()
    db = CardDB(cfg)
    deck = a.deck or (cfg.get("deck", "name", default=None) or "deck")
    with io.open(a.research, encoding="utf-8") as fh:
        data = json.load(fh)
    rows = data.get(deck, {}).get("table") if isinstance(data, dict) else None
    if rows is None:
        rows = data if isinstance(data, list) else (data.get("table") or [])
    deck_bases = [str(k).replace("_evo", "") for k in (cfg.get("deck", "cards", default=[]) or [])]
    if not deck_bases:
        deck_bases = sorted({str(k) for k in (db.deck_identities() or [])})
    clean, dropped = build(rows, deck_bases, db)
    out = a.out or os.path.join(os.path.dirname(__file__), "..", "config", "counters.yaml")
    dump_yaml(clean, out, deck, "generated from %s" % os.path.basename(a.research))
    print("[counters] %d rows kept, %d dropped -> %s" % (len(clean), len(dropped), out))
    for threat, why in dropped[:40]:
        print("   dropped %-28s %s" % (threat, why))
    if len(dropped) > 40:
        print("   ... and %d more" % (len(dropped) - 40))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
