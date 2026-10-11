from pipeline.tests.memory_fixtures import tmp_path
import copy
import hashlib
import json
import numpy as np
import pytest
import torch

from pipeline.model_gen import GenModel, load_model
from pipeline.eval_gen import GenRows
from pipeline.add_memory import convert
from pipeline.tests.test_model_gen import toy

torch.set_num_threads(1)


def fixture(cap=8):
    a = toy(n=4)['gen']
    a.update(unit_form=np.zeros(len(a['tok']), np.int64), opp_past=np.zeros((4, 3, 5), np.float32),
             opp_cycle=np.zeros((4, 8, 4), np.float32), projectiles=np.zeros((4, 64, 8), np.float32),
             effects=np.zeros((4, 32, 6), np.float32), own_ability=np.zeros((4, 4, 7), np.float32),
             history_events=np.zeros((4, cap, 10), np.float32))
    a['history_events'][:, :3, :7] = np.array([[1, 0, 1, 0, .3, .7, 1], [1, 1, 2, 1, .7, .3, 2], [2, 1, 0, 0, .2, .2, 3]])
    model = GenModel(d=32, layers=1, d_c=8, n_cards=9, feature_version=4).eval()
    batch = GenRows(a, np.arange(4), 'cpu').batch(np.arange(4))
    return model, batch, a


def checkpoint(model):
    return dict(gen=True, model=model.state_dict(), args=dict(d=32, layers=1, feature_version=4, grid='lattice'),
                d_c=8, card_vocab=['<pad>']+[f'card{i}' for i in range(1, 9)], epoch=0, deck='icebow', n_params=0)


def test_zero_init_identity_all_outputs_and_empty_history():
    base, batch, _ = fixture()
    converted = copy.deepcopy(base)
    converted.add_history(cap=8, width=16, layers=1)
    converted.eval()
    for empty in (False, True):
        b = dict(batch)
        if empty:
            b['history_events'] = torch.zeros_like(b['history_events'])
        with torch.no_grad():
            a = base(b, card=b['card'], form=b['form'])
            c = converted(b, card=b['card'], form=b['form'])
        assert a.keys() == c.keys()
        for key in a:
            assert torch.equal(a[key], c[key]), key


def test_converter_round_trip_and_ablation(tmp_path):
    base, b, _ = fixture()
    src, out = tmp_path/'base.pt', tmp_path/'memory.pt'
    torch.save(checkpoint(base), src)
    st = convert(src, out, cap=8, width=16, layers=1)
    loaded, meta = load_model(out, torch.device('cpu'))
    loaded.eval()
    assert meta['args']['history_events'] is True
    assert all(torch.equal(v, st['model'][k]) for k, v in loaded.state_dict().items())
    with torch.no_grad():
        for k, v in base(b, card=b['card'], form=b['form']).items():
            assert torch.equal(v, loaded(b, card=b['card'], form=b['form'])[k])
        loaded.history.gate.fill_(.4)
        active = loaded(b, card=b['card'], form=b['form'])
        assert not torch.equal(active['gate'], base(b, card=b['card'], form=b['form'])['gate'])
        loaded.history.zero_history = True
        for k, v in base(b, card=b['card'], form=b['form']).items():
            assert torch.equal(v, loaded(b, card=b['card'], form=b['form'])[k])
    with pytest.raises(ValueError):
        convert(out, tmp_path/'twice.pt')


def test_flag_off_unchanged_constructor_state_rng_and_config_hash():
    torch.manual_seed(123)
    old = GenModel(d=32, layers=1)
    rng = torch.get_rng_state()
    torch.manual_seed(123)
    off = GenModel(d=32, layers=1, history_events=False)
    assert torch.equal(rng, torch.get_rng_state())
    assert old.state_dict().keys() == off.state_dict().keys()
    assert all(torch.equal(v, off.state_dict()[k]) for k, v in old.state_dict().items())
    from pipeline.rl_royale import config_sha
    cfg = {'seed': 74, 'init': 'original.pt'}
    expected = hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()
    assert config_sha(cfg) == expected
    assert config_sha(dict(cfg, history_events=False, history_cap=256)) == expected
    assert config_sha(dict(cfg, history_events=True)) != expected


def test_actor_strict_weight_loading_auto_constructs_history():
    model, _, _ = fixture()
    actor = copy.deepcopy(model)
    model.add_history(cap=8, width=16, layers=1)
    actor.load_state_dict(model.state_dict(), strict=True)
    assert actor.history.cap == 8
    broken = dict(model.state_dict())
    del broken['history.out.weight']
    with pytest.raises(RuntimeError):
        actor.load_state_dict(broken, strict=True)
