"""Step 4 distill scaffolding: laptop CPU, seconds, no simulator (the 20261012 runtime is Linux-pod only).

    icebow/.venv/Scripts/python.exe -m pytest -q scratchpad/gauntlet/L74/distill/test_distill.py
"""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

import numpy as np
import pytest
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gen_distill as G  # noqa: E402
import train_distill as T  # noqa: E402
from pipeline.dataset import PAST_K, _tag_split  # noqa: E402
from pipeline.model_gen import GenModel, load_model  # noqa: E402
from pipeline.model_v3 import N_CELLS, cell_label, cell_xy  # noqa: E402
from pipeline.obs_contract import F, S  # noqa: E402
from pipeline.train_gen import GenRows  # noqa: E402

VOCAB = ['<pad>'] + [f'c{i}' for i in range(1, 9)]
MODEL_KEYS = ('tok', 'mask', 'sc', 'past', 'hand_card', 'hand_form', 'next_card', 'next_form', 'deck_card', 'deck_form',
              'unit_form', 'opp_past', 'opp_cycle', 'projectiles', 'effects', 'own_ability')


def fake_row(rng):
    """A gen row with SelfPlaySide._gen_row's keys and dtypes (feature_version 6), card ids 1..8."""
    slot_card = np.r_[rng.permutation(np.arange(1, 9)), 0].astype(np.int64)
    slot_form = np.r_[rng.integers(0, 3, 8), 3].astype(np.int64)
    perm = rng.permutation(8)
    hand_slot, nxt = perm[:4].astype(np.int64), int(perm[4])
    order = np.argsort(slot_card[:8], kind='stable')
    n = int(rng.integers(1, 12))
    tok = np.zeros((64, F), np.float32)
    tok[:n] = rng.normal(size=(n, F))
    tok[:n, 0] = rng.integers(0, 50, n)
    tok[:n, 4:6] = rng.uniform(0, 1, (n, 2))
    sc = rng.normal(size=S).astype(np.float32)
    sc[7:52] = 0
    past = np.zeros((PAST_K, 5), np.float32)
    past[:, 0], past[:, 1], past[:, 2:5] = rng.integers(0, 9, PAST_K), 3, rng.uniform(0, 1, (PAST_K, 3))

    def objs(k, width):
        o = np.zeros((k, width), np.float32)
        o[:3, 0] = rng.integers(1, 9, 3)
        o[:3, 1:] = rng.uniform(0, 1, (3, width - 1))
        return o
    return dict(tok=tok, mask=np.arange(64) < n, sc=sc, past=past, hand_card=slot_card[hand_slot],
                hand_form=slot_form[hand_slot], next_card=slot_card[nxt], next_form=slot_form[nxt],
                deck_card=slot_card[:8][order], deck_form=slot_form[:8][order], hand_slot=hand_slot,
                slot_card=slot_card, slot_form=slot_form,
                unit_form=np.where(np.arange(64) < n, rng.integers(0, 3, 64), 0).astype(np.int64),
                opp_past=past.copy(), opp_cycle=objs(8, 4), projectiles=objs(64, 8), effects=objs(32, 6),
                own_ability=objs(8, 7))


def fake_classes():
    class Side:
        model = SimpleNamespace(gid={k: i for i, k in enumerate(VOCAB)}, model=SimpleNamespace(feature_version=6))

        def __init__(self):
            self.applied, self.plays = [], []

        def apply(self, p, d):                          # stands in for SelfPlaySide.apply
            self.applied.append((p, d))

    class Runner:
        def __init__(self, script, plays, rec):
            self.script, self._plays, self.rec = script, plays, rec

        def play(self, arm, m, deadline=None):         # stands in for search_s0.Runner.play
            for tick, p, d, row in self.script:
                for s in (m.learner, m.opp):
                    s._gen_row, s._cur = row, (tick, None, None)
                    s.apply(p, d)
                row['tok'][:] = -1                     # a later in-place change must not reach the record
            m.learner.plays = self._plays
            return self.rec
    return Side, Runner


