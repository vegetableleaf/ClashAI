import json
from pathlib import Path

import numpy as np
import pytest

from pipeline.rocket_teaching import (durable, groups, load_curriculum, sampling_probabilities,
                                     scaled_stat, sequence_rows, sha, PublicBodies)


def troop(x, y, deployment, cost=5, hp=1000, maximum=1200):
    return dict(x=x, y=y, deployment=deployment, cost=cost, hp=hp, max_hp=maximum,
                is_troop=True, pullable=True, shield=0)


def test_damage_strict_boundaries():
    assert not durable(troop(0, 0, 1, hp=600), 1000, 300)
    assert durable(troop(0, 0, 1, hp=601), 1000, 300)
    assert not durable(troop(0, 0, 1, hp=1120), 1000, 300)  # exactly 10%
    assert durable(troop(0, 0, 1, hp=1119), 1000, 300)
    assert not durable(dict(hp=1000, max_hp=None), 1000, 300)


def test_compact_spread_and_out_of_range():
    a = troop(9000, 16000, 'a')
    compact = groups([a, troop(10000, 16000, 'b', cost=4)], 1000, 300)
    assert compact['rocket_only'] and not compact['pull_candidate']
    spread = groups([troop(6000, 16000, 'a'), troop(12000, 16000, 'b', cost=4)], 1000, 300)
    assert spread['pull_candidate'] and not spread['rocket_only']
    far = groups([troop(1000, 16000, 'a'), troop(17000, 16000, 'b')], 1000, 300)
    assert not far['rocket_only'] and not far['pull_candidate']


def test_cost_is_per_deployment_and_excludes_unknown_shields_buildings():
    same = [troop(9000, 16000, 'same'), troop(10000, 16000, 'same')]
    assert not groups(same, 1000, 300)['rocket_only']
    for change in ({'cost': 3}, {'deployment': None}, {'shield': 1}, {'is_troop': False}, {'pullable': False}):
        pair = [troop(9000, 16000, 'a', cost=5), dict(troop(10000, 16000, 'b', cost=4), **change)]
        assert not groups(pair, 1000, 300)['rocket_only']
    with pytest.raises(ValueError, match='Inconsistent cost'):
        groups([troop(9000, 16000, 'same', cost=5), troop(10000, 16000, 'same', cost=4)], 1000, 300)


def test_catalog_damage_is_level_scaled():
    assert scaled_stat('rocket', 'damage', 11) == 1484
    assert scaled_stat('the-log', 'damage', 11) == 268
    with pytest.raises(ValueError):
        scaled_stat('the-log', 'damage', 2)


def test_sequence_keeps_waits_and_both_actions_side_local():
    ticks = np.array([59, 60, 95, 100, 130, 145, 180, 181, 130])
    sides = np.array([0] * 8 + [1])
    event = dict(card='rocket', side=0, tick=100, landing_tick=160, rocket_then_tornado=True,
                 tower_hits=[dict(finish=True)])
    seq, combo, finish = sequence_rows(ticks, sides, [event])
    assert seq.tolist() == [False, True, True, True, True, True, True, False, False]
    assert np.array_equal(seq, combo) and np.array_equal(seq, finish)
    assert not sequence_rows(ticks, sides, [dict(event, landing_tick=None)])[0].any()


def test_sampling_is_seeded_train_only_and_preserves_negative_rows():
    pool = np.ones(10, bool)
    split = np.array([0] * 8 + [1, 1])
    opp = np.array([1, 1, 0, 0, 0, 0, 0, 0, 1, 0], bool)
    seq = np.array([0, 0, 1, 1, 0, 0, 0, 0, 0, 1], bool)
    p = sampling_probabilities(pool, opp, seq, split)
    np.testing.assert_allclose(p, [.15] * 4 + [.1] * 4 + [0, 0])
    # Dataset labels have no place in this API; negatives in either bucket retain mass.
    a = np.random.default_rng(7).choice(10, 1000, p=p)
    b = np.random.default_rng(7).choice(10, 1000, p=p)
    assert np.array_equal(a, b) and a.max() < 8
    uniform = sampling_probabilities(pool, opp, seq, split, uniform=True)
    np.testing.assert_allclose(uniform, [.125] * 8 + [0, 0])


