#!/usr/bin/env python
"""L62 -- loader for the ghost pool (icebow/data/ghost_pool/pool.jsonl).

Schema: scratchpad/gauntlet/L62/ghost_pool.md §0.  Pure stdlib, no engine import, safe anywhere.

    from ghost_pool import load_pool, sample
    pool = load_pool()                       # default path
    rec  = sample(pool, random.Random(0), rating_range=(3000, None))
"""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "icebow" / "data" / "ghost_pool" / "pool.jsonl"


def load_pool(path=None):
    """Read pool.jsonl -> list of battle dicts (schema in ghost_pool.md §0).

    Blank lines are skipped; a truncated final line (the file may be rewritten while a trainer reads
    it) raises, it is not silently dropped -- a short pool is worse than a loud failure.
    """
    p = Path(path) if path is not None else DEFAULT_PATH
    out = []
    with p.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError("%s line %d is not valid JSON: %s" % (p, lineno, exc)) from exc
    return out


def _rating_ok(rec, rating_range):
    if rating_range is None:
        return True
    lo, hi = rating_range
    r = rec.get("rating", "")
    if r == "" or r is None:
        return False  # unrated battles cannot satisfy a rating filter
    return (lo is None or r >= lo) and (hi is None or r <= hi)


def filter_pool(pool, rating_range=None, result=None, engine_verified=None,
                mirror=None, min_ghost_plays=None):
    """Subset of the pool.  Every filter is optional; None means "do not filter on this".

    rating_range   (lo, hi) inclusive on the ICEBOW player's rating; either bound may be None.
                   Records with rating "" are EXCLUDED whenever a range is given.
    result         "win" or "loss" from the icebow side.
    engine_verified True -> only tags the real engine has already driven (L61 batch_v2);
                    False -> only tags it has not.
    mirror         True/False on the icebow-vs-icebow flag.
    min_ghost_plays minimum number of ghost commands.
    """
    out = []
    for rec in pool:
        if not _rating_ok(rec, rating_range):
            continue
        if result is not None and rec.get("result") != result:
            continue
        if engine_verified is not None and bool(rec.get("engine_verified")) != bool(engine_verified):
            continue
        if mirror is not None and bool(rec.get("mirror")) != bool(mirror):
            continue
        if min_ghost_plays is not None and len(rec.get("ghost_commands", [])) < min_ghost_plays:
            continue
        out.append(rec)
    return out


def sample(pool, rng, rating_range=None, **filters):
    """One battle drawn uniformly from the pool (optionally rating-filtered).

    `rng` is a random.Random (pass a seeded one for reproducibility).  Raises ValueError when the
    filters leave nothing -- silently widening the filter would hide a broken curriculum.
    """
    candidates = filter_pool(pool, rating_range=rating_range, **filters)
    if not candidates:
        raise ValueError("no battle matches rating_range=%r %r" % (rating_range, filters))
    return candidates[rng.randrange(len(candidates))]


def ghost_deck_key(rec):
    """Hashable identity of the opponent's deck: sorted (slug, form) pairs."""
    return tuple(sorted((c["slug"], c["form"]) for c in rec["ghost_deck"]))


if __name__ == "__main__":
    import random
    pool = load_pool()
    print("pool", len(pool), "battles;", len({ghost_deck_key(r) for r in pool}), "distinct ghost decks")
    rec = sample(pool, random.Random(0))
    print("sample", rec["tag"], rec["result"], rec["rating"], len(rec["ghost_commands"]), "ghost cmds")