def fake_game(seed, n=40, rng=None):
    """n decisions every 10 ticks; plays every 5th decision (hand position 1); the 3rd play refused at landing."""
    rng = rng or np.random.default_rng(seed)
    script, plays = [], []
    for i in range(n):
        row, tick = fake_row(rng), 10 * i
        play = i % 5 == 4
        d = dict(play=play, slot=int(row['hand_slot'][1]), cell=int(rng.integers(N_CELLS)) if play else -1,
                 why='gate' if play else 'wait')
        script.append((tick, 0.5, d, row))
        if play:
            plays.append(dict(tick=tick, accepted=len(plays) != 2))
    rec = dict(seed=seed, tag=f's0:gen:{seed}', learner_side=seed % 2, outcome='win', crowns_for=2, crowns_against=1,
               opp_deck=['x'])
    return script, plays, rec


def record(out, seed):
    Side, Runner = fake_classes()
    G.install(SimpleNamespace(Runner=Runner), SimpleNamespace(SelfPlaySide=Side), Path(out), 'cal_evo')
    script, plays, rec = fake_game(seed)
    orig = copy.deepcopy(script)
    m = SimpleNamespace(learner=Side(), opp=Side())
    got = Runner(script, plays, rec).play('plain', m)
    return orig, script, m, got, rec


def test_wrappers_pass_decisions_through_unchanged_and_record_copies():
    with tempfile.TemporaryDirectory() as tmp:
        orig, script, m, got, rec = record(tmp, 7)
        assert got is rec                                        # Runner.play's result untouched
        for side in (m.learner, m.opp):                          # the original apply saw the very same p and d
            assert [(p, id(d)) for p, d in side.applied] == [(p, id(d)) for _, p, d, _ in script]
        assert [d for _, _, d, _ in script] == [d for _, _, d, _ in orig]   # decisions not mutated
        assert not hasattr(m.opp, '_distill')                    # the opponent is never recorded
        z, _ = T.load_game(Path(tmp)/'distill_7.npz')
        for k in G.row_keys():                                   # the record is a copy taken at decision time
            assert np.array_equal(z[k], np.stack([row[k] for *_, row in orig])), k
        assert z['tick'].tolist() == [t for t, *_ in orig]
        assert z['accepted'].sum() == 7 and z['play'].sum() == 8  # 8 plays, one refused


def test_follow_up_plays_fail_closed():
    side = SimpleNamespace(_gen_row=fake_row(np.random.default_rng(0)), _cur=(0, None, None))
    with pytest.raises(ValueError):
        G.snapshot(side, 0.5, dict(play=True, slot=0, cell=0, why='rocket_tornado', follow_ups=[{}]))


def test_worker_command_is_gaps_d3_command():
    job = dict(seeds=[750000, 750001], checkpoint='t.pt', opponent=dict(path='o.pt', temperature=.1), fast=False)
    orig = G.gap.command('D3', job, Path('cal_evo.json'), Path('out'), 'py')
    cmd = G.distill_command('D3', job, Path('cal_evo.json'), Path('out'), 'py')
    assert cmd[1].endswith('gen_distill.py') and orig[1].endswith('livecal.py')
    assert cmd[2:] == orig[2:] and '--own-effects' in cmd       # same worker args = the D3 stack


def test_generation_seeds_avoid_the_evaluation_pairs():
    assert G.block_starts(750000, 5) == [750000, 751000, 752000, 753000, 754000]
    for bad in (741000, 741300, 741900):
        with pytest.raises(ValueError):
            G.block_starts(bad, 1)


def test_row_selection_mirrors_build_replay():
    tick = np.arange(0, 400, 10)
    play = np.isin(tick, [100, 200, 300])
    acc = play & (tick != 300)                                   # the last play refused -> no row, not a wait target
    plays, waits, nxt = T.select(dict(tick=tick, play=play, accepted=acc))
    assert tick[plays].tolist() == [100, 200]
    # buckets of 40: first decisions 0, 40, 80, 120, 160, 200 (play), 240..; 80 is within 20 ticks before 100;
    # 160 is not (200 - 160 = 40); everything after the last accepted play (200) is dropped
    assert tick[waits].tolist() == [0, 40, 120, 160]
    assert tick[nxt].tolist() == [100, 100, 200, 200]


def test_cell_label_inverts_cell_xy():
    xy = torch.tensor([cell_xy(c, 'lattice') for c in range(N_CELLS)], dtype=torch.float32)
    assert torch.equal(cell_label(xy, 'lattice'), torch.arange(N_CELLS))


def tiny_model():
    torch.manual_seed(0)
    return GenModel(d=32, layers=1, d_c=8, n_cards=len(VOCAB), feature_version=6).eval()


