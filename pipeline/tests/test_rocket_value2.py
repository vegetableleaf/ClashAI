"""--rocket-value V and its sub-options (owner 2026-10-09: the bot never Rocketed a Lava Hound push; iteration 2).

With Rocket affordable and nothing pending, cast it when the best blast centred on MY half holds >= V enemy elixir. The sub-options
change how that value is counted (cost / damage / kill, centre / edge hitbox, lead) and gate it (min elixir, idle, min y). Off
(V = 0) must be byte-identical, RNG included."""
import argparse
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from pipeline import vocab
from pipeline.decision_options import (DecisionOptions, ROCKET_UNIT_DAMAGE, add_arguments, best_rocket_clump, body_value,
                                      config_from_args, decide_batch, match_kwargs, options_from_config, rocket_bodies,
                                      rocket_lands_in, rocket_radius_tiles, rocket_track, rocket_unit_table, rocket_value_cell,
                                      rocket_value_choice, rocket_velocities, unit_values)
from pipeline.live_gen_v2 import GenPilot
from pipeline.model_v3 import cell_xy
from pipeline.obs_contract import Tower, Unit
from pipeline.tests.test_lethal_rocket import live_frame, towers

ON = DecisionOptions(rocket_value=7.0)
DE = dict(rocket_value_mode='damage', rocket_value_hitbox='edge')
NAMES, OK = ['Knight', 'Rocket', 'Log', 'Tesla'], [True] * 4


def unit(name, x_tiles, y_tiles, hp=1.0, side=1):
    return Unit(vocab.unit_id(name), side, x_tiles / 18.0, y_tiles / 32.0, hp, None, None, 1.0)


def board(*units, elixir=7.3, t=100.0, towers=()):
    return SimpleNamespace(units=tuple(units), t_sec=t, my_elixir=elixir, towers=towers, double_elixir=False, overtime=False)


def six_towers(l=1.0, r=1.0, k=1.0):
    mine = (Tower(0, 'king', None, k, True), Tower(0, 'princess', 'L', l, True), Tower(0, 'princess', 'R', r, True))
    return mine + (Tower(1, 'king', None, 1.0, True), Tower(1, 'princess', 'L', 1.0, True), Tower(1, 'princess', 'R', 1.0, True))


def pups(n=6, x=4.0, y=24.0, hp=1.0):
    return [unit('lava_pups', x + .3 * i, y + .2 * i, hp) for i in range(n)]


def best(bs, mode='cost', hitbox='centre', **kw):
    return best_rocket_clump(rocket_bodies(bs, mode), 'lattice', hitbox, **kw)


def test_default_off_flags_and_validation():
    d = DecisionOptions()
    assert d.rocket_value == 0.0 and not d.active and ON.active
    assert not DecisionOptions(rocket_value_mode='damage', rocket_value_lead='on', rocket_value_min_elixir=9.0).active   # inert without V
    ap = argparse.ArgumentParser(); add_arguments(ap)
    assert options_from_config(config_from_args(ap.parse_args([]))) == DecisionOptions()
    assert options_from_config(config_from_args(ap.parse_args(['--rocket-value', '7']))) == ON
    full = ['--rocket-value', '9', '--rocket-value-mode', 'kill', '--rocket-value-hitbox', 'edge', '--rocket-value-lead', 'on',
            '--rocket-value-idle', 'on', '--rocket-value-min-elixir', '9', '--rocket-value-min-y', '21', '--rocket-value-threat', 'on']
    assert options_from_config(config_from_args(ap.parse_args(full))) == DecisionOptions(
        rocket_value=9.0, rocket_value_mode='kill', rocket_value_hitbox='edge', rocket_value_lead='on', rocket_value_idle='on',
        rocket_value_min_elixir=9.0, rocket_value_min_y=21.0, rocket_value_threat='on')
    assert options_from_config(config_from_args(ap.parse_args(['--rocket-value', '9', '--rocket-value-max-left', '3']))).rocket_value_max_left == 3.0
    for kw in (dict(rocket_value=-1.0), dict(rocket_value=float('nan')), dict(rocket_value=float('inf')), dict(rocket_value_mode='x'),
               dict(rocket_value_hitbox='x'), dict(rocket_value_lead='yes'), dict(rocket_value_idle='x'),
               dict(rocket_value_min_elixir=11.0), dict(rocket_value_min_elixir=-1.0), dict(rocket_value_min_y=10.0),
               dict(rocket_value_min_y=40.0), dict(rocket_value_min_y=float('nan')), dict(rocket_value_max_left=-1.0), dict(rocket_value_threat='x')):
        with pytest.raises(ValueError):
            DecisionOptions(**kw)


def test_value_table_from_catalog_cost_over_bodies():
    v = unit_values()
    assert v['lava_hound'] == 7 and v['golem'] == 8 and v['balloon'] == 5 and v['x_bow'] == 6
    assert v['minions'] == 1 and v['skeleton_army'] == pytest.approx(3 / 15) and v['skeletons'] == pytest.approx(1 / 3)
    assert v['skeleton_dragons'] == 2 and v['lava_pups'] == pytest.approx(7 / 6) and v['golemite'] == 4
    assert v['elixir_golemite'] == 1.5 and v['elixir_blob'] == .75
    hound = rocket_unit_table()['lava_hound']
    assert hound[1] == 1399 and hound[2] == 0.75                         # catalog hitpoints and collision radius (tiles)
    assert rocket_unit_table()['balloon'][2] == 0.5 and rocket_unit_table()['skeleton_dragons'][2] == 0.9


