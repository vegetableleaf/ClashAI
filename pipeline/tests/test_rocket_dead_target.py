"""--rocket-dead-target block (owner 2026-10-08: "i noticed the model cast rocket on a fallen tower, this is another bug
you must fix."; standing rule: never the king). Verifier fixes 10-09: no re-aim onto the king (unless the Rocket finishes
it), a blocked Rocket with no real target left is not cast, a princess counts as destroyed only after 60 ticks dead
(reader glitch), and an unblocked aim lands exactly where it would with the option off."""
import argparse
import copy
import itertools
import math
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from pipeline import e1_eval as E
from pipeline import live_gen_v2
from pipeline.decision_options import (ENEMY_TOWERS_TILES, PRINCESS_DEAD_CONFIRM_TICKS, ROCKET_BODY_SLACK_TILES,
                                      DecisionOptions, add_arguments, choose_cells, config_from_args, decide_batch,
                                      enemy_body_tiles, match_kwargs, options_from_config, princess_dead_state,
                                      rocket_covers_king, rocket_kills_king, rocket_radius_tiles, rocket_target_cells)
from pipeline.live_mem import deck_of
from pipeline.model_v3 import cell_xy
from pipeline.obs_contract import Tower, Unit
from pipeline.tests.test_lethal_rocket import towers as raw_towers
from pipeline.tests.test_live_decision_options import HAND, icebow_frame, pilot
from pipeline.tests.test_xbow_dead_lane import BUNDLE, LOCK, BACK, cell, peaked

BLOCK = DecisionOptions(rocket_dead_target='block')
AREA = DecisionOptions(spell_aim='rocket_area', rocket_dead_target='block')
CENTRE = {'L': cell(3.5, 6.5), 'R': cell(14.5, 6.5)}     # enemy princess centres (lattice)
NEAR = {'L': cell(4.0, 7.5), 'R': cell(14.0, 7.5)}       # 1.1 tiles from the centre, river side
FAR = {'L': cell(5.0, 11.5), 'R': cell(13.0, 11.5)}      # 5.2 tiles out: no tower footprint in the blast
KING = cell(9.0, 3.0)
ROCKET_HAND = (0., 1., 9., 0.)                           # HAND = Knight, Xbow, Rocket, Tesla -> Rocket at position 2
STATES = list(itertools.product((True, False), repeat=2))
CONFIRMED = (-10 ** 6, -10 ** 6)                         # princess_dead_state: both dead "forever" (alive ones reset)


def reference(x, y, alive_l, alive_r, bodies=(), kills_king=False):
    """(blocked, target) for one cell, written from the definition."""
    r = rocket_radius_tiles()
    over = [math.hypot(x - tx, y - ty) <= r + tr for (tx, ty), tr in zip(ENEMY_TOWERS_TILES, (1.4, 1.0, 1.0))]
    alive = (True, alive_l, alive_r)
    body = any(math.hypot(x - bx, y - by) <= r + ROCKET_BODY_SLACK_TILES for bx, by in bodies)
    princess = any(over[j] and alive[j] for j in (1, 2))
    dead = any(over[j] and not alive[j] for j in (0, 1, 2))
    king = over[0]
    blocked = not body and ((dead and not princess and not (king and kills_king)) or (king and not kills_king))
    return blocked, body or princess or (king and kills_king)


def test_default_allow_and_flag():
    assert DecisionOptions().rocket_dead_target == 'allow' and not DecisionOptions().active and BLOCK.active
    ap = argparse.ArgumentParser(); add_arguments(ap)
    assert options_from_config(config_from_args(ap.parse_args([]))) == DecisionOptions()
    assert options_from_config(config_from_args(ap.parse_args(['--rocket-dead-target', 'block']))) == BLOCK
    with pytest.raises(ValueError):
        DecisionOptions(rocket_dead_target='king')


