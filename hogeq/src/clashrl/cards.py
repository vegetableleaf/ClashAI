"""Card knowledge base loader.

Reads `config/cards.yaml` and exposes lookups for the policy/reward logic:
elixir cost, category, targeting, and behaviour flags per card, plus the
configured deck. Combat stats (hitpoints/damage/hit_speed) are optional and may
be null until imported from a stats source -- `missing_stats()` lists what still
needs importing so the KB can be refreshed after balance updates.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import yaml


def _key(name: str) -> str:
    return (str(name).strip().lower()
            .replace(" ", "_").replace("-", "_").replace(".", "").replace("'", ""))


def _table(tbl: Dict[str, float], name: str):
    """Look a card up in a geometry table, falling back to its BASE card for an Evolution.

    An Evolution shares its base card's body and reach -- only the stats and special effect differ --
    but the tables are keyed on base names, so `minion_horde_evo` / `princess_evo` / `goblin_drill_evo`
    missed entirely and dropped to the 'melee' 1.2-tile default. Evolved Princess is a 9-tile sniper;
    resolving her to 1.2 would have had her walk into the arena to shoot.
    """
    k = _key(name)
    if k in tbl:
        return tbl[k]
    if k.endswith("_evo") and k[:-4] in tbl:
        return tbl[k[:-4]]
    return None


# ---------------------------------------------------------------------------------------------
# PROVENANCE WARNING for the three tables below. They were baked from RoyaleAPI's cr-api-data,
# which is ABANDONED: its last commit is 2023-10-18, so it predates every balance change and card
# released since, and knows nothing of e.g. boss_bandit / spirit_empress / goblinstein / rune_giant.
#   * ATTACK RANGE now has a LIVE source -- the Fandom wiki's unit-attributes table, imported into
#     cards_stats.json as `range_tiles` -- and `attack_range_tiles` prefers it, so _RANGE_TILES is
#     now only a fallback for cards the wiki parse misses.
#   * COLLISION RADIUS and SIGHT RANGE have NO live source: Supercell does not publish either and
#     the wiki does not tabulate them. They stay here because both are PHYSICAL properties that are
#     rebalanced far less often than damage/HP -- but treat them as approximate, and as UNKNOWN for
#     any card released after 2023-10.
# ---------------------------------------------------------------------------------------------
# AGGRO/SIGHT range in TILES per base card, sourced from the game data (RoyaleAPI cr-api-data
# `characters[].sight_range`, 1000 game units = 1 tile; verified 2026-08-03). Only the cards that
# DIFFER from the 5.5-tile baseline are listed -- everything else (79 of 125 characters) is 5.5.
# Role-driven, NOT attack-range-driven: kite-able heavies see SHORT, building-seekers see LONG.
_SIGHT_TILES: Dict[str, float] = {
    # deliberately short-sighted (kiting works)
    "pekka": 5.0, "giant_skeleton": 5.0,
    # slightly wide
    "musketeer": 6.0, "three_musketeers": 6.0, "elite_barbarians": 6.0,
    # building-seekers / split units -- wide (must find buildings/regroup early)
    "golem": 7.0, "golemite": 7.0, "ice_golem": 7.0,
    "giant": 7.5, "goblin_giant": 7.5, "royal_giant": 7.5, "electro_giant": 7.5,
    "elixir_golem": 7.5, "elixir_golemite": 7.5, "elixir_blob": 7.5, "dart_goblin": 7.5,
    "balloon": 7.7, "skeleton_barrel": 7.7,
    # extreme outliers
    "firecracker": 8.5,
    "hog_rider": 9.5, "royal_hogs": 9.5, "princess": 9.5,
}

# COLLISION (body) RADIUS in TILES per base card -- cr-api-data `collision_radius`, 1000 units =
# 1 tile (fetched 2026-08-08). This is the unit's physical SIZE: it drives body-blocking, how many
# bodies fit around a tank, and how far a melee attacker stands off. EVERY resolved card is listed,
# including the 0.5-tile baseline ones -- listing only the outliers made the role-flag fallback
# override real data (Skeletons measure 0.5 but have `swarm`, so the fallback shrank them to 0.4).
_COLLISION_TILES: Dict[str, float] = {
    "archer_queen": 0.5, "archers": 0.5, "baby_dragon": 0.5, "balloon": 0.5, "barbarians": 0.5,
    "bats": 0.5, "battle_healer": 0.5, "battle_ram": 0.75, "bomber": 0.5, "bowler": 0.75,
    "dark_prince": 0.6, "dart_goblin": 0.5, "electro_dragon": 0.6, "electro_giant": 0.75,
    "electro_spirit": 0.4, "electro_wizard": 0.5, "fire_spirit": 0.4, "firecracker": 0.5,
    "fisherman": 0.5, "giant": 0.75, "giant_skeleton": 1.0, "goblin_barrel": 0.5,
    "goblin_cage": 0.5, "goblin_gang": 0.5, "goblin_giant": 0.75, "goblins": 0.5,
    "golden_knight": 0.8, "golem": 0.75, "heal_spirit": 0.4, "hog_rider": 0.6, "hunter": 0.6,
    "ice_spirit": 0.4, "ice_wizard": 0.5, "inferno_dragon": 0.5, "knight": 0.5,
    "lava_hound": 0.75, "mega_knight": 0.75, "mega_minion": 0.6, "mighty_miner": 0.5,
    "miner": 0.5, "mini_pekka": 0.45, "minion_horde": 0.5, "minions": 0.5, "monk": 0.5,
    "musketeer": 0.5, "pekka": 0.75, "phoenix": 0.5, "prince": 0.6, "princess": 0.5,
    "ram_rider": 0.6, "rascals": 0.75, "royal_ghost": 0.6, "royal_giant": 0.75,
    "royal_hogs": 0.6, "skeleton_army": 0.5, "skeleton_barrel": 0.5, "skeleton_dragons": 0.9,
    "skeleton_king": 1.0, "skeletons": 0.5, "spear_goblins": 0.5, "three_musketeers": 0.5,
    "valkyrie": 0.5, "wall_breakers": 0.4, "witch": 0.5, "wizard": 0.5,
}

# ATTACK RANGE in TILES per base card -- cr-api-data `range`. Measured from the ATTACKER'S CENTRE
# to the TARGET'S HITBOX EDGE (so a big target is engaged from further out). Melee is NOT one
# value: it spreads 0.5 (Skeletons) / 0.8 (Hog, Mini P.E.K.K.A) / 1.2 (Knight, P.E.K.K.A, most)
# / 1.6 (Prince, Mega Minion), which is exactly why some melee units trade differently.
_RANGE_TILES: Dict[str, float] = {
    "archer_queen": 5.0, "archers": 5.0, "baby_dragon": 3.5, "balloon": 0.1, "barbarians": 0.7,
    "bats": 1.2, "battle_healer": 1.6, "battle_ram": 0.5, "bomber": 4.5, "bowler": 4.0,
    "dark_prince": 1.2, "dart_goblin": 6.5, "electro_dragon": 3.5, "electro_giant": 1.2,
    "electro_spirit": 2.5, "electro_wizard": 5.0, "firecracker": 6.0,
    "fisherman": 1.2, "giant": 1.2, "giant_skeleton": 0.8, "goblin_barrel": 0.5,
    "goblin_cage": 0.8, "goblin_gang": 0.5, "goblin_giant": 1.2, "goblins": 0.5,
    "golden_knight": 1.2, "golem": 0.75, "heal_spirit": 2.5, "hog_rider": 0.8, "hunter": 4.0,
    "ice_spirit": 2.5, "ice_wizard": 5.5, "inferno_dragon": 3.5, "knight": 1.2,
    "lava_hound": 3.5, "mega_knight": 1.2, "mega_minion": 1.6, "mighty_miner": 1.6,
    "miner": 1.2, "mini_pekka": 0.8, "monk": 1.2,
    "musketeer": 6.0, "pekka": 1.2, "phoenix": 1.6, "prince": 1.6, "princess": 9.0,
    "rascals": 0.8, "royal_ghost": 1.2, "royal_giant": 5.0,
    "skeleton_army": 0.5, "skeleton_barrel": 0.35, "skeleton_dragons": 3.5,
    "skeleton_king": 1.2, "skeletons": 0.5, "three_musketeers": 6.0,
    "valkyrie": 1.2, "wall_breakers": 0.5, "witch": 5.5, "wizard": 5.5,
    # DEFENSIVE BUILDINGS normally get `range_tiles` from the wiki import, so they are absent here
    # -- but a building the import MISSES falls through to _RANGE_BUCKET, whose default is "melee"
    # (1.2 tiles). That is silent and severe: Inferno Tower parsed no attribute row at all, so it
    # was resolving to 1.2 and was OUT-RANGED BY EVERYTHING, including a 5.5-tile Ice Wizard.
    # Wiki (May 2016 "range bug" fix): Inferno Tower range is 6 tiles.
    "inferno_tower": 6.0,
}
# REMOVED from the table above because the LIVE wiki import supersedes them and they had drifted:
#   fire_spirit 2.0 -> 2.5, minions/minion_horde 1.6 -> 2.5, ram_rider 5.5 -> 0.8 (it is a MELEE
#   rider; 5.5 was badly wrong), royal_hogs 0.75 -> 0.7, spear_goblins 5.5 -> 5.0.
# The import already won at runtime, so behaviour does not change -- but leaving stale numbers here
# means they silently take over for any card the import ever misses. Anything the wiki publishes
# belongs in cards_stats.json, not in this table.

# Fallback attack range (tiles) per CATEGORICAL bucket, for cards missing from _RANGE_TILES.
_RANGE_BUCKET: Dict[str, float] = {"melee": 1.2, "short": 3.5, "long": 5.5}


class CardDB:
    def __init__(self, cfg=None, path=None):
        if path is None:
            if cfg is not None:
                path = cfg.path(cfg.get("cards", "file", default="config/cards.yaml"))
            else:
                path = Path(__file__).resolve().parents[2] / "config" / "cards.yaml"
        self.path = Path(path)
        data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        self.meta: dict = data.get("meta", {})
        self._deck: dict = data.get("deck", {})
        curated: Dict[str, dict] = data.get("cards", {})

        # Merge imported stats (base layer) with curated entries. Curated fields
        # win; null curated fields never clobber a real imported value.
        merged: Dict[str, dict] = {}
        self.stats_meta: dict = {}
        gen_path = self.path.parent / "cards_stats.json"
        if gen_path.exists():
            gen = json.loads(gen_path.read_text(encoding="utf-8"))
            self.stats_meta = gen.get("meta", {})
            for k, v in (gen.get("cards") or {}).items():
                merged[k] = dict(v)
        # GAME-FILE MECHANICS sit between the two: more precise than anything the wiki prints
        # (it never publishes mass, sight range, collision radius or weapon load time), but still
        # below hand curation, because this dump froze in 2023 and a curated value is usually a
        # deliberate correction to it. Only the structural constants are imported -- see
        # tools/import_mechanics.py for why hitpoints/damage are pointedly not.
        mech_path = self.path.parent / "card_mechanics.json"
        self.mechanics_meta: dict = {}
        if mech_path.exists():
            mech = json.loads(mech_path.read_text(encoding="utf-8"))
            self.mechanics_meta = mech.get("meta", {})
            for k, v in (mech.get("cards") or {}).items():
                base = merged.setdefault(k, {})
                for kk, vv in v.items():
                    if vv is not None and kk != "character" and not kk.startswith("_"):
                        base[kk] = vv
        for k, v in curated.items():
            base = merged.setdefault(k, {})
            for kk, vv in v.items():
                if vv is not None:
                    base[kk] = vv
        self.cards: Dict[str, dict] = merged

    def mass(self, name: str) -> Optional[float]:
        """How heavy a body is for SHOVING, from the game files (Skeleton 1 ... Golem 20).

        Returns None for cards the 2023 dump predates, so callers can fall back rather than
        treat a missing mass as weightless.
        """
        c = self.get(name) or {}
        if c.get("mass") is not None:
            return float(c["mass"])
        b = self._base_card(name)                     # an Evolution shoves like its base card
        return float(b["mass"]) if b.get("mass") is not None else None

    # -- lookups -------------------------------------------------------
    def get(self, name: Optional[str]) -> Optional[dict]:
        return self.cards.get(_key(name)) if name else None

    def elixir(self, name: str) -> Optional[int]:
        c = self.get(name)
        return c.get("elixir") if c else None

    def kind(self, name: str) -> Optional[str]:
        c = self.get(name)
        return c.get("kind") if c else None

    def attack_range(self, name: str) -> Optional[str]:
        """Categorical attack reach: 'melee' | 'short' | 'long' | None."""
        c = self.get(name)
        return c.get("range") if c else None

    def _base_card(self, name: str) -> dict:
        """An Evolution's BASE card record, or {} when `name` is not an Evolution.

        An Evolution shares the base card's body and reach, so it must inherit the base's LIVE
        imported geometry BEFORE any hardcoded fallback -- `minion_horde_evo` otherwise picked up the
        2023 table's 1.6 tiles while the base card had been re-imported at the wiki's current 2.5.
        """
        k = _key(name)
        return (self.get(k[:-4]) or {}) if k.endswith("_evo") else {}

    def sight_range_tiles(self, name: str) -> float:
        """AGGRO/SIGHT radius in TILES -- how far this troop notices enemy units before defaulting to a
        march at the nearest tower (why opposite-lane pushes ignore each other: lanes are ~9 tiles apart).
        From the game data (cr-api-data characters.sight_range, 1000 units = 1 tile): NOT correlated with
        attack range -- role-driven. Most troops 5.5; PEKKA/Giant Skeleton deliberately SHORT (5.0, why
        kiting them works); building-targeting tanks LONG (7.0-7.7, they must find buildings early);
        Hog/Royal Hogs/Princess/Firecracker extreme (8.5-9.5). A curated `sight` (tiles) in cards.yaml
        overrides; unknown cards fall back to the 5.5 baseline."""
        c = self.get(name)
        if c and c.get("sight") is not None:
            return float(c["sight"])
        b = self._base_card(name)
        if b.get("sight") is not None:
            return float(b["sight"])
        v = _table(_SIGHT_TILES, name)
        return v if v is not None else 5.5

    def flags(self, name: str) -> List[str]:
        c = self.get(name)
        return list(c.get("flags") or []) if c else []

    def collision_radius_tiles(self, name: str) -> float:
        """Body radius in TILES (cr-api-data `collision_radius`). Drives body-blocking, how many
        units can surround a target, and the stand-off distance of a melee attacker. A curated
        `collision` (tiles) in cards.yaml wins; unknown cards fall back to a size guess from the
        KB role flags (tank 0.75 / swarm 0.4 / 0.5 baseline) rather than one flat value."""
        c = self.get(name) or {}
        if c.get("collision") is not None:
            return float(c["collision"])
        b = self._base_card(name)
        if b.get("collision") is not None:
            return float(b["collision"])
        v = _table(_COLLISION_TILES, name)
        if v is not None:
            return v
        fl = set(c.get("flags") or []) or set(b.get("flags") or [])
        if "tank" in fl:
            return 0.75
        if "swarm" in fl or int(c.get("count") or 1) >= 3:
            return 0.4
        return 0.5

    def attack_range_tiles(self, name: str) -> float:
        """Attack range in TILES, measured ATTACKER CENTRE -> TARGET HITBOX EDGE (cr-api-data
        `range`). Melee spans 0.5-1.6 tiles, so the old single 'melee' constant mis-modelled how
        far apart melee units actually trade. A curated `range_tiles` in cards.yaml wins; unknown
        cards fall back to their categorical bucket (`range: melee|short|long`)."""
        c = self.get(name) or {}
        if c.get("range_tiles") is not None:
            return float(c["range_tiles"])
        b = self._base_card(name)
        if b.get("range_tiles") is not None:
            return float(b["range_tiles"])       # Evolution inherits the base card's LIVE range
        v = _table(_RANGE_TILES, name)
        if v is not None:
            return v
        return _RANGE_BUCKET.get(c.get("range") or b.get("range") or "melee", 1.2)

    def evo_cycles(self, name: str) -> int:
        """How many times the BASE card must be PLAYED before its Evolution is available.

        cycles:2 => base, base, EVO (every 3rd play is evolved). 0 when the card has no
        evolution, so callers can treat 0 as 'never evolves'.

        A curated `evolution.cycles` still wins, but the wiki publishes this as a `Cycles` column on
        the Evolution page and the importer now reads it for 39 cards. Four (musketeer, skeletons,
        archers, valkyrie) had been sitting on an UNVERIFIED hand-guess of 1 when the real value is 2
        -- an evolution arriving every 2nd play instead of every 3rd is a large cycle-economy error.
        """
        c = self.get(name) or {}
        ev = c.get("evolution") or {}
        if not isinstance(ev, dict) or not ev.get("available"):
            return 0
        if ev.get("cycles"):
            return int(ev["cycles"])
        evo = self.get(f"{_key(name)}_evo") or {}     # the wiki's Cycles column lives on the EVO page
        return int(evo.get("evo_cycles") or 0)

    def shield_hp(self, name: str) -> float:
        """Shield pool absorbed before hitpoints (Dark Prince 240, Guards 256, Royal Recruits 240).

        Published per level by the wiki as `shield_11`. The engine previously GUESSED this as a flat
        fraction of the card's own hitpoints, which is wrong in both directions: Guards are 3 bodies
        of ~130hp carrying a 256 shield EACH (a bigger pool than their health), while a Dark Prince's
        240 is small next to his. Returns 0.0 for cards with no shield.
        """
        c = self.get(name) or {}
        v = c.get("shield_hp")
        if v is None:
            v = (self._base_card(name) or {}).get("shield_hp")
        return float(v) if v is not None else 0.0

    def attacks_air(self, name: str) -> bool:
        c = self.get(name)
        return bool(c and "air" in (c.get("attacks") or []))

    def is_flying(self, name: str) -> bool:
        c = self.get(name)
        return bool(c and c.get("movement") == "air")

    def river_jump(self, name: str) -> bool:
        """Crosses the river WITHOUT using a bridge (Hog/Royal Hogs/Ram Rider/Prince/Dark Prince).

        Imported from the card's own wiki prose ("He is able to jump over the river"), not a
        hand-written list, so a future card with the ability picks it up on the next import."""
        c = self.get(name)
        return bool(c and c.get("river_jump"))

    def is_kamikaze(self, name: str) -> bool:
        """Leaps at its target, lands ONE hit, and dies on impact (the four spirits)."""
        c = self.get(name)
        return bool(c and c.get("kamikaze"))

    def speed_tiles(self, name: str) -> Optional[float]:
        """Move speed in TILES/SECOND, from the wiki's speed rating (60 units = 1 tile/s)."""
        c = self.get(name)
        v = c.get("speed_tiles") if c else None
        return float(v) if v is not None else None

    def spawner(self, name: str) -> Optional[dict]:
        """This card's troop-production, or None when it summons nothing.

        Returns ``{unit, count, on_death, interval, delay, range}`` -- ``unit`` is a KB key to
        build the summoned troop from, ``interval``/``delay`` are seconds and ``range`` is in
        TILES. Timings come from the wiki attribute table (they move with balance changes); only
        the ``unit`` identity is curated, since the table never names the card being summoned.

        ``range`` is the PROXIMITY GATE: when set, the spawner only ticks while an enemy is inside
        it. Goblin Hut works this way (Spawn Range 6) -- it stopped spawning automatically in the
        May 2025 update. When ``range`` is None the spawner produces unconditionally.
        """
        c = self.get(name) or {}
        sp = c.get("spawns") or {}
        unit = sp.get("unit")
        if not unit:
            return None
        return {
            "unit": str(unit),
            "count": int(sp.get("count") or 1),
            "on_death": int(sp.get("on_death") or 0),
            # Timings come from the imported attribute table, but a curated `interval`/`delay` wins:
            # the wiki contradicts ITSELF on some cards (Tombstone's table says 4s while its prose
            # says 3.5s AND its Common modifier says "doubled, for a total of 1.75 seconds", which
            # only works from 3.5). An override is for a source that is provably wrong, not for
            # convenience -- every one carries its cross-check in cards.yaml.
            "interval": float(sp.get("interval") or c.get("spawn_interval_s") or 0.0),
            "delay": float(sp.get("delay") or c.get("spawn_delay_s") or 0.0),
            "range": float(c["spawn_range_tiles"]) if c.get("spawn_range_tiles") else None,
        }

    def projectile(self, name: str) -> Optional[dict]:
        """This card's shot, or None when it hits instantly / has no attack.

        speed is TILES/SECOND, radius is the blast footprint in tiles (0 = single target).
        `pierce` marks a shot that keeps travelling past its target (Firecracker's rocket,
        Magic Archer, Executioner's axe, Bowler's boulder) -- those carry a longer
        `projectile_range` than the unit's own attack range.
        """
        c = self.get(name)
        if not c:
            return None
        spd = c.get("projectile_speed")
        if not spd:
            return None
        rng = c.get("projectile_range")
        return {
            "speed": float(spd) / 60.0,
            "radius": float(c.get("projectile_radius") or c.get("splash_radius") or 0.0),
            "range": float(rng) if rng else None,
            # HALF the published Projectile Width -- the wiki quotes width (Executioner 2, Bowler
            # 3.6) but reasons in radius ("the axe itself has a 1 tile radius, so his effective
            # reach is 8.5" = 7.5 throw + 1). Kept apart from `radius`, which is the BLAST footprint
            # of a shot that explodes; these shots do not explode, they sweep a lane.
            "width": float(c.get("projectile_width_tiles") or 0.0) / 2.0,
            "pierce": bool(rng and rng > (c.get("range_tiles") or 0)),
        }

    def is_spell(self, name: str) -> bool:
        return self.kind(name) == "spell"

    def is_win_condition(self, name: str) -> bool:
        c = self.get(name)
        return bool(c and c.get("win_condition"))

    def has_splash(self, name: str) -> bool:
        c = self.get(name)
        return bool(c and c.get("splash"))

    def crown_tower_damage(self, name: str) -> Optional[int]:
        """A spell's reduced damage to crown towers, if the source defines one (else None)."""
        c = self.get(name)
        return c.get("crown_tower_damage") if c else None

    def tower_damage(self, name: str) -> Optional[int]:
        """Damage dealt to a crown tower: the reduced crown-tower value if the card has
        one (most damage spells), else its full damage -- troops, and spells with no
        separate reduced value (e.g. Goblin Barrel/Graveyard, whose troops hit full),
        deal full tower damage."""
        c = self.get(name)
        if not c:
            return None
        ct = c.get("crown_tower_damage")
        return ct if ct is not None else c.get("damage")

    # -- deck ----------------------------------------------------------
    def deck(self) -> List[dict]:
        """Resolved deck: each card's data merged with its `evolved` flag.

        When a slot is `evolved`, the imported Evolution stats (`<key>_evo`, e.g.
        the tougher Evo Royal Giant) overlay the base card's numbers.
        """
        out: List[dict] = []
        for entry in self._deck.get("cards", []):
            key = entry.get("card")
            base = self.get(key)
            if base is None:
                continue
            merged = dict(base)
            merged["key"] = _key(key)
            merged["evolved"] = bool(entry.get("evolved"))
            if merged["evolved"]:
                evo = self.cards.get(_key(key) + "_evo")
                if evo:
                    for kk, vv in evo.items():
                        if vv is not None and kk not in ("display", "base", "evolution", "champion"):
                            merged[kk] = vv
            lvl = entry.get("level")
            if lvl:                                   # KB stats are level 11; scale ~10%/level
                merged["level"] = int(lvl)
                mult = 1.1 ** (int(lvl) - 11)
                for kk in ("hitpoints", "damage", "crown_tower_damage", "dps", "damage_per_second"):
                    if merged.get(kk) is not None:
                        merged[kk] = int(round(merged[kk] * mult))
            out.append(merged)
        return out

    def evolution(self, name: str) -> Optional[dict]:
        """Imported Evolution stats for a card, if any (keyed `<base>_evo`)."""
        return self.cards.get(_key(name) + "_evo")

    def level(self, name: str) -> Optional[int]:
        """Configured deck level for a card (from cards.yaml `deck`), or None."""
        k = _key(name)
        for e in self._deck.get("cards", []):
            if _key(e.get("card")) == k:
                return e.get("level")
        return None

    def champions(self) -> List[str]:
        """Keys of champion (hero) cards in the KB."""
        return [k for k, c in self.cards.items() if c.get("champion")]

    def deck_names(self) -> List[str]:
        return [_key(e.get("card")) for e in self._deck.get("cards", [])]

    def deck_identities(self) -> List[str]:
        """Ordered hand-card identities for the policy's action space.

        Each deck card is one identity; an **evolved** slot adds a second, separate
        `<key>_evo` identity, because the evolved card has a different mechanic and
        is played differently from its normal version (both appear in hand at
        different times, since evolutions are cycle-gated). Champions are already
        their own deck cards, so they are naturally separate identities.
        """
        out: List[str] = []
        for entry in self._deck.get("cards", []):
            k = _key(entry.get("card"))
            out.append(k)
            if entry.get("evolved"):
                out.append(k + "_evo")
        return out

    def deck_levels(self) -> List[int]:
        """Per-identity card levels, PARALLEL to deck_identities() (an evolved slot repeats the level)."""
        out: List[int] = []
        for entry in self._deck.get("cards", []):
            lvl = int(entry.get("level", 11))
            out.append(lvl)
            if entry.get("evolved"):
                out.append(lvl)
        return out

    def deck_slots(self) -> List[dict]:
        """The deck's PHYSICAL cards -- one entry per slot in the 8-card cycle.

        Distinct from :meth:`deck_identities`, which splits an evolved slot into two policy
        identities. In a real match the Evolution does NOT occupy its own cycle position: it IS
        the base card, shown evolved once the slot has been played `evo_cycles` times. Modelling
        it as a separate cycle entry let base and Evo sit in hand simultaneously and let the Evo
        be replayed every cycle, neither of which can happen in game.

        Each slot: {base, evo (or None), cycles, level}.
        """
        out: List[dict] = []
        for entry in self._deck.get("cards", []):
            k = _key(entry.get("card"))
            evolved = bool(entry.get("evolved"))
            out.append({
                "base": k,
                "evo": (k + "_evo") if evolved else None,
                "cycles": self.evo_cycles(k) if evolved else 0,
                "level": int(entry.get("level", 11)),
            })
        return out

    def deck_name(self) -> str:
        return self._deck.get("name", "deck")

    def deck_avg_elixir(self) -> Optional[float]:
        costs = [self.elixir(k) for k in self.deck_names()]
        costs = [c for c in costs if c is not None]
        return round(sum(costs) / len(costs), 2) if costs else None

    # -- maintenance ---------------------------------------------------
    def missing_stats(self) -> List[str]:
        """Cards whose level-scaled combat stats still need importing."""
        return [k for k, c in self.cards.items() if c.get("hitpoints") is None]

    def unverified(self) -> List[str]:
        """Cards whose stable fields still need a source check."""
        return [k for k, c in self.cards.items() if not c.get("verified", False)]


def load(cfg=None, path=None) -> CardDB:
    return CardDB(cfg, path)


_SHARED: Dict[str, "CardDB"] = {}


def shared(cfg=None, path=None) -> CardDB:
    """A CardDB reused across callers, keyed by the files it was built from.

    Building one parses cards.yaml plus cards_stats.json, which is wasted work when a
    vectorised run creates dozens of environments that all read the same knowledge base
    (64 envs spent ~27 s on it). The instance is treated as READ-ONLY -- nothing in the
    codebase writes to it -- and the cache drops as soon as either file's timestamp moves,
    so an edited deck still takes effect on the next run.
    """
    if path is None and cfg is not None:
        path = cfg.path(cfg.get("cards", "file", default="config/cards.yaml"))
    p = Path(path) if path else Path(__file__).resolve().parents[2] / "config" / "cards.yaml"
    stats = p.parent / "cards_stats.json"
    try:
        key = f"{p}|{p.stat().st_mtime_ns}|{stats.stat().st_mtime_ns if stats.exists() else 0}"
    except OSError:
        return CardDB(cfg, path)
    db = _SHARED.get(key)
    if db is None:
        _SHARED.clear()                       # only ever one generation is useful
        db = _SHARED[key] = CardDB(cfg, p)
    return db
