"""--rocket-dead-target block (owner 2026-10-08: "the model cast rocket on a fallen tower"): the Rocket never takes a cell
whose blast covers a destroyed enemy tower and nothing alive on the decision board."""
import argparse
import copy
import itertools
import math

import numpy as np
import pytest
import torch

from pipeline import e1_eval as E
from pipeline.decision_options import (ENEMY_TOWERS_TILES, ROCKET_BODY_SLACK_TILES, DecisionOptions, add_arguments,
                                      choose_cells, config_from_args, decide_batch, enemy_body_tiles, match_kwargs,
                                      options_from_config, rocket_dead_target_cells, rocket_radius_tiles,
                                      xbow_dead_lane_cells)
from pipeline.live_mem import deck_of
from pipeline.model_v3 import cell_xy
from pipeline.tests.test_lethal_rocket import towers as raw_towers
from pipeline.tests.test_live_decision_options import HAND, icebow_frame, pilot
from pipeline.tests.test_xbow_dead_lane import BUNDLE, LOCK, BACK, cell, peaked

BLOCK = DecisionOptions(rocket_dead_target='block')
AREA = DecisionOptions(spell_aim='rocket_area', rocket_dead_target='block')
CENTRE = {'L': cell(3.5, 6.5), 'R': cell(14.5, 6.5)}     # enemy princess centres (lattice)
NEAR = {'L': cell(4.0, 7.5), 'R': cell(14.0, 7.5)}       # 1.1 tiles from the centre, river side
FAR = {'L': cell(5.0, 11.5), 'R': cell(13.0, 11.5)}      # 5.2 tiles out: clear of every tower footprint
ROCKET_HAND = (0., 1., 9., 0.)                           # HAND = Knight, Xbow, Rocket, Tesla -> Rocket at position 2
STATES = list(itertools.product((True, False), repeat=2))


def reference(x, y, alive_l, alive_r, bodies=()):
    r = rocket_radius_tiles()
    radii = (1.4, 1.0, 1.0)
    over = [math.hypot(x - tx, y - ty) <= r + tr for (tx, ty), tr in zip(ENEMY_TOWERS_TILES, radii)]
    alive = (True, alive_l, alive_r)
    dead = any(o and not a for o, a in zip(over, alive))
    live = any(o and a for o, a in zip(over, alive)) or any(math.hypot(x - bx, y - by) <= r + ROCKET_BODY_SLACK_TILES
                                                            for bx, by in bodies)
    return dead and not live


def test_default_allow_and_flag():
    assert DecisionOptions().rocket_dead_target == 'allow' and not DecisionOptions().active and BLOCK.active
    ap = argparse.ArgumentParser(); add_arguments(ap)
    assert options_from_config(config_from_args(ap.parse_args([]))) == DecisionOptions()
    assert options_from_config(config_from_args(ap.parse_args(['--rocket-dead-target', 'block']))) == BLOCK
    with pytest.raises(ValueError):
        DecisionOptions(rocket_dead_target='king')