def test_training_rows_are_the_teachers_model_inputs():
    with tempfile.TemporaryDirectory() as tmp:
        script, *_ = record(tmp, 7)
        g, meta = T.load_game(Path(tmp)/'distill_7.npz')
    arrs, st = T.build_rows([(g, meta)], 'lattice')
    plays, waits, _ = T.select(g)
    ids = np.r_[plays, waits]
    b = GenRows(arrs, np.arange(len(ids)), torch.device('cpu')).batch(np.arange(len(ids)))
    direct = {k: torch.from_numpy(np.stack([script[i][3][k] for i in ids])) for k in MODEL_KEYS}
    for k in MODEL_KEYS:
        assert torch.equal(b[k].to(direct[k].dtype), direct[k]), k
    model = tiny_model()
    with torch.no_grad():
        o1, o2 = model(b), model(direct)
    for k in ('gate', 'card', 'wait', 'value'):
        assert torch.equal(o1[k], o2[k]), k
    n = len(plays)
    assert st['play_rows'] == n == 7 and b['gate'][:n].eq(1).all() and b['gate'][n:].eq(0).all()
    hs = np.stack([script[i][3]['hand_slot'] for i in plays])
    slot = np.array([script[i][2]['slot'] for i in plays])
    assert (hs[np.arange(n), b['slot'][:n].numpy()] == slot).all()   # card target = the played hand position
    assert cell_label(b['xy'][:n], 'lattice').tolist() == [script[i][2]['cell'] for i in plays]
    assert b['value'].eq(2 - 1 + 3).all()                        # crowns 2-1


def test_trainer_smoke_writes_a_plain_loadable_student():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        seeds = [next(s for s in range(1, 999) if _tag_split(f'cal_evo:{s}', 10) == k) for k in (0, 1)]
        for s in seeds:
            record(tmp, s)
        model = tiny_model()
        init = tmp/'init.pt'
        torch.save({'model': model.state_dict(), 'gen': True, 'd_c': 8, 'card_vocab': VOCAB, 'epoch': 1, 'n_params': 0,
                    'deck': 'generalist', 'args': {'d': 32, 'layers': 1, 'feature_version': 6, 'grid': 'lattice'}}, init)
        assert T.main(['--data', str(tmp), '--init', str(init), '--out', str(tmp/'student.pt'), '--bs', '4',
                       '--max-steps', '2', '--amp', 'none']) == 0
        student, st = load_model(tmp/'student.pt', torch.device('cpu'))
        assert getattr(student, 'cell_refine', None) is None and st['distill']['stats']['games'] == 2
        assert any(not torch.equal(a, b) for a, b in zip(student.state_dict().values(), model.state_dict().values()))
        assert T.main(['--data', str(tmp), '--init', str(init), '--out', str(tmp/'s0.pt'), '--bs', '4',
                       '--max-steps', '1', '--amp', 'none', '--val-pct', '0']) == 0   # pod smoke: no val game
        model.add_cell_refine()                                  # a grafted (refine-head) init is refused
        torch.save({**torch.load(init), 'model': model.state_dict()}, tmp/'grafted.pt')
        with pytest.raises(SystemExit):
            T.main(['--data', str(tmp), '--init', str(tmp/'grafted.pt'), '--out', str(tmp/'x.pt')])


def test_score_pairs_both_seed_sets():
    import json
    import score_distill as SD
    with tempfile.TemporaryDirectory() as tmp:
        for name, arm, win in (('student_D1', 'D1', lambda s: s % 2 == 0), ('teacher_D3', 'D3', lambda s: s % 4 == 0)):
            for start in SD.SEEDS:
                d = Path(tmp)/f'{name}_{start}'/arm
                d.mkdir(parents=True)
                rows = [dict(census=c, seed=s, outcome='win' if win(s) else 'loss', searched=0, opp_deck=['x'],
                             learner_side=s % 2, opp_gen_sha256='e4', plays_accepted=40)
                        for c in ('evo', 'lad') for s in range(start, start+240)]
                (d/'matches.jsonl').write_text('\n'.join(map(json.dumps, rows)))
        text = SD.report(SD.runs(tmp))
    assert 'student_D1: win 50.00% (480/960)' in text and 'teacher_D3: win 25.00% (240/960)' in text
    assert 'student_D1 - teacher_D3: +25.00 pp' in text and 'plain_D1' not in text