def test_body_value_scales_with_hp_resolves_variants_and_skips_spells():
    assert body_value(vocab.unit_id('lava_hound')) == 7 and body_value(vocab.unit_id('lava_hound'), .5) == 3.5
    assert body_value(vocab.unit_id('balloon'), None) == 5
    assert body_value(vocab.unit_id('knight_evo')) == 3 == body_value(vocab.unit_id('knight_hero'))
    assert body_value(vocab.unit_id('rocket')) == 0 == body_value(vocab.unit_id('fireball_aoe'))
    assert body_value(vocab.unit_id('golden_knight_ability')) == 0


def test_modes_value_what_the_rocket_does_not_what_the_card_cost():
    def one(name, hp, mode):
        rows = rocket_bodies(board(unit(name, 9, 24, hp)), mode)
        return float(rows[0, 3]) if len(rows) else 0.0
    assert ROCKET_UNIT_DAMAGE == 580
    # cost: cost / bodies x hp fraction, whatever the Rocket does
    assert one('giant', 1.0, 'cost') == 5 and one('giant', .5, 'cost') == 2.5
    # damage: min(580, hp now) / max hp of it. Giant 1550 hp: 580/1550 of 5; Skeleton Dragon (219 hp, 2 elixir each) dies in full
    assert one('giant', 1.0, 'damage') == pytest.approx(5 * 580 / 1550)
    assert one('skeleton_dragons', 1.0, 'damage') == 2 and one('skeleton_dragons', .5, 'damage') == 1
    assert one('balloon', 1.0, 'damage') == pytest.approx(5 * 580 / 655)               # survives with 11 %
    assert one('balloon', .5, 'damage') == pytest.approx(2.5)                          # 327 hp: killed, its remaining half counts
    assert one('lava_hound', 1.0, 'damage') == pytest.approx(7 * 580 / 1399)
    # kill: only a body the Rocket kills outright counts, at its remaining value
    assert one('giant', 1.0, 'kill') == 0 and one('balloon', 1.0, 'kill') == 0 and one('balloon', .5, 'kill') == 2.5
    assert one('skeleton_dragons', 1.0, 'kill') == 2
    assert one('lava_hound', .13, 'kill') == pytest.approx(7 * .13)                   # 182 hp: the nearly dead Hound of 011626
    # unknown hp = full; spells / markers / my own bodies contribute nothing
    assert one('giant', None, 'damage') == one('giant', 1.0, 'damage')
    assert len(rocket_bodies(board(unit('balloon', 9, 20, side=0), unit('rocket', 9, 20)), 'cost')) == 0


def test_six_lava_pups_are_the_hound_seven_not_forty_two():
    assert rocket_bodies(board(*pups()), 'cost')[:, 3].sum() == pytest.approx(7.0)


def test_only_enemy_bodies_count_unknown_side_included():
    b = rocket_bodies(board(unit('balloon', 9, 20, side=0), unit('giant', 9, 20, side=-1), unit('knight', 9, 20)), 'cost')
    assert sorted(b[:, 3]) == [3.0, 5.0]


def test_best_blast_my_half_only_and_eligible_cells_cover_the_whole_clump():
    R = rocket_radius_tiles()
    value, ok = best(board(*pups()))
    assert value == pytest.approx(7.0)
    xs, ys = np.meshgrid(np.arange(36) * .5, np.arange(64) * .5)
    x, y = xs.reshape(-1), ys.reshape(-1)
    assert ok.any() and (y[ok] >= 16).all()
    for bx, by in [(4.0 + .3 * i, 24.0 + .2 * i) for i in range(6)]:
        assert (np.hypot(x[ok] - bx, y[ok] - by) <= R + 1e-9).all()
    assert best(board(*pups(y=8.0))) == (0.0, None)                                   # the same push on the enemy half: out of range
    assert best(board(unit('balloon', 9, 14.5), unit('giant', 9, 17.2)))[0] == 10.0   # centre at y >= 16 still covers y 14.5
    assert best(board(unit('balloon', 9, 12.0)))[0] == 0.0
    assert best_rocket_clump(np.zeros((0, 7)), 'lattice') == (0.0, None)


def test_best_blast_picks_the_biggest_clump_not_the_first():
    spread = [unit('giant', 2, 20), unit('balloon', 9, 20), unit('knight', 9.5, 21), unit('knight', 9, 22)]
    value, ok = best(board(*spread))
    assert value == 11.0 and not ok[40 * 36 + 4]


