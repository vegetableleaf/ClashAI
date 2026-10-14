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


# ---------------------------------------------------------------- iteration 2: DAgger rounds (DISTILL_PLAN.md)
JOB = dict(seeds=[760000, 760001], checkpoint='s.pt', opponent=dict(path='o.pt', temperature=.1), fast=False)
CENSUS = Path('cal_evo.json')


def d3_flags():
    """The decision flags gap's D3 command adds to D1's (the live stack's rules + --own-effects)."""
    d1, d3 = (G.gap.command(arm, JOB, CENSUS, Path('out'), 'py') for arm in ('D1', 'D3'))
    assert d3[:len(d1)] == d1
    return d3[len(d1):]


def test_command_takes_run_arms_extra_positionally():
    """gap.run_arm calls command(arm, job, census, dest, python, extra): the 6th argument must not replace _orig."""
    args = ('D3', JOB, CENSUS, Path('out'), 'py')
    assert G.distill_command(*args, ()) == G.distill_command(*args)
    assert G.distill_command(*args, ('--tornado-river', 'on'))[-2:] == ['--tornado-river', 'on']
    assert '--tau-threatened' not in G.distill_command(*args, (), ('tau_threatened',))   # gap.run_arm's 7th positional (drop)


def test_dagger_command_is_gaps_d1_plus_the_d3_flags():
    d1 = G.gap.command('D1', JOB, CENSUS, Path('out'), 'py')
    cmd = G.distill_command('D1', JOB, CENSUS, Path('out'), 'py', (), teacher='t.pt', p_teacher=0.5)
    i = cmd.index('--distill')
    assert cmd[1].endswith('gen_distill.py') and cmd[2:i] == d1[2:]          # the student plays exactly gap's D1
    assert cmd[i+1:i+3] == ['t.pt', '0.5'] and cmd[i+3:] == d3_flags() and '--own-effects' in d3_flags()
    argv, path, p, flags = G.split_argv(cmd[1:])
    assert argv == cmd[1:i] and path == 't.pt' and p == .5 and flags == d3_flags()   # livecal.worker sees D1 args only
    assert G.split_argv(['x', '--worker', '--out', 'o']) == (['x', '--worker', '--out', 'o'], None, 0.0, [])
    with pytest.raises(ValueError):
        G.distill_command('D3', JOB, CENSUS, Path('out'), 'py', (), teacher='t.pt')   # the student never plays D3


def policies():
    from pipeline.e1_eval import GenPolicy
    torch.manual_seed(1)
    teacher = GenModel(d=32, layers=1, d_c=8, n_cards=len(VOCAB), feature_version=6)
    teacher.add_cell_refine()                                   # a "grafted" head that acts inside cell_logits
    with torch.no_grad():
        for p in teacher.cell_refine.parameters():
            p.normal_(0, .2)
    return GenPolicy(tiny_model(), VOCAB), GenPolicy(teacher.eval(), VOCAB)


