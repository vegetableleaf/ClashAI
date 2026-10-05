"""Adapter witnesses for new engine behavior, without learning or GPU work."""
from collections import Counter
import hashlib
import json

import pytest

from pipeline.royale_env import RoyaleSelfPlayEnv
from pipeline.body_identity import resolve
from pipeline import vocab
from royalegym.protocol import MatchSetup, ShuffleMode

DECK = ['Tornado', 'Tesla', 'IceWizard', 'Xbow', 'Rocket', 'Knight', 'Log', 'Skeletons']


def test_empty_refill_slot_is_omitted_then_returns_to_public_hand():
    env = RoyaleSelfPlayEnv()
    try:
        before = env.reset(DECK, DECK, seed=7)
        available = [x['name'] for x in before['players'][0]['hand']]
        name = min(available, key=lambda n: env.costs(0)[DECK.index(n)])
        result = env.act(0, DECK.index(name), 9000, 10000)
        assert result['accepted']
        # An idle timer refills the first play immediately; a second play waits.
        # Commit that play's logic tick, which starts the refill clock.
        first = env.advance_to(env.tick+1)['players'][0]['hand']
        assert len(first) == 4
        name = min((x['name'] for x in first), key=lambda n: env.costs(0)[DECK.index(n)])
        assert env.act(0, DECK.index(name), 9000, 10000)['accepted']
        after = env.raw()['players'][0]['hand']
        assert len(after) == 3
        assert name not in [x['name'] for x in after]
        assert len(env.advance_to(env.tick+20)['players'][0]['hand']) == 4
    finally:
        env.close()


@pytest.mark.parametrize('weak_side', [None, 0, 1])
def test_tower_drain_reaches_real_terminal_outcome(weak_side):
    env = RoyaleSelfPlayEnv(warmup_ticks=0)
    try:
        env.reset(DECK, DECK, seed=7)
        hp = [[3000, 1000, 1000], [3000, 1000, 1000]]
        if weak_side is not None:
            hp[weak_side][1] = 100
        env.core.reset(7, MatchSetup(decks=[env.deck_ids[0], env.deck_ids[1]],
            shuffle=ShuffleMode.NONE, start_tick=5999, tower_hp=hp))
        env.tick = 5999
        env.advance_to(6000)
        assert not env.done  # An old immediate tiebreak would end here.
        env.advance_to(7200)
        assert env.terminated and env.episode['termination_reason'] == 'game_over'
        # State.tick counts completed ticks: the judge on6147 reports6148.
        assert 6000 < env.tick <= 6148
        if weak_side is None:
            assert env.outcome(0)[0] == env.outcome(1)[0] == 'draw'
        else:
            assert env.outcome(weak_side)[0] == 'loss'
            assert env.outcome(1-weak_side)[0] == 'win'
    finally:
        env.close()


def test_same_seed_and_actions_reproduce_public_trace():
    def trace():
        env = RoyaleSelfPlayEnv(feature_version=5)
        try:
            env.reset(DECK, DECK, seed=7)
            hashes = []
            for tick in range(100, 801, 50):
                state = env.advance_to(tick)
                hashes.append(hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest())
                for side in (0, 1):
                    hand = state['players'][side]['hand']
                    if hand:
                        name = min((x['name'] for x in hand), key=lambda n: env.costs(side)[DECK.index(n)])
                        env.act(side, DECK.index(name), 3500, 10000 if side == 0 else 22000)
            return hashes, len(env.public_plays)
        finally:
            env.close()
    first, second = trace(), trace()
    assert first == second and first[1] > 4
    assert len(set(first[0])) > 4


@pytest.mark.parametrize('parent,child', [('Witch','skeletons'), ('DarkWitch','bats'), ('FirespiritHut','fire_spirit')])
def test_originating_card_children_resolve_through_repeated_waves(parent, child):
    env = RoyaleSelfPlayEnv(feature_version=5, tail_cap=800)
    try:
        deck = [parent, 'Knight', 'Skeletons', 'Log', 'Rocket', 'Tesla', 'IceWizard', 'Tornado']
        env.reset(deck, deck, seed=1)
        assert env.act(1, 0, 3500, 28500)['accepted']
        seen, arrivals = set(), Counter()
        for tick in range(100, 701, 10):
            for entity in env.advance_to(tick)['entities']:
                if entity['side'] != 1 or entity['hp'] <= 0 or entity['entity_id'] in seen:
                    continue
                seen.add(entity['entity_id'])
                identity = resolve(entity['name'], entity['max_hp'])
                if identity.cls == vocab.unit_id(child):
                    assert entity['name'] == parent
                    assert identity.form == 0
                    arrivals[tick] += 1
        assert sum(arrivals.values()) >= 4 and len(arrivals) >= 2
    finally:
        env.close()