def test_edge_hitbox_covers_what_the_centre_rule_misses():
    # two Balloons (collision radius 0.5) 4.8 tiles apart: no blast centre is within 2.0 of both, one within 2.0 + 0.5 of both
    two = board(unit('balloon', 6.6, 22), unit('balloon', 11.4, 22))
    assert best(two, hitbox='centre')[0] == 5.0
    value, ok = best(two, hitbox='edge')
    assert value == 10.0 and ok.any()
    xs, ys = np.meshgrid(np.arange(36) * .5, np.arange(64) * .5)
    x, y = xs.reshape(-1), ys.reshape(-1)
    assert (np.hypot(x[ok] - 6.6, y[ok] - 22) <= rocket_radius_tiles() + .5 + 1e-9).all()
    assert (np.hypot(x[ok] - 11.4, y[ok] - 22) <= rocket_radius_tiles() + .5 + 1e-9).all()
    # the bigger hitbox of the Lava Hound (0.75) reaches farther than a Knight's (0.5): same gap, only the Hound is covered
    gap = lambda name: best(board(unit(name, 5.8, 22), unit(name, 11.2, 22)), hitbox='edge')[0] / body_value(vocab.unit_id(name))
    assert gap('lava_hound') == 2 and gap('knight') == 1


def test_011626_cluster_fires_with_the_damage_value_not_the_cost_sum():
    # live_play_20261009_011626 tick 3884 (board frame): Hound at 13.7 % hp, Mega Minion 74 %, one Skeleton Dragon 77 %, Balloon 58 %
    cluster = board(unit('lava_hound', 3.7, 21.2, .137), unit('mega_minion', 4.8, 21.0, .74), unit('skeleton_dragons', 5.2, 22.3, .77),
                    unit('balloon', 4.1, 24.6, .58), elixir=7.8)
    assert best(cluster, 'cost', 'centre')[0] < 9.0                                   # the iteration-1 reading
    assert best(cluster, 'damage', 'edge')[0] == pytest.approx(7.61, abs=.05)
    full = ON.__class__(rocket_value=7.0, **DE)
    assert rocket_value_choice(full, NAMES, OK, cluster, 'lattice')[2] == pytest.approx(7.61, abs=.05)
    assert rocket_value_choice(DecisionOptions(rocket_value=9.0, **DE), NAMES, OK, cluster, 'lattice') is None


def test_max_left_refuses_a_blast_that_leaves_a_tank_standing():
    # a Golem (hp 2000 -> keeps 8 x (1 - 580/2000) = 5.68) with three Skeleton Dragons (2 each, all killed)
    push = board(unit('golem', 4.0, 22.0), unit('skeleton_dragons', 4.5, 22.5), unit('skeleton_dragons', 3.5, 22.5),
                 unit('skeleton_dragons', 4.0, 23.0))
    rows = rocket_bodies(push, 'damage')
    assert rows[:, 5].sum() == pytest.approx(8 * (2000 - 580) / 2000)                    # only the Golem keeps value
    free = DecisionOptions(rocket_value=7.0, rocket_value_mode='damage')
    assert rocket_value_choice(free, NAMES, OK, push, 'lattice')[2] == pytest.approx(8 * 580 / 2000 + 6)
    assert rocket_value_choice(DecisionOptions(rocket_value=7.0, rocket_value_mode='damage', rocket_value_max_left=5.0), NAMES, OK,
                               push, 'lattice') is None
    assert rocket_value_choice(DecisionOptions(rocket_value=7.0, rocket_value_mode='damage', rocket_value_max_left=5.7), NAMES, OK,
                               push, 'lattice') is not None
    # kill mode: the Golem counts nothing, need not be covered, but still counts as left
    kill = DecisionOptions(rocket_value=6.0, rocket_value_mode='kill')
    value, ok, left = best_rocket_clump(rocket_bodies(push, 'kill'), 'lattice', 'centre', None, 16.0, True)
    assert value == 6.0 and left == pytest.approx(8 * (2000 - 580) / 2000) and ok.any()
    assert rocket_value_choice(kill, NAMES, OK, push, 'lattice')[2] == 6.0
    assert rocket_value_choice(DecisionOptions(rocket_value=6.0, rocket_value_mode='kill', rocket_value_max_left=3.0), NAMES, OK, push, 'lattice') is None


def test_threat_gate_fires_only_while_a_tower_of_mine_is_under_fire_with_a_body_near_it():
    on = DecisionOptions(rocket_value=7.0, rocket_value_threat='on')
    holder = SimpleNamespace()
    ask = lambda t, l: rocket_value_choice(on, NAMES, OK, board(*pups(), t=t, towers=six_towers(l=l)), 'lattice', holder=holder)
    assert ask(100.0, 1.0) is None                                                      # nobody hit my tower
    assert ask(100.5, 0.9) is not None                                                  # the left princess just lost HP, the pups are on it
    assert ask(101.5, 0.9) is not None and ask(102.4, 0.9) is not None                  # within the 2 s window
    assert ask(103.0, 0.9) is None                                                      # window over, no new loss
    assert ask(103.5, 0.8) is not None                                                  # lost again
    far = [unit('lava_pups', 4.0 + .3 * i, 17.0, 1.0) for i in range(6)]               # the same loss, the pups are 8.5 tiles from the tower
    h2 = SimpleNamespace()
    rocket_value_choice(on, NAMES, OK, board(*far, t=100.0, towers=six_towers()), 'lattice', holder=h2)
    assert rocket_value_choice(on, NAMES, OK, board(*far, t=100.5, towers=six_towers(l=.9)), 'lattice', holder=h2) is None
    assert rocket_value_choice(on, NAMES, OK, board(*pups(), towers=six_towers()), 'lattice') is None      # no holder: cannot know
    # the state is kept at EVERY decision, with no Rocket affordable too
    h3 = SimpleNamespace()
    rocket_value_choice(on, NAMES, [True, False, True, True], board(*pups(), t=100.0, towers=six_towers()), 'lattice', holder=h3)
    assert rocket_value_choice(on, NAMES, OK, board(*pups(), t=100.5, towers=six_towers(l=.9)), 'lattice', holder=h3) is not None
    off = DecisionOptions(rocket_value=7.0)
    assert rocket_value_choice(off, NAMES, OK, board(*pups(), towers=six_towers()), 'lattice') is not None      # threat off: ignored


