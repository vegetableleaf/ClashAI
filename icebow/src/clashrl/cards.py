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
        for k, v in curated.items():
            base = merged.setdefault(k, {})
            for kk, vv in v.items():
                if vv is not None:
                    base[kk] = vv
        self.cards: Dict[str, dict] = merged

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
        return _SIGHT_TILES.get(_key(name), 5.5)

    def flags(self, name: str) -> List[str]:
        c = self.get(name)
        return list(c.get("flags") or []) if c else []

    def attacks_air(self, name: str) -> bool:
        c = self.get(name)
        return bool(c and "air" in (c.get("attacks") or []))

    def is_flying(self, name: str) -> bool:
        c = self.get(name)
        return bool(c and c.get("movement") == "air")

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
