"""--log-air retarget|block (owner 2026-10-09: "played log on yet another air troop"; "log should still be cyclable"):
a Log whose roll corridor holds only flyers is re-aimed (or, for comparison, not played). Off = byte-identical."""
import argparse
import itertools
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from pipeline import vocab
from pipeline.decision_options import (LOG_AIR_BLOCKED, DecisionOptions, log_air_ground_child_tiles, log_air_ground_children, add_arguments, choose_cells, config_from_args,
                                      decide_batch, log_air_board, log_air_cell, log_air_traits, lethal_log_cell,
                                      match_kwargs, options_from_config, rolling_corridor)
from pipeline.obs_contract import Tower, Unit
from pipeline.tests.test_xbow_dead_lane import cell, peaked

RETARGET, BLOCK = DecisionOptions(log_air='retarget'), DecisionOptions(log_air='block')
CORRIDOR = rolling_corridor('Log')
ID = vocab.unit_id


def unit(name, x, y, side=1):
    return Unit(ID(name), side, x / 18.0, y / 32.0, 1., None, None, 1.)


def board(units=(), alive=(True, True, True), hp=(1., 1., 1.)):
    tw = [Tower(0, 'king', None, 1., True), Tower(0, 'princess', 'L', 1., True), Tower(0, 'princess', 'R', 1., True),
          Tower(1, 'king', None, hp[0], alive[0]), Tower(1, 'princess', 'L', hp[1], alive[1]),
          Tower(1, 'princess', 'R', hp[2], alive[2])]
    return SimpleNamespace(t_sec=100., towers=tuple(tw), units=tuple(units))


def pick(logits, bs, barrels=(), mode='retarget', at=None):
    at = int(logits.argmax()) if at is None else at
    return log_air_cell(logits, CORRIDOR, log_air_board(bs), barrels, 'lattice', mode, at)


AIM = cell(3.5, 22.5)                       # a Log cast in my territory, rolling toward the enemy's left lane
AIM_LOGITS = peaked({AIM: .9, cell(9.0, 20.0): .05, cell(14.5, 17.5): .05})


def test_default_off_and_flag():
    assert DecisionOptions().log_air == 'off' and not DecisionOptions().active and RETARGET.active and BLOCK.active
    ap = argparse.ArgumentParser(); add_arguments(ap)
    assert options_from_config(config_from_args(ap.parse_args([]))) == DecisionOptions()
    for mode, o in (('retarget', RETARGET), ('block', BLOCK)):
        assert options_from_config(config_from_args(ap.parse_args(['--log-air', mode]))) == o
    with pytest.raises(ValueError):
        DecisionOptions(log_air='wait')


def test_traits_from_the_catalog():
    t = log_air_traits()
    air = {vocab.UNIT_VOCAB[i] for i, (a, _) in t.items() if a}
    assert {'balloon', 'mega_minion', 'minions', 'minion_horde', 'bats', 'lava_hound', 'lava_pups', 'baby_dragon',
            'inferno_dragon', 'balloon_hero', 'bats_evo'} <= air
    assert not air & {'knight', 'tesla', 'hog_rider', 'golem', 'giant', 'skeletons', 'goblin_barrel', 'x_bow'}
    assert t[ID('tesla')] == (False, 4.0) and abs(t[ID('skeletons')][1] - 1 / 3) < 1e-9
    assert all(vocab.UNIT_VOCAB[i] not in vocab.SPELL_CLASSES for i in t)


def test_skeleton_barrel_is_exempt_like_the_goblin_barrel():
    t = log_air_traits()
    for name in ('skeleton_barrel', 'skeleton_barrel_evo'):
        assert t[ID(name)][0] is False                     # counted as ground: its landing drops skeletons
    assert t[ID('balloon')][0] and t[ID('minions')][0]      # every other flyer still blocks
    barrel = board([unit('skeleton_barrel', 3.5, 15.0)])
    assert pick(AIM_LOGITS, barrel, mode='block') == AIM and pick(AIM_LOGITS, barrel) == AIM
    mixed = board([unit('skeleton_barrel', 3.5, 15.0), unit('mega_minion', 3.5, 14.0)])
    assert pick(AIM_LOGITS, mixed, mode='block') == AIM    # the barrel alone makes the corridor not air-only
    assert pick(AIM_LOGITS, board([unit('mega_minion', 3.5, 14.0)]), mode='block') == LOG_AIR_BLOCKED