def test_sampling_refuses_missing_bucket_or_outside_pool():
    with pytest.raises(ValueError, match='Empty'):
        sampling_probabilities([1, 1], [0, 0], [1, 0], [0, 1])
    with pytest.raises(ValueError, match='outside'):
        sampling_probabilities([1, 0], [0, 1], [1, 0], [0, 0])


def test_birth_attribution_ignores_hidden_elixir_future_plays_and_children(monkeypatch):
    import pipeline.rocket_teaching as rt
    monkeypatch.setattr(rt, 'catalog_card_form', lambda cid: ('Witch', 0))
    maximum = scaled_stat('witch', 'hitpoints', 11)
    play = dict(side=1, tick=100, card='witch', x=9000, y=16000, cost=5, deployment=7)
    observer = PublicBodies([play, dict(play, tick=110, deployment=8)], 11)
    frame = dict(tick=105, elixir=[0, 10], entities=[
        [1, 9000, 16000, '-1', maximum, maximum, 15, 1, 7],
        [1, 9200, 16000, '-1', 81, 81, 15, 1, 8]])
    out = observer.read(frame)
    assert len(out) == 1 and out[0]['deployment'] == 7
    assert observer.stats['child_or_modified_max_hp'] == 1
    other = PublicBodies([play, dict(play, tick=110, deployment=8)], 11)
    assert out == other.read(dict(frame, elixir=[10, 0], players=[{'hand': ['secret']}]))


def test_manifest_rejects_corruption_samples_and_wrong_dataset(tmp_path):
    data = tmp_path / 'data.bin'
    data.write_bytes(b'dataset')
    np.savez(tmp_path / 'cohorts.npz', pool=[1, 1, 1], opportunity=[1, 0, 0], sequence=[0, 1, 0])
    m = dict(schema=1, dataset_sha256=sha(data), cohorts_sha256=sha(tmp_path/'cohorts.npz'),
             expert_targets_unchanged=True, public_only=True, trainable=True, rows=3)
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps(m))
    assert load_curriculum(tmp_path, data, [0, 0, 1])[1]['rows'] == 3
    for change in ({'trainable': False}, {'public_only': False}, {'cohorts_sha256': 'corrupt'}, {'dataset_sha256': 'bad'}):
        manifest.write_text(json.dumps(dict(m, **change)))
        with pytest.raises(ValueError):
            load_curriculum(tmp_path, data, [0, 0, 1])


def test_trainer_changes_weights_with_real_imitation_losses_and_loads_existing_format(tmp_path):
    import torch
    from pipeline.tests.test_model_gen import toy
    from pipeline.eval_gen import GenRows
    from pipeline.model_gen import load_model, GenModel
    from pipeline.train_rocket_curriculum import train_step
    torch.set_num_threads(1)
    arrays = toy(n=8)['gen']
    model = GenModel(d=32, layers=1, d_c=8, n_cards=9)
    rows = GenRows(arrays, np.arange(8), 'cpu')
    before = {k: v.clone() for k, v in model.state_dict().items()}
    opt = torch.optim.AdamW(model.parameters(), lr=1e-5)
    loss, parts = train_step(model, rows.batch(np.arange(8)), opt, True, 'lattice')
    assert np.isfinite(loss) and {'gate', 'cell', 'card', 'wait', 'value'} == set(parts)
    assert any(not torch.equal(v, before[k]) for k, v in model.state_dict().items())
    path = tmp_path/'candidate.pt'
    torch.save(dict(gen=True, model=model.state_dict(), d_c=8, card_vocab=list(range(9)),
                    args=dict(d=32, layers=1, feature_version=1, grid='lattice')), path)
    loaded, _ = load_model(path, 'cpu')
    model.eval(); loaded.eval()
    batch = rows.batch(np.arange(8))
    with torch.no_grad():
        assert torch.equal(model(batch)['card'], loaded(batch)['card'])


def test_streaming_subset_preserves_exact_rows(tmp_path):
    import zipfile
    from pipeline.train_rocket_curriculum import take
    values = np.arange(300).reshape(100, 3).astype(np.float32)
    p = tmp_path/'array.npz'
    np.savez_compressed(p, values=values)
    with zipfile.ZipFile(p) as archive:
        np.testing.assert_array_equal(take(archive, 'values', np.array([0, 15, 99])), values[[0, 15, 99]])
