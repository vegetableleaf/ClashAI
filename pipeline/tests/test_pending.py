import copy
import importlib
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from pipeline import pending_states as P, train_pending as T
from pipeline.eval_gen import GenRows
from pipeline.tests.test_memory_model import fixture, checkpoint
from pipeline.tests.memory_fixtures import tmp_path


def synthetic():
    _, _, a = fixture()
    a = {k: np.concatenate([v, v]) if k not in ('off', 'tok', 'unit_form') else v for k, v in a.items()}
    # Selection-only synthetic rows: no ragged observations needed here.
    a['past'] = np.zeros((8, 3, 5), np.float32)
    a['past'][:, 0, 0] = 1
    a['past'][:, 0, 4] = [0, .05, 1.2, 1.25, 1.2, -1, np.nan, .5]
    a['past'][7, :, 0] = 0  # padding must never become a prior play
    a['y_gate'][:] = 1
    a['y_gate'][4] = 0
    a['y_hand_pos'][:] = 0
    a['y_card'] = a['hand_card'][:, 0].copy()
    a['y_xy'][:] = [.4, .6]
    a['split'] = np.arange(8) % 2
    return a


def test_pending_inclusive_boundary_waits_padding_and_labels(tmp_path):
    a = synthetic()
    pending, ordinary = P.masks(a)
    assert np.flatnonzero(pending).tolist() == [0, 1, 2]
    assert np.flatnonzero(ordinary).tolist() == [3, 5, 6, 7]
    meta = dict(kind='generalist', shift_ticks=0, grid='lattice', card_vocab=['<pad>']+[f'card{i}' for i in range(1, 9)])
    src, out = tmp_path/'data.npz', tmp_path/'pending.npz'
    np.savez_compressed(src, **a, meta=json.dumps(meta))
    report = P.build(src, out)
    assert report['rows'] == 3 and report['train_rows'] == 2 and report['val_rows'] == 1
    assert sum(report['second_card_mix'].values()) == pytest.approx(1)
    with np.load(out) as z:
        np.testing.assert_array_equal(z['y_card'], a['y_card'][:3])
        np.testing.assert_array_equal(z['y_xy'], a['y_xy'][:3])
        np.testing.assert_array_equal(z['y_cell'], T.cell_label(torch.from_numpy(a['y_xy'][:3]), 'lattice').numpy())
    assert P.deck_mask(a, meta['card_vocab'], meta['card_vocab'][1:]).all()
    a['deck_card'][0, 0] = 0
    assert not P.deck_mask(a, meta['card_vocab'], meta['card_vocab'][1:])[0]
    with pytest.raises(FileExistsError):
        P.build(src, out)
    np.savez_compressed(src, **a, meta=json.dumps(dict(meta, shift_ticks=26)))
    with pytest.raises(ValueError, match='unshifted'):
        P.build(src, tmp_path/'shifted.npz')


def test_pending_rejects_corrupt_label():
    a = synthetic()
    a['y_hand_pos'][0] = -1
    with pytest.raises(ValueError, match='label'):
        P.masks(a)


def test_drift_known_fraction_and_strict_selection():
    ref = torch.tensor([[2., 1., -torch.inf], [0., 4., -torch.inf], [1., 1., -torch.inf]])
    alt = ref.clone()
    alt[0, 1] = 3
    assert T.top_card_drift(ref, ref) == 0
    assert T.top_card_drift(alt, ref) == pytest.approx(1/3)
    assert T.eligible(.009, .9, 1.)
    assert not T.eligible(.01, .9, 1.)
    assert not T.eligible(0, 1., 1.)
    assert not T.eligible(float('nan'), .9, 1.)
    with pytest.raises(ValueError):
        T.top_card_drift(torch.full((1, 4), -torch.inf), torch.full((1, 4), -torch.inf))


def test_kl_padding_direction_and_gradient():
    ref = torch.tensor([[1., 2., -torch.inf]], requires_grad=True)
    alt = torch.tensor([[2., 1., -torch.inf]], requires_grad=True)
    assert T.head_kl(ref, ref) == 0
    kl = T.head_kl(alt, ref)
    kl.backward()
    assert kl > 0 and torch.isfinite(alt.grad).all()
    assert alt.grad[0, 0] > 0 and alt.grad[0, 1] < 0 and alt.grad[0, 2] == 0
    assert ref.grad is None


