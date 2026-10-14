"""Offline NEWSIM acceptance: synthetic observations, no SIM or model assets."""
import copy
import csv
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from pipeline import e1_eval as E, rl_royale as R
from scratchpad.gauntlet.L74.newsim import census as C, driver as D, evaluate as EV, metrics as M

ROOT = R.REPO


def cfg(*args):
    return R.load_config(ROOT/'pipeline/rl_royale.yaml', list(args), False)


def test_zero_identical_hash_and_rollouts():
    c = cfg()
    legacy = {k: v for k, v in c.items() if k != 'hero_abilities'}
    golden = hashlib.sha256(json.dumps(legacy, sort_keys=True, default=str).encode()).hexdigest()
    assert R.config_sha(c) == golden == R.config_sha(cfg('learner_pipeline_frac=0'))
    js = [(1, dict(tag='x'), 2)]
    expected = [(1, dict(tag='x'), 2, dict(rollout_index=2, update=4, obs_seed=R.rl_obs_seed('x', 2, 4)))]
    assert R.rollout_jobs(js, 4) == expected == R.rollout_jobs(js, 4, 0, 74)
    assert 'pipeline_decisions' not in R.actor_cfg({**cfg('action_delay_ticks=26', 'learner_pipeline_frac=.3'), 'grid': 'lattice'}, 'screen', 0, 'cpu')


@pytest.mark.parametrize('value', ['-0.1', '1.1', 'true', '.nan', '.inf', 'nope'])
def test_fraction_validation(value):
    with pytest.raises(SystemExit, match='learner_pipeline_frac'):
        cfg('action_delay_ticks=26', f'learner_pipeline_frac={value}')


def test_delay_required_and_old_key_not_passed():
    with pytest.raises(SystemExit, match='action_delay_ticks'):
        cfg('learner_pipeline_frac=.3')
    with pytest.raises(SystemExit, match='unknown config key'):
        cfg('pipeline_decisions=true')
    assert 'pipeline_decisions' not in R.actor_cfg({**cfg(), 'grid': 'lattice', 'pipeline_decisions': True}, 'rollout', 0, 'cpu')


@pytest.mark.parametrize('seed', [0, 74, 75])
def test_seeded_mixture_actor_order_independent(seed):
    js = [(i, dict(tag=f'm{i}'), g) for i in range(2500) for g in range(4)]
    a = R.rollout_jobs(js, 3, .3, seed)
    flags = [r[3]['pipeline_decisions'] for r in a]
    assert .28 < sum(flags)/len(flags) < .32
    assert all(r[3]['pipeline_tau_delta'] == 0 for r in a)
    assert R.rollout_jobs(js[::-1], 3, .3, seed)[::-1] == a
    assert R.rollout_jobs(js[:30], 3, .3, seed) == a[:30]
    assert R.rollout_jobs(js, 4, .3, seed) != a
    assert R.rollout_jobs(js, 3, .3, seed+1) != a
    assert all(r[3]['pipeline_decisions'] for r in R.rollout_jobs(js[:20], 3, 1, seed))


def test_mixture_never_leaks_to_opponent(monkeypatch):
    got = []
    class Match:
        def __init__(self, env, spec, k, lc, oc, *args):
            self.env = env
            got.append((lc, oc))
        def due(self):
            return []
        def result(self):
            return {}
    monkeypatch.setattr(E, 'SelfPlayMatch', Match)
    js = R.rollout_jobs([(0, dict(tag='a', opp=dict(id='o')), 0)], 1, 1, 74)
    E.run_selfplay_batch(object, object(), {'o': (object(), dict(policy='sample', record=False))},
                        js, dict(policy='sample', record=True), 1, lambda r: None)
    lc, oc = got[0]
    assert lc['pipeline_decisions'] is True and lc['pipeline_tau_delta'] == 0
    assert not {'obs_seed', 'pipeline_decisions', 'pipeline_tau_delta'} & oc.keys()
    assert oc['rollout_index'] == 0 and oc['update'] == 1


NAMES = ['Golem', 'Knight', 'Archer', 'Zap', 'Fireball', 'Musketeer', 'Minions', 'Log', 'HogRider', 'Earthquake']
BAD = NAMES[:8]
GOOD = ['HogRider', *NAMES[1:7], 'Earthquake']


def csv_file(tmp_path, rows):
    p = tmp_path/'battles.csv'
    with p.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['replay_tag', 'team_deck', 'opponent_deck'])
        w.writeheader()
        w.writerows(rows)
    return p


