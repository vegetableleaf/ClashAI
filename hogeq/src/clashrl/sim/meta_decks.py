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
                "giant", "royal_giant", "giant_skeleton", "elixir_golem"}


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


def _slots(d: dict, field: str, cards: List[str]) -> List[str]:
    """A deck entry's declared `evo:` / `support:` slot list, normalised and validated.

    Accepts a single key or a list (the importer writes `evo: [a, b]` and `support: x`). An `evo`
    key that is not IN the deck is dropped: it can only be a data error, and silently believing it
    would put the bot's evolution on a card it does not hold.
    """
    v = d.get(field)
    if v is None:
        return []
    keys = [str(x) for x in (v if isinstance(v, (list, tuple)) else [v]) if x]
    if field == "evo":
        keys = [k for k in keys if k in cards]
    return keys


def has_evolution(db, base: str) -> bool:
    """True when the KB can really build `<base>_evo` -- an imported `_evo` row or a curated block.

    The single definition of "this card has an evolution", shared by the loader, tools/evo_audit.py
    and the tests, so they cannot drift apart. The KB's 42 `_evo` rows match the 42 wiki-verified
    evolutions in research/sim_parity/ledger/r1a_evolutions.json exactly (zero additions, zero
    removals), which is what makes the derived candidate list checkable rather than a guess.
    """
    if db.get(base + "_evo"):
        return True
    return isinstance((db.get(base) or {}).get("evolution"), dict)


def evo_candidates(db, cards: List[str]) -> List[str]:
    """Every card in this deck that really HAS an evolution, in deck order.

    DERIVED DATA, not an inference about any player: no accessible source says which card a given
    player put in their Evolution slot, so the sim does not name one. `meta_decks.yaml` carries this
    list per deck for inspectability, but the KB is authoritative and the loader re-derives it when
    the entry does not carry one -- a regenerated pool or a built-in fallback must not silently
    field no evolutions at all.
    """
    return [c for c in cards if has_evolution(db, _base(c))]


def load_meta_decks(cfg, db) -> List[dict]:
    """Return [{name, weight, cards, style, evo, support, evo_candidates}], validated against the KB.

    `support` is the deck's tower troop, measured from top-ladder battlelogs
    (research/sim_parity/ledger/meta_evo_slots.json, R4) and reliable.

    `evo` is a DECLARED evolution slot and is empty for every shipped deck: the battlelog field it
    came from reports a player's OWNED evolution level, not the fielded slot, so all 233
    declarations were stripped. The hook stays for the day a real source appears.

    `evo_candidates` is what replaced it -- the deck's cards that really HAVE an evolution. Nothing
    names the slotted card, so ScriptedBot draws one of these uniformly per match instead of
    guessing a fixed one (which is what used to fabricate phantom evolutions). Falls back to the
    built-ins.

    Cached by the file's timestamp: parsing ~1000 decks out of a 140 KB YAML and classifying
    each one is pure startup cost that a vectorised run would otherwise pay once per env.
    Callers get their own dicts, so nobody can disturb another env by editing an entry.
    """
    path = Path(cfg.path(cfg.get("sim", "meta_decks_file", default="config/meta_decks.yaml")))
    try:
        # The boost settings are part of the identity of the cached result -- without them a
        # second config in the same process (a test, a sweep) silently gets the first one's
        # weighting back.
        key = (str(path), path.stat().st_mtime_ns if path.exists() else 0, id(db),
               repr(sorted((cfg.get("sim", "meta_deck_boost", default=None) or {}).items())),
               cfg.get("sim", "meta_deck_top_n", default=0),
               cfg.get("sim", "meta_deck_top_n_boost", default=1.0))
    except OSError:
        key = None
    if key is not None and key in _CACHE:
        return [{**d, "cards": list(d["cards"]), "evo": list(d["evo"]),
                 "support": list(d["support"]),
                 "evo_candidates": list(d["evo_candidates"])} for d in _CACHE[key]]

    out: List[dict] = []
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for d in (data.get("decks") or []):
            cards = list(d.get("cards") or [])
            if len(cards) == 8 and all(db.get(_base(c)) for c in cards):
                # `evo_candidates` is VALIDATED against the KB, never trusted blind: a stale entry
                # can then only under-report (fewer candidates), never resurrect a phantom. Absent
                # entirely -> derived, so a freshly imported pool is not silently evolution-less.
                cands = ([c for c in _slots(d, "evo_candidates", cards) if has_evolution(db, _base(c))]
                         if "evo_candidates" in d else evo_candidates(db, cards))
                out.append({"name": str(d.get("name", "deck")), "weight": float(d.get("weight", 1.0)),
                            "cards": cards, "style": classify_style(db, cards),
                            "evo": _slots(d, "evo", cards), "support": _slots(d, "support", cards),
                            "evo_candidates": cands})
    if not out:
        out = [{"name": n, "weight": 1.0, "cards": list(c), "style": classify_style(db, c),
                "evo": [], "support": [], "evo_candidates": evo_candidates(db, list(c))}
               for n, c in _BUILTIN]

    # LADDER SKEW. meta_decks.yaml is scraped popularity across the whole population, but the bot
    # plays at ~10k trophies, where Royal Hogs / Lava Hound / Balloon / Royal Giant show up far
    # more than their global share (user, 2026-08-17). Re-weighting here rather than editing a
    # thousand scraped entries keeps the file as DATA and the skew as a tunable opinion.
    #
    # MAX, never product: LavaLoon holds two boosted win conditions and multiplying would give it
    # the square of the intended weight -- the deck would flood the pool and the other three would
    # effectively get rarer, which is the opposite of the ask.
    boosts = cfg.get("sim", "meta_deck_boost", default=None) or {}
    top_n = int(cfg.get("sim", "meta_deck_top_n", default=0) or 0)
    top_mult = float(cfg.get("sim", "meta_deck_top_n_boost", default=1.0) or 1.0)
    # THE MOST-PLAYED DECKS, by the pool's own popularity weights. Ranked on the RAW weight before
    # any boost, so the card multipliers below cannot promote a deck into the top N and then
    # compound on it. Self-updating: re-run `decks-import` and the same rule tracks the new meta.
    top_ids = set()
    if top_n > 0 and top_mult != 1.0:
        ranked = sorted(range(len(out)), key=lambda i: -float(out[i].get("weight", 1.0)))
        top_ids = set(ranked[:top_n])
    if boosts or top_ids:
        for i, d in enumerate(out):
            m = max((float(v) for k, v in boosts.items()
                     if any(str(c).startswith(str(k)) for c in d["cards"])), default=1.0)
            if i in top_ids:
                m = max(m, top_mult)              # MAX again: a top-N deck holding a boosted win
            if m != 1.0:                          # condition is raised once, not multiplied twice
                d["weight"] = max(0.01, float(d.get("weight", 1.0))) * m
    if key is not None:
        _CACHE.clear()                        # only the current generation is useful
        _CACHE[key] = out
    return [{**d, "cards": list(d["cards"]), "evo": list(d["evo"]),
             "support": list(d["support"]),
             "evo_candidates": list(d["evo_candidates"])} for d in out]