def test_choice_threshold_slot_pending_and_default_off():
    b = board(*pups())
    assert rocket_value_choice(ON, NAMES, OK, b, 'lattice')[0] == 1
    assert rocket_value_choice(DecisionOptions(rocket_value=7.1), NAMES, OK, b, 'lattice') is None
    assert rocket_value_choice(DecisionOptions(), NAMES, OK, b, 'lattice') is None
    assert rocket_value_choice(ON, NAMES, OK, b, 'lattice', pending=True) is None
    assert rocket_value_choice(ON, NAMES, [True, False, True, True], b, 'lattice') is None
    assert rocket_value_choice(ON, ['Knight', 'Xbow', 'Log', 'Tesla'], OK, b, 'lattice') is None
    assert rocket_value_choice(ON, NAMES, OK, board(*pups(hp=.5)), 'lattice') is None
    assert rocket_value_choice(ON, NAMES, OK, board(unit('x_bow', 9, 12)), 'lattice') is None


def test_gates_min_elixir_idle_and_min_y():
    b = board(*pups(), elixir=7.3)
    assert rocket_value_choice(DecisionOptions(rocket_value=7.0, rocket_value_min_elixir=7.3), NAMES, OK, b, 'lattice') is not None
    assert rocket_value_choice(DecisionOptions(rocket_value=7.0, rocket_value_min_elixir=7.4), NAMES, OK, b, 'lattice') is None
    idle = DecisionOptions(rocket_value=7.0, rocket_value_idle='on')
    assert rocket_value_choice(idle, NAMES, OK, b, 'lattice', playing=False) is not None
    assert rocket_value_choice(idle, NAMES, OK, b, 'lattice', playing=True) is None             # the model plays: displaces nothing
    assert rocket_value_choice(ON, NAMES, OK, b, 'lattice', playing=True) is not None           # idle off: the gate is ignored
    deep = DecisionOptions(rocket_value=7.0, rocket_value_min_y=26.0)
    assert rocket_value_choice(deep, NAMES, OK, board(*pups(y=20.0)), 'lattice') is None       # a blast centred at y >= 26 cannot reach y 20
    assert rocket_value_choice(deep, NAMES, OK, board(*pups(y=27.0)), 'lattice') is not None
    _, ok = best(board(*pups(y=27.0)), min_y=26.0)
    xs, ys = np.meshgrid(np.arange(36) * .5, np.arange(64) * .5)
    assert ok is not None and (ys.reshape(-1)[ok] >= 26.0).all()


def test_lead_moves_the_blast_to_where_the_bodies_will_be():
    holder = SimpleNamespace()
    old = rocket_bodies(board(unit('giant', 4.0, 19.0), unit('knight', 4.5, 19.5)), 'cost')
    rocket_track(holder, 100, old)                                                   # 1 s earlier, 1 tile behind
    now = rocket_bodies(board(unit('giant', 4.0, 20.0), unit('knight', 4.5, 20.5)), 'cost')
    hist = rocket_track(holder, 120, now)
    vel = rocket_velocities(hist, 120, now)
    assert np.allclose(vel, [[0, .05], [0, .05]])                                    # 1 tile in 20 ticks, +y (toward my side)
    _, ok_static = best_rocket_clump(now, 'lattice')
    value, ok_lead = best_rocket_clump(now, 'lattice', 'centre', (120, hist, 'on'))
    assert value == 8.0
    ys = np.meshgrid(np.arange(36) * .5, np.arange(64) * .5)[1].reshape(-1)
    shift = ys[ok_lead].mean() - ys[ok_static].mean()
    horizon = rocket_lands_in(4.25, 22.0)
    assert shift == pytest.approx(.05 * horizon, abs=1.0) and shift > .5
    assert rocket_lands_in(9.0, 28.65) == 2 + 0 + 2 and rocket_lands_in(9.0, 18.15) == 2 + 30 + 2    # king tower: no flight; 10.5 tiles
    # a swarm of identical bodies moves as a group; no history / a new class: still
    assert not rocket_velocities([], 120, now).any() and not rocket_velocities(hist, 120, rocket_bodies(board(unit('witch', 4, 20)), 'cost')).any()
    assert not rocket_velocities([(118, old)], 120, now).any()                       # a snapshot < 6 ticks old is not a baseline


