"""Default-off adapter over the shipped Battle save/load/step API.

There is no Python forced deploy binding in 0.1.17/0.1.33. Rust's
spawn_unit[_resolved/_tapped] is not exported; Gym scripted spawns reset a battle.
Instead edit ONLY hand/queue/refill and the injection side's synthetic mana in
the engine's own freshly saved snapshot, then use the regular deploy path.
"""
from __future__ import annotations

from copy import deepcopy
import json
import re

NO_CARD = 65535  # state.rs NO_CARD (u16::MAX), not a catalogue id
SELF_CHECK = re.compile(r'snapshot self-check failed: saved hash 0x[0-9a-f]+, rebuilt (0x[0-9a-f]+)')


def load_edited(battle, before, after):
    """Rehash an intentional scenario edit using the engine's exact hash oracle.

    load_with computes the rebuilt hash before assigning Battle.state, and reports
    both hashes. Only that exact diagnostic permits ONE retry. All format, card,
    arena, calibre and catalogue validation still executes; a changed API fails.
    No snapshot travels across runtimes. Roll back on any other rejection.
    """
    encode = lambda x: json.dumps(x, separators=(',', ':'), allow_nan=False).encode()
    try:
        try:
            battle.load(encode(after))
        except ValueError as e:
            match = SELF_CHECK.fullmatch(str(e))
            if not match:
                raise
            after['state_hash'] = int(match[1], 16)
            battle.load(encode(after))
        actual = json.loads(battle.save())
        if actual['tick'] != before['tick'] or actual['players'] != after['players']:
            raise ValueError('parity_snapshot_edit_not_preserved')
    except Exception:
        battle.load(encode(before))
        raise


class SnapshotReplay:
    def __init__(self, battle, sim, opts, plan, ids, level):
        self.battle = battle
        self.internal = {}
        # Learn internal CardDb indices from reset + public catalogue IDs. Never
        # assume catalogue order == CardDb order or depend on opening-deal swaps.
        names = list(dict.fromkeys(c['name'] for c in plan['own_deck']+plan['opponent_roster']))
        probe = sim.Battle(None, [[0, 1, 2], [0, 2, 1]], **opts)
        for start in range(0, len(names), 4):
            chunk = names[start:start+4]
            decks = [[ids[n] for n in chunk]]*2
            probe.reset(424242, decks, 0, 0, None, None, [],
                        levels=[[level]*len(chunk)]*2, tower_levels=[level]*2)
            snap = json.loads(probe.save())
            raw = json.loads(probe.state_json())
            player = next(p for p in raw['players'] if p['team']==0)
            for internal, public in zip(snap['players'][0]['hand'], player['hand']):
                name = next(n for n in chunk if ids[n]==public)
                self.internal[name] = internal
        if set(self.internal) != set(names):
            raise ValueError('parity_internal_card_mapping_incomplete')

    def sync(self, side, hand, queue, inject=False):
        before = json.loads(self.battle.save())
        after = deepcopy(before)
        player = after['players'][side]
        player['hand'] = [self.internal[n] if n else NO_CARD for n in hand]
        player['queue'] = [self.internal[n] for n in queue]
        player['refill_ms'] = 0
        if inject:
            # Synthetic affordability, not measured/inferred enemy elixir.
            player['mana'] = after['calib']['max_mana'] * after['mana_unit']
        if after != before:
            load_edited(self.battle, before, after)

    def action(self, play):
        if play['mode'] == 'public_injection':
            self.sync(play['side'], [play['name'], None, None, None], [], inject=True)
        else:
            self.sync(play['side'], play['hand'], play['queue'])
        return play['slot']
