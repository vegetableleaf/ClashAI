import copy
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scratchpad/gauntlet/L70/gen_v31'))
from mine_xbows import mine, summarize, xy, rate


def recording(side=0):
    def frame(tick):
        return dict(tick=tick, elixir=[9, 8], towers=[
            [0, 'king', None, 9000, 3000, 4000, 4824],
            [0, 'princess', 'left', 3500, 6500, 0, 3052],
            [0, 'princess', 'right', 14500, 6500, 2000, 3052],
            [1, 'king', None, 9000, 29000, 4000, 4824],
            [1, 'princess', 'left', 3500, 25500, 0, 3052],
            [1, 'princess', 'right', 14500, 25500, 1000, 3052]])
    return dict(tag='fixture', record_native=True, record_full=True,
        frames=[frame(3600)], final={}, log=[
            dict(play_index=0, tick=3600, engine_tick=3600, side=side, card='x-bow', accepted=True,
                 x=3500 if side == 0 else 14500, y=12500 if side == 0 else 19500)])


def rocket(tick=3800, side=0, target=True, index=1):
    return dict(tag='fixture', tick=tick, side=side, play_index=index,
                targets=[dict(tower=[1-side, 'princess', 'left'])] if target else [])


def test_orientation_forward_and_enemy_lane_by_geometry():
    assert xy(3500, 12500, 0) == xy(14500, 19500, 1)
    assert xy(3500, 14000, 0)[1] < xy(3500, 12500, 0)[1]
    assert xy(14500, 18000, 1)[1] < xy(14500, 19500, 1)[1]
    a = mine(recording(0), [])[0][0]
    b = mine(recording(1), [])[0][0]
    assert a['lane'] == b['lane'] == 'left'
    assert a['lane_state'] == 'dead' and b['lane_state'] == 'alive'
    assert a['crowns_ours_enemy'] == b['crowns_ours_enemy'] == [1, 1]
    assert a['xy'][1] == .609375 and a['river_distance_tiles'] == 3.5


def test_following_same_side_candidate_inclusive_ten_second_window():
    rows, n = mine(recording(), [rocket(3599), rocket(3600, index=-1), rocket(3600), rocket(),
                                rocket(3801), rocket(3700, side=1), rocket(3700, target=False)])
    assert n == 1
    assert [r['gap_s'] for r in rows[0]['tower_rocket_candidates_within_10s']] == [0, 10]


def test_no_future_context_or_delayed_pre_attempt_frame():
    rec = recording()
    rec['play_frames'] = [dict(rec['frames'][0], play_index=0)]
    rec['log'][0]['engine_tick'] = 3620
    later = copy.deepcopy(rec['frames'][0]); later['tick'] = 3615; later['towers'][4][5] = 200
    future = copy.deepcopy(later); future['tick'] = 3621; future['towers'][4][5] = 0
    rec['frames'] += [later, future]
    row = mine(rec, [])[0][0]
    assert row['context_tick'] == 3615 and row['lane_state'] == 'alive'
    assert row['context_age_s'] == .25


def test_missing_towers_and_stale_context_excluded_not_dead():
    rec = recording(); rec['frames'][0]['towers'] = []
    row = mine(rec, [])[0][0]
    assert row['lane_state'] == 'unknown' and row['enemy_princess_down'] is None
    assert row['crowns_ours_enemy'] is None
    assert summarize([row])['dead_lane_when_enemy_princess_down']['n'] == 0
    rec = recording(); rec['log'][0]['engine_tick'] = 3611
    row = mine(rec, [])[0][0]
    assert row['lane_state'] == 'dead' and row['context_age_s'] == .55
    assert summarize([row])['dead_lane_when_enemy_princess_down']['n'] == 0
    rec['frames'] = []
    assert mine(rec, [])[0][0]['context_tick'] is None


def test_center_lane_is_not_arbitrarily_right():
    rec = recording(); rec['log'][0]['x'] = 9000
    r = mine(rec, [])[0][0]
    assert r['lane'] == 'center' and r['lane_state'] == 'unknown'


def test_private_opponent_mutations_cannot_change_side_zero_audit():
    rec = recording(); expected = mine(rec, [])
    rec['frames'][0]['elixir'][1] = 999
    rec['frames'][0]['players'] = [dict(side=1, hand=['secret'], next='secret', deck_form_flags=[2]*8)]
    rec['log'][0]['hand_before'] = ['secret']
    rec['decks'] = {'1': ['secret']*8}
    assert mine(rec, []) == expected


def test_failed_plays_abilities_and_other_cards_do_not_enter_census():
    rec = recording(); p = rec['log'][0]
    rec['log'] += [dict(p, accepted=False), dict(p, ability=True), dict(p, card='rocket')]
    rows, n = mine(rec, [])
    assert len(rows) == 1 and n == 2


def test_zero_denominator_and_cluster_bootstrap_reproducibility():
    assert rate([], lambda r: True, lambda r: True)['percent'] is None
    a = mine(recording(), [])[0][0]; b = dict(a, tag='other', legacy_y_gt_058=False)
    r = rate([a, b], lambda r: True, lambda r: r['legacy_y_gt_058'])
    assert r['count'] == 1 and r['n'] == 2 and r['percent'] == 50
    assert r['ci95_percent'] == [0, 100]
    assert r == rate([a, b], lambda r: True, lambda r: r['legacy_y_gt_058'])


def test_baseline_geometry_uses_grid_and_accepted_time_and_counts():
    from xbow_baselines import vectors, metrics
    from pipeline.model_v3 import cell_xy
    for grid in ('floor', 'lattice'):
        row = dict(end_tick=3600, plays=[
            dict(card='x_bow', cell=39*36+5, tick=2390, land_tick=2416, accepted=True),
            dict(card='rocket', cell=0, tick=2600, land_tick=2616, accepted=True),
            dict(card='x_bow', cell=0, tick=2400, accepted=False)])
        v, ys = vectors(row, grid)
        assert ys == [cell_xy(39*36+5, grid)[1]]
        assert v.tolist() == [2, 3, 1, 1, 1, 1]
        assert metrics(v[None])[1:].tolist() == [50, 100, 100]
