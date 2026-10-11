import copy
from types import SimpleNamespace
import numpy as np
import pytest
import torch

from pipeline.train_memory import freeze_base, anchored_loss, policy_kl
from pipeline.tests.test_memory_model import fixture
from pipeline.match_memory import mirror_history
from pipeline.tests.memory_fixtures import tmp_path


def test_only_memory_parameters_change_and_kl_is_finite():
    base, b, _ = fixture()
    model = copy.deepcopy(base)
    model.add_history(cap=8, width=16, layers=1)
    params = freeze_base(model)
    assert all(p.requires_grad == n.startswith('history.') for n, p in model.named_parameters())
    before = {k: v.clone() for k, v in model.state_dict().items()}
    optimizer = torch.optim.AdamW(params, lr=.01)
    for _ in range(3):
        optimizer.zero_grad()
        loss, _, kl = anchored_loss(model, base, b, 1)
        assert torch.isfinite(loss) and torch.isfinite(kl)
        loss.backward()
        assert all(p.grad is None for n, p in model.named_parameters() if not n.startswith('history.'))
        optimizer.step()
    assert all(torch.equal(before[k], v) for k, v in model.state_dict().items() if not k.startswith('history.'))
    assert not torch.equal(before['history.gate'], model.history.gate)
    assert not torch.equal(before['history.card.weight'], model.history.card.weight)
    with pytest.raises(ValueError):
        anchored_loss(model, base, b, 0)


def test_kl_padding_and_known_distribution_positive_control():
    same = dict(card=torch.tensor([[1., -float('inf')]]), wait=torch.tensor([[0., 1.]]),
                cell=torch.tensor([[0., 1.]]), value=torch.tensor([[0., 1.]]), gate=torch.tensor([0.]))
    assert policy_kl(same, same) == 0
    other = {**same, 'gate': torch.tensor([2.], requires_grad=True)}
    kl = policy_kl(other, same)
    assert kl > 0
    kl.backward()
    assert other['gate'].grad.item() > 0


def test_history_mirror_is_involution_and_preserves_padding():
    _, b, _ = fixture()
    h = b['history_events']
    torch.testing.assert_close(mirror_history(mirror_history(h)), h)
    assert torch.equal(mirror_history(h)[:, 3:], h[:, 3:])


def test_rl_collation_and_actor_row_keys_carry_memory():
    from pipeline import e1_eval as E, rl_royale as R
    from pipeline.tests.test_rl_royale import _results, _tiny_model
    results = _results(_tiny_model(1), [(0, 0, 3, 'win'), (0, 1, 3, 'loss')], all_allowed=True)
    model, batch, _ = fixture()
    model.add_history(cap=8, width=16, layers=1)
    batch.update(hand_slot=torch.arange(4).repeat(4, 1), slot_card=torch.arange(9).repeat(4, 1),
                 slot_form=torch.zeros((4, 9), dtype=torch.long))
    for r in results:
        n = len(r['traj']['played'])
        for key in E.gen_row_keys(model):
            r['traj'][key] = np.repeat(batch[key][:1].numpy(), n, axis=0)
    B, _ = R.collate(results)
    assert B['history_events'].shape[1:] == (8, 10)
    assert B['history_events'][:, 0, 0].sum() == len(B['history_events'])
    policy = E.GenPolicy(model, ['<pad>']+[str(i) for i in range(8)])
    env = SimpleNamespace()
    E.enable_sim_features(env, policy)
    assert env.history_events is True
    assert E.enable_sim_features(object(), None) == 1  # off never mutates a legacy env


def test_pretrain_cli_saves_only_memory_changes(tmp_path):
    import json
    from pipeline.tests.test_memory_model import checkpoint
    from pipeline.add_memory import convert
    from pipeline.train_memory import main
    from pipeline.model_gen import load_model
    model, _, arrs = fixture()
    ck = checkpoint(model)
    torch.save(ck, tmp_path/'base.pt')
    convert(tmp_path/'base.pt', tmp_path/'memory.pt', cap=8, width=16, layers=1)
    arrs['split'] = np.array([0, 0, 1, 1])
    np.savez_compressed(tmp_path/'data.npz', **arrs, meta=json.dumps(dict(
        card_vocab=ck['card_vocab'], feature_version=4, history_events=True, history_cap=8)))
    main(['--init', str(tmp_path/'memory.pt'), '--data', str(tmp_path/'data.npz'), '--out', str(tmp_path/'trained.pt'),
          '--epochs', '1', '--bs', '2', '--device', 'cpu'])
    trained, st = load_model(tmp_path/'trained.pt', torch.device('cpu'))
    assert st['memory_pretrain']['parameters'] == 'history.* only'
    assert all(torch.equal(v, trained.state_dict()[k]) for k, v in model.state_dict().items())
    assert trained.history.gate.abs().sum() > 0


def test_npz_history_selection_and_proagreement(tmp_path):
    import json
    from pipeline.dataset_spool import select_npz_rows
    from pipeline.rl_royale import gen_v3val_arrays
    _, _, arrs = fixture()
    arrs['v3val'] = np.array([0, 1, 0, 1])
    path = tmp_path/'dataset.npz'
    np.savez_compressed(path, **arrs, meta=json.dumps({}))
    selected = select_npz_rows(path, 'history_events', [1, 3])
    np.testing.assert_array_equal(selected, arrs['history_events'][[1, 3]])
    out, _ = gen_v3val_arrays(path)
    np.testing.assert_array_equal(out['history_events'], selected)
    with pytest.raises(ValueError):
        select_npz_rows(path, 'history_events', [3, 1])