def test_lead_drift_and_blend_walk_toward_my_side_at_the_catalog_speed():
    now = rocket_bodies(board(unit('giant', 4.0, 20.0), unit('knight', 4.5, 20.5)), 'cost')
    assert rocket_unit_table()['giant'][3] == pytest.approx(45 / 1200) and rocket_unit_table()['knight'][3] == pytest.approx(.05)
    ys = np.meshgrid(np.arange(36) * .5, np.arange(64) * .5)[1].reshape(-1)
    _, ok_static = best_rocket_clump(now, 'lattice')
    horizon = rocket_lands_in(4.25, 22.0)
    for mode in ('drift', 'blend'):                                                  # blend with no history = drift
        value, ok = best_rocket_clump(now, 'lattice', 'centre', (120, [], mode))
        assert value == 8.0 and ys[ok].mean() - ys[ok_static].mean() == pytest.approx(.044 * horizon, abs=1.0)
    holder = SimpleNamespace()                                                       # blend: a body that moves keeps its measured velocity
    rocket_track(holder, 100, rocket_bodies(board(unit('giant', 4.0, 19.0), unit('knight', 4.5, 20.5)), 'cost'))
    hist = rocket_track(holder, 120, now)
    value, ok = best_rocket_clump(now, 'lattice', 'centre', (120, hist, 'blend'))
    assert value == 8.0 and ok.any()
    opts = DecisionOptions(rocket_value=7.0, rocket_value_lead='drift')
    assert rocket_value_choice(opts, NAMES, OK, board(*pups()), 'lattice', holder=None) is not None      # drift needs no holder
    assert not hasattr(SimpleNamespace(), 'rv_hist')


def test_lead_history_is_kept_short_and_per_holder():
    holder = SimpleNamespace()
    for tick in range(0, 400, 10):
        rocket_track(holder, tick, rocket_bodies(board(unit('giant', 4.0, 20.0)), 'cost'))
    assert holder.rv_hist[0][0] >= 400 - 10 - 40 and len(holder.rv_hist) <= 5
    other = SimpleNamespace()
    assert rocket_track(other, 5, np.zeros((0, 7))) == [] and len(other.rv_hist) == 1


def test_aim_follows_the_model_mass_among_the_eligible_cells_only():
    _, ok = best(board(*pups()))
    idx = np.flatnonzero(ok)
    peak = int(idx[7])
    logits = torch.full((2304,), -9.0)
    logits[peak] = 3.0
    for hot in (None, 5 * 36 + 5):
        if hot:
            logits[hot] = 50.0
        cell = rocket_value_cell(logits, ok)
        (cx, cy), (px, py) = cell_xy(cell, 'lattice'), cell_xy(peak, 'lattice')
        assert ok[cell] and np.hypot((cx - px) * 18, (cy - py) * 32) <= rocket_radius_tiles()
    assert rocket_value_cell(torch.zeros(2304), ok) in set(map(int, idx))
    assert rocket_value_cell(torch.full((2304,), -torch.inf), ok) == int(idx[0])


class Model:
    def cell_logits(self, enc, slot):
        return torch.zeros(len(slot), 2304)


def sim_args(n):
    return dict(enc={'g': torch.zeros(n, 2)}, heads={'card': torch.tensor([[9., 0, 0, 0]] * n)}, p=np.full(n, .1),
                allowed=np.ones((n, 4), bool), stalled=np.zeros(n, bool))


def test_sim_decide_batch_overrides_only_qualifying_rows_and_lethal_wins():
    a = sim_args(3)
    names = [['knight', 'rocket', 'the-log', 'tesla']] * 3
    boards = [(board(*pups()), False, SimpleNamespace()), (board(unit('knight', 9, 24)), False, SimpleNamespace()),
              (board(*pups()), True, SimpleNamespace())]
    kw = dict(tau=.35, device='cpu', rngs=[None] * 3, card_names=names, grid='lattice')
    out = decide_batch(Model(), **a, options=ON, rocket_value=boards, **kw)
    base = decide_batch(Model(), **a, options=DecisionOptions(spell_aim='rocket_area'), **kw)
    assert out[0]['why'] == 'rocket_value' and out[0]['play'] and out[0]['slot'] == 1
    assert out[1:] == base[1:]
    x, y = cell_xy(out[0]['cell'], 'lattice')
    assert y * 32 >= 16 and np.hypot(x * 18 - 4.75, y * 32 - 24.5) <= rocket_radius_tiles() + 1
    with pytest.raises(ValueError, match='rocket_value'):
        decide_batch(Model(), **a, options=ON, rocket_value=None, **kw)
    both = DecisionOptions(rocket_value=7.0, lethal_rocket='ot')
    lethal = [(towers(0, 453, 1092), 0, False)] * 3
    out = decide_batch(Model(), **a, options=both, rocket_value=boards, lethal=lethal, t_sec=[200.0] * 3, **kw)
    assert out[0]['why'] == 'lethal_rocket'


def test_sim_idle_option_follows_the_gate_decision_row_by_row():
    a = sim_args(2)
    a['p'] = np.array([.1, .9])                                                      # row 0 waits, row 1 plays (p > tau)
    boards = [(board(*pups()), False, SimpleNamespace())] * 2
    kw = dict(tau=.35, device='cpu', rngs=[None] * 2, card_names=[['knight', 'rocket', 'the-log', 'tesla']] * 2, grid='lattice')
    out = decide_batch(Model(), **a, options=DecisionOptions(rocket_value=7.0, rocket_value_idle='on'), rocket_value=boards, **kw)
    assert out[0]['why'] == 'rocket_value' and out[1]['why'] == 'gate'


