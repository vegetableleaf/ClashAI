"""Ticket GB-DECOY: the evolved Goblin Barrel's decoy barrel, told apart in the public projectile objects.

The evolved cast throws the real barrel at the play point and a decoy (GoblinBarrelSpell_EV1_Decoy, which lands
GoblinDummy bodies) at the point mirrored across the arena's width (crforge ActionMirroredExtraSpell; SME.md A2c-M).
The reader lists both under the Goblin Barrel's card id, so the model's projectile tokens show two identical barrels
and log_barrel / barrel_lane cannot pick (live CLXIII, 50 evo casts: first answer in the real lane 30 / 50, plain
barrel 446 / 467; scratchpad/gauntlet/L74/gb_decoy/).

Public in the game: since the 2025-08-01 balance update the fake barrel has a different colour for its first second
in flight, and the Decoy Goblins look like dolls (wiki Goblin_Barrel/Evolution). The reader shows the same thing as
creation order: of a mirrored pair (same side, same target y, target x summing to the arena width), the real barrel is
the earlier object (lower generation key; 50 / 50 live evo casts, both rows on the same frames).

``objects`` is ``projectile_observation.objects`` with each reader decoy renamed DECOY_KEY. A checkpoint whose card
vocab lacks DECOY_KEY (CLXIII and every model so far) drops that token (``tokens_from_objects``: unknown card), so it
sees one barrel, as for a plain cast, and ``decision_options.barrel_landings`` returns the real landing only. A
successor that adds DECOY_KEY to its vocab learns the decoy as its own card. Not wired: the live path keeps
``projectile_observation.objects`` until the lead and owner say go (gb_decoy/wiring.diff)."""
from __future__ import annotations

from .obs_contract import catalog_card_form
from . import vocab

BARREL_KEY = 'goblin-barrel'
DECOY_KEY = 'goblin-barrel-decoy'
ARENA_W = 18000          # millitiles: the decoy's aim is ARENA_W - the real aim's x
TOL = 2                  # millitiles: rounding of the mirrored aim (live pairs: x sum 18000, same y)


def _key(row):
    name, _ = catalog_card_form(int(row.get('card_id', -1)))
    return vocab.base_key(vocab.engine_key(name)).replace('_', '-') if name else None


def decoy_indices(rows):
    """Indices of reader projectile dicts that are an evolved Goblin Barrel's decoy: of each mirrored barrel pair, the
    later-created one (higher generation_key). Rows without a target or a generation key are never marked."""
    gb = [i for i, r in enumerate(rows or ()) if _key(r) == BARREL_KEY and r.get('generation_key') is not None
          and r.get('target_x') is not None and r.get('target_y') is not None]
    out = set()
    for a in gb:
        ra = rows[a]
        for b in gb:
            rb = rows[b]
            if (b != a and int(ra['side']) == int(rb['side']) and abs(ra['target_y'] - rb['target_y']) <= TOL
                    and abs(ra['target_x'] + rb['target_x'] - ARENA_W) <= TOL
                    and int(ra['generation_key']) > int(rb['generation_key'])):
                out.add(a)
    return out


def objects(frame, *, source):
    """projectile_observation.objects, the reader's decoy barrels renamed DECOY_KEY (other sources unchanged)."""
    from .projectile_observation import objects as base
    rows = frame.get('projectiles') or []
    decoys = decoy_indices(rows) if source == 'reader' else set()
    if not decoys:
        return base(frame, source=source)
    keep = dict(frame, projectiles=[r for i, r in enumerate(rows) if i not in decoys])
    fake = dict(frame, projectiles=[rows[i] for i in sorted(decoys)], effects=[])
    out = base(keep, source=source)
    out['projectiles'] = out['projectiles'] + [(DECOY_KEY, *r[1:]) for r in base(fake, source=source)['projectiles']]
    return out