@pytest.mark.parametrize('grid', ['lattice', 'floor'])
@pytest.mark.parametrize('alive_l,alive_r', STATES)
@pytest.mark.parametrize('bodies', [(), ((3.5, 9.0),), ((14.5, 4.5), (9.0, 20.0)), ((9.0, 4.0),)])
@pytest.mark.parametrize('kills_king', [False, True])
def test_cells_match_the_definition_cell_by_cell(grid, alive_l, alive_r, bodies, kills_king):
    off = 0.5 if grid == 'floor' else 0.0
    c = np.arange(2304)
    x, y = (c % 36 + off) * 0.5, (c // 36 + off) * 0.5
    want = np.array([reference(a, b, alive_l, alive_r, bodies, kills_king) for a, b in zip(x, y)])
    blocked, target = rocket_target_cells(((True, alive_l, alive_r), bodies, kills_king), grid)
    np.testing.assert_array_equal(blocked, want[:, 0])
    np.testing.assert_array_equal(target, want[:, 1])


def test_named_cells_king_and_lanes():
    blocked, target = rocket_target_cells(((True, True, True), (), False), 'lattice')
    assert blocked[KING] and not target[KING]                         # never the king
    assert not blocked[CENTRE['L']] and target[CENTRE['L']] and not blocked[FAR['L']] and not target[FAR['L']]
    blocked, target = rocket_target_cells(((True, True, True), (), True), 'lattice')
    assert not blocked[KING] and target[KING]                         # ... unless this Rocket finishes it
    blocked, _ = rocket_target_cells(((True, True, True), ((9.0, 4.5),), False), 'lattice')
    assert not blocked[KING]                                          # an enemy body at the king: a real target
    for dead, other in (('L', 'R'), ('R', 'L')):
        alive = (True, dead != 'L', dead != 'R')
        blocked, target = rocket_target_cells((alive, (), False), 'lattice')
        assert blocked[CENTRE[dead]] and blocked[NEAR[dead]] and not target[CENTRE[dead]]
        assert not blocked[CENTRE[other]] and target[CENTRE[other]]
        mirror, _ = rocket_target_cells(((True, dead == 'L', dead == 'R'), (), False), 'lattice')
        np.testing.assert_array_equal(blocked.reshape(64, 36)[:, 1:], mirror.reshape(64, 36)[:, 1:][:, ::-1])


def test_kills_king_uses_the_lethal_level_rule():
    assert rocket_kills_king(raw_towers(0, 4000, 4000, king_hp=497), 0)          # level 15 Rocket: 497 crown damage
    assert not rocket_kills_king(raw_towers(0, 4000, 4000, king_hp=498), 0)
    assert rocket_kills_king(raw_towers(1, 0, 4000, king_hp=300), 1)
    assert rocket_covers_king(KING, 'lattice') and not rocket_covers_king(CENTRE['L'], 'lattice')


def board(t, alive_l=True, alive_r=True):
    tw = tuple(Tower(s, k, l, 1., a) for s, k, l, a in [(0, 'king', None, 1), (0, 'princess', 'L', 1),
                                                         (0, 'princess', 'R', 1), (1, 'king', None, 1),
                                                         (1, 'princess', 'L', alive_l), (1, 'princess', 'R', alive_r)])
    return SimpleNamespace(t_sec=t * 0.05, towers=tw, units=())


def test_reader_glitch_needs_60_ticks_of_death():
    state, alive = princess_dead_state(None, board(1000))
    assert alive == (True, True, True)
    seq = [(1010, False), (1020, False), (1040, False), (1045, True), (1050, False), (1100, False), (1109, False),
           (1110, False), (1200, False)]
    seen = []
    for t, a in seq:                                                   # L glitches dead 1010-1040, then dies at 1050
        state, alive = princess_dead_state(state, board(t, alive_l=a))
        seen.append(alive[1])
    assert seen == [True, True, True, True, True, True, True, False, False]
    assert PRINCESS_DEAD_CONFIRM_TICKS == 60
    _, alive = princess_dead_state(state, board(1200, alive_l=False, alive_r=False))
    assert alive == (True, False, True)                                # R: first dead read -> still counted alive


def choices(logits, alive, bodies=(), kills_king=False, opts=AREA):
    return choose_cells(logits, ['Rocket'] * len(logits), opts, rocket_boards=[(alive, bodies, kills_king)] * len(logits),
                        grid='lattice', enemy_alive=[alive] * len(logits))


@pytest.mark.parametrize('spell_aim', ['argmax', 'rocket_area'])
def test_unblocked_aims_never_shift(spell_aim):
    """Random boards and logits: whenever the option-off aim is not blocked, the block arm lands exactly there."""
    g = torch.Generator().manual_seed(7)
    rng = np.random.default_rng(7)
    on, off = DecisionOptions(spell_aim=spell_aim, rocket_dead_target='block'), DecisionOptions(spell_aim=spell_aim)
    checked = moved = 0
    for _ in range(60):
        logits = torch.randn(8, 2304, generator=g) * 3
        for k in range(8):                                             # mass clusters at towers, the king, random spots
            for c in rng.choice([CENTRE['L'], CENTRE['R'], NEAR['L'], KING, FAR['R'], int(rng.integers(2304))], 2):
                logits[k, c] += 12
        alive = (True, bool(rng.random() < .5), bool(rng.random() < .5))
        bodies = tuple((float(rng.uniform(0, 18)), float(rng.uniform(0, 16))) for _ in range(int(rng.integers(0, 3))))
        rb = [(alive, bodies, False)] * 8
        a = choose_cells(logits, ['Rocket'] * 8, off, rocket_boards=rb, grid='lattice')
        b = choose_cells(logits, ['Rocket'] * 8, on, rocket_boards=rb, grid='lattice')
        blocked, target = rocket_target_cells(rb[0], 'lattice')
        for i in range(8):
            if not blocked[int(a[i])]:
                checked += 1
                assert int(b[i]) == int(a[i])
            else:
                moved += 1
                assert int(b[i]) == -1 or (target[int(b[i])] and not blocked[int(b[i])])
    assert checked > 100 and moved > 50


def sharp(mass):
    """Logits with the named cells only (every other cell -inf), so re-aims have one exact answer."""
    p = torch.zeros(2304)
    for c, m in mass.items():
        p[c] = m
    return p.log()


def test_blocked_rocket_reaims_at_a_real_target_or_is_not_cast():
    alive = (True, False, True)
    logits = sharp({CENTRE['L']: .6, KING: .2, FAR['L']: .1, CENTRE['R']: .1})[None]
    assert choices(logits, alive).item() == CENTRE['R']                 # not the king, not the empty FAR: the princess
    assert choices(logits, alive, opts=BLOCK).item() == CENTRE['R']
    both_dead = (True, False, False)
    assert choices(logits, both_dead).item() == -1                      # nothing real left: not cast (saves 6 elixir)
    assert choices(logits, both_dead, bodies=((5.0, 12.0),)).item() == FAR['L']   # an enemy unit by FAR: shoot it
    king = peaked({KING: .9, FAR['R']: .1})[None]
    c = choices(king, (True, True, True)).item()
    _, target = rocket_target_cells(((True, True, True), (), False), 'lattice')
    assert c not in (KING, FAR['R']) and target[c] and not rocket_covers_king(c, 'lattice')   # off the king: a princess
    assert choices(king, both_dead).item() == -1
    c = choices(king, both_dead, kills_king=True).item()                # the logged exception: it finishes the king,
    assert rocket_covers_king(c, 'lattice') and c == choices(king, both_dead, opts=DecisionOptions(  # usual aim kept
        spell_aim='rocket_area')).item()


class SimModel:
    def __init__(self, per_slot):
        self.per_slot = per_slot

    def cell_logits(self, enc, slot):
        return torch.stack([self.per_slot[int(s)] for s in slot])


NAMES = ['knight', 'xbow', 'rocket', 'tesla']


def sim(options, cells, *, card=(0., 5., 9., 1.), allowed=(1, 1, 1, 1), alive=(True, False, True), bodies=(), p=.9,
        kills_king=False, **kw):
    out = decide_batch(SimModel(cells), {'g': torch.zeros(1, 2)}, {'card': torch.tensor([card])}, np.array([p]),
                       np.array([allowed], bool), np.zeros(1, bool), tau=.35, device='cpu', options=options,
                       rngs=[np.random.default_rng(0)], card_names=[NAMES], enemy_alive=[alive],
                       rocket_boards=[(alive, bodies, kills_king)], grid='lattice', **kw)
    return out[0]


def test_sim_not_cast_takes_the_next_card_else_wait():
    cells = {0: peaked({2000: 1.}), 1: peaked({LOCK['R']: 1.}),
             2: peaked({CENTRE['L']: .7, FAR['L']: .2, CENTRE['R']: .1}),
             3: peaked({2100: 1.})}
    assert sim(BLOCK, cells) == dict(play=True, slot=2, cell=CENTRE['R'], why='gate')   # the other princess
    assert sim(BLOCK, cells, alive=(True, True, True)) == dict(play=True, slot=2, cell=CENTRE['L'], why='gate')
    assert sim(BLOCK, cells, alive=(True, False, False)) == dict(play=True, slot=1, cell=LOCK['R'], why='gate')
    assert sim(BLOCK, cells, alive=(True, False, False), allowed=(0, 0, 1, 0)) == \
        dict(play=False, slot=2, cell=-1, why='wait')                                    # never forced
    assert sim(BLOCK, cells, p=.1) == dict(play=False, slot=2, cell=-1, why='wait')


def test_lethal_rocket_overrides_and_both_blocks_compose():
    cells = {0: peaked({2000: 1.}), 1: peaked({LOCK['L']: .7, BACK['L']: .3}),
             2: peaked({CENTRE['L']: .7, FAR['L']: .2, CENTRE['R']: .1}),
             3: peaked({2100: 1.})}
    both = DecisionOptions(lethal_rocket='ot', rocket_dead_target='block', xbow_dead_lane='block')
    lethal = [(raw_towers(0, 0, 400), 0, False)]                     # side 0: enemy L down, enemy R at 400 HP (lethal)
    d = sim(both, cells, t_sec=[200.0], lethal=lethal)
    assert d['why'] == 'lethal_rocket' and d['slot'] == 2 and d['cell'] == cell(14.5, 6.5)
    lethal = [(raw_towers(0, 0, 4000), 0, False)]
    assert sim(both, cells, t_sec=[200.0], lethal=lethal) == dict(play=True, slot=2, cell=CENTRE['R'], why='gate')
    assert sim(both, cells, card=(0., 9., 5., 1.), t_sec=[200.0], lethal=lethal) == \
        dict(play=True, slot=1, cell=BACK['L'], why='gate')          # the X-Bow row keeps its own block


def test_match_kwargs_carries_the_glitch_state_and_king_hp():
    m = SimpleNamespace(tag='a', k=1, cfg={'rocket_dead_target': 'block', 'grid': 'lattice'}, side=0,
                        deck=SimpleNamespace(cards=['rocket']), state={'episode': {'crown_towers': raw_towers(0, 0, 4000,
                                                                                                           king_hp=300)}})
    b = board(2400, alive_l=False)
    b.units = (Unit(1, 0, .5, .8, 1., None, None, 1.), Unit(2, 1, .25, .25, 1., None, None, 1.),
               Unit(3, -1, .75, .5, None, None, None, 1.))
    m._cur = (2400, b, None)
    kw = match_kwargs([m])
    assert kw['decision_options'] == BLOCK and kw['grid'] == 'lattice'
    assert kw['rocket_boards'] == [((True, True, True), ((4.5, 8.0), (13.5, 16.0)), True)]   # dead 0 ticks: alive
    m._cur = (2460, board(2460, alive_l=False), None)
    assert match_kwargs([m])['rocket_boards'][0][0] == (True, False, True)                  # 60 ticks: destroyed


# ---- live GenPilot on the real reader frame, both observer sides -------------------------------------------------------
def dead_lane(side, drop):
    return None if drop is None else ('L' if (drop == 3500) == (side == 0) else 'R')


def rocket_pilot(options, logits, gate_p=.6, card=ROCKET_HAND, seed=0, confirmed=True):
    p = pilot(options, gate_p, card_logits=card, cell=logits, seed=seed)
    if confirmed:
        p._princess_dead_state = CONFIRMED
    return p


def sim_of(d, opts, seed, logits, f, side, state):
    _, names = deck_of(f, side)
    cfg = {k: getattr(opts, k) for k in DecisionOptions.__dataclass_fields__}
    m = SimpleNamespace(cfg=dict(cfg, grid='lattice'), tag='t', k=0, deck=SimpleNamespace(cards=[names[i] for i in HAND]),
                        _cur=(1000, d['bs'], None), rng_decision_options=np.random.default_rng(seed), side=side,
                        state=None, princess_dead_state=state)
    kw = match_kwargs([m])
    return E.live_decide_batch(SimModel({i: logits for i in range(4)}), {'g': torch.zeros(1, 2)},
                               {'card': torch.tensor([ROCKET_HAND])}, [d['p_play']], np.ones((1, 4), bool),
                               np.zeros(1, bool), tau=.35, decision_options=kw.pop('decision_options'), **kw)[0]


CASES = [(side, drop) for side in (0, 1) for drop in (None, 3500, 14500)]


@pytest.mark.parametrize('side,drop', CASES)
def test_live_block_on_both_sides_matches_sim(side, drop):
    lane = dead_lane(side, drop) or 'L'
    other = 'R' if lane == 'L' else 'L'
    logits = peaked({CENTRE[lane]: .5, NEAR[lane]: .2, KING: .15, FAR[lane]: .1, CENTRE[other]: .05})
    f = icebow_frame(1000, side, drop)
    plain = pilot(DecisionOptions(spell_aim='rocket_area'), .6, card_logits=ROCKET_HAND, cell=logits).decide(f)
    opts = DecisionOptions(spell_aim='rocket_area', rocket_dead_target='block')
    p = rocket_pilot(opts, logits)
    new = p.decide(f)
    assert plain['name'] == new['name'] == 'Rocket' and plain['play'] and new['play']
    if drop is None:
        assert new == plain
    else:
        assert new['why'] == 'rocket_dead_target' and 'why' not in plain
        c = cell(new['xy'][0] * 18, new['xy'][1] * 32)                      # the other princess, never the king
        ox, oy = cell_xy(CENTRE[other], 'lattice')
        assert not rocket_covers_king(c, 'lattice') and math.hypot((new['xy'][0] - ox) * 18, (new['xy'][1] - oy) * 32) <= 3
    s = sim_of(new, opts, 0, logits, f, side, CONFIRMED)
    assert (s['play'], s['slot']) == (new['play'], new['hand_pos']) and cell_xy(s['cell'], 'lattice') == new['xy']


@pytest.mark.parametrize('side,drop', [(0, 3500), (1, 14500)])
def test_live_reader_glitch_is_not_a_fallen_tower(side, drop):
    """A princess reading dead for < 60 ticks is still alive for the block: the Rocket lands as with the option off."""
    lane = dead_lane(side, drop)
    logits = peaked({CENTRE[lane]: .6, FAR[lane]: .4})
    p = rocket_pilot(BLOCK, logits, confirmed=False)
    plain = pilot(DecisionOptions(), .6, card_logits=ROCKET_HAND, cell=logits)
    for tick in (1000, 1030, 1059):
        d, e = p.decide(icebow_frame(tick, side, drop)), plain.decide(icebow_frame(tick, side, drop))
        assert d['xy'] == e['xy'] == cell_xy(CENTRE[lane], 'lattice') and 'why' not in d
    d = p.decide(icebow_frame(1060, side, drop))                          # 60 ticks dead: now a fallen tower
    assert d['why'] == 'rocket_dead_target' and d['xy'] != cell_xy(CENTRE[lane], 'lattice')


def test_live_glitch_that_comes_back_resets():
    p = rocket_pilot(BLOCK, peaked({CENTRE['R']: .6, FAR['R']: .4}), confirmed=False)
    p.decide(icebow_frame(1000, 1, 3500))
    p.decide(icebow_frame(1030, 1, None))                                 # read alive again: the run restarts
    d = p.decide(icebow_frame(1080, 1, 3500))
    assert d['xy'] == cell_xy(CENTRE['R'], 'lattice') and 'why' not in d


@pytest.mark.parametrize('side', [0, 1])
def test_live_king_aim_moves_off_the_king_unless_lethal(side, monkeypatch):
    logits = peaked({KING: .7, CENTRE['L']: .2, FAR['R']: .1})
    f = icebow_frame(1000, side)
    d = rocket_pilot(BLOCK, logits).decide(f)
    assert d['play'] and d['name'] == 'Rocket' and d['xy'] == cell_xy(CENTRE['L'], 'lattice')
    assert d['why'] == 'rocket_dead_target'
    monkeypatch.setattr(live_gen_v2, 'rocket_kills_king', lambda towers, s: True)
    d = rocket_pilot(BLOCK, logits).decide(f)
    assert d['xy'] == cell_xy(KING, 'lattice') and d['why'] == 'rocket_king_lethal'


def test_live_not_cast_takes_the_next_card():
    f = icebow_frame(1000, 1, 3500)                                      # side 1: dropped native-3500 princess = my R
    f['entities'] = [e for e in f['entities'] if not (e['kind'] == 13 and e['side'] == 0)]     # both princesses down
    p = rocket_pilot(BLOCK, peaked({CENTRE['R']: .9, NEAR['R']: .1}), card=(0., 5., 9., 1.))
    d = p.decide(f)
    assert d['play'] and d['name'] == 'Xbow' and d['hand_pos'] == 1 and d['why'] == 'rocket_dead_target'


def test_live_wait_keeps_the_plain_rocket_cell():
    p = rocket_pilot(AREA, peaked({CENTRE['R']: .9, FAR['R']: .1}), gate_p=.2, seed=4)
    before = copy.deepcopy(p.rng_decisions.bit_generator.state)
    d = p.decide(icebow_frame(1000, 1, 3500))
    q = pilot(DecisionOptions(spell_aim='rocket_area'), .2, card_logits=ROCKET_HAND,
              cell=peaked({CENTRE['R']: .9, FAR['R']: .1}), seed=4).decide(icebow_frame(1000, 1, 3500))
    assert not d['play'] and d == q and 'why' not in d and p.rng_decisions.bit_generator.state == before


@pytest.mark.parametrize('side', [0, 1])
@pytest.mark.parametrize('tick,gate_p', [(1000, .6), (1000, .2), (3000, .5), (3700, .6)])
def test_live_bundle_block_is_a_no_op_with_every_enemy_tower_standing(side, tick, gate_p):
    """Deployed bundle (+ xbow_dead_lane block; log_aim left out: the stub has no fv >= 4 tokens) +/- rocket block, a
    Rocket aimed at a princess / open ground: identical decisions and decision RNG."""
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