def test_off_is_byte_identical_to_main_rng_included():
    a = sim_args(2)
    rngs = [np.random.default_rng(5), np.random.default_rng(5)]
    kw = dict(tau=.35, device='cpu', card_names=[['knight', 'rocket', 'the-log', 'tesla']] * 2, grid='lattice')
    plain = DecisionOptions(spell_aim='rocket_area', card_choice='filtered', card_ratio=.01)
    sub = DecisionOptions(spell_aim='rocket_area', card_choice='filtered', card_ratio=.01, rocket_value_mode='kill',
                          rocket_value_lead='on', rocket_value_min_elixir=9.0)      # sub-options without V: inert
    x = decide_batch(Model(), **a, options=plain, rngs=rngs[:1] * 2, **kw)
    y = decide_batch(Model(), **a, options=sub, rngs=rngs[1:] * 2, rocket_value=None, **kw)
    assert x == y and rngs[0].bit_generator.state == rngs[1].bit_generator.state
    m = SimpleNamespace(tag='a', k=1, cfg={'grid': 'lattice'}, side=0, deck=SimpleNamespace(cards=['rocket']), state={})
    assert match_kwargs([m]) == {}
    assert not hasattr(m, 'rv_hist')


def test_match_kwargs_hands_over_the_decision_board_pending_and_the_match():
    bs = board(*pups())
    m = SimpleNamespace(tag='a', k=1, cfg={'rocket_value': 7.0, 'grid': 'lattice'}, side=0,
                        deck=SimpleNamespace(cards=['rocket']), state={}, _cur=(3700, bs, None))
    kw = match_kwargs([m])
    assert kw['grid'] == 'lattice' and kw['rocket_value'] == [(bs, False, m)]
    m.pending = (3720, .5, {})
    assert match_kwargs([m])['rocket_value'][0][1] is True


def live_pilot(options, bs, p_gate=-3.):
    pilot = object.__new__(GenPilot)
    pilot.decision_options, pilot.rng_decisions = options, np.random.default_rng(0)
    pilot.dev, pilot.grid, pilot.gate_tau, pilot.public_audit = torch.device('cpu'), 'lattice', .35, False
    pilot.rv_hist = None
    names = ['Knight', 'Rocket', 'Log', 'Tesla', 'Xbow', 'IceWizard', 'Skeletons', 'Tornado']
    info = dict(hand=[(1, 0), (2, 0), (3, 0), (4, 0)], costs=[3, 6, 2, 4], el_int=7, names=names,
                hand_deck_indices=[0, 1, 2, 3], bs=bs)
    pilot.row = lambda frame: ({}, info)
    pilot.stalled = lambda frame, el: False
    pilot.guard_cells = lambda frame, d, logits: logits

    class LiveModel:
        def __call__(self, b, card=None, form=None):
            if card is not None:
                return {'cell': torch.zeros(1, 2304)}
            return {'gate': torch.tensor([p_gate]), 'card': torch.tensor([[9., 0, 0, 0]])}
    pilot.model = LiveModel()
    return pilot


def test_live_fires_on_the_clump_whatever_the_gate_and_matches_sim():
    bs = board(*pups())
    d = live_pilot(ON, bs).decide(live_frame(0, 1092, 1092))
    assert d['play'] and d['name'] == 'Rocket' and d['hand_pos'] == 1 and d['why'] == 'rocket_value'
    assert d['rocket_value'] == pytest.approx(7.0)
    slot, ok, _ = rocket_value_choice(ON, NAMES, OK, bs, 'lattice')
    assert slot == 1
    assert d['xy'] == cell_xy(rocket_value_cell(torch.zeros(1, 2304), ok), 'lattice')


def test_live_idle_option_uses_the_gate_after_the_hazard_draw():
    bs = board(*pups())
    idle = DecisionOptions(rocket_value=7.0, rocket_value_idle='on')
    waiting = live_pilot(idle, bs, p_gate=-3.).decide(live_frame(0, 1092, 1092))      # p << tau: the model waits
    playing = live_pilot(idle, bs, p_gate=3.).decide(live_frame(0, 1092, 1092))       # p >> tau: the model plays
    assert waiting['why'] == 'rocket_value' and playing.get('why') != 'rocket_value'


def test_live_lead_history_is_kept_on_every_decision_and_reset_per_match():
    lead = DecisionOptions(rocket_value=7.0, rocket_value_lead='on')
    pilot = live_pilot(lead, board(unit('giant', 4.0, 20.0)))
    pilot.decide(live_frame(0, 1092, 1092))
    assert len(pilot.rv_hist) == 1
    pilot.reset_match = lambda: None                                                  # GenPilot.reset_match needs the full pilot
    pilot.rv_hist = None
    assert pilot.rv_hist is None


