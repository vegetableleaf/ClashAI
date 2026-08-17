"""Import the GAME-FILE mechanics fields into config/card_mechanics.json.

  python tools/import_mechanics.py [--write]

WHAT THIS TAKES, AND WHAT IT DELIBERATELY DOES NOT
--------------------------------------------------
The game files behind RoyaleAPI/cr-api-data expose the per-unit constants the wiki never
prints: `mass`, `sight_range`, `collision_radius`, `load_time`, `deploy_delay`,
`ignore_pushback`. Those are what this importer takes.

It does NOT take hitpoints or damage. That dump was last updated 2023-10-18 and its balance
numbers have since drifted (Archers' damage is 107 there, 112 today), so importing stats would
quietly roll the knowledge base back three years. Stats keep coming from the wiki via
tools/stat_sweep.py; this file covers the STRUCTURAL constants, which balance patches leave
alone. Anything it cannot map is listed, never guessed -- roughly a dozen cards released after
the dump froze (Little Prince, Goblinstein, Boss Bandit, ...) simply keep their curated values.

MASS IS THE POINT
-----------------
engine.py used to say mass "is not published as a field, only named in prose" and approximated
it as collision_radius**3. It IS published, and the approximation was badly wrong: cubing the
radius makes a Giant 3.4x a Skeleton when the game says 18x, and it gives Knight, Musketeer,
Archer, Skeleton, Goblin and Bat IDENTICAL shoving weight because they share a 0.5 radius --
where the real masses are 6, 5, 3, 1, 2 and 1.

ONE FIELD IS A TRAP, AND IS SKIPPED ON PURPOSE
----------------------------------------------
`walking_speed_tweak_percentage` looks like the find of the night -- P.E.K.K.A +20%, Ice Wizard
-26%, Miner +20%. It is not a movement modifier. The wiki publishes Ice Wizard as "Medium (60)"
and P.E.K.K.A as "Slow (45)", i.e. the RAW speed field with no tweak applied; a real -26% would
make the Ice Wizard slower than "Slow" and players would have noticed a decade ago. It scales
the walk ANIMATION so the feet do not slide. Importing it as speed would have desynced every
one of those units from the game. Recorded here so nobody "discovers" it again.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from clashrl import cr_web            # noqa: E402
from clashrl.config import Config     # noqa: E402
from clashrl.sim.env import SimMatchEnv  # noqa: E402

SRC = ("https://raw.githubusercontent.com/RoyaleAPI/cr-api-data/master/docs/json/"
       "cards_stats.json")
TILE = 1000.0        # game distance units per arena tile
OUT = _ROOT / "config" / "card_mechanics.json"


def _tiles(v):
    return round(float(v) / TILE, 3) if v else None


def _secs(v):
    return round(float(v) / 1000.0, 3) if v else None


def main(argv) -> int:
    raw = cr_web.fetch_raw(SRC, max_age_s=7 * 86400)
    if not raw:
        print("could not fetch the game-file dump"); return 2
    d = json.loads(raw)
    chars = {r["name"]: r for r in d["characters"] if r.get("name")}
    rows = {}
    for tbl in ("troop", "building", "spell"):
        for r in d.get(tbl, []):
            if r.get("key"):
                rows[r["key"].replace("-", "_")] = r

    cfg = Config.load()
    env = SimMatchEnv(cfg, seed=0)
    wanted = set(env.deck_keys)
    for dk in env.meta_pool:
        wanted.update(dk if isinstance(dk, (list, tuple)) else dk.get("cards", []))
    wanted = sorted(k for k in wanted if not k.endswith("_evo"))

    out, missing, spells = {}, [], []
    for key in wanted:
        # Classify by OUR knowledge base, not by absence from the dump. The dump keys only 10 of
        # its 71 spell rows, so falling back to "not found = new card" reported Arrows, Fireball,
        # Rocket and The Log as 2024 releases. A spell has no body to import either way; saying so
        # honestly is the difference between a clean report and a misleading one.
        is_spell = (env.db.get(key) or {}).get("kind") == "spell"
        row = rows.get(key)
        if row is None:
            (spells if is_spell else missing).append(key)
            continue
        # A troop card points at a `characters` entry; a BUILDING carries its own mechanics on the
        # card row (there is no separate character for a Tesla or an X-Bow). Falling through to the
        # row itself is what makes buildings importable at all -- keying only off `characters` had
        # silently dropped every one of them, X-Bow and Tesla included.
        #
        # The CARD ROW WINS per field, because a building's `summon_character` can be a TRANSIENT
        # state rather than the thing that sits on the arena: Goblin Drill points at GoblinDrillDig,
        # the underground form, whose collision_radius is 1 game unit (0.001 tiles) precisely
        # because it cannot be body-blocked while burrowing. Taking the character wholesale gave
        # the drill a body of zero. Troop rows simply do not carry these fields, so they still fall
        # through to the character.
        chr_row = chars.get(row.get("summon_character") or "") or {}
        ch = {k: (row.get(k) or chr_row.get(k)) for k in set(chr_row) | set(row)}
        if not (ch.get("sight_range") or ch.get("collision_radius") or ch.get("mass")):
            spells.append(key)          # a real spell: no body, no mass, nothing to import
            continue
        m = {
            "character": chr_row.get("name") or row.get("name"),
            "mass": ch.get("mass") or None,
            "sight": _tiles(ch.get("sight_range")),
            "collision": _tiles(ch.get("collision_radius")),
            "load_time_s": _secs(ch.get("load_time")),
            "deploy_delay_s": _secs(ch.get("deploy_delay")),
            "knockback_immune": bool(ch.get("ignore_pushback")) or None,
            "lifetime_s": _secs(ch.get("life_time")),          # buildings: X-Bow 30 s, Tesla 40 s
            "turret_rotation": ch.get("turret_movement") or None,   # X-Bow/Mortar retarget swivel
            # cross-check only -- the sim keeps its wiki-sourced values for these
            "_speed_units": ch.get("speed"),
            "_range_tiles": _tiles(ch.get("range")),
            "_hit_speed_s": _secs(ch.get("hit_speed")),
            "_deploy_time_s": _secs(ch.get("deploy_time")),
        }
        out[key] = {k: v for k, v in m.items() if v is not None}

    payload = {
        "meta": {
            "source": SRC,
            "source_frozen": "2023-10-18",
            "imports": "mass, sight, collision, load_time, deploy_delay, knockback_immune",
            "excludes": "hitpoints/damage (stale in this dump -- see tools/stat_sweep.py), "
                        "walking_speed_tweak_percentage (walk ANIMATION, not movement)",
            "cards": len(out),
        },
        "cards": out,
    }
    print("mapped %d/%d cards" % (len(out), len(wanted)))
    if spells:
        print("no body to import (spells): %s" % ", ".join(spells))
    if missing:
        print("NOT IN THE DUMP -- keep curated values (released after 2023-10-18): %s"
              % ", ".join(missing))
    if "--write" in argv:
        OUT.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
        print("wrote %s" % OUT)
    else:
        print("(dry run -- pass --write to save)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