def test_ability_classes_are_not_flyers():
    """balloon_hero_ability = the Hero Balloon's thrown SkeletonTroopers (ground); mega_minion_hero_ability = the warp strike
    (an effect, not a body). Detector-only classes, never emitted by the engine / reader path; never air."""
    t = log_air_traits()
    for name in ('balloon_hero_ability', 'mega_minion_hero_ability', 'knight_hero_ability'):
        assert t[ID(name)][0] is False
    assert t[ID('balloon_hero')][0] and t[ID('mega_minion_hero')][0] and t[ID('mega_minion')][0]   # the units still fly


def test_phoenix_egg_hps_are_ground_children_and_the_flyer_is_not():
    kids = log_air_ground_children()['phoenix']
    assert kids == {262, 288, 317, 348, 383, 420, 461, 507, 558}              # PhoenixEgg 124 x the level ladder
    from pipeline.body_identity import tables
    parent = {hp for hp, v in tables()[('phoenix', 0)].items() if any(x[2] == 'parent' for x in v)}
    assert 411 not in kids and not kids & parent and {1528, 1052, 871} <= parent   # the (respawned) Phoenix keeps flying


def raw(side, x, y, name, mhp):
    return dict(side=side, x=x, y=y, name=name, max_hp=mhp, hp=mhp)


def test_ground_child_tiles_follow_my_frame_for_both_sides():
    # my frame has my king at the high-y edge: observer side 0 sees the enemy (side 1) egg at native (16000, 23100) at
    # model (16.0, 8.9); observer side 1 (mirror on) sees the enemy (side 0) egg at native (2000, 8900) at the same tile
    a = log_air_ground_child_tiles([raw(1, 16000, 23100, 'Phoenix', 420)], 0)
    b = log_air_ground_child_tiles([raw(0, 2000, 8900, 'Phoenix', 420)], 1)
    assert len(a) == len(b) == 1 and np.allclose(a, b, atol=1e-6) and np.allclose(a[0], (16.0, 8.9), atol=1e-6)
    assert log_air_ground_child_tiles([raw(1, 16000, 23100, 'Phoenix', 1528), raw(1, 1000, 1000, 'Bats', 420),
                                       raw(0, 16000, 23100, 'Phoenix', 420), raw(1, 1000, 1000, '-1', 420)], 0) == ()
    assert log_air_ground_child_tiles(None, 0) == ()


def test_phoenix_egg_in_the_corridor_is_ground_but_bats_alone_still_block():
    """Real case 20261006_141406 tick 3878: 5 Bats plus a 420-HP egg (here moved mid-lane): the Log hits the egg."""
    bats = [unit('bats', 8.2 + .3 * k, 10.0 + .2 * k) for k in range(5)]
    egg = unit('phoenix', 9.0, 8.9)
    eggs = log_air_ground_child_tiles([raw(1, 9000, 23100, 'Phoenix', 420)], 0)
    aim = cell(9.0, 17.5)                                   # mid-lane: no tower in the roll
    logits = peaked({aim: 1.})
    with_egg = board(bats + [egg])
    # per-class (the defect): the egg counts as a flyer and the Log is blocked
    assert log_air_cell(logits, CORRIDOR, log_air_board(with_egg), (), 'lattice', 'block', aim) == LOG_AIR_BLOCKED
    # per-body: the egg is ground, so the corridor is not air-only
    assert log_air_cell(logits, CORRIDOR, log_air_board(with_egg, eggs), (), 'lattice', 'block', aim) == aim
    assert log_air_cell(logits, CORRIDOR, log_air_board(board(bats), ()), (), 'lattice', 'block', aim) == LOG_AIR_BLOCKED
    g, a, _ = log_air_board(with_egg, eggs)
    assert len(g) == 1 and len(a) == 5
    # a real Phoenix 3 tiles from an egg stays air; one egg claims one unit only
    g, a, _ = log_air_board(board([unit('phoenix', 9.0, 8.9), unit('phoenix', 9.2, 9.0)]), eggs)
    assert len(g) == 1 and len(a) == 1
    g, a, _ = log_air_board(board([unit('phoenix', 10.0, 12.0)]), eggs)
    assert len(g) == 0 and len(a) == 1