def test_live_lethal_has_priority_and_unchanged_when_the_rule_does_not_hold():
    bs = board(*pups())
    both = DecisionOptions(rocket_value=7.0, lethal_rocket='ot')
    bs.t_sec = 215.2
    assert live_pilot(both, bs).decide(live_frame(0, 453, 1092))['why'] == 'lethal_rocket'
    quiet = board(unit('knight', 9, 24))
    plain = DecisionOptions(spell_aim='rocket_area', card_choice='filtered', card_ratio=.01)
    a = live_pilot(DecisionOptions(**{**vars(plain), 'rocket_value': 7.0}), quiet, p_gate=3.)
    b = live_pilot(plain, quiet, p_gate=3.)
    da, db = a.decide(live_frame(0, 1092, 1092)), b.decide(live_frame(0, 1092, 1092))
    assert da == db and 'why' not in da
    assert a.rng_decisions.bit_generator.state == b.rng_decisions.bit_generator.state


# ---- rocket_tornado: the combo on a clump too spread for one blast (live only; the follow-up tap API is stubbed) ----------------------
from pipeline.decision_options import (LIVE_FOLLOW_MIN_GAP_TICKS, PULL_LANDS_FROM, PULL_LANDS_TO, best_tornado_centre,  # noqa: E402
                                      cell_centres_tiles, rocket_flight_ticks, rocket_tornado_choice, rocket_tornado_plan, rocket_tornado_timing,
                                      tornado_radius_tiles)

COMBO = DecisionOptions(rocket_value=7.0, rocket_tornado='on')
HAND = ['Knight', 'Rocket', 'Log', 'Tornado']


def split_pups(y=22.0, gap=3.0):
    """Six pups in two tight groups 2 x gap apart: no single 2-tile blast holds more than 3 (3.5), the Tornado pull holds all 6 (7.0)."""
    return [unit('lava_pups', 9 - gap + .3 * i, y) for i in range(3)] + [unit('lava_pups', 9 + gap + .3 * i, y) for i in range(3)]


def test_combo_flag_validation_and_default_off():
    assert DecisionOptions().rocket_tornado == 'off' and COMBO.active
    for bad in ('yes', 'ON', ''):
        with pytest.raises(ValueError):
            DecisionOptions(rocket_value=7.0, rocket_tornado=bad)
    with pytest.raises(ValueError, match='rocket_value'):
        DecisionOptions(rocket_tornado='on')
    ap = argparse.ArgumentParser(); add_arguments(ap)
    assert options_from_config(config_from_args(ap.parse_args(['--rocket-value', '7', '--rocket-tornado', 'on']))) == COMBO


@pytest.mark.parametrize('d,flight', [(5, 16), (7, 22), (9, 28), (11, 33), (13, 39), (15, 45), (17, 51), (20, 59), (23, 68)])
def test_rocket_flight_matches_the_royalesim_measurement(d, flight):
    assert abs(rocket_flight_ticks(9.0, 28.65 - d) - flight) <= 1                    # straight ahead of my king tower


def test_follow_up_timing_table_at_the_live_gap_and_the_sim_gap():
    x, y = cell_centres_tiles('lattice')
    mine = y >= 16.0
    share = lambda gap: np.mean([rocket_tornado_plan(cx, cy, gap) is not None for cx, cy in zip(x[mine], y[mine])])
    assert share(LIVE_FOLLOW_MIN_GAP_TICKS) == pytest.approx(.781, abs=.02)           # 78.1 % of my-half cells (window_table2.txt)
    assert share(30) == pytest.approx(.029, abs=.01)                                  # the SIM pending lock: 2.9 %
    assert rocket_tornado_plan(9.0, 22.0) == (4, 9)                                   # a clump 6.7 tiles from my king: 4..9 ticks after the Rocket
    assert rocket_tornado_plan(9.0, 17.0) == (4, 23)
    assert rocket_tornado_plan(9.0, 26.0) is None                                     # 2.7 tiles from my king: the Rocket lands too early
    lo, hi = rocket_tornado_plan(3.5, 17.0)
    assert hi == rocket_flight_ticks(3.5, 17.0) - PULL_LANDS_FROM and lo == max(4, rocket_flight_ticks(3.5, 17.0) - PULL_LANDS_TO)


def test_tornado_centre_covers_the_split_clump_a_single_blast_cannot():
    bodies = rocket_bodies(board(*split_pups()), 'cost')
    assert best_rocket_clump(bodies, 'lattice')[0] == pytest.approx(3.5)
    value, cell = best_tornado_centre(bodies, 'lattice')
    assert value == pytest.approx(7.0) and tornado_radius_tiles() == 5.5
    x, y = cell_centres_tiles('lattice')
    assert abs(x[cell] - 9.0) <= 1.0 and 16 <= y[cell]


def test_combo_choice_conditions():
    bs = board(*split_pups(), elixir=9.5)
    ok = [True, True, True, True]
    hit = rocket_tornado_choice(COMBO, HAND, ok, bs, 'lattice')
    assert hit[0] == 1 and hit[1] == 3 and hit[4] == pytest.approx(7.0) and hit[3][1] - hit[3][0] + 1 >= 5
    assert rocket_tornado_choice(COMBO, HAND, ok, board(*split_pups(), elixir=8.0), 'lattice') is None       # 6 now + 3 later needs ~9
    assert rocket_tornado_choice(COMBO, HAND, ok, bs, 'lattice', pending=True) is None
    assert rocket_tornado_choice(COMBO, ['Knight', 'Rocket', 'Log', 'Tesla'], ok, bs, 'lattice') is None     # no Tornado in hand
    assert rocket_tornado_choice(COMBO, HAND, [True, False, True, True], bs, 'lattice') is None              # Rocket not affordable
    assert rocket_tornado_choice(DecisionOptions(rocket_value=7.0), HAND, ok, bs, 'lattice') is None         # combo off
    assert rocket_tornado_choice(DecisionOptions(rocket_value=7.1, rocket_tornado='on'), HAND, ok, bs, 'lattice') is None   # pull holds 7.0
    assert rocket_tornado_choice(COMBO, HAND, ok, board(*pups(), elixir=9.5), 'lattice') is None             # one blast holds it: the lone rule's
    assert rocket_tornado_choice(COMBO, HAND, ok, board(*split_pups(y=27.0), elixir=9.5), 'lattice') is None  # too close to my king: no window
    gated = DecisionOptions(rocket_value=7.0, rocket_tornado='on', rocket_value_min_elixir=9.9)
    assert rocket_tornado_choice(gated, HAND, ok, bs, 'lattice') is None