@pytest.mark.parametrize('grid', ['lattice', 'floor'])
@pytest.mark.parametrize('alive_l,alive_r', STATES)
@pytest.mark.parametrize('bodies', [(), ((3.5, 9.0),), ((14.5, 4.5), (9.0, 20.0))])
def test_blocked_cells_match_the_definition_cell_by_cell(grid, alive_l, alive_r, bodies):
    off = 0.5 if grid == 'floor' else 0.0
    c = np.arange(2304)
    x, y = (c % 36 + off) * 0.5, (c // 36 + off) * 0.5
    want = np.array([reference(a, b, alive_l, alive_r, bodies) for a, b in zip(x, y)])
    np.testing.assert_array_equal(rocket_dead_target_cells((True, alive_l, alive_r), bodies, grid), want)
    assert want.sum() < 300                                   # disks around dead towers (~113 cells each), never the board


def test_named_cells_lanes_and_bodies():
    assert not rocket_dead_target_cells((True, True, True), (), 'lattice').any()      # every tower standing: no-op
    for dead, other in (('L', 'R'), ('R', 'L')):
        alive = (True, dead != 'L', dead != 'R')
        blocked = rocket_dead_target_cells(alive, (), 'lattice')
        assert blocked[CENTRE[dead]] and blocked[NEAR[dead]] and not blocked[FAR[dead]]
        assert not blocked[CENTRE[other]] and not blocked[NEAR[other]]
        # an enemy body at the fallen tower makes the shot a real one again
        assert not rocket_dead_target_cells(alive, ((*ENEMY_TOWERS_TILES['LR'.index(dead) + 1],),), 'lattice')[CENTRE[dead]]
        a = blocked.reshape(64, 36)
        b = rocket_dead_target_cells((True, dead == 'L', dead == 'R'), (), 'lattice').reshape(64, 36)
        np.testing.assert_array_equal(a[:, 1:], b[:, 1:][:, ::-1])                  # left-right mirror


def test_choose_cells_touches_only_rocket_rows_and_area_scores_the_remaining_cells():
    alive = (True, False, True)
    logits = torch.stack([peaked({CENTRE['L']: .5, NEAR['L']: .3, FAR['L']: .2})] * 3)
    names = ['Rocket', 'Log', 'rocket']
    kw = dict(enemy_alive=[alive] * 3, enemy_bodies=[()] * 3, grid='lattice')
    assert choose_cells(logits, names, DecisionOptions(), **kw).tolist() == [CENTRE['L']] * 3
    assert choose_cells(logits, names, BLOCK, **kw).tolist() == [FAR['L'], CENTRE['L'], FAR['L']]
    out = choose_cells(logits, names, AREA, **kw).tolist()
    assert out[1] == CENTRE['L'] and out[0] == out[2] and not rocket_dead_target_cells(alive, (), 'lattice')[out[0]]
    # rocket_area alone keeps the cluster at the fallen tower; its plain winner is a blocked cell
    plain = choose_cells(logits, names, DecisionOptions(spell_aim='rocket_area'), **kw).tolist()
    assert rocket_dead_target_cells(alive, (), 'lattice')[plain[0]]
    with pytest.raises(ValueError, match='rocket_dead_target'):
        choose_cells(logits, names, BLOCK, enemy_alive=[alive] * 3, grid='lattice')


def test_area_mass_of_blocked_cells_cannot_win():
    """Ring of mass just outside the blocked disk + a heavy blocked centre: the winner must be a finite, allowed cell."""
    alive = (True, False, True)
    blocked = rocket_dead_target_cells(alive, (), 'lattice')
    p = torch.full((2304,), 1e-9)
    p[CENTRE['L']] = .6
    x, y = (np.arange(2304) % 36) * .5, (np.arange(2304) // 36) * .5
    ring = np.flatnonzero(~blocked & (np.hypot(x - 3.5, y - 6.5) <= 4.0))
    p[ring] = .4 / len(ring)
    c = choose_cells(p.log()[None], ['Rocket'], AREA, enemy_alive=[alive], enemy_bodies=[()], grid='lattice').item()
    assert not blocked[c] and math.hypot(x[c] - 3.5, y[c] - 6.5) <= 6.0     # an allowed cell by the remaining ring


class SimModel:
    def __init__(self, per_slot):
        self.per_slot = per_slot

    def cell_logits(self, enc, slot):
        return torch.stack([self.per_slot[int(s)] for s in slot])


NAMES = ['knight', 'xbow', 'rocket', 'tesla']


def sim(options, cells, *, card=(0., 5., 9., 1.), allowed=(1, 1, 1, 1), alive=(True, False, True), bodies=(), p=.9,
        **kw):
    out = decide_batch(SimModel(cells), {'g': torch.zeros(1, 2)}, {'card': torch.tensor([card])}, np.array([p]),
                       np.array([allowed], bool), np.zeros(1, bool), tau=.35, device='cpu', options=options,
                       rngs=[np.random.default_rng(0)], card_names=[NAMES], enemy_alive=[alive], enemy_bodies=[bodies],
                       grid='lattice', **kw)
    return out[0]


def test_sim_block_reaims_and_falls_back_to_the_next_card_only_with_no_cell():
    rk = peaked({CENTRE['L']: .7, FAR['L']: .3})
    cells = {0: peaked({2000: 1.}), 1: peaked({LOCK['R']: 1.}), 2: rk, 3: peaked({2100: 1.})}
    assert sim(DecisionOptions(spell_aim='argmax', card_choice='argmax', tau_phase=(.35,) * 3), cells,
               t_sec=[100.]) == dict(play=True, slot=2, cell=CENTRE['L'], why='gate')
    assert sim(BLOCK, cells) == dict(play=True, slot=2, cell=FAR['L'], why='gate')
    assert sim(BLOCK, cells, alive=(True, True, True)) == dict(play=True, slot=2, cell=CENTRE['L'], why='gate')
    assert sim(BLOCK, cells, bodies=((4.0, 8.0),)) == dict(play=True, slot=2, cell=CENTRE['L'], why='gate')
    cells[2] = torch.where(torch.as_tensor(rocket_dead_target_cells((True, False, True), (), 'lattice')), rk, -torch.inf)
    assert sim(BLOCK, cells) == dict(play=True, slot=1, cell=LOCK['R'], why='gate')     # next card: the X-Bow
    assert sim(BLOCK, cells, allowed=(0, 0, 1, 0)) == dict(play=False, slot=2, cell=-1, why='wait')   # never forced
    assert sim(BLOCK, cells, p=.1) == dict(play=False, slot=2, cell=-1, why='wait')


def test_lethal_rocket_overrides_and_both_blocks_compose():
    cells = {0: peaked({2000: 1.}), 1: peaked({LOCK['L']: .7, BACK['L']: .3}), 2: peaked({CENTRE['L']: .7, FAR['L']: .3}),
             3: peaked({2100: 1.})}
    both = DecisionOptions(lethal_rocket='ot', rocket_dead_target='block', xbow_dead_lane='block')
    lethal = [(raw_towers(0, 0, 400), 0, False)]                     # side 0: enemy L down, enemy R at 400 HP (lethal)
    d = sim(both, cells, t_sec=[200.0], lethal=lethal)
    assert d['why'] == 'lethal_rocket' and d['slot'] == 2 and d['cell'] == cell(14.5, 6.5)
    lethal = [(raw_towers(0, 0, 4000), 0, False)]
    assert sim(both, cells, t_sec=[200.0], lethal=lethal) == dict(play=True, slot=2, cell=FAR['L'], why='gate')
    assert sim(both, cells, card=(0., 9., 5., 1.), t_sec=[200.0], lethal=lethal) == \
        dict(play=True, slot=1, cell=BACK['L'], why='gate')          # the X-Bow row keeps its own block


def test_match_kwargs_supplies_enemy_bodies_for_block():
    from types import SimpleNamespace
    from pipeline.obs_contract import Tower, Unit
    towers = tuple(Tower(s, k, l, 1., a) for s, k, l, a in
                   [(0, 'king', None, 1), (0, 'princess', 'L', 1), (0, 'princess', 'R', 1),
                    (1, 'king', None, 1), (1, 'princess', 'L', 0), (1, 'princess', 'R', 1)])
    units = (Unit(1, 0, .5, .8, 1., None, None, 1.), Unit(2, 1, .25, .25, 1., None, None, 1.),
             Unit(3, -1, .75, .5, None, None, None, 1.))
    bs = SimpleNamespace(t_sec=120.0, towers=towers, units=units)
    m = SimpleNamespace(tag='a', k=1, cfg={'rocket_dead_target': 'block', 'grid': 'lattice'},
                        deck=SimpleNamespace(cards=['rocket']), _cur=(2400, bs, None))
    kw = match_kwargs([m])
    assert kw['decision_options'] == BLOCK and kw['enemy_alive'] == [(True, False, True)]
    assert kw['enemy_bodies'] == [((4.5, 8.0), (13.5, 16.0))] == [enemy_body_tiles(bs)]   # side 1 and unknown -1


# ---- live GenPilot on the real reader frame, both observer sides -------------------------------------------------------
def dead_lane(side, drop):
    return None if drop is None else ('L' if (drop == 3500) == (side == 0) else 'R')


def with_enemy_body(f, side, drop):
    """An enemy Knight 1 tile river-side of the dropped enemy princess (native coordinates)."""
    me = next(e for e in f['entities'] if e.get('card_id', -1) != -1)
    body = dict(me, side=1 - side, x=drop, y=7500 if side == 1 else 24500, address='0xfeed')
    f['entities'] = f['entities'] + [body]
    return f


CASES = [(side, drop) for side in (0, 1) for drop in (None, 3500, 14500)]


def sim_of(d, opts, seed, logits, f, side):
    from types import SimpleNamespace
    _, names = deck_of(f, side)
    cfg = {k: getattr(opts, k) for k in DecisionOptions.__dataclass_fields__}
    m = SimpleNamespace(cfg=dict(cfg, grid='lattice'), tag='t', k=0, deck=SimpleNamespace(cards=[names[i] for i in HAND]),
                        _cur=(1000, d['bs'], None), rng_decision_options=np.random.default_rng(seed))
    kw = match_kwargs([m])
    return E.live_decide_batch(SimModel({i: logits for i in range(4)}), {'g': torch.zeros(1, 2)},
                               {'card': torch.tensor([ROCKET_HAND])}, [d['p_play']], np.ones((1, 4), bool),
                               np.zeros(1, bool), tau=.35, decision_options=kw.pop('decision_options'), **kw)[0]


@pytest.mark.parametrize('side,drop', CASES)
def test_live_block_on_both_sides_matches_sim(side, drop):
    lane = dead_lane(side, drop) or 'L'
    other = 'R' if lane == 'L' else 'L'
    logits = peaked({CENTRE[lane]: .5, NEAR[lane]: .2, FAR[lane]: .2, CENTRE[other]: .1})
    f = icebow_frame(1000, side, drop)
    plain = pilot(DecisionOptions(spell_aim='rocket_area'), .6, card_logits=ROCKET_HAND, cell=logits).decide(f)
    opts = DecisionOptions(spell_aim='rocket_area', rocket_dead_target='block')
    new = pilot(opts, .6, card_logits=ROCKET_HAND, cell=logits).decide(f)
    assert plain['name'] == new['name'] == 'Rocket' and plain['play'] and new['play']
    if drop is None:
        assert new == plain
    else:
        alive = (True, lane != 'L', lane != 'R')
        assert tuple(t.alive for t in new['bs'].towers[3:6]) == alive
        blocked = rocket_dead_target_cells(alive, enemy_body_tiles(new['bs']), 'lattice')
        assert new['why'] == 'rocket_dead_target' and 'why' not in plain
        assert rocket_dead_target_cells(alive, (), 'lattice')[cell(plain['xy'][0] * 18, plain['xy'][1] * 32)]
        chosen = cell(new['xy'][0] * 18, new['xy'][1] * 32)          # rocket_area over the remaining cells: by FAR
        fx, fy = cell_xy(FAR[lane], 'lattice')
        assert not blocked[chosen] and math.hypot((new['xy'][0] - fx) * 18, (new['xy'][1] - fy) * 32) <= 2.5
    s = sim_of(new, opts, 0, logits, f, side)
    assert (s['play'], s['slot']) == (new['play'], new['hand_pos']) and cell_xy(s['cell'], 'lattice') == new['xy']


@pytest.mark.parametrize('side,drop', [(0, 3500), (1, 3500), (0, 14500), (1, 14500)])
def test_live_enemy_body_at_the_fallen_tower_keeps_the_shot(side, drop):
    lane = dead_lane(side, drop)
    logits = peaked({CENTRE[lane]: .6, FAR[lane]: .4})
    f = with_enemy_body(icebow_frame(1000, side, drop), side, drop)
    a = pilot(DecisionOptions(), .6, card_logits=ROCKET_HAND, cell=logits).decide(f)
    b = pilot(BLOCK, .6, card_logits=ROCKET_HAND, cell=logits).decide(f)
    assert len(enemy_body_tiles(b['bs'])) == 1 and a['xy'] == b['xy'] == cell_xy(CENTRE[lane], 'lattice')
    assert 'why' not in b


def test_live_falls_back_to_the_next_card_when_no_rocket_cell_is_left():
    f = icebow_frame(1000, 1, 3500)                                  # side 1: dropped native-3500 princess = my R
    blocked = torch.as_tensor(rocket_dead_target_cells((True, True, False), (), 'lattice'))
    p = pilot(BLOCK, .6, card_logits=(0., 5., 9., 1.), cell=peaked({CENTRE['R']: .9, NEAR['R']: .1}))
    p.guard_cells = lambda frame, d, logits: logits.masked_fill(~blocked, -torch.inf)
    d = p.decide(f)
    assert d['play'] and d['name'] == 'Xbow' and d['hand_pos'] == 1 and d['why'] == 'rocket_dead_target'


def test_live_wait_keeps_the_plain_rocket_cell():
    p = pilot(AREA, .2, card_logits=ROCKET_HAND, cell=peaked({CENTRE['R']: .9, FAR['R']: .1}), seed=4)
    before = copy.deepcopy(p.rng_decisions.bit_generator.state)
    d = p.decide(icebow_frame(1000, 1, 3500))
    q = pilot(DecisionOptions(spell_aim='rocket_area'), .2, card_logits=ROCKET_HAND,
              cell=peaked({CENTRE['R']: .9, FAR['R']: .1}), seed=4).decide(icebow_frame(1000, 1, 3500))
    assert not d['play'] and d == q and 'why' not in d and p.rng_decisions.bit_generator.state == before


@pytest.mark.parametrize('side', [0, 1])
@pytest.mark.parametrize('tick,gate_p', [(1000, .6), (1000, .2), (3000, .5), (3700, .6)])
def test_live_bundle_block_is_a_no_op_with_every_enemy_tower_standing(side, tick, gate_p):
    """Deployed bundle (+ xbow_dead_lane block; log_aim left out: the stub has no fv >= 4 tokens) +/- rocket block."""
    bundle = {k: v for k, v in BUNDLE.items() if k != 'log_aim'}
    bundle.update(xbow_dead_lane='block', lethal_rocket='ot_behind')
    logits = peaked({CENTRE['L']: .4, NEAR['R']: .3, FAR['L']: .3})
    f = icebow_frame(tick, side)
    for seed in range(4):
        for hand in (ROCKET_HAND, (0., 9., 1., 0.)):
            a = pilot(DecisionOptions(**bundle), gate_p, card_logits=hand, cell=logits, seed=seed)
            b = pilot(DecisionOptions(**bundle, rocket_dead_target='block'), gate_p, card_logits=hand, cell=logits,
                      seed=seed)
            for q in (a, b):
                q._hazard_prev = (tick - 40, True)
            assert a.decide(f) == b.decide(f)
            assert a.rng_decisions.bit_generator.state == b.rng_decisions.bit_generator.state
