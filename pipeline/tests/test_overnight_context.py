import copy
import importlib.util
from pathlib import Path
import numpy as np
import pytest
from pipeline.rocket_context import require_weight_artifact

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('fit_context', ROOT/'scratchpad/gauntlet/L70/gen_v31/fit_context.py')
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)


def test_defensive_xbow_exclusion_is_explicit_and_fallback_is_one():
    arrays = dict(y_gate=np.zeros(2), rocket_context_probability=np.array([.2, .8]))
    e = dict(fit_tags=['a'], tune_tags=['b'], test_tags=['c'], public_only=True,
             classifier_sha256='fixture', heldout_report_sha256='fixture', selected_weight=2,
             context_targets=C.TARGETS, defensive_xbow_excluded=True)
    with pytest.raises(ValueError): require_weight_artifact(arrays, dict(rocket_context=e), 2)
    require_weight_artifact(arrays, dict(rocket_context=e), 2, exclude_defensive_xbow=True)
    require_weight_artifact({}, {}, 1, inputs_only=True)
    with pytest.raises(ValueError): require_weight_artifact({}, {}, 2, inputs_only=True)
    e['defensive_xbow_excluded'] = False
    with pytest.raises(ValueError): require_weight_artifact(arrays, dict(rocket_context=e), 2, exclude_defensive_xbow=True)


def test_motion_estimate_authorization_does_not_hide_absent_areas():
    from pipeline.projectile_observation import require_complete_training, PROJECTILE_COLS, EFFECT_COLS
    meta = dict(feature_version=4, projectile_cols=list(PROJECTILE_COLS), effect_cols=list(EFFECT_COLS),
                stats=dict(projectiles_observed=10, effects_observed=2, projectiles_motion_estimated=5,
                           projectiles_missing_timing=5))
    with pytest.raises(ValueError): require_complete_training(meta)
    require_complete_training(meta, allow_causal_tti_unknowns=True)
    meta['stats']['native_area_effects_unavailable'] = 1
    with pytest.raises(ValueError): require_complete_training(meta, allow_causal_tti_unknowns=True)


def test_context_features_ignore_label_and_opponent_private_fields():
    sc = np.zeros((3,70), np.float32); sc[:,6] = 1
    a = dict(sc=sc, hand_card=np.array([[1,2,3,4]]*3), y_card=np.array([1,2,3]),
             y_xy=np.ones((3,2)), y_crowns=np.ones((3,2)), opponent_hand=['secret'])
    meta = dict(card_vocab=['pad','rocket','x-bow','tornado','the-log'])
    expected = C.public_features(a, meta)
    b = copy.deepcopy(a); b.update(y_card=np.array([4,4,4]), y_xy=np.zeros((3,2)), opponent_hand=['changed'], opponent_elixir=999)
    np.testing.assert_array_equal(expected, C.public_features(b, meta))


def test_proxy_unknowns_and_dead_lane_are_not_silently_negative():
    a = dict(y_gate=np.ones(2), y_card=np.array([1,2]), rep=np.zeros(2,dtype=int),
             side=np.array([0,0]), tick=np.array([100,200]))
    r = dict(tag='a', side=0, tick=100, proxy_tower_rocket=True, proxy_defensive_rocket=None,
             proxy_rocket_then_tornado=True, proxy_tornado_then_rocket=False)
    bow = dict(tag='a', side=0, tick=200, lane='left', lane_state='dead')
    y,k,report = C.labels(a, ['a'], dict(card_vocab=['pad','rocket','x-bow']), [r], [bow])
    assert y[0].tolist() == [1,0,0,1,0] and k[0,2] == 0
    assert y[1,1] == 1 and report['matched'] == {'rocket':1,'x-bow':1}
    with pytest.raises(ValueError, match='lack audited'): C.labels(a, ['a'], dict(card_vocab=['pad','rocket','x-bow']), [], [bow])