def row(tag='a', team=BAD, opp=GOOD):
    return dict(replay_tag=tag, team_deck=','.join(team), opponent_deck=','.join(opp))


def test_census_both_sides_deck_dedupe_and_replay_dedupe(tmp_path):
    p = csv_file(tmp_path, [row(), row(), row('b', BAD[::-1], GOOD[::-1])])
    decks, report = C.load_humans(p, NAMES)
    assert report['rows'] == 3 and report['battles'] == 2
    assert report['duplicate_battles'] == 1 and report['accepted_sides'] == 4
    assert report['unique_decks'] == 2 and report['deduped_deck_sides'] == 2
    assert report['archetypes']['golem'] == dict(decks=1, sides=2)
    assert sorted(decks.values()) == [2, 2]


def test_unloadable_cards_drop_whole_deck_and_count(tmp_path):
    p = csv_file(tmp_path, [row(team=['Unreleased', *BAD[1:]])])
    decks, report = C.load_humans(p, NAMES)
    assert len(decks) == 1 and report['dropped_sides'] == 1
    assert report['unloadable_card_occurrences'] == {'Unreleased': 1}
    assert all(len(d) == 8 for d in decks)


def test_slug_forms_and_different_forms_remain_distinct(tmp_path):
    p = csv_file(tmp_path, [row(team=['golem', 'knight@evolution', 'archers', 'zap', 'fireball', 'musketeer', 'minions', 'the-log']), row('b')])
    decks, report = C.load_humans(p, NAMES)
    assert report['accepted_sides'] == 4 and len(decks) == 3
    assert any('Knight@evolution' in d for d in decks)


@pytest.mark.parametrize('bad', [BAD[:7], BAD[:7]+['Golem'], BAD[:7]+['Log@invalid']])
def test_invalid_decks_not_repaired(tmp_path, bad):
    _, report = C.load_humans(csv_file(tmp_path, [row(team=bad)]), NAMES)
    assert report['dropped_sides'] == 1


def test_conflicting_replay_rejected(tmp_path):
    with pytest.raises(ValueError, match='conflicting duplicate'):
        C.load_humans(csv_file(tmp_path, [row(), row(opp=BAD)]), NAMES)


def test_weighting_dedupe_and_runtime_drop():
    source = dict(decks=[dict(engine=BAD, sides=5), dict(engine=GOOD, sides=20)])
    human = {tuple(sorted(BAD)): 1, tuple(sorted(GOOD)): 1}
    result = C.combine([source], human, NAMES)
    assert len(result['decks']) == 2
    assert result['adaptive_unfavourable_share'] == pytest.approx(.6)
    assert result['newsim_census']['natural_archetypes']['golem']['sides'] == 6
    seen = []
    C.combine([source], human, NAMES, validate=lambda d: seen.append(d))
    assert len(seen) == 2
    with pytest.raises(ValueError, match='both favourable'):
        C.combine([source], human, NAMES, validate=lambda d: 'unsupported' if 'Golem' in d else None)


@pytest.mark.parametrize('args', [[], ['--arm', 'bogus'], ['--arm', 'base', '--out', 'x', '--workers', '25'],
                                  ['--arm', 'base', '--out', 'x', '--workers', '0'],
                                  ['--arm', 'base', '--out', 'x', '--unknown']])
def test_bad_driver_arguments(args):
    with pytest.raises(SystemExit):
        D.parse_args(args)


@pytest.mark.parametrize('arm,fraction', [('base', 0), ('fast', .3)])
def test_driver_plan_and_training_contract(arm, fraction):
    a = D.parse_args(['--arm', arm, '--workers', '24', '--out', 'x', '--plan-only'])
    p = D.plan(a)
    assert p['learner_pipeline_frac'] == fraction and p['max_processes'] == 28
    assert [c['main_target'] for c in p['cycles']] == [20, 40, 60]
    assert [c['exploiter_target'] for c in p['cycles']] == [15]*3
    assert len(p['extra_exploiters']) == 3 and len(p['evaluations']) == 4
    for phase in ('main', 'exploiter'):
        c = D.training_config(cfg(), phase, p['cycles'][0], 'decks.json', ['exp.pt'], a)
        assert c['learner_pipeline_frac'] == fraction and c['n_actors'] == 24
        assert c['hero_abilities'] and c['ability_policy'] == 'v2' and c['opp_style'] == 'on'
        assert c['shaping'] == 'none' and c['stall_elixir'] is None and not c['branch_gate']
        assert c['opp_elixir'] == 'counter'
        if phase == 'main':
            assert c['init'] == str(D.INIT) and c['league_pfsp'] == 'hard'
        else:
            assert c['league_frozen_opponent'] == p['cycles'][0]['frozen']