def test_log_hits_ground_only_in_the_catalog():
    from pipeline.body_identity import CATALOG
    import json
    log = next(c for c in json.loads(CATALOG.read_text(encoding='utf-8'))['cards'] if c['name'] == 'Log')
    roll = log['projectile']['spawn_projectile']
    assert roll['aoe_to_air'] is False and roll['aoe_to_ground'] is True


def test_only_air_in_the_corridor_is_reaimed_at_ground_value():
    bs = board([unit('mega_minion', 3.5, 15.0), unit('knight', 12.0, 20.0), unit('skeletons', 12.5, 19.0),
                unit('tesla', 14.5, 19.5)])
    got = pick(AIM_LOGITS, bs)
    assert got != AIM
    x, y = np.arange(2304) % 36 * .5, np.arange(2304) // 36 * .5
    assert abs(x[got] - 13.0) <= 3 and y[got] >= 17.5 and y[got] - 19.5 <= 10.1       # the Tesla + knight lane, mine
    assert pick(AIM_LOGITS, bs, mode='block') == LOG_AIR_BLOCKED


def test_ground_unit_building_tower_or_barrel_in_the_corridor_keeps_the_aim():
    air = unit('minions', 3.5, 15.0)
    for extra in (unit('knight', 4.0, 12.0), unit('tesla', 3.0, 14.0), unit('skeleton_army', 3.5, 17.0)):
        for mode in ('retarget', 'block'):
            assert pick(AIM_LOGITS, board([air, extra]), mode=mode) == AIM
    near_tower = cell(3.5, 17.5)                          # the roll ends at the princess at (3.5, 6.5)
    assert pick(peaked({near_tower: 1.}), board([air, unit('minions', 3.5, 9.0)])) == near_tower
    assert pick(peaked({near_tower: 1.}), board([air]), mode='block') == near_tower
    barrel = [(3.6 / 18.0, 14.0 / 32.0)]                  # a Goblin Barrel landing in the corridor: not blocked
    assert pick(AIM_LOGITS, board([air]), barrels=barrel, mode='block') == AIM
    assert pick(AIM_LOGITS, board([air]), barrels=[(15 / 18., 14 / 32.)], mode='block') == LOG_AIR_BLOCKED


def test_nothing_or_no_air_keeps_the_aim():
    assert pick(AIM_LOGITS, board([])) == AIM and pick(AIM_LOGITS, board([unit('balloon', 15.0, 5.0)])) == AIM
    assert pick(AIM_LOGITS, board([unit('knight', 15.0, 5.0)]), mode='block') == AIM
    assert pick(AIM_LOGITS, board([unit('balloon', 3.5, 15.0, side=0)]), mode='block') == AIM   # my own flyer


