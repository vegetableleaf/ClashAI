"""watch_detect.py INPUT.jsonl [--self-check] -- F1FIX-3 watch list detector.

Flags SME input matches (one JSON object per line, the format of inputs_v30.jsonl / f1_gen2_rf.jsonl:
`derived["0"|"1"]` holds `deck` (engine base card names), `slot_flags`, and the match id in `match`)
where the Rune Giant's enchant (GiantBuffer) reaches one of the F1FIX-3 (b) paths, so evidence accrues:
a flagged match that ENG-SME replays frame-exact promotes that path from (b) to (a); a divergence on a
flagged match is a bug to fix. It is a pre-filter on decks, so it over-flags (the card may never be
played near the Rune Giant); the exact replay of a flagged match is the confirmation.

Engine conditions (all measured from the shipped 16.402.22 / 16.635.3 tables; see CRFORGE_S0.md
"F1FIX-3 WATCH LIST"). The Rune Giant (GiantBuffer) buffs friendly troops only, so a watch unit must be
on the SAME side as the GiantBuffer. Monk / MegaMonk on the OPPOSING side deflects an enchanted
projectile -> the one path still REFUSED (expected fault), flagged so it stays tracked.
"""
import json
import sys

# card (engine base name in the deck) -> (path label, form rule)
#   form rule: "any" fires in base and evolved; "evo" fires only when the slot is evolved
#   (slot_flags != 0); "hero" fires only in a hero-form match (base card does not take the path).
SEQ = {  # attack-sequence path: actionAttackSequence() now false for hit/projectile entries
    "Bowler": "hero",          # BowlerHero: 3 projectile entries (siege)
    "EliteArcher": "hero",     # EliteArcherHero: 2 projectile entries; entry[1] @340 in the buff row
    "Musketeer": "evo",        # Musketeer_EV1: 2 projectile entries (base Musketeer has none)
    "Princess": "evo",         # Princess_EV1: 2 projectile entries (base Princess has none)
    "AngryBarbarians": "evo",  # AngryBarbarian_EV1/_2 (Elite Barbarians): damage + projectile entries
    "LittlePrince": "any",     # 3 projectiles via AttackSequence -- already (a), live-held
}
BERSERK = {"Berserker": "any"}   # Berserk index branch skipped because entries are uniform (base + hero)
ATTACH = {                        # attached-children path: copies omitted, child rows multiplier 0
    "GoblinGiant": "any",         # SpawnAttach SpearGoblinGiant; SpearGoblinGiantProjectile mult 0
    "RamRider": "any",            # SpawnAttach rider; RamRiderBola mult 0
}
DEFLECT = {"Monk", "MegaMonk"}    # opposing side -> enchanted projectile deflected == REFUSED (fault)

PATHS = [("attack_sequence", SEQ), ("berserker_index", BERSERK), ("attached_children", ATTACH)]


def flags_for(match):
    """Yield (path, card, form_note, side) for one parsed match dict, or (REFUSED_deflect,...)."""
    d = match.get("derived") or {}
    sides = {s: d[s] for s in ("0", "1") if isinstance(d.get(s), dict)}
    for s, side in sides.items():
        deck = side.get("deck") or []
        if "GiantBuffer" not in deck:
            continue
        # maker-left is runtime-only (the Giant dies mid-flight), decidable from the deck as "possible"
        yield ("maker_left?", "GiantBuffer", "any RuneGiant match", s)
        slot = side.get("slot_flags") or []
        for label, cards in PATHS:
            for card, rule in cards.items():
                if card not in deck:
                    continue
                idx = deck.index(card)
                evolved = idx < len(slot) and slot[idx] not in (0, None)
                if rule == "evo" and not evolved:
                    continue  # base form does not take the path
                note = rule + ("/evolved" if evolved else "")
                if rule == "hero":
                    note += " (hero-form match only)"
                yield (label, card, note, s)
        # Monk/MegaMonk on the other side deflects the enchanted projectile -> refused
        other = "1" if s == "0" else "0"
        for card in (sides.get(other, {}).get("deck") or []):
            if card in DEFLECT:
                yield ("REFUSED_deflect_copy", card, "opposing " + card, other)


def run(path):
    counts = {}
    n = flagged = 0
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        n += 1
        m = json.loads(line)
        hits = list(flags_for(m))
        if hits:
            flagged += 1
            for (label, card, note, side) in hits:
                counts[label] = counts.get(label, 0) + 1
                print("\t".join((m.get("match", "?"), label, card, note, "side" + side)))
    sys.stderr.write("matches %d  flagged %d  by path %s\n" % (n, flagged, counts))


def self_check():
    giant = {"deck": ["GiantBuffer", "Musketeer", "Berserker", "GoblinGiant", "Bowler", "Knight", "Log", "Archers"],
             "slot_flags": [0, 1, 0, 0, 0, 0, 0, 0]}
    opp = {"deck": ["Monk", "Hog", "X", "Y", "Z", "A", "B", "C"], "slot_flags": [0] * 8}
    hits = {(l, c) for (l, c, _n, _s) in flags_for({"derived": {"0": giant, "1": opp}, "match": "t"})}
    assert ("maker_left?", "GiantBuffer") in hits
    assert ("attack_sequence", "Musketeer") in hits          # evolved slot -> fires
    assert ("berserker_index", "Berserker") in hits
    assert ("attached_children", "GoblinGiant") in hits
    assert ("REFUSED_deflect_copy", "Monk") in hits
    # base (non-evolved) Musketeer on another match must NOT fire the evo path
    g2 = {"deck": ["GiantBuffer", "Musketeer", "K", "L", "M", "N", "O", "P"], "slot_flags": [0] * 8}
    hits2 = {(l, c) for (l, c, _n, _s) in flags_for({"derived": {"0": g2, "1": {"deck": [], "slot_flags": []}}, "match": "t2"})}
    assert ("attack_sequence", "Musketeer") not in hits2
    # a deck with no GiantBuffer yields nothing
    assert not list(flags_for({"derived": {"0": {"deck": ["Musketeer"], "slot_flags": [1]}}, "match": "t3"}))
    print("self-check OK")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--self-check":
        self_check()
    elif len(sys.argv) >= 2:
        run(sys.argv[1])
    else:
        sys.exit("usage: watch_detect.py INPUT.jsonl | --self-check")
