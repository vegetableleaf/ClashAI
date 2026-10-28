"""GB-DECOY: the evolved Goblin Barrel's decoy is told apart by creation order; with it renamed, log_barrel and
barrel_lane answer the real barrel's lane (both abstain or follow the logits on two identical barrels). CPU only."""
import torch

from pipeline import barrel_decoy as B
from pipeline.decision_options import DecisionOptions, barrel_landings, choose_cells
from pipeline.projectile_observation import objects, tokens_from_objects

GB_ID = 28000004                    # the reader's Goblin Barrel card id (both barrels of an evolved cast carry it)
GID = {'goblin-barrel': 42}         # CLXIII's card vocab has no decoy key
ME = 0                              # observer side 0: my frame y = 1 - raw y / 32000


def barrel(gen, tx, side=1, ty=6499):
    return dict(side=side, x=9000, y=28224, card_id=GB_ID, target_x=tx, target_y=ty, generation_key=gen)


REAL, DECOY = barrel(4000357, 3499), barrel(4000358, 14501)       # live 090643@4315 (real left, decoy mirrored right)


def test_the_later_created_mirrored_barrel_is_the_decoy():
    assert B.decoy_indices([REAL, DECOY]) == {1}
    assert B.decoy_indices([DECOY, REAL]) == {0}                    # order of the reader's list does not matter
    assert B.decoy_indices([REAL]) == set()                         # a plain barrel
    assert B.decoy_indices([REAL, dict(DECOY, generation_key=None)]) == set()
    assert B.decoy_indices([REAL, dict(DECOY, target_x=12000)]) == set()     # not mirrored
    assert B.decoy_indices([REAL, dict(DECOY, side=0)]) == set()             # the other player's barrel
    assert B.decoy_indices([REAL, dict(DECOY, card_id=28000001)]) == set()   # an Arrows shot


def test_objects_rename_only_the_reader_decoy_and_the_model_sees_one_barrel():
    frame = dict(projectiles=[DECOY, REAL], effects=[])
    got = B.objects(frame, source='reader')['projectiles']
    assert sorted(r[0] for r in got) == ['goblin-barrel', 'goblin-barrel-decoy']
    assert [r[4] for r in got if r[0] == 'goblin-barrel'] == [3499]
    plain = dict(projectiles=[REAL], effects=[])
    assert B.objects(plain, source='reader') == objects(plain, source='reader')
    before = tokens_from_objects(objects(frame, source='reader'), ME, GID)['projectiles']
    after = tokens_from_objects(B.objects(frame, source='reader'), ME, GID)['projectiles']
    assert [round(t[0] * 18, 1) for t in barrel_landings(before, 42)] == [3.5, 14.5]
    assert [round(t[0] * 18, 1) for t in barrel_landings(after, 42)] == [3.5]


def cell(col, row=55):              # lattice: x = col / 2 tiles, y = row / 2 tiles (row 55 = 27.5: 2 tiles behind the landing)
    return row * 36 + col


def test_rules_answer_the_real_lane_once_the_decoy_is_told_apart():
    logits = torch.full((1, 2304), -5.0)
    logits[0, cell(29)] = 3.0       # the model prefers the decoy's lane (right, x 14.5)
    logits[0, cell(7)] = 1.0        # the real barrel's lane (left, x 3.5)
    frame = dict(projectiles=[REAL, DECOY], effects=[])
    both = barrel_landings(tokens_from_objects(objects(frame, source='reader'), ME, GID)['projectiles'], 42)
    fixed = barrel_landings(tokens_from_objects(B.objects(frame, source='reader'), ME, GID)['projectiles'], 42)
    log = DecisionOptions(log_aim='log_barrel')
    assert int(choose_cells(logits, ['Log'], log, grid='lattice', barrels=[both])[0]) == cell(29)    # was: decoy lane
    assert int(choose_cells(logits, ['Log'], log, grid='lattice', barrels=[fixed])[0]) == cell(7)
    lane = DecisionOptions(barrel_lane='on')
    assert int(choose_cells(logits, ['Knight'], lane, grid='lattice', barrels=[both])[0]) == cell(29)   # abstains
    assert int(choose_cells(logits, ['Knight'], lane, grid='lattice', barrels=[fixed])[0]) == cell(7)


def test_flag_off_is_todays_observation_and_on_renames_the_decoy():
    from pipeline.public_observation import PublicObserver
    frame = dict(game_tick=300, entities=[], projectiles=[REAL, DECOY], effects=[])
    off, on = PublicObserver(ME), PublicObserver(ME)
    on.barrel_decoy = True
    off.update(frame, source='reader')
    on.update(frame, source='reader')
    assert sorted(r[0] for r in off.object_rows[-1]['projectiles']) == ['goblin-barrel', 'goblin-barrel']
    assert sorted(r[0] for r in on.object_rows[-1]['projectiles']) == ['goblin-barrel', 'goblin-barrel-decoy']
    assert len(tokens_from_objects(on.object_rows[-1], ME, GID)['projectiles'][:, 0].nonzero()[0]) == 1


def test_live_options_file_accepts_the_flag(tmp_path):
    from pipeline.live_options import _decision_parser
    assert _decision_parser('t').parse_args(['--barrel-decoy', 'on']).barrel_decoy == 'on'
    assert _decision_parser('t').parse_args([]).barrel_decoy == 'off'
