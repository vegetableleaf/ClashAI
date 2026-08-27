"""Cross-check the card KB against the live wiki.  `python tools/stat_sweep.py [--all]`

WHY THIS IS NOT A ONE-LINER
---------------------------
The obvious sweep -- compare our level-11 hp/damage against the page's `hp_11`/`dmg_11` -- is
WRONG for most of the interesting cards, and wrong in a way that looks like a bug report. Run
naively (2026-08-16) it flagged 18 cards, 17 of them false positives that would have corrupted
the KB if applied. The wiki's field layout varies by card SHAPE:

  * SPAWNER buildings publish the SPAWNED TROOP under hp_11 -- goblin_hut 133 is a spear
    goblin (the hut is 1228), tombstone 81 is a skeleton (the tombstone is 529). The building's
    own hitpoints are not in a vardefine at all.
  * MULTI-BODY cards prefix every field: golem_/mite_, hound_/pup_, giant_/spear_,
    stab_/spear_, cage_ ... goblin_cage's hp_11 (1080) is the BRAWLER inside; the cage is
    cage_hp_11 (780). battle_ram's hp_11 (670) is the Barbarians; the ram is ram_hp_11 (967).
  * SPELLS have no hitpoints at all -- dmg_11 + crown_dmg_11, which map to spell_dmg and
    spell_tower_dmg.
  * OLDER PAGES define ` hp_base ` / ` dmg_base ` (note the spaces) instead of per-level
    values, and on those pages BASE IS THE LEVEL-11 REFERENCE, not level 1. Scaling it by
    1.1^10 "to reach level 11" produces level-21 nonsense (archers 304 -> 788).
  * Some titles carry a trailing dot: "P.E.K.K.A." / "Mini P.E.K.K.A.". Resolve via the search
    API rather than guessing from the key.

So the mapping below is per-shape, and anything it cannot map confidently is REPORTED as
unmapped rather than silently compared.

MODES
-----
  (no flag)  the DECK plus the meta-deck pool -- what actually gets played.
  --evo      the same, plus every `_evo` row.
  --all      EVERY key in the merged CardDB (I5). That is the honest gate: a card only the
             opponent pool fields, or a row nobody has slotted yet, is still a card the sim can
             build a spec for. It also means dozens of keys with no wiki page of their own --
             spawned sub-units (ghost_souldier, decoy_goblin, goblin_brawler, phoenix_egg ...),
             the second form of a two-form card, the ability pseudo-cards. Those come back
             UNMAPPED and are LISTED, never guessed at: an invented page title is how a sweep
             starts reporting one card's numbers against another card's page.

DELIBERATE DEVIATIONS LIVE IN ONE FILE
--------------------------------------
`EXPECTED` used to be a hand-written dict here, which meant the sweep had its own private
opinion about which disagreements were fine. Since I5 it is DERIVED from
`config/import_pins.json`: a pin is exactly "a value we hold on purpose against what the wiki
prints", the importer already refuses to overwrite one, and having two lists would let them
drift. Anything that disagrees with the wiki and is NOT pinned is a finding.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from clashrl.config import Config          # noqa: E402
from clashrl.sim.env import SimMatchEnv    # noqa: E402
from clashrl import cr_web                 # noqa: E402
import clashrl.sim.engine as E             # noqa: E402

# card key -> (page title, hp field, damage field). None = do not compare that field.
PREFIXED = {
    "golem": ("Golem", "golem_hp_11", "golem_dmg_11"),
    "elixir_golem": ("Elixir Golem", "golem_hp_11", "golem_dmg_11"),
    "lava_hound": ("Lava Hound", "hound_hp_11", "hound_dmg_11"),
    "goblin_giant": ("Goblin Giant", "giant_hp_11", "giant_dmg_11"),
    "goblin_gang": ("Goblin Gang", "stab_hp_11", "stab_dmg_11"),
    "goblin_cage": ("Goblin Cage", "cage_hp_11", None),
    "battle_ram": ("Battle Ram", "ram_hp_11", "ram_dmg_11"),
    "pekka": ("P.E.K.K.A.", "hp_11", "dmg_11"),
    "mini_pekka": ("Mini P.E.K.K.A.", "hp_base", "dmg_base"),
    "archers": ("Archers", "hp_base", "dmg_base"),
    "minions": ("Minions", "hp_base", "dmg_base"),
    "minion_horde": ("Minion Horde", "hp_base", "dmg_base"),
}
# SPAWNERS publish the SPAWNED BODY under the headline hp_11/dmg_11 -- goblin_hut's 133/81 is a
# Spear Goblin, tombstone's 81/81 is a Skeleton, barbarian_hut's 670/192 is a Barbarian. Neither
# column describes the card, so BOTH are skipped. (Until I5 only hp was skipped, and the damage
# comparison was saved from firing purely by a truthiness bug: our body deals 0, and `if wdmg and
# ours_dmg` skipped every row where either side was zero. Fixing the bug exposed eight of these.)
SPAWNERS = {"goblin_hut", "barbarian_hut", "tombstone", "furnace", "goblin_drill",
            "skeleton_barrel", "goblinstein", "suspicious_bush",
            # spell-shaped spawners: the payload's numbers under the spell's own field names
            "graveyard", "goblin_barrel"}
# SPELLS whose own damage is NOT dmg_11. Royal Delivery's dmg_11 133 is the spawned Recruit's
# melee and the landing blast is spawn_11; Goblin Curse's dmg_11 120 is the GOBLIN a cursed
# victim becomes, while the curse itself is curse_dmg_11 (decisions.md #12).
SPELL_FIELDS = {
    "royal_delivery": ("spawn_11", "spawn_crown_11"),
    "goblin_curse": ("curse_dmg_11", None),
}

# KNOWN, DELIBERATE deviations. DERIVED from config/import_pins.json (I5) so that pins are the
# single registry of "we hold this on purpose"; see the module docstring. The mapping from a pin's
# field to a sweep column is not one-to-one, because the sweep compares what the ENGINE ends up
# with: `hit_dmg` is rebuilt as dps * hit_speed, so a pin on either of those is a pin on `damage`.
_PIN_FIELD_TO_COL = {
    "hitpoints": "hp",
    "damage": "damage", "dps": "damage", "hit_speed": "damage",
    "crown_tower_damage": "crown_dmg",
}


def _expected(root=None) -> dict:
    path = (root or Path(__file__).resolve().parents[1]) / "config" / "import_pins.json"
    try:
        pins = json.loads(path.read_text(encoding="utf-8"))["pins"]
    except (OSError, KeyError, ValueError) as exc:  # noqa: BLE001
        print("WARNING: could not read %s (%s) -- every deviation will report as NEW" % (path, exc))
        return {}
    out = {}
    for p in pins:
        col = _PIN_FIELD_TO_COL.get(p.get("field"))
        if col:
            out.setdefault((p.get("key"), col), p.get("source", "pinned"))
    return out


EXPECTED = _expected()


# EVOLUTIONS repeat the shape problem on their own pages: the headline hp_11/dmg_11 belong to
# whatever the card SPAWNS, and the evolved body hides behind a prefix. Verified 2026-08-16 by
# reading each page's own table headers rather than assuming the base card's layout carries over.
EVO_FIELDS = {
    "battle_ram_evo": ("ram_hp_11", "ram_dmg_11"),      # hp_11 737 is the Barbarians
    "goblin_drill_evo": ("drill_hp_11", None),          # hp_11 202 is the Goblin it spawns
    "skeleton_barrel_evo": ("hp_11", None),             # the barrel does not attack; dmg is the skeletons'
    "witch_evo": ("hp_11", "dmg_11"),                   # maks_hp_11 1039 is the OVERHEAL CAP, not hp
}


def no_page_keys(db) -> set:
    """Keys that are BODIES, not cards -- derived, never hand-listed.

    `cards-import` walks every card category on the wiki, so a base key the importer did not
    emit is by construction not a card: it is a spawned body (ghost_souldier, goblin_brawler,
    decoy_goblin, golemite...), a second form (spirit_empress_air), or a curated fragment
    (phoenix_egg). MEASURED 2026-08-26: exactly 15 of 137 base keys. Deriving it from the
    imported set means a card released tomorrow moves out of this set by itself.
    """
    try:
        gen = json.loads((Path(db.path).parent / "cards_stats.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):  # noqa: BLE001
        return set()
    have = set(gen.get("cards") or {})
    return {k for k in db.cards
            if not k.endswith(("_evo", "_hero")) and k not in have and k not in PREFIXED}


def page_for(key: str, db=None, no_page=frozenset()) -> str:
    """The wiki page title for a card key, or "" when there is no page to guess at.

    Hardened for --all. The base-card guess ("goblin_hut" -> "Goblin Hut") is safe for a deck and
    a meta pool, which only ever hold real cards; over the WHOLE db it would invent "Ghost
    Souldier" and "Phoenix Egg" and then compare a spawned body against whatever page happened to
    answer. Returning "" makes the caller REPORT those as unmapped, which is the honest answer.
    """
    if key in PREFIXED:
        return PREFIXED[key][0]
    if key in no_page:
        return ""
    for suf, sub in (("_evo", "Evolution"), ("_hero", "Hero")):
        if key.endswith(suf):
            base = key[: -len(suf)]
            # PREFIXED first: it carries the titles the key cannot produce, and the trailing dot
            # is one of them -- the merged row's display is "Mini P.E.K.K.A" while the page is
            # "Mini P.E.K.K.A./Hero", so a display-first guess 404s on exactly the cards the
            # module docstring already warned about.
            disp = (PREFIXED[base][0] if base in PREFIXED else
                    ((db.get(base) or {}).get("display") if db else None) or
                    page_for(base, db, no_page))
            return "%s/%s" % (disp, sub) if disp else ""
    return " ".join(w.capitalize() for w in key.split("_")).replace("X Bow", "X-Bow")


def _base_of(key: str) -> str:
    """The base card behind an `_evo` / `_hero` key.

    A variant inherits its parent's PAGE SHAPE: Tombstone/Hero publishes hp_11 81 / dmg_11 81 --
    the Skeleton it spawns -- exactly as the base Tombstone page does, while the Hero Tombstone's
    own 4224/422 live in the attribute table. MEASURED: without this, --all reported
    tombstone_hero as +5115% hp.
    """
    for suf in ("_evo", "_hero"):
        if key.endswith(suf):
            return key[: -len(suf)]
    return key


def num(st: dict, field):
    if not field:
        return None
    try:
        return float(str(st.get(field)).replace(",", ""))
    except Exception:  # noqa: BLE001
        return None


_BAND = 0.02        # relative tolerance; the wiki rounds and we scale, so exact equality is noise


def _off(theirs, ours) -> bool:
    """Is OUR value outside the band around the WIKI's?

    The comparison used to be written `if theirs and ours and abs(...)`, which silently skipped
    any row where either side was legitimately ZERO -- the exact case worth catching. A card the
    KB says deals 0 damage while the wiki publishes a number, or vice versa, is not agreement; it
    is the largest possible disagreement. Only a MISSING value (None) is a reason to skip.
    """
    if theirs is None or ours is None:
        return False
    return abs(float(theirs) - float(ours)) / max(1.0, abs(float(theirs))) > _BAND


def main(argv) -> int:
    cfg = Config.load()
    env = SimMatchEnv(cfg, seed=0)
    all_keys = "--all" in argv
    no_page = no_page_keys(env.db) if all_keys else frozenset()
    if all_keys:
        # EVERY row in the merged KB, not the deck + meta-pool union. A card the pool does not
        # happen to field is still a card the sim builds a spec for.
        cards = sorted(env.db.cards)
    else:
        pool = set(env.deck_keys)
        for d in env.meta_pool:
            pool.update(d if isinstance(d, (list, tuple)) else d.get("cards", []))
        cards = sorted(c for c in pool if not c.endswith("_evo"))
        if "--evo" in argv:
            cards += sorted(k for k in env.db.cards if k.endswith("_evo"))

    bad, unmapped, checked = [], [], 0
    for key in cards:
        try:
            spec = E.build_spec(env.db, key, 11)
        except Exception:  # noqa: BLE001
            continue
        if key.endswith("_evo"):
            page = page_for(key, env.db, no_page)
            hf, df = EVO_FIELDS.get(key, ("hp_11", "dmg_11"))
        elif key.endswith("_hero"):
            page, hf, df = page_for(key, env.db, no_page), "hp_11", "dmg_11"
        else:
            page, hf, df = PREFIXED.get(key, (page_for(key, env.db, no_page), "hp_11", "dmg_11"))
        st = cr_web.card_stats(page) if page else {}
        if not st:
            why = "no wiki page of its own -- spawned body / second form" if key in no_page \
                else "no vardefines on %r" % page
            unmapped.append("%s (%s)" % (key, why))
            continue
        checked += 1
        if spec.kind == "spell":
            sdf, scf = SPELL_FIELDS.get(key, ("dmg_11", "crown_dmg_11"))
            whp, wdmg = None, num(st, sdf)
            ours_hp, ours_dmg = None, spec.spell_dmg
            wc, ours_c = num(st, scf), spec.spell_tower_dmg
            if _base_of(key) in SPAWNERS:
                wdmg = wc = None                 # the payload's numbers, not the spell's
            if _off(wc, ours_c):
                bad.append((key, "crown_dmg", ours_c, wc))
        else:
            whp, wdmg = num(st, hf), num(st, df)
            ours_hp, ours_dmg = spec.hp, spec.hit_dmg
            if _base_of(key) in SPAWNERS:
                whp = wdmg = None                # BOTH columns are the SPAWNED body's
        if _off(whp, ours_hp):
            bad.append((key, "hp", ours_hp, whp))
        if _off(wdmg, ours_dmg):
            bad.append((key, "damage", ours_dmg, wdmg))

    known = [b for b in bad if (b[0], b[1]) in EXPECTED]
    bad = [b for b in bad if (b[0], b[1]) not in EXPECTED]
    print("cross-checked %d cards against the live wiki" % checked)
    print("MISMATCHES: %d" % len(bad))
    for k, f, ours, theirs in sorted(bad):
        print("   %-20s %-10s ours %-9.1f wiki %-9.1f (%+.0f%%)"
              % (k, f, ours, theirs, 100 * (ours - theirs) / max(1.0, theirs)))
    if known:
        print("\nKNOWN DEVIATIONS (deliberate, see EXPECTED): %d" % len(known))
        for k, f, ours, theirs in sorted(known):
            print("   %-20s %-10s ours %-8.1f wiki %-8.1f -- %s"
                  % (k, f, ours, theirs, EXPECTED[(k, f)]))
    if unmapped:
        print("\nUNMAPPED (report, never guess): %d" % len(unmapped))
        for u in unmapped:
            print("   " + u)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
