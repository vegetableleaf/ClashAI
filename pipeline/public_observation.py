"""gen_v3.1 public-only opponent observations shared by replay, live and SIM.

The detector is deliberately independent of player blocks, commands and decks.
Recording spell IDs are unavailable, so all adapters use the same conservative
card/presence deduplication. Counts describe observations, never a hidden hand.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import replace
from functools import lru_cache
import json

import numpy as np

from . import vocab
from .obs_contract import REPO, catalog_card_form, entity_form, TICK_S
from .opp_elixir_count import PlayDetector, OppElixirCounter, card_db, card_cost

FEATURE_VERSION = 4
CYCLE_K = 8


def body_only_board(bs):
    """The common v3.1 board: bodies with exact forms; no unverified timing fields.

    Full re-drive waits contain effects/kind while the existing PLAY reducer
    strips them. Mask both paths consistently, including live and SIM. Spells
    still enter the shared public play history. Age/deployment are future reader
    fields, not a row-format shortcut for the gate.
    """
    return replace(bs, units=tuple(replace(u, deploying=None, age_sec=None) for u in bs.units), spells=())


@lru_cache(maxsize=1)
def _native_ids():
    cards = json.loads((REPO / 'research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json')
                       .read_text(encoding='utf-8'))['cards']
    return {(vocab.engine_key(c['display_name']), form): int(c[field])
            for c in cards for form, field in enumerate(('card_id', 'evolution_form_id', 'hero_form_id'))
            if c.get(field) is not None}


def public_frame(frame, *, source):
    """Normalize an explicitly identified schema; never inspect player/deck fields.

    native = tag_native_recording output, reader = v2, sim = Royale raw().
    Projectile positions are their visible current positions, not target memory.
    """
    if source not in ('native', 'reader', 'sim'):
        raise ValueError('Unknown public observation schema')
    out = dict(game_tick=int(frame['game_tick' if source == 'reader' else 'tick']),
               entities=[], spells=[])
    for i, e in enumerate(frame.get('entities') or []):
        if source == 'native' and not isinstance(e, dict):
            cid = int(frame['native_card_ids'][i])
            eid = frame['entity_ids'][i]
            side, x, y, _, hp, mhp = e[:6]
        else:
            side, x, y, hp, mhp = (e[k] for k in ('side', 'x', 'y', 'hp', 'max_hp'))
            if source == 'sim':
                key = vocab.engine_key(e.get('name', ''))
                cid = _native_ids().get((key, entity_form(e)), -1)
                eid = e['entity_id']
            else:
                cid = int(e['card_id'])
                # Category is the reader's generation identity; address alone is reusable.
                eid = (e['address'], e.get('category')) if source == 'reader' else e['entity_id']
        # lead 2026-10-06 (IDENTITY_AUDIT #3): keep UNREADABLE bodies (max_hp <= 0, e.g. every Evo Witch 13000007 reads
        # hp/max_hp -1) -- dropping them hid the parent, so her Skeletons became 'new Witch plays' (+5 elixir each;
        # native 232 phantom vs 556 true Evo Witch plays, live 13 / 92). PlayDetector already treats max_hp <= 0 as a
        # possible parent. Dead bodies (hp 0 with a known max) are still dropped.
        if int(side) not in (0, 1) or cid < 0 or (hp <= 0 and mhp > 0):
            continue
        out['entities'].append(dict(side=int(side), x=float(x), y=float(y), hp=hp,
                                    max_hp=mhp, card_id=cid, address=(int(side), eid)))
    for kind in ('projectiles', 'effects'):
        field = 'area_effects' if source == 'native' and kind == 'effects' else kind
        evidence = frame.get('public_objects') if source == 'native' else None
        rows = evidence.get(field, []) if evidence is not None else frame.get(field, [])
        for e in rows or []:
            if isinstance(e, dict):
                side, x, y = (e[k] for k in ('side', 'x', 'y'))
                if source == 'sim':
                    key, form = vocab.engine_key(e.get('name', '')), 0
                else:
                    name, form = catalog_card_form(int(e.get('card_id', -1)))
                    key = vocab.engine_key(name) if name else None
            else:
                side, x, y = e[:3]
                key, form = vocab.engine_key(e[5 if kind == 'projectiles' else 3]), 0
            # Card ID on a troop's projectile denotes its source, not a new play.
            if int(side) in (0, 1) and key and card_db().kind(key) == 'spell':
                out['spells'].append(dict(side=int(side), card=key, form=form, x=float(x), y=float(y)))
    return out


class PublicObserver:
    def __init__(self, side, *, schedule=None):
        self.side = int(side)
        if self.side not in (0, 1):
            raise ValueError('Invalid observer side')
        self.schedule = schedule
        self.reset()

    def reset(self):
        self.body = PlayDetector()
        self.body.my_side = self.side
        self.counter = OppElixirCounter(schedule=self.schedule)
        self.plays = []
        self.ticks = []
        self.estimates = []
        self.last_tick = -1
        self.spell_last_seen = {}
        self.last_play = {}
        self.object_ticks = []
        self.object_rows = []
        self.ability_ticks = []
        self.ability_rows = []
        self.own_events = []
        from .projectile_motion import ProjectileMotion
        self.motion = ProjectileMotion(catalog_fallback=True)

    def update(self, frame, *, source):
        f = public_frame(frame, source=source)
        tick = f['game_tick']
        if tick < self.last_tick:
            self.reset()
        self.last_tick = tick
        from .own_ability import observe
        own = observe(frame, self.side, source)
        if self.ability_ticks and self.ability_ticks[-1] == tick:
            self.ability_rows[-1] = own
        elif not self.ability_rows or own != self.ability_rows[-1]:
            self.ability_ticks.append(tick)
            self.ability_rows.append(own)
        from .projectile_observation import objects
        observed = self.motion.update(objects(frame, source=source), tick)
        # Store only normalized public objects, never the player/private blocks.
        # Compress unchanged snapshots; past queries must not see future objects.
        if self.object_ticks and self.object_ticks[-1] == tick:
            self.object_rows[-1] = observed
        elif not self.object_rows or observed != self.object_rows[-1]:
            self.object_ticks.append(tick)
            self.object_rows.append(observed)
        candidates = {}
        for e in self.body.feed(f):
            if e.key not in self.spell_last_seen or tick-self.spell_last_seen[e.key] > 100:
                candidates[e.key] = dict(card=e.key, form=e.form, x=e.x, y=e.y)
        groups = {}
        for e in f['spells']:
            if e['side'] != self.side:
                groups.setdefault(e['card'], []).append(e)
        for key, group in groups.items():
            # A spell can persist much longer than the swarm window (Poison etc.).
            # Continuous sightings extend presence; frame gaps <= 100 ticks do not
            # invent a fresh cast. This can miss overlapping casts, never resolves
            # them using replay truth or an opponent's private state.
            previous = self.spell_last_seen.get(key)
            self.spell_last_seen[key] = tick
            if previous is None or tick - previous > 100:
                candidates[key] = dict(card=key, form=max(e['form'] for e in group),
                                       x=sum(e['x'] for e in group)/len(group),
                                       y=sum(e['y'] for e in group)/len(group))
        for key, e in sorted(candidates.items()):
            window = self.body.swarm_ticks_by_key.get(key, self.body.swarm_ticks)
            if key in self.last_play and tick - self.last_play[key] <= window:
                continue
            # Bodies produced by an already-visible spell (Barrel/Graveyard) are
            # not another cast, even if the spell has persisted past the window.
            if key not in groups and key in self.spell_last_seen and tick-self.spell_last_seen[key] <= 100:
                continue
            self.last_play[key] = tick
            self.plays.append(dict(e, tick=tick, side=1-self.side, accepted=True))
            self.counter.play(tick, key, card_cost(key))
            self.ticks.append(tick)
            self.estimates.append(self.counter.est)
        return self.estimate_at(tick)

    def estimate_at(self, tick):
        """Causal public counter, excluding same-tick sightings like opp_past."""
        i = bisect_left(self.ticks, int(tick)) - 1
        counter = OppElixirCounter(schedule=self.schedule)
        if i >= 0:
            counter.tick, counter.est = self.ticks[i], self.estimates[i]
        return counter.at(int(tick))

    def object_context(self, tick):
        """Causal snapshots for inference look-ahead; never ingest a projected future as an observation."""
        i = bisect_right(self.object_ticks, int(tick))-1
        return dict(public_objects=self.object_rows[i] if i >= 0 else dict(projectiles=[], effects=[]),
                    previous_objects=self.object_rows[i-1] if i > 0 else None,
                    object_gap_ticks=self.object_ticks[i]-self.object_ticks[i-1] if i > 0 else 0)

    def features(self, tick, gid, *, objects_override=None):
        from .dataset_gen import opponent_past
        from .projectile_observation import tokens_from_objects
        i = bisect_right(self.object_ticks, int(tick))-1
        observed = self.object_rows[i] if i >= 0 else dict(projectiles=[], effects=[])
        if objects_override is not None:
            observed = objects_override
        from .own_ability import tokens
        ai = bisect_right(self.ability_ticks, int(tick))-1
        return dict(opp_past=opponent_past(self.plays, int(tick), self.side, gid),
                    own_ability=tokens(self.ability_rows[ai] if ai >= 0 else [], gid, self.own_events, int(tick)),
                    opp_cycle=opponent_cycle(self.plays, int(tick), self.side, gid),
                    **tokens_from_objects(observed, self.side, gid))


def opponent_cycle(plays, tick, side, gid):
    """Eight distinct observed cards, latest first: card/form/plays_since/age_s.

    Simultaneous first sightings have unknown order: neither increments the
    other's plays_since. Four subsequent sightings do NOT assert readiness.
    """
    from .dataset_gen import card_key
    prev = [e for e in plays if e.get('accepted', True) and int(e['side']) != side and int(e['tick']) < tick]
    prev.sort(key=lambda e: int(e['tick']))
    out = np.tile(np.array([0, 3, -1, -1], np.float32), (CYCLE_K, 1))
    seen = set()
    for e in reversed(prev):
        key = card_key(e['card'])
        if key in seen:
            continue
        if len(seen) == CYCLE_K:
            break
        i = len(seen)
        seen.add(key)
        c = gid.get(key, 0)
        if c:
            out[i] = (c, int(e['form']), sum(int(p['tick']) > int(e['tick']) for p in prev),
                      (tick-int(e['tick']))*TICK_S)
    return out


def recording_observers(rec):
    """Use recorded board frames, not private command/play_frames records.

    These board snapshots are normally <= record_every ticks apart but the
    re-driver also splits its steps at commands. That cadence difference from
    live is declared; no command field or command-timed play_frame is consumed.
    """
    if rec.get('record_native') is not True or rec.get('record_full') is not True:
        raise ValueError('gen_v3.1 requires record_native=true and record_full=true')
    observers = [PublicObserver(0), PublicObserver(1)]
    for observer in observers:
        observer.own_events=[dict(e) for e in rec.get('log',[]) if int(e['side'])==observer.side and e.get('accepted') and e.get('card')]
    for frame in sorted(rec['frames'], key=lambda f: int(f['tick'])):
        for observer in observers:
            observer.update(frame, source='native')
    return observers