@pytest.mark.parametrize('pool,t', [('CAL', .1), ('P2', .3)])
def test_eval_flags_and_pairing(pool, t, tmp_path):
    off, on = [EV.worker_config('model.pt', 'decks.json', pool, b) for b in (False, True)]
    assert off['opp_T'] == t and off['opp_policy'] == 'sample'
    assert not off['pipeline_decisions'] and on['pipeline_decisions']
    assert on['pipeline_tau_delta'] == 0
    assert {k: v for k, v in off.items() if k != 'pipeline_decisions'} == {k: v for k, v in on.items() if k != 'pipeline_decisions'}
    assert off['decision_options']['gate_hazard_min_elixir'] == 9
    path = tmp_path/'decks.json'
    path.write_text(json.dumps(C.combine([], {tuple(BAD): 1, tuple(GOOD): 1}, NAMES)))
    jobs = EV.jobs(path, 30000)
    assert len(jobs) == 480 and jobs == EV.jobs(path, 30000)


def test_comparison_rejects_partial_wrong_decks_and_duplicates(tmp_path):
    a = {('evo', str(i)): dict(outcome='loss', opp_deck=BAD, seed=i, learner_side=i%2) for i in range(960)}
    b = copy.deepcopy(a)
    assert D.compare(a, b)['delta_pp'] == 0
    b['evo', '0']['outcome'] = 'win'
    assert D.compare(a, b)['delta_pp'] > 0
    b['evo', '0']['opp_deck'] = GOOD
    with pytest.raises(ValueError, match='paired decks'):
        D.compare(a, b)
    with pytest.raises(ValueError, match='960'):
        D.compare({}, {})


def frame(t, own_hp=100, other_hp=100, y=None, side=1):
    return dict(tick=t, towers=[dict(side=side, hp=own_hp), dict(side=1-side, hp=other_hp)],
        bodies=[] if y is None else [dict(side=1-side, id=7, card='golem', x=3500, y=y, hp=100)])


def test_public_phase_boundaries_and_tiebreak_excluded():
    frames = [frame(0), frame(2399, 90, 80), frame(2400, 90, 80), frame(4799, 70, 60),
              frame(4800, 70, 60), frame(5999, 60, 30), frame(6000, 0, 0)]
    m = M.measure(frames, [], 1)
    assert [m['phases'][p]['net_hp_end'] for p in ('1x', '2x', '3x')] == [10, 10, 30]
    assert [m['phases'][p]['net_damage'] for p in ('1x', '2x', '3x')] == [10, 0, 20]
    assert M.measure([frame(0), frame(20)], [], 1)['phases']['3x'] is None


@pytest.mark.parametrize('side', [0, 1])
def test_tank_crossing_delay_and_missing_response(side):
    y = lambda v: v if side == 1 else 32000-v
    frames = [frame(t, y=y(15900 if t == 0 else 16100), side=side) for t in range(0, 21, 10)]
    plays = [dict(tick=20, side=side, card='Tesla', accepted=True, x=9000, y=y(22000))]
    e = M.measure(frames, plays, side)['tank_crossings'][0]
    assert e['delay_s'] == .5 and not e['complete']
    assert M.measure(frames, [], side)['tank_crossings'][0]['delay_s'] is None
    assert not M.measure(frames[1:], plays, side)['tank_crossings']  # first-seen intrusion is not a crossing


def test_launcher_contract():
    s = (Path(__file__).parent/'run_newsim.sh').read_text()
    assert s.index('flock 9') < s.index('flock 8') < s.index('-m venv')
    assert '--no-index' in s and 'royalesim==0.1.33 royalegym==0.1.23' in s
    assert 'trap finish EXIT' in s and 'SUMMARY.txt' in s and 'DONE' in s
    assert 'ROYALE_RUNTIME=20261012-linux' in s and 'WORKERS <= 24' in s
    assert 'if [[ ! -e "$NEW" ]]' in s