def decision_script(n=24):
    """n prepared decisions: real BoardStates through 1x / 2x / overtime, my left princess losing HP with an enemy near
    it every few decisions (threat state), raw crown towers (lethal / dead-target rules), elixir 10 (hazard draws)."""
    from pipeline.tests.test_lethal_rocket import towers
    from pipeline.tests.test_tau_threatened import L, board
    rng = np.random.default_rng(3)
    out = []
    for i in range(n):
        t = 20.0 + 9.5 * i
        bs = board(t, (1.0, 1.0 - .03 * (i // 3), 1.0), [(L, 5.0, 1)] if i % 3 else ())
        out.append((int(t * 20), bs, {'episode': {'crown_towers': towers(0, 3052 - 90 * i, 3052)}}, fake_row(rng)))
    return out


def fake_side_class():
    """A SelfPlaySide as search_s0.Runner.round and decision_options.match_kwargs use it; apply records."""
    from pipeline import e1_eval as E

    class Side:
        def __init__(self, model, cfg, script):
            self.model, self.cfg, self.script = model, cfg, iter(script)
            self.tag, self.k, self.side = 's0:gen:760001', 0, 0
            self.deck = E.selfplay_deck(E.ICEBOW_ENGINE_DECK)
            self.done_plays, self.pend, self.pending, self.applied, self._gen_row = [], [], None, [], None

        def prepare(self):
            tick, bs, self.state, self._row = next(self.script)
            self._cur, self._gen_row = (tick, bs, bs), None

        def gen_row(self, policy):
            self._gen_row = self._row
            return self._row

        def pre(self, hand):                                    # every hand card affordable, no stall
            return 10.0, np.asarray(hand, bool).copy(), False

        def apply(self, p, d):
            self.applied.append((p, d))
    return Side


def run_rounds(side, n):
    from pipeline import search_s0 as SS
    m = SimpleNamespace(learner=side)
    for _ in range(n):
        SS.Runner.round(None, m, [side], 'plain', {}, None)     # gap's worker loop, one learner decision per round
    return side


def test_teacher_label_is_gaps_d3_decision_and_the_student_acts():
    import argparse
    from pipeline import search_s0 as SS
    from pipeline.decision_options import add_arguments, config_from_args
    ap = argparse.ArgumentParser()
    add_arguments(ap)
    ap.add_argument('--own-effects', action='store_true')
    d1_cfg = {**SS.live_cfg(.35, 'lattice', 'cpu'), 'entry_index': 0, 'feature_version': 6, 'stall_elixir': None}
    d3_cfg = {**d1_cfg, **config_from_args(ap.parse_args(d3_flags()))}   # search_s0._init_worker: cfg.update(options)
    script = decision_script()
    n = len(script)
    student, teacher = policies()
    ref = run_rounds(fake_side_class()(teacher, d3_cfg, script), n)      # gap's D3 path: the teacher plays
    stu = run_rounds(fake_side_class()(student, d1_cfg, script), n)      # gap's D1 path: the student plays
    keys = ('play', 'slot', 'cell', 'why')
    assert any({k: a[k] for k in keys} != {k: b[k] for k in keys} for (_, a), (_, b) in zip(ref.applied, stu.applied))
    assert {d['why'] for _, d in ref.applied} - {'gate', 'wait'}       # a rule decided at least once
    for p_teacher in (0.0, 1.0, 0.5):
        Side = fake_side_class()
        t = G.Teacher(teacher, p_teacher, d3_flags())
        G.install(SimpleNamespace(Runner=SimpleNamespace(play=None)), SimpleNamespace(SelfPlaySide=Side), Path('.'),
                  'cal_evo', teacher=t)
        h = Side(student, d1_cfg, script)
        h._distill = []
        run_rounds(h, n)
        rec = h._distill
        assert [(r['p'], {k: r[k] for k in keys}) for r in rec] == [(p, {k: d[k] for k in keys}) for p, d in ref.applied]
        assert h.rng_decision_options.bit_generator.state == ref.rng_decision_options.bit_generator.state
        assert [(r['s_p'], r['s_play'], r['s_slot'], r['s_cell']) for r in rec] == \
            [(p, d['play'], d['slot'], d['cell']) for p, d in stu.applied]
        for r, (_, _, _, row) in zip(rec, script):                       # the input row = the student's row
            assert all(np.array_equal(r[k], row[k]) for k in G.row_keys() if k in row)
        exe = [r['teacher_exec'] for r in rec]
        if p_teacher in (0.0, 1.0):
            assert exe == [p_teacher == 1.0] * n
        else:
            assert 0 < sum(exe) < n
        for e, got, a, b in zip(exe, h.applied, ref.applied, stu.applied):
            assert got == (a if e else b)                               # the executed action
        assert t.meta['own_effects_not_applied'] and t.meta['p_teacher'] == p_teacher
    other = G.Teacher(type(teacher)(teacher.model, VOCAB[:-1] + ['zz']), 0.0, d3_flags())
    s = fake_side_class()(student, d1_cfg, script)
    s.prepare()
    s.gen_row(student)
    with pytest.raises(ValueError):
        other.decide(s)                                                 # another vocab = another input row: refused


def dagger_record(out, seed):
    """A DAgger game through install's wrappers with a stand-in teacher: it always plays hand position 2 at cell 7,
    and its action is executed at every second decision."""
    class FakeTeacher:
        meta, n = dict(mode='dagger', p_teacher=.5), 0

        def decide(self, side):
            return .7, dict(play=True, slot=int(side._gen_row['hand_slot'][2]), cell=7, why='gate')

        def executes(self, side):
            self.n += 1
            return self.n % 2 == 0
    Side, Runner = fake_classes()
    G.install(SimpleNamespace(Runner=Runner), SimpleNamespace(SelfPlaySide=Side), Path(out), 'cal_evo', FakeTeacher())
    script, plays, rec = fake_game(seed)
    m = SimpleNamespace(learner=Side(), opp=Side())
    Runner(script, plays, rec).play('plain', m)
    return script, m


def test_dagger_game_file_labels_the_teacher_and_executes_the_mix():
    with tempfile.TemporaryDirectory() as tmp:
        script, m = dagger_record(tmp, 7)
        z, meta = T.load_game(Path(tmp)/'distill_7.npz')
    n = len(script)
    assert meta['mode'] == 'dagger' and z['play'].all() and (z['cell'] == 7).all()     # labels = the teacher's
    assert z['accepted'].all()                                 # every teacher play is a PLAY row (no landing to check)
    assert z['teacher_exec'].tolist() == [i % 2 == 1 for i in range(n)]
    assert z['s_play'].tolist() == [d['play'] for _, _, d, _ in script]
    for (p, d), e, (_, ps, ds, _) in zip(m.learner.applied, z['teacher_exec'], script):
        assert (p, d['cell']) == ((.7, 7) if e else (ps, ds['cell']))
    assert [(p, id(d)) for p, d in m.opp.applied] == [(p, id(d)) for _, p, d, _ in script]   # the opponent untouched
    landed = {10 * i for i in range(n) if i % 5 == 4} - {140}  # fake_game: the student plays every 5th, the 3rd refused
    ex = np.where(z['teacher_exec'], z['play'], z['s_play'])
    assert z['exec_accepted'].tolist() == [bool(e and t in landed) for e, t in zip(ex, z['tick'])]


def split_seeds():
    return [next(s for s in range(1, 999) if _tag_split(f'cal_evo:{s}', 50) == k) for k in (0, 1)]


def plain_init(tmp):
    init = tmp/'init.pt'
    torch.save({'model': tiny_model().state_dict(), 'gen': True, 'd_c': 8, 'card_vocab': VOCAB, 'epoch': 1,
                'n_params': 0, 'deck': 'generalist',
                'args': {'d': 32, 'layers': 1, 'feature_version': 6, 'grid': 'lattice'}}, init)
    return init


def test_defaults_reproduce_iteration_1_training_bit_for_bit():
    """Every iteration-2 flag off = the trainer that produced iteration 1 (commit c66f6af)."""
    import importlib.util
    import subprocess
    src = subprocess.run(['git', 'show', 'c66f6af:scratchpad/gauntlet/L74/distill/train_distill.py'],
                         cwd=HERE.parents[3], capture_output=True)
    if src.returncode:
        pytest.skip('iteration-1 trainer not in this git checkout')
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        old_py = tmp/'a'/'b'/'c'/'d'/'train_distill_iter1.py'
        old_py.parent.mkdir(parents=True)
        old_py.write_bytes(src.stdout)
        spec = importlib.util.spec_from_file_location('train_distill_iter1', old_py)
        old = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old)
        (tmp/'gen').mkdir()
        for s in split_seeds():
            record(tmp/'gen', s)
        args = ['--data', str(tmp/'gen'), '--init', str(plain_init(tmp)), '--bs', '4', '--max-steps', '6',
                '--amp', 'none', '--val-pct', '50']
        assert old.main(args + ['--out', str(tmp/'old.pt')]) == 0 and T.main(args + ['--out', str(tmp/'new.pt')]) == 0
        a, b = torch.load(tmp/'old.pt'), torch.load(tmp/'new.pt')
    assert a['model'].keys() == b['model'].keys() and all(torch.equal(a['model'][k], b['model'][k]) for k in a['model'])
    assert a['distill']['hist'] == b['distill']['hist'] and a['distill']['val0'] == b['distill']['val0']


def test_union_cell_kl_and_rehearsal():
    import json
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for d in ('teach', 'dag'):
            (tmp/d).mkdir()
        for s in split_seeds():
            record(tmp/'teach', s)
            dagger_record(tmp/'dag', s)
        g, meta = T.load_game(tmp/'teach'/f'distill_{split_seeds()[0]}.npz')
        arrs, _ = T.build_rows([(g, meta)], 'lattice')
        arrs['split'][:] = 0                                    # a stand-in pro set: every row a TRAIN row
        np.savez(tmp/'pro.npz', meta=json.dumps({'card_vocab': VOCAB}), **arrs)
        init = plain_init(tmp)
        base = ['--data', str(tmp/'teach'), str(tmp/'dag'), '--init', str(init), '--bs', '8', '--max-steps', '4',
                '--amp', 'none', '--val-pct', '50']
        runs = {}
        for name, extra in (('plain', []), ('kl', ['--cell-kl', '1']),
                            ('reh', ['--rehearse', str(tmp/'pro.npz'), '--rehearse-frac', '.25'])):
            assert T.main(base + extra + ['--out', str(tmp/f'{name}.pt')]) == 0
            runs[name] = torch.load(tmp/f'{name}.pt')
        with pytest.raises(SystemExit):
            T.main(base + ['--rehearse-frac', '.25', '--out', str(tmp/'x.pt')])     # a fraction without the data
    d = runs['plain']['distill']
    assert {'src0', 'src1'} <= set(d['val0']) and d['stats']['games'] == 4         # val per data dir
    st = d['stats']                                    # 2 DAgger games x 40 decisions; student plays 8 per game
    assert st['dagger_decisions'] == 80 and st['teacher_exec'] == 40 and st['teacher_play'] == 80
    assert st['gate_agree'] == st['student_play'] == st['both_play'] == 16
    for other in ('kl', 'reh'):                                 # each flag changes the training
        assert any(not torch.equal(runs['plain']['model'][k], runs[other]['model'][k]) for k in runs['plain']['model'])


def test_cell_kl_is_zero_against_itself_and_positive_otherwise():
    torch.manual_seed(0)
    a, b = torch.randn(5, N_CELLS), torch.randn(5, N_CELLS)
    play = torch.tensor([True, False, True, True, False])
    assert T.cell_kl(a, a, play).abs() < 1e-6 and T.cell_kl(a, b, play) > 0
    assert T.cell_kl(a, b, torch.zeros(5, dtype=torch.bool)) == 0
    p, q = a[play].log_softmax(-1), b[play].log_softmax(-1)      # KL(plain = b || student = a), mean over play rows
    assert torch.allclose(T.cell_kl(a, b, play), (q.exp() * (q - p)).sum(-1).mean())


def test_pro_report_applies_the_bar():
    import json
    import score_distill as SD
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for name, nll in (('plain', 3.10), ('dagger', 3.35), ('daggerkl', 3.45)):
            m = dict(cell_nll=nll, cell_half_top1=.2, card_top1=.65, gate_bal_acc=.75, n=12237, n_play=3854)
            (Path(tmp)/f'{name}.json').write_text(json.dumps({'v3val': {'model': m}}))
            paths.append((name, Path(tmp)/f'{name}.json'))
        text = SD.pro_report(paths)
    assert 'dagger: cell_nll 3.350 (+0.250 PASS)' in text and 'daggerkl: cell_nll 3.450 (+0.350 FAIL)' in text
    assert 'plain: cell_nll 3.100 (+0.000)' in text
