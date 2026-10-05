"""Training isolation and actual R1e checkpoint migration checks."""
from pathlib import Path

import numpy as np
import pytest
import torch

from pipeline.expert_context import probabilities, MIXTURES
from pipeline.rocket_teaching import sampling_probabilities
from pipeline.train_expert_context import initialize
from pipeline.tests.test_spatial_projectiles import batch

ROOT = Path(__file__).resolve().parents[2]


def cohorts():
    split = np.array([0]*10 + [1]*10)
    c = dict(pool=np.ones(20, bool))
    for name, rows in [('opportunity',[1,11]), ('sequence',[2,12]), ('xbow',[3,13]), ('barrel',[4,14])]:
        c[name] = np.isin(np.arange(20), rows)
    return c, split


@pytest.mark.parametrize('arm', list(MIXTURES))
def test_training_distribution_retains_waits_and_excludes_validation(arm):
    c, split = cohorts()
    p = probabilities(c, split, arm)
    assert np.isclose(p.sum(), 1) and (p[10:] == 0).all()
    ordinary = MIXTURES[arm]['pool'] / 10
    for name, row in [('opportunity',1), ('sequence',2), ('xbow',3), ('barrel',4)]:
        assert np.isclose(p[row], ordinary + MIXTURES[arm].get(name,0))
    draws = np.random.default_rng(7).choice(20, 10000, p=p)
    assert (split[draws] == 0).all()


@pytest.mark.parametrize('arm,uniform', [('uniform',True), ('rocket',False)])
def test_original_rocket_recipe_is_bit_exact(arm, uniform):
    c, split = cohorts()
    expected = sampling_probabilities(c['pool'], c['opportunity'], c['sequence'], split, uniform=uniform)
    np.testing.assert_array_equal(probabilities(c, split, arm), expected)


def test_missing_or_out_of_pool_bucket_rejected():
    c, split = cohorts()
    c['barrel'][:10] = False
    with pytest.raises(ValueError, match='Empty required'):
        probabilities(c, split, 'rocket_barrel')
    c, split = cohorts()
    c['pool'][3] = False
    with pytest.raises(ValueError, match='Invalid cohort'):
        probabilities(c, split, 'rocket_xbow')


def test_actual_r1e_migration_preserves_all_initial_outputs():
    torch.set_num_threads(1)
    path=ROOT/'icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0155.pt'
    state=torch.load(path,map_location='cpu')
    meta=dict(card_vocab=state['card_vocab'],grid=state['args']['grid'],feature_version=4)
    original=initialize(state,4,meta).eval()
    b=batch()
    with torch.no_grad():
        before=original(b,card=b['card'],form=b['form'])
        for version in (5,6):
            migrated=initialize(state,version,dict(meta,feature_version=5)).eval()
            after=migrated(b,card=b['card'],form=b['form'])
            assert all(torch.equal(before[k],after[k]) for k in before)
    bad=dict(meta,card_vocab=list(reversed(meta['card_vocab'])))
    with pytest.raises(ValueError,match='migration'):
        initialize(state,4,bad)
    with pytest.raises(ValueError,match='contract'):
        initialize(state,6,meta)
    corrupted=dict(state,model=dict(state['model']))
    corrupted['model'].pop(next(iter(corrupted['model'])))
    with pytest.raises(ValueError,match='Unexpected checkpoint'):
        initialize(corrupted,6,dict(meta,feature_version=5))
