"""Generate config/import_pins.json (both decks) from the adjudicated R2 ledger.

    python research/sim_parity/scripts/gen_pins.py

A PIN is a curated value the wiki is known to lag or contradict: the importer applies
pins as a post-pass over the scraped rows, and `--write` refuses if a pinned field
would regress (PLAN.md I4 "Curated values survive import"). Sources, in order:

  1. every ledger/stat_diffs.jsonl row with verdict "pin" (66 rows, R2 sweep) --
     value = the row's current_db (the curated value the sweep upheld);
  2. the owner rulings in decisions.md (2026-08-26 R2 ADJUDICATION) that assert a
     specific number, including the 5 balance-lag crown pins the sweep re-derived.

Where both name the same (key, field) the stat_diffs row wins the provenance slot and
the script asserts the values agree -- a disagreement would mean the ledger and the
rulings diverged, which is a stop-and-investigate, not a merge.

Pin schema: {key, field, value, source, date}. `value: null` means "this field must
NOT be imported" (e.g. the champion ability_cooldown_s entries -- dead numbers under
the 4/8/2026 single-use rework, decisions.md "Still open"). Fields the importer does
not emit (cards.yaml-curated values like spark_dps_small, composite fields like
`spawns.delay`) are ADVISORY here: recorded for I5's stat_sweep EXPECTED sync, no-ops
in the importer post-pass.

The file is a byte-identical pair; this script writes both decks' copies and verifies.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LEDGER = ROOT / "research" / "sim_parity" / "ledger"
DECKS = ("icebow", "hogeq")

# decisions.md 2026-08-26 R2 ADJUDICATION -- owner-verified values that must survive
# any re-import. (key, field, value, which ruling).
DECISION_PINS = [
    ("mighty_miner", "ability_bomb_damage", 332,
     "decisions.md #9: rarity-floor anchor, wiki integer base 332 @ L11 reproduces the "
     "owner's observed 440 @ L14; replaces the 366 reverse-derivation"),
    ("firecracker_evo", "spark_dps_small", 48,
     "decisions.md #5: wiki correct for ALL firecracker_evo entries; owner overturned "
     "the old verified 60 (closes the long-flagged spark_dps_small conflict)"),
    ("earthquake", "damage", 81,
     "decisions.md #5: earthquake damage = 81 @ L11, not 84 (overrides the 2026-08 "
     "HANDOFF card-data row)"),
    ("tesla_evo", "hitpoints", 1182,
     "decisions.md #5: tesla_evo hitpoints = base = 1182 @ L11 (evo hp same as base)"),
    ("cannon_evo", "volley_damage", 281,
     "decisions.md #9: cannon_evo volley damage 281 @ L11 (nerfed; wiki vardefine "
     "lags at 304)"),
    ("mortar", "hit_speed", 4.7, "decisions.md #10: mortar AND mortar_evo hit speed 4.7 s"),
    ("mortar_evo", "hit_speed", 4.7,
     "decisions.md #10: mortar AND mortar_evo hit speed 4.7 s"),
    # The 5 balance-lag crown pins (post-1/6/2026 percentages; wiki vardefines lag their
    # own balance history -- tools/crown_damage_audit.py is the detector).
    ("rocket", "crown_tower_damage", 341,
     "decisions.md balance-lag pin: 1/6/2026 set 23% of full; 1484 * 0.23 = 341.32 -> 341 "
     "(cards.yaml's 342 is off by one against this pin -- I5 applies 341)"),
    ("lightning", "crown_tower_damage", 264, "decisions.md balance-lag pin (post-1/6/2026)"),
    ("zap", "crown_tower_damage", 48, "decisions.md balance-lag pin (post-1/6/2026)"),
    ("the_log", "crown_tower_damage", 35, "decisions.md balance-lag pin (post-1/6/2026)"),
    ("poison", "crown_tower_damage", 21, "decisions.md balance-lag pin (post-1/6/2026)"),
]
DECISION_DATE = "2026-08-26"


def main() -> int:
    rows = [json.loads(line) for line in
            (LEDGER / "stat_diffs.jsonl").read_text(encoding="utf-8").splitlines() if line]
    pin_rows = [r for r in rows if r.get("verdict") == "pin"]
    assert len(pin_rows) == 66, f"expected 66 verdict:pin rows, got {len(pin_rows)}"

    pins: dict = {}
    for r in pin_rows:
        key, field = r["key"], r["field"]
        src = r.get("sources") or []
        date = (src[0].get("fetched") if src else None) or "2026-08-26"
        prov = r.get("provenance") or {}
        pins[(key, field)] = {
            "key": key,
            "field": field,
            "value": r.get("current_db"),
            "source": f"stat_diffs.jsonl verdict:pin ({prov.get('file', '?')}:"
                      f"{prov.get('line', '?')}, family {r.get('family')})",
            "date": date,
        }

    dup = 0
    for key, field, value, why in DECISION_PINS:
        if (key, field) in pins:
            got = pins[(key, field)]["value"]
            assert got == value, \
                f"pin disagreement for {key}.{field}: stat_diffs {got!r} vs decisions {value!r}"
            pins[(key, field)]["source"] += " + " + why
            dup += 1
        else:
            pins[(key, field)] = {"key": key, "field": field, "value": value,
                                  "source": why, "date": DECISION_DATE}

    ordered = [pins[k] for k in sorted(pins)]
    payload = {
        "meta": {
            "generator": "research/sim_parity/scripts/gen_pins.py",
            "sources": ["ledger/stat_diffs.jsonl (66 verdict:pin rows)",
                        "decisions.md 2026-08-26 R2 ADJUDICATION (owner rulings)"],
            "semantics": "the importer applies pins as a post-pass over the scraped rows and "
                         "--write refuses if a pinned field would regress; value null = the "
                         "field must not be imported; fields the importer does not emit are "
                         "advisory (curated layer / stat_sweep EXPECTED sync)",
            "pair": "byte-identical across icebow/ and hogeq/ -- regenerate with the "
                    "generator and it writes both; never hand-edit one copy",
            "counts": {"total": len(ordered),
                       "from_stat_diffs": len(pin_rows),
                       "from_decisions": len(DECISION_PINS),
                       "overlapping": dup},
        },
        "pins": ordered,
    }
    text = json.dumps(payload, indent=1, sort_keys=False) + "\n"
    outs = [ROOT / d / "config" / "import_pins.json" for d in DECKS]
    for o in outs:
        o.write_text(text, encoding="utf-8", newline="\n")
    same = outs[0].read_bytes() == outs[1].read_bytes()
    print(f"wrote {len(ordered)} pins ({len(pin_rows)} stat_diffs + "
          f"{len(DECISION_PINS)} decisions, {dup} overlapping) to:")
    for o in outs:
        print(f"  {o}")
    print(f"pair byte-identical: {same}")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