@pytest.mark.parametrize('train_cell', [False, True])
def test_ordinary_anchor_wiring_and_only_heads_change(train_cell):
    torch.manual_seed(74)
    base, b, _ = fixture()
    base.add_history(cap=8, width=16, layers=1)
    base.add_cell_refine()
    base.add_tower_refine()
    base.eval()
    pending = dict(b, slot=torch.zeros(4, dtype=torch.long), card=b['hand_card'][:, 0],
                   form=b['hand_form'][:, 0], xy=torch.full((4, 2), .5), gate=torch.ones(4))
    ordinary = dict(b, sc=b['sc'] + .1)
    model = copy.deepcopy(base)
    params = T.freeze_heads(model, train_cell)
    before = {k: v.clone() for k, v in model.state_dict().items()}
    with torch.no_grad():
        # A uniform query-weight shift can cancel against LayerNorm's zero
        # sum. Perturb an individual weight and distinct card biases instead.
        model.card_q.weight[0, 0].add_(.05)
        model.card_b.weight.add_(torch.arange(model.n_cards)[:, None] * .1)
    total, ce, kl = T.anchored_loss(model, base, pending, ordinary, 123., train_cell=train_cell)
    assert torch.isfinite(total) and kl > 0
    assert total.detach() == pytest.approx(float(ce + 123*kl))
    # Independent ordinary-only KL calculation catches anchoring pending rows.
    with torch.no_grad():
        ref = base(ordinary)['card']
        expected = T.head_kl(model(ordinary)['card'], ref)
    assert kl == pytest.approx(float(expected), abs=1e-6)  # unchanged cell weights => zero cell KL
    opt = torch.optim.AdamW(params, lr=.001, weight_decay=0)
    total.backward()
    assert all(p.grad is None for n, p in model.named_parameters() if not T.head_parameter(n, train_cell))
    assert all(p.grad is None for p in base.parameters())
    opt.step()
    assert all(torch.equal(before[k], v) for k, v in model.state_dict().items() if not T.head_parameter(k, train_cell))
    assert not torch.equal(before['card_q.weight'], model.card_q.weight)
    with pytest.raises(ValueError, match='mandatory'):
        T.anchored_loss(model, base, pending, ordinary, 0)


def test_imports_default_off_outputs_rng_and_checkpoint_unchanged(tmp_path):
    model, b, _ = fixture()
    src = tmp_path/'original.pt'
    torch.save(checkpoint(model), src)
    original = src.read_bytes()
    with torch.no_grad():
        before = model(b, card=b['card'], form=b['form'])
    rng = torch.get_rng_state().clone()
    importlib.reload(P)
    importlib.reload(T)
    assert torch.equal(rng, torch.get_rng_state())
    with torch.no_grad():
        after = model(b, card=b['card'], form=b['form'])
    assert all(torch.equal(v, after[k]) for k, v in before.items())
    assert src.read_bytes() == original
    assert sorted(x.name for x in tmp_path.iterdir()) == ['original.pt']


def test_cpu_training_checkpoint_and_heldout_samples(tmp_path, monkeypatch):
    torch.manual_seed(1)
    model, _, arrays = fixture()
    # Two repeated pending observations, in different replay splits, plus
    # ordinary observations. Small LR changes probabilities but not top cards.
    arrays['split'] = np.array([0, 1, 0, 1], np.int8)
    arrays['past'][:] = 0
    arrays['past'][:2, 0, 0] = 1
    arrays['past'][:2, 0, 4] = .5
    arrays['y_gate'][:] = 1
    arrays['y_xy'][:] = [.5, .5]
    batch = GenRows(arrays, np.arange(4), 'cpu').batch(np.arange(4))
    with torch.no_grad():
        pos = model(batch)['card'].argmax(-1).numpy()
    arrays['y_hand_pos'] = pos
    arrays['y_card'] = arrays['hand_card'][np.arange(4), pos]
    ck = checkpoint(model)
    data, init, index, out = [tmp_path/name for name in ('data.npz', 'init.pt', 'pending.npz', 'fixed.pt')]
    torch.save(ck, init)
    meta = dict(kind='generalist', grid='lattice', shift_ticks=0, feature_version=4, card_vocab=ck['card_vocab'])
    np.savez_compressed(data, **arrays, meta=json.dumps(meta))
    P.build(data, index)
    T.main(['--data', str(data), '--init', str(init), '--pending', str(index), '--out', str(out),
            '--epochs', '1', '--bs', '2', '--lr', '0.000001', '--ordinary-rows', '2', '--val-rows', '2', '--device', 'cpu'])
    loaded, st = T.load_model(out, 'cpu')
    assert st['pending_pretrain']['ordinary_top_card_drift'] == 0
    assert all(torch.equal(v, loaded.state_dict()[k]) for k, v in model.state_dict().items() if not T.head_parameter(k))
    assert P.digest(init) == st['pending_pretrain']['init_sha256']
    with np.load(out.with_suffix('.samples.npz')) as z:
        assert z['pending_train'].tolist() == [0] and z['pending_val'].tolist() == [1]
        assert z['ordinary_train'].tolist() == [2] and z['ordinary_val'].tolist() == [3]
    monkeypatch.setattr(T, 'eligible', lambda *args: False)
    rejected = tmp_path/'rejected.pt'
    with pytest.raises(RuntimeError, match='no checkpoint saved'):
        T.main(['--data', str(data), '--init', str(init), '--pending', str(index), '--out', str(rejected),
                '--epochs', '1', '--bs', '2', '--lr', '0.000001', '--ordinary-rows', '2', '--val-rows', '2', '--device', 'cpu'])
    assert not rejected.exists()
    assert rejected.with_suffix('.metrics.json').exists()