def test_chip_the_lower_hp_princess_else_unchanged():
    bs = lambda **k: board([unit('balloon', 3.5, 15.0)], **k)
    assert pick(AIM_LOGITS, bs(hp=(1., .8, .4))) == lethal_log_cell('R', 'lattice')       # R has the lower HP
    assert pick(AIM_LOGITS, bs(hp=(1., .3, .4))) == lethal_log_cell('L', 'lattice')
    assert pick(AIM_LOGITS, bs(alive=(True, False, True))) == lethal_log_cell('R', 'lattice')
    tie = pick(peaked({AIM: .8, lethal_log_cell('L', 'lattice'): .01, lethal_log_cell('R', 'lattice'): .19}), bs())
    assert tie == lethal_log_cell('R', 'lattice')                                           # equal HP: the logit decides
    assert pick(AIM_LOGITS, bs(alive=(True, False, False))) == AIM                          # no princess: unchanged
    cell_xy = (lethal_log_cell('L', 'lattice') % 36 * .5, lethal_log_cell('L', 'lattice') // 36 * .5)
    assert cell_xy == (3.5, 17.5)


def test_ground_value_beats_the_chip_and_illegal_cells_are_never_picked():
    bs = board([unit('balloon', 3.5, 15.0), unit('knight', 15.0, 12.0)], hp=(1., .1, 1.))
    got = pick(AIM_LOGITS, bs)
    x, y = got % 36 * .5, got // 36 * .5
    assert abs(x - 15.0) <= 2.5 and y >= 17.5                                  # the Knight, not the weak princess
    legal = torch.full((2304,), -torch.inf)
    legal[AIM], legal[lethal_log_cell('R', 'lattice')] = 0., 0.                # live legality: only two cells
    got = pick(AIM_LOGITS + legal, bs)
    assert got == lethal_log_cell('R', 'lattice')                              # AIM is a flyer-only cell: chip it


def test_equal_ground_value_takes_the_higher_logit():
    bs = board([unit('balloon', 3.5, 15.0), unit('knight', 15.0, 12.0)])
    a, b = cell(14.0, 20.0), cell(15.0, 20.0)
    assert pick(peaked({AIM: .6, a: .3, b: .1}), bs) == a and pick(peaked({AIM: .6, a: .1, b: .3}), bs) == b


def test_choose_cells_only_touches_log_rows():
    logits = torch.stack([AIM_LOGITS, AIM_LOGITS, AIM_LOGITS])
    bs = board([unit('mega_minion', 3.5, 15.0)])
    boards = [log_air_board(bs)] * 3
    moved = []
    out = choose_cells(logits, ['the_log', 'knight', 'rocket'], RETARGET, log_air_boards=boards, grid='lattice',
                       barrels=[[]] * 3, log_air_moved=moved)
    assert moved == [0] and int(out[0]) != AIM and int(out[1]) == int(out[2]) == AIM
    out = choose_cells(logits, ['the_log', 'knight', 'rocket'], BLOCK, log_air_boards=boards, grid='lattice')
    assert out.tolist() == [LOG_AIR_BLOCKED, AIM, AIM]
    off = choose_cells(logits, ['the_log', 'knight', 'rocket'], DecisionOptions())
    assert off.tolist() == [AIM] * 3
    with pytest.raises(ValueError):
        choose_cells(logits, ['the_log'] * 3, RETARGET)


class SimModel:
    def __init__(self, per_slot):
        self.per_slot = per_slot

    def cell_logits(self, enc, slot):
        return torch.stack([self.per_slot[int(s)] for s in slot])


NAMES = ['knight', 'the_log', 'rocket', 'tesla']


def sim(options, bs, *, card=(0., 9., 5., 1.), allowed=(1, 1, 1, 1), p=.9, rngs=None, barrels=()):
    cells = {0: peaked({2000: 1.}), 1: AIM_LOGITS, 2: peaked({2100: 1.}), 3: peaked({2200: 1.})}
    rngs = rngs or [np.random.default_rng(0)]
    return decide_batch(SimModel(cells), {'g': torch.zeros(1, 2)}, {'card': torch.tensor([card])}, np.array([p]),
                        np.array([allowed], bool), np.zeros(1, bool), tau=.35, device='cpu', options=options, rngs=rngs,
                        card_names=[NAMES], grid='lattice', projectiles=[torch.zeros(0, 20)] if options.uses_barrels else None,
                        log_air_boards=[log_air_board(bs)])[0]


def test_sim_retarget_keeps_the_card_and_block_waits_without_substituting():
    bs = board([unit('mega_minion', 3.5, 15.0)])
    off = sim(DecisionOptions(), bs)
    assert off == dict(play=True, slot=1, cell=AIM, why='gate')
    d = sim(RETARGET, bs)
    assert d['play'] and d['slot'] == 1 and d['cell'] != AIM and d['why'] == 'log_air'
    d = sim(BLOCK, bs)
    assert d == dict(play=False, slot=1, cell=-1, why='log_air')                   # WAIT: the Rocket is not played
    assert sim(BLOCK, board([unit('knight', 3.5, 12.0)])) == off                    # a ground target: untouched
    assert sim(BLOCK, bs, card=(0., 0., 9., 1.))['slot'] == 2                       # the Log was not even chosen


def test_sim_rng_stream_is_untouched_by_log_air():
    bs = board([unit('mega_minion', 3.5, 15.0)])
    states = []
    for mode in ('off', 'retarget', 'block'):
        rng = [np.random.default_rng(3)]
        sim(DecisionOptions(card_choice='filtered', log_air=mode), bs, rngs=rng)
        states.append(rng[0].bit_generator.state)
    assert states[0] == states[1] == states[2]                                       # log_air draws nothing itself


def test_match_kwargs_carries_the_enemy_board():
    bs = board([unit('mega_minion', 3.5, 15.0), unit('knight', 12.0, 20.0)])
    m = SimpleNamespace(tag='a', k=1, cfg={'log_air': 'retarget', 'grid': 'lattice'}, side=0,
                        deck=SimpleNamespace(cards=NAMES), state=None, _cur=(100, bs, None),
                        _gen_row={'projectiles': torch.zeros(0, 20)})
    kw = match_kwargs([m])
    assert kw['decision_options'] == RETARGET and kw['grid'] == 'lattice'
    ground, air, towers = kw['log_air_boards'][0]
    assert len(ground) == 1 and len(air) == 1 and len(towers) == 3 and len(kw['projectiles']) == 1
    del m._gen_row
    with pytest.raises(ValueError):
        match_kwargs([m])                                                            # the barrel exemption needs fv >= 4
    assert match_kwargs([SimpleNamespace(cfg={'grid': 'lattice'}, tag='a', k=0)]) == {}


# ---- live GenPilot on the real reader frame, both observer sides ----------------------------------------------------
LIVE_HAND = [0, 4, 5, 7]                                  # Knight, Xbow, Rocket, Log (deck index 7) -> Log at position 3
LOG_HAND = (0., 0., 0., 9.)
LIVE_AIM = cell(14.5, 22.5)                               # the enemy Minions sit at model (14.5, 15.0) after the mirror


def live_frame(side, flyer=26000005, tick=1000):
    import copy
    from pipeline.tests.test_live_decision_options import icebow_frame
    f = icebow_frame(tick, side)
    for pl in f['players']:
        if pl['side'] == side:
            pl['hand_deck_indices'] = LIVE_HAND
    if flyer is not None:
        e = copy.deepcopy(next(e for e in f['entities'] if e['kind'] == 15))
        e.update(side=1 - side, card_id=flyer, x=3500 if side == 1 else 14500, y=15000 if side == 1 else 17000,
                 address='0x99')
        f['entities'].append(e)
    return f


def live_pilot(options, seed=0, gate_p=.6):
    from pipeline.tests.test_live_decision_options import pilot
    p = pilot(options, gate_p, card_logits=LOG_HAND, cell=peaked({LIVE_AIM: 1.}), seed=seed)
    row = p.row

    def with_tokens(frame):                                # the stub model has no fv >= 4 projectile tokens
        b, info = row(frame)
        b['projectiles'] = torch.zeros(1, 0, 20)
        return b, info
    p.row = with_tokens
    return p


@pytest.mark.parametrize('side', [0, 1])
def test_live_off_is_unchanged_and_modes_match_sim(side):
    from pipeline import e1_eval as E
    f = live_frame(side)
    plain = live_pilot(DecisionOptions()).decide(f)
    assert plain['name'] == 'Log' and plain['play'] and plain['xy'] == (LIVE_AIM % 36 * .5 / 18, LIVE_AIM // 36 * .5 / 32)
    assert 'why' not in plain
    new = live_pilot(RETARGET).decide(f)
    assert new['name'] == 'Log' and new['play'] and new['why'] == 'log_air' and new['xy'] != plain['xy']
    blocked = live_pilot(BLOCK).decide(f)
    assert blocked['name'] == 'Log' and not blocked['play'] and blocked['why'] == 'log_air' and blocked['xy'] == plain['xy']
    for opts, d in ((RETARGET, new), (BLOCK, blocked)):
        m = SimpleNamespace(cfg=dict({k: getattr(opts, k) for k in DecisionOptions.__dataclass_fields__}, grid='lattice'),
                            tag='t', k=0, deck=SimpleNamespace(cards=['knight', 'xbow', 'rocket', 'the_log']),
                            _cur=(1000, d['bs'], None), rng_decision_options=np.random.default_rng(0),
                            _gen_row={'projectiles': torch.zeros(0, 20)})
        kw = match_kwargs([m])
        s = E.live_decide_batch(SimModel({i: peaked({LIVE_AIM: 1.}) for i in range(4)}), {'g': torch.zeros(1, 2)},
                                {'card': torch.tensor([LOG_HAND])}, [d['p_play']], np.ones((1, 4), bool), np.zeros(1, bool),
                                tau=.35, decision_options=kw.pop('decision_options'), **kw)[0]
        assert (s['play'], s['slot'], s['why']) == (d['play'], d['hand_pos'], 'log_air')
        if d['play']:
            assert s['cell'] == cell(d['xy'][0] * 18, d['xy'][1] * 32)


@pytest.mark.parametrize('side', [0, 1])
def test_live_ground_or_no_flyer_is_untouched_and_block_never_swaps_cards(side):
    for flyer in (None, 26000000):                          # nothing / a Knight (ground)
        f = live_frame(side, flyer)
        plain = live_pilot(DecisionOptions()).decide(f)
        for opts in (RETARGET, BLOCK):
            p = live_pilot(opts)
            assert p.decide(f) == plain
            assert p.rng_decisions.bit_generator.state == live_pilot(DecisionOptions()).rng_decisions.bit_generator.state
    b = live_pilot(BLOCK).decide(live_frame(side))
    assert b['hand_pos'] == 3 and not b['play']             # still the Log's slot: no other card was substituted


def test_match_kwargs_reads_the_raw_egg_from_the_sim_state():
    bs = board([unit('phoenix', 9.0, 8.9), unit('bats', 8.5, 10.0)])
    m = SimpleNamespace(tag='a', k=1, cfg={'log_air': 'block', 'grid': 'lattice'}, side=0, deck=SimpleNamespace(cards=NAMES),
                        state={'entities': [raw(1, 9000, 23100, 'Phoenix', 420), raw(1, 8500, 21900, 'Bats', 30)]},
                        _cur=(100, bs, None), _gen_row={'projectiles': torch.zeros(0, 20)})
    ground, air, _ = match_kwargs([m])['log_air_boards'][0]
    assert len(ground) == 1 and len(air) == 1                      # the egg is ground, the bat is air
    m.state = {'entities': [raw(1, 9000, 23100, 'Phoenix', 1528)]}  # a real (parent-HP) Phoenix: still air
    ground, air, _ = match_kwargs([m])['log_air_boards'][0]
    assert len(ground) == 0 and len(air) == 2


def card_id_of(name):
    from pipeline.obs_contract import _catalog_names
    return next(k for k, v in _catalog_names().items() if v == name)


@pytest.mark.parametrize('side', [0, 1])
def test_live_phoenix_egg_with_bats_is_not_blocked(side):
    import copy
    from pipeline.tests.test_live_decision_options import pilot
    f = live_frame(side, flyer=None)
    base = next(e for e in f['entities'] if e['kind'] == 15)
    mid = (9000, 15000) if side == 1 else (9000, 17000)           # the centre column, 15 tiles up in my frame

    def add(card, mhp, dx):
        e = copy.deepcopy(base)
        e.update(side=1 - side, card_id=card_id_of(card), x=mid[0] + dx, y=mid[1], hp=mhp, max_hp=mhp, address=f'0x{card}{dx}')
        f['entities'].append(e)

    def run(options):
        p = pilot(options, .6, card_logits=LOG_HAND, cell=peaked({cell(9.0, 22.5): 1.}))
        row = p.row

        def with_tokens(frame):                                   # the stub model has no fv >= 4 projectile tokens
            b, info = row(frame)
            b['projectiles'] = torch.zeros(1, 0, 20)
            return b, info
        p.row = with_tokens
        return p.decide(f)
    for dx in (-600, -300, 0, 300):
        add('Bats', 30, dx)
    d = run(BLOCK)
    assert d['name'] == 'Log' and not d['play'] and d['why'] == 'log_air'          # bats alone: blocked
    add('Phoenix', 420, 600)                                       # a 420-HP "Phoenix": the level-14 egg, a ground body
    d = run(BLOCK)
    assert d['play'] and 'why' not in d and d == run(DecisionOptions())
    f['entities'][-1].update(hp=1393, max_hp=1393)                 # a level-14 flying Phoenix instead: blocked again
    assert not run(BLOCK)['play']
