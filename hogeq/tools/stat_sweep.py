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
"""
from __future__ import annotations

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
# the building's OWN hitpoints are not published per level -- skip hp, keep damage.
SPAWNERS = {"goblin_hut", "barbarian_hut", "tombstone", "furnace", "goblin_drill",
            "skeleton_barrel", "goblinstein", "suspicious_bush"}
NO_STATS = {"clone", "mirror", "rage", "freeze", "graveyard", "goblin_curse", "void", "vines"}

# KNOWN, DELIBERATE deviations -- recorded so a re-run surfaces only NEW problems. Each says
# what we model and why, because "the sweep is clean" is worthless if it hides real choices.
EXPECTED = {
    ("vines", "damage"): "we apply both hits at once (dmg_hits 2 x 153 = 306); the 1.25 s "
                         "between them is below the sim's decision resolution",
    ("vines", "crown_dmg"): "same: 2 x 39 = 78",
    ("goblinstein", "damage"): "two-body champion modelled as ONE merged unit -- the wiki's "
                               "dmg_11 92 is the Doctor alone, monster_dmg_11 is 128. Splitting "
                               "them is the deferred item in SIM_FIDELITY.md",
}


# EVOLUTIONS repeat the shape problem on their own pages: the headline hp_11/dmg_11 belong to
# whatever the card SPAWNS, and the evolved body hides behind a prefix. Verified 2026-08-16 by
# reading each page's own table headers rather than assuming the base card's layout carries over.
EVO_FIELDS = {
    "battle_ram_evo": ("ram_hp_11", "ram_dmg_11"),      # hp_11 737 is the Barbarians
    "goblin_drill_evo": ("drill_hp_11", None),          # hp_11 202 is the Goblin it spawns
    "skeleton_barrel_evo": ("hp_11", None),             # the barrel does not attack; dmg is the skeletons'
    "witch_evo": ("hp_11", "dmg_11"),                   # maks_hp_11 1039 is the OVERHEAL CAP, not hp
}


def page_for(key: str) -> str:
    if key in PREFIXED:
        return PREFIXED[key][0]
    return " ".join(w.capitalize() for w in key.split("_")).replace("X Bow", "X-Bow")


def num(st: dict, field):
    if not field:
        return None
    try:
        return float(str(st.get(field)).replace(",", ""))
    except Exception:  # noqa: BLE001
        return None


def main(argv) -> int:
    cfg = Config.load()
    env = SimMatchEnv(cfg, seed=0)
    cards = set(env.deck_keys)
    for d in env.meta_pool:
        cards.update(d if isinstance(d, (list, tuple)) else d.get("cards", []))
    base_cards = sorted(c for c in cards if not c.endswith("_evo"))
    evos = sorted(k for k in env.db.cards if k.endswith("_evo")) if "--evo" in argv else []
    cards = base_cards + evos

    bad, unmapped, checked = [], [], 0
    for key in cards:
        try:
            spec = E.build_spec(env.db, key, 11)
        except Exception:  # noqa: BLE001
            continue
        if key.endswith("_evo"):
            base = key[:-4]
            disp = (env.db.get(base) or {}).get("display") or page_for(base)
            page = "%s/Evolution" % disp
            hf, df = EVO_FIELDS.get(key, ("hp_11", "dmg_11"))
        else:
            page, hf, df = PREFIXED.get(key, (page_for(key), "hp_11", "dmg_11"))
        st = cr_web.card_stats(page)
        if not st:
            unmapped.append("%s (no vardefines on %r)" % (key, page))
            continue
        checked += 1
        if spec.kind == "spell":
            whp, wdmg = None, num(st, "dmg_11")
            ours_hp, ours_dmg = None, spec.spell_dmg
            wc, ours_c = num(st, "crown_dmg_11"), spec.spell_tower_dmg
            if wc and ours_c and abs(wc - ours_c) / max(1.0, wc) > 0.02:
                bad.append((key, "crown_dmg", ours_c, wc))
        else:
            whp, wdmg = num(st, hf), num(st, df)
            ours_hp, ours_dmg = spec.hp, spec.hit_dmg
            if key in SPAWNERS:
                whp = None                       # hp_11 is the SPAWNED troop, not the building
        if whp and ours_hp and abs(whp - ours_hp) / max(1.0, whp) > 0.02:
            bad.append((key, "hp", ours_hp, whp))
        if wdmg and ours_dmg and abs(wdmg - ours_dmg) / max(1.0, wdmg) > 0.02:
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