def test_smoke_failure_writes_summary_done_without_training(tmp_path, monkeypatch):
    from pipeline import royale_runtime as runtime
    monkeypatch.setattr(runtime, 'activate', lambda: {'runtime_id': '20261012-linux'})
    calls = []
    def fail(args, log):
        calls.append(list(map(str, args)))
        raise RuntimeError('hero smoke failed')
    monkeypatch.setattr(D.D, 'run', fail)
    with pytest.raises(RuntimeError, match='smoke failed'):
        D.main(['--arm', 'base', '--out', str(tmp_path)])
    assert len(calls) == 1 and calls[0][1].endswith('smoke.py')
    assert (tmp_path/'SUMMARY.txt').read_text().startswith('VERDICT: Failed')
    assert (tmp_path/'DONE').read_text() == 'exit_code=1\n'
    with pytest.raises(FileExistsError):
        D.main(['--arm', 'base', '--out', str(tmp_path)])


def test_complete_driver_with_fake_training_and_eval(tmp_path, monkeypatch):
    """Execute the real control flow with tiny checkpoint/stage fixtures, no SIM."""
    import torch
    from pipeline import royale_runtime as runtime
    monkeypatch.setattr(D, 'ROOT', tmp_path)
    monkeypatch.setattr(D.D, 'REPO', tmp_path)
    monkeypatch.setattr(R, 'RUN_ROOT', tmp_path/'train_logs')
    (tmp_path/'pipeline').mkdir()
    (tmp_path/'pipeline/rl_royale.yaml').write_bytes((ROOT/'pipeline/rl_royale.yaml').read_bytes())
    monkeypatch.setattr(runtime, 'activate', lambda: dict(runtime_id='20261012-linux'))
    monkeypatch.setattr(D, 'input_receipt', lambda *args: None)
    monkeypatch.setattr(D.census, 'prepare', lambda *args: {'fixture': True})
    donor = {'model': {'cell_refine.weight': torch.tensor([3.])}}
    D.D.save_checkpoint(tmp_path/D.D.OLD, donor)
    configs, commands = [], []
    def train(c, run, out):
        configs.append((run, copy.deepcopy(c)))
        payload = dict(model={'base': torch.tensor([1.])}, rl=dict(league=dict(external=list(c['league_external']))))
        D.D.save_checkpoint(tmp_path/D.D.checkpoint(run), payload)
        D.D.save_checkpoint(tmp_path/D.D.CKROOT/run/f'{run}_u0015.pt', payload)
        log = R.RUN_ROOT/run
        log.mkdir(parents=True, exist_ok=True)
        (log/'train_log.jsonl').write_text('{}\n')
        return payload
    def run(args, log):
        args = list(map(str, args))
        commands.append(args)
        Path(log).write_text('fixture subprocess log\n')
        if args[1].endswith('smoke.py'):
            Path(args[-1]).write_text('{"passed": true}')
        elif args[1].endswith('graft_generic.py'):
            payload = torch.load(tmp_path/args[2], weights_only=True)
            payload['model'].update(donor['model'])
            D.D.save_checkpoint(Path(args[-1]), payload)
        elif args[1].endswith('evaluate.py'):
            dest = Path(args[args.index('--out')+1])
            dest.mkdir()
            start = int(args[args.index('--start')+1])
            rows = [dict(tag=f's0:gen:{i}', seed=i, learner_side=i%2, outcome='draw', opp_deck=GOOD,
                         phase_stats=dict(available=True, phases={p: None for p in M.V.PHASES}, tank_crossings=[]))
                    for i in range(start, start+480)]
            (dest/'matches.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            (dest/'COMPLETE').write_text('480 games\n')
        else:
            pytest.fail(f'unexpected stage {args}')
    monkeypatch.setattr(D.D, 'train', train)
    monkeypatch.setattr(D.D, 'run', run)
    out = tmp_path/'results'
    D.main(['--arm', 'fast', '--workers', '24', '--out', str(out)])
    assert (out/'DONE').read_text() == 'exit_code=0\n'
    assert (out/'SUMMARY.txt').read_text().startswith('VERDICT: Improvement not established')
    assert (out/'newsim_fast_final_grafted.pt').is_file()
    assert len(list((out/'training_logs').glob('*/train_log.jsonl'))) == 4
    assert len(configs) == 6 and all(c['learner_pipeline_frac'] == .3 for _, c in configs)
    assert [len(c['league_external']) for n, c in configs if n.endswith('_main')] == [3, 4, 5]
    evaluations = [c for c in commands if c[1].endswith('evaluate.py')]
    assert len(evaluations) == 16 and sum('--fast' in c for c in evaluations) == 8
    scores = json.loads((out/'scores.json').read_text())
    assert len(scores) == 8 and all(v['pairs'] == 960 for v in scores.values())
