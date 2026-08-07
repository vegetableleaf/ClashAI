"""Meta opponent-deck pool for the sim: load current top decks (config/meta_decks.yaml, populated by
`run.py decks-import` from the official CR API, or the committed curated fallback) and classify each
deck's play STYLE so a scripted bot can pilot it. See sim/opponents.py + icebow/DECK_SWITCH.md.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import yaml

# Known-good fallback archetypes (used if the yaml is missing / all entries invalid).
_BUILTIN = [
    ("hog_cycle", ["hog_rider", "musketeer", "knight", "skeletons", "ice_spirit", "cannon", "fireball", "zap"]),
    ("beatdown", ["giant", "musketeer", "mini_pekka", "archers", "minions", "fireball", "arrows", "knight"]),
    ("control", ["valkyrie", "musketeer", "tesla", "skeletons", "ice_spirit", "fireball", "archers", "knight"]),
    ("siege", ["x_bow", "tesla", "archers", "skeletons", "ice_spirit", "fireball", "knight", "rocket"]),
]

_HEAVY_TANKS = {"golem", "lava_hound", "electro_giant", "goblin_giant", "pekka", "mega_knight",
                "giant", "royal_giant", "giant_skeleton", "elixir_golem", "super_lava_hound"}


def _base(k: str) -> str:
    return k[:-4] if k.endswith("_evo") else k


def classify_style(db, cards: List[str]) -> str:
    """Infer a coarse play style from a deck so the scripted bot picks sensible deploy heuristics."""
    bases = [_base(c) for c in cards]
    flags = set()
    elix = []
    for b in bases:
        flags |= set(db.flags(b))
        e = db.elixir(b)
        if e is not None:
            elix.append(e)
    avg = sum(elix) / len(elix) if elix else 4.0
    if "siege" in flags:
        return "siege"
    if any(b in _HEAVY_TANKS for b in bases) and avg >= 3.7:
        return "beatdown"
    if avg <= 3.3:
        return "cycle"
    return "control"


_CACHE: dict = {}


def load_meta_decks(cfg, db) -> List[dict]:
    """Return [{name, weight, cards, style}], validated against the KB. Falls back to the built-ins.

    Cached by the file's timestamp: parsing ~1000 decks out of a 140 KB YAML and classifying
    each one is pure startup cost that a vectorised run would otherwise pay once per env.
    Callers get their own dicts, so nobody can disturb another env by editing an entry.
    """
    path = Path(cfg.path(cfg.get("sim", "meta_decks_file", default="config/meta_decks.yaml")))
    try:
        key = (str(path), path.stat().st_mtime_ns if path.exists() else 0, id(db))
    except OSError:
        key = None
    if key is not None and key in _CACHE:
        return [{**d, "cards": list(d["cards"])} for d in _CACHE[key]]

    out: List[dict] = []
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for d in (data.get("decks") or []):
            cards = list(d.get("cards") or [])
            if len(cards) == 8 and all(db.get(_base(c)) for c in cards):
                out.append({"name": str(d.get("name", "deck")), "weight": float(d.get("weight", 1.0)),
                            "cards": cards, "style": classify_style(db, cards)})
    if not out:
        out = [{"name": n, "weight": 1.0, "cards": list(c), "style": classify_style(db, c)}
               for n, c in _BUILTIN]
    if key is not None:
        _CACHE.clear()                        # only the current generation is useful
        _CACHE[key] = out
    return [{**d, "cards": list(d["cards"])} for d in out]
