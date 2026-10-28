"""Ticket GB-DECOY: the evolved Goblin Barrel's decoy barrel, told apart in the public projectile objects.

The evolved cast throws the real barrel at the play point and a decoy (GoblinBarrelSpell_EV1_Decoy, which lands
GoblinDummy bodies) at the point mirrored across the arena's width (crforge ActionMirroredExtraSpell; SME.md A2c-M).
The reader lists both under the Goblin Barrel's card id, so the model's projectile tokens show two identical barrels
and log_barrel / barrel_lane cannot pick (live CLXIII, 50 evo casts: first answer in the real lane 30 / 50, plain
barrel 446 / 467; scratchpad/gauntlet/L74/gb_decoy/).

Public in the game: since the 2025-08-01 balance update the fake barrel has a different colour for its first second
in flight, and the Decoy Goblins look like dolls (wiki Goblin_Barrel/Evolution). The reader shows the same thing as
creation order (owner 10-28: accepted as the stand-in for the colour cue): of a mirrored pair (same side, same target
y, target x summing to the arena width) created back to back (adjacent generation keys), the real barrel is the earlier
object. 52 / 52 live two-barrel casts: generation gap 1, first seen on the same frame; the real barrel the lower key on
50 / 50 landing-labelled casts. Two separate casts at mirrored points (Mirror + Goblin Barrel) are not adjacent
objects, so they are not marked (zero such frames recorded; the verifier's F1).

``objects`` is ``projectile_observation.objects`` with each reader decoy renamed DECOY_KEY. A checkpoint whose card
vocab lacks DECOY_KEY (CLXIII and every model so far) drops that token (``tokens_from_objects``: unknown card), so it
sees one barrel, as for a plain cast, and ``decision_options.barrel_landings`` returns the real landing only. A
successor that adds DECOY_KEY to its vocab learns the decoy as its own card. Wired behind live_play.py
--barrel-decoy on (LIVE_OPTIONS; GenPilot.barrel_decoy -> PublicObserver.barrel_decoy, 464b32d); off = unchanged.
A malformed barrel row (non-numeric side / target / generation key) is never marked (today's behaviour) and is
reported once per match through ``on_malformed``: this path never raises on reader data."""
from __future__ import annotations

from .obs_contract import catalog_card_form
from . import vocab

BARREL_KEY = 'goblin-barrel'
DECOY_KEY = 'goblin-barrel-decoy'
ARENA_W = 18000          # millitiles: the decoy's aim is ARENA_W - the real aim's x
TOL = 2                  # millitiles: rounding of the mirrored aim (live pairs: x sum 18000, same y)


def _key(row):
    try:
        name, _ = catalog_card_form(int(row.get('card_id', -1)))
    except (TypeError, ValueError):
        return None
    return vocab.base_key(vocab.engine_key(name)).replace('_', '-') if name else None


def _barrels(rows):
    """[(index, side, target_x, target_y, generation)] of the barrel rows with all four readable; and whether a barrel
    row was malformed (a value present but not numeric)."""
    out, bad = [], False
    for i, r in enumerate(rows or ()):
        if _key(r) != BARREL_KEY or any(r.get(k) is None for k in ('generation_key', 'target_x', 'target_y')):
            continue
        try:
            out.append((i, int(r['side']), float(r['target_x']), float(r['target_y']), int(r['generation_key'])))
        except (TypeError, ValueError, KeyError):
            bad = True
    return out, bad


def decoy_indices(rows, malformed=None):
    """Indices of reader projectile dicts that are an evolved Goblin Barrel's decoy: of each mirrored barrel pair with
    adjacent generation keys, the later-created one. Rows without a target or a generation key, or with a malformed
    one, are never marked; ``malformed`` (a list) gets True appended when such a row was skipped."""
    gb, bad = _barrels(rows)
    if bad and malformed is not None:
        malformed.append(True)
    out = set()
    for a, sa, xa, ya, ga in gb:
        for b, sb, xb, yb, gb_ in gb:
            if (b != a and sa == sb and abs(ya - yb) <= TOL and abs(xa + xb - ARENA_W) <= TOL and ga - gb_ == 1):
                out.add(a)
    return out


def objects(frame, *, source, on_malformed=None):
    """projectile_observation.objects, the reader's decoy barrels renamed DECOY_KEY (other sources unchanged).
    ``on_malformed()`` is called when a malformed barrel row was left unmarked."""
    from .projectile_observation import objects as base
    rows = frame.get('projectiles') or []
    bad = []
    decoys = decoy_indices(rows, bad) if source == 'reader' else set()
    if bad and on_malformed is not None:
        on_malformed()
    if not decoys:
        return base(frame, source=source)
    keep = dict(frame, projectiles=[r for i, r in enumerate(rows) if i not in decoys])
    fake = dict(frame, projectiles=[rows[i] for i in sorted(decoys)], effects=[])
    out = base(keep, source=source)
    out['projectiles'] = out['projectiles'] + [(DECOY_KEY, *r[1:]) for r in base(fake, source=source)['projectiles']]
    return out