def combo_pilot(options, bs, calls):
    pilot = live_pilot(options, bs)
    pilot.row = lambda frame: ({}, dict(hand=[(1, 0), (2, 0), (3, 0), (4, 0)], costs=[3, 6, 2, 3], el_int=9, names=[
        'Knight', 'Rocket', 'Log', 'Tornado', 'Xbow', 'IceWizard', 'Skeletons', 'Tesla'], hand_deck_indices=[0, 1, 2, 3], bs=bs))

    def plan_follow_up(frame, first, name, xy, after_ticks, within_ticks=20, **kw):
        calls.append((first['name'], name, xy, after_ticks, within_ticks))
        return dict(play=True, name=name, xy=xy, follow=dict(after_ticks=after_ticks, within_ticks=within_ticks))
    pilot.plan_follow_up = plan_follow_up
    return pilot


def test_live_combo_rocket_now_tornado_planned_in_the_middle_of_the_window():
    calls = []
    bs = board(*split_pups(), elixir=9.5)
    d = combo_pilot(COMBO, bs, calls).decide(live_frame(0, 1092, 1092))
    assert d['play'] and d['name'] == 'Rocket' and d['why'] == 'rocket_tornado' and d['hand_pos'] == 1
    lo, hi = d['rocket_tornado_window']
    (first, name, xy, after, within), = calls
    assert (first, name) == ('Rocket', 'Tornado') and (after, within) == rocket_tornado_timing((lo, hi)) and xy == d['xy']
    assert d['follow_ups'][0]['follow']['after_ticks'] == after
    # the lone rule has priority where one blast holds it; the combo is silent without a clump / off
    calls.clear()
    d = combo_pilot(COMBO, board(*pups(), elixir=9.5), calls).decide(live_frame(0, 1092, 1092))
    assert d['why'] == 'rocket_value' and not calls and 'follow_ups' not in d
    d = combo_pilot(DecisionOptions(rocket_value=7.0), bs, calls).decide(live_frame(0, 1092, 1092))
    assert d.get('why') != 'rocket_tornado'
    assert not calls


def test_sim_combo_rocket_now_tornado_as_a_follow_up_spec_on_deck_slots():
    from pipeline.e1_eval import follow_up_spec
    deck = ['knight', 'rocket', 'the-log', 'tornado', 'x-bow', 'ice-wizard', 'skeletons', 'tesla']
    hand_ids = (vocab.unit_id('rocket'), vocab.unit_id('tornado'), vocab.unit_id('knight'), vocab.unit_id('the_log'))
    bs = board(*split_pups(), elixir=9.5)
    bs.my_hand = hand_ids
    allowed = np.zeros((1, 8), bool); allowed[0, [0, 1, 2]] = True                      # Tornado (deck slot 3) is not affordable NOW
    a = sim_args(1)
    a['allowed'] = allowed; a['heads'] = {'card': torch.tensor([[9., 0, 0, 0, 0, 0, 0, 0]])}
    kw = dict(tau=.35, device='cpu', rngs=[None], card_names=[deck], grid='lattice')
    out = decide_batch(Model(), **a, options=COMBO, rocket_value=[(bs, False, SimpleNamespace())], **kw)[0]
    assert out['why'] == 'rocket_tornado' and out['play'] and out['slot'] == 1
    hit = rocket_tornado_choice(COMBO, deck, allowed[0], bs, 'lattice')
    after, within = rocket_tornado_timing(hit[3])
    assert out['cell'] == hit[2] and out['follow_ups'] == [follow_up_spec(3, hit[2], after, within)]
    bs.my_hand = (vocab.unit_id('rocket'), vocab.unit_id('knight'), vocab.unit_id('the_log'), vocab.unit_id('x_bow'))   # Tornado not in hand
    out = decide_batch(Model(), **a, options=COMBO, rocket_value=[(bs, False, SimpleNamespace())], **kw)[0]
    assert out.get('why') != 'rocket_tornado' and 'follow_ups' not in out
    # the lone rule keeps priority, and a threat / idle gate holds the combo back
    bs.my_hand = hand_ids
    gated = DecisionOptions(rocket_value=7.0, rocket_tornado='on', rocket_value_threat='on')
    out = decide_batch(Model(), **a, options=gated, rocket_value=[(bs, False, SimpleNamespace())], **kw)[0]
    assert out.get('why') != 'rocket_tornado'
