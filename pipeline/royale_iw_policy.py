"""Default-off SIM adapter of live Hero IW geometry + deterministic p >= .03.

No engine imports. Only visible bodies, own state/history and a public opponent
counter reach the rule. Live files are read-only dependencies, never imported
through hero_button's device/UI dependencies.
"""
from functools import lru_cache
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

LIVE = Path(__file__).resolve().parents[1] / 'scratchpad/gauntlet/L68/live_reader'
P_STAR = .03
IW_RANGE, FREEZE_R, TESLA_COST = 5.5, 2.5, 4.0
CLUMP_BODIES_MIN, CLUMP_VALUE_MIN, UNKNOWN_UNIT_VALUE = 2, 4.0, .5
WINCONS = {'HogRider', 'SuperHogRider', 'Giant', 'GoblinGiant', 'Golem', 'RoyalGiant', 'ElectroGiant', 'Balloon',
           'LavaHound', 'RamRider', 'BattleRam', 'Miner', 'RoyalHogs', 'Wallbreakers', 'ElixirGolem', 'GiantSkeleton',
           'SkeletonBalloon', 'Pekka', 'MegaKnight'}
BUILDINGS = {'Cannon', 'Tesla', 'InfernoTower', 'BombTower', 'Mortar', 'Xbow', 'Tombstone', 'GoblinHut', 'Furnace',
             'FirespiritHut', 'BarbarianHut', 'Elixir Collector', 'GoblinCage', 'GoblinDrill', 'GoblinPartyHut'}


@lru_cache(maxsize=1)
def hazard_module():
    spec = importlib.util.spec_from_file_location('iwdiag_live_hazard', LIVE/'ability_ice_wizard.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def unit_values():
    return json.loads((LIVE/'unit_values.json').read_text(encoding='utf8'))['value_per_unit']


def geometry(frame, side, hero, names):
    """Pure port of hero_button.ice_wizard_should_press, including nearest target."""
    if hero is None:
        return False
    distance = lambda a, b: ((a['x']-b['x'])**2 + (a['y']-b['y'])**2)**.5 / 1000
    foes = [e for e in frame['entities'] if e['side'] != side and int(e['card_id']) >= 0]
    in_range = [e for e in foes if distance(e, hero) <= IW_RANGE]
    if not in_range:
        return False
    target = min(in_range, key=lambda e: distance(e, hero))
    frozen = [e for e in foes if distance(e, target) <= FREEZE_R and names.get(int(e['card_id']), '') not in BUILDINGS]
    value = sum(unit_values().get(names.get(int(e['card_id']), ''), UNKNOWN_UNIT_VALUE) for e in frozen)
    if len(frozen) >= CLUMP_BODIES_MIN and value >= CLUMP_VALUE_MIN:
        return True
    me = next(p for p in frame['players'] if p['side'] == side)
    hand = [names.get(int(me['deck_card_ids'][i]), '') for i in me['hand_deck_indices'] if i >= 0]
    tesla_ok = 'Tesla' in hand and me['elixir_raw']/1e4 >= TESLA_COST
    return any(names.get(int(e['card_id']), '') in WINCONS and (e['y'] > 16000) == (side == 1)
               for e in frozen) and not tesla_ok


class LiveIWPolicy:
    def __init__(self):
        self.reset()

    def reset(self):
        self.observers = {}
        self.frames = {}

    def observe(self, env, side):
        from .public_observation import PublicObserver
        from .dataset_gen import card_key
        if env.feature_version < 3:
            raise ValueError('Live IW needs confirmed own play history (feature version >= 3)')
        if side not in self.observers:
            self.observers[side] = PublicObserver(side, schedule=env.elixir_regen_schedule)
        pub = self.observers[side]
        raw = env.raw()
        pub.update(raw, source='sim')  # strips private opponent player blocks
        pub.own_events = [dict(e, card=card_key(e['card'])) for e in env.public_plays
                          if e['side'] == side]
        self.frames[side] = raw

    def gate(self, env, hero, state):
        from .public_observation import public_frame, _native_ids
        from .obs_contract import _catalog_names
        from .reader_identity_aliases import dedupe_hero_bodies
        from . import vocab
        side = int(hero.team)
        raw = self.frames[side]
        # Same visible body coordinates as live (millitiles); no target IDs,
        # opponent elixir, opponent hand, or debug_units are consulted.
        me = state.players[side]
        deck = env.deck_ids[side]
        frame = dedupe_hero_bodies(public_frame(raw, source='sim'))
        frame['players'] = [dict(side=side, elixir_raw=me.elixir_milli*10,
                                 deck_card_ids=[_native_ids().get((vocab.engine_key(env.names[c]), 0), -1) for c in deck],
                                 hand_deck_indices=[deck.index(c) if c in deck else -1 for c in me.hand])]
        visible_hero = next((e for e in frame['entities'] if e['address'] == (side, hero.uid)), None)
        ok = geometry(frame, side, visible_hero, _catalog_names())
        pub = self.observers[side]
        deploys = [int(e['tick']) for e in pub.own_events if e['card'] == 'ice-wizard'
                   and not e.get('ability') and e.get('accepted', True)]
        if not deploys:
            return ok  # same explicit no-deploy-history fallback as live should_press
        decision, _ = hazard_module().should_press_pro(SimpleNamespace(public=pub), frame, side, deploys[-1],
                                                       geometry_ok=ok, v_min=CLUMP_VALUE_MIN, p_star=P_STAR)
        return decision
