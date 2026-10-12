import copy
import importlib.util
import json
from pathlib import Path

import pytest
from pipeline.tests.memory_fixtures import tmp_path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('tornado_driver_test', ROOT/'scratchpad/gauntlet/L74/tornado/driver.py')
D = importlib.util.module_from_spec(spec)
spec.loader.exec_module(D)


def games(n=960, tornado=False):
    return {('evo' if i < n//2 else 'lad', str(i)): dict(seed=i, learner_side=i % 2,
        opp_deck=['deck'], opp_gen_sha256='opp', outcome='win' if i % 2 else 'loss',
        own_plays=[[0, 26, 'the_log', True, 7.], [10, 50, 'tornado' if tornado else 'skeletons', True, 5.],
                   [35, 75, 'knight', True, 4.], [36, 76, 'tornado', False, 1.]], plays_accepted=3)
        for i in range(n)}


def test_eval_plan_exact_960_per_arm_opponents_and_modes():
    for ck, temp in [(D.A.CAL_C, .1), (D.GEN1, .3)]:
        for pipeline in (False, True):
            seeds = []
            for census, start in [(D.A.EVO, 30000), (D.A.LAD, 30480)]:
                cmd = D.eval_command('fixed.pt', 'out', census, start, 20, ck, temp, pipeline)
                assert cmd[cmd.index('--opp-gen')+1] == str(ck)
                assert cmd[cmd.index('--opp-T')+1] == str(temp)
                assert ('--pipeline-decisions' in cmd) == pipeline
                if pipeline:
                    assert cmd[cmd.index('--pipeline-tau-delta')+1] == '0'
                assert '--record-plays' in cmd and '--behaviour-telemetry' in cmd
                lo, hi = map(int, cmd[cmd.index('--seeds')+1].split(':'))
                seeds.extend(range(lo, hi))
            assert len(set(seeds)) == len(seeds) == 960
    cmd = D.eval_command('base.pt', 'out', D.A.EVO, 0, 20, D.GEN1, .3, True, bait=True)
    assert cmd[1].endswith('logbait_s0.py') and '-m' not in cmd


def test_profile_counts_accepted_landings_boundary_mix_and_elixir():
    p = D.profile(games(2).values())
    assert p['second_cards'] == 2 and p['plays'] == 6
    assert p['second_card_mix'] == {'skeletons': 1.}
    assert p['share_plays_within_24_ticks'] == pytest.approx(1/3)
    assert p['share_consecutive_gaps_within_24_ticks'] == .5
    assert p['elixir_at_play'] == pytest.approx(16/3)


def test_paired_ci_and_candidate_fail_closed():
    live = games()
    c = D.compare(live, copy.deepcopy(live), {'tornado': .119})
    assert c['paired_win_delta_ci'] == dict(mean=0., low=0., high=0.)
    assert c['live_wins'] == 480 and c['non_inferior'] and c['tornado_ok']
    all_results = {k: c for k in ('hard_on', 'hard_off', 'old_on', 'old_off')}
    assert D.verdict(all_results) == 'candidate'
    bad = D.compare(live, games(tornado=True), {'tornado': .119})
    assert not bad['tornado_ok']
    assert D.verdict(dict(all_results, hard_on=bad)) == 'not candidate'
    assert D.verdict(dict(all_results, old_off=dict(c, non_inferior=False))) == 'not candidate'
    worse = copy.deepcopy(live)
    for r in worse.values():
        r['outcome'] = 'loss'
    assert not D.compare(live, worse, {'tornado': .119})['non_inferior']
    with pytest.raises(ValueError):
        D.verdict({'hard_on': c})
    with pytest.raises(ValueError):
        D.compare(live, {}, {'tornado': .119})
    changed = copy.deepcopy(live)
    next(iter(changed.values()))['opp_deck'] = ['different']
    with pytest.raises(ValueError, match='setup mismatch'):
        D.compare(live, changed, {'tornado': .119})
    empty = copy.deepcopy(live)
    for r in empty.values():
        r.update(own_plays=[], plays_accepted=0)
    assert not D.compare(live, empty, {'tornado': .119})['tornado_ok']


def test_load_group_rejects_stale_incomplete_and_wrong_pipeline(tmp_path):
    for census in ('evo', 'lad'):
        dest = tmp_path/f'fixed_{census}'
        dest.mkdir()
        run = dict(gen_sha256='fixed', opp_gen_sha256='opp', opp_T=.1, pipeline_decisions=True,
                   pipeline_tau_delta=0, record_plays=True)
        (dest/'run.json').write_text(json.dumps(run))
        r = next(iter(games(2).values()))
        r.update(arm='plain', tag='one', pipeline_decisions={})
        (dest/'matches.jsonl').write_text(json.dumps(r)+'\n')
    assert len(D.load_group(tmp_path, 'fixed', True, 'fixed', 'opp', .1, games=1)) == 2
    with pytest.raises(ValueError, match='configuration'):
        D.load_group(tmp_path, 'fixed', False, 'fixed', 'opp', .1, games=1)
    with pytest.raises(ValueError, match='incomplete'):
        D.load_group(tmp_path, 'fixed', True, 'fixed', 'opp', .1)
    with pytest.raises(ValueError, match='configuration'):
        D.load_group(tmp_path, 'fixed', True, 'stale', 'opp', .1, games=1)


def test_shell_wait_gate_locks_done_and_no_deploy_writes():
    sh = (ROOT/'scratchpad/gauntlet/L74/tornado/run_tornado_fix.sh').read_text()
    assert sh.index('while [ ! -f "$WAIT_FOR" ]') < sh.index('flock /workspace/gpu.lock')
    assert 'flock /workspace/cpu.lock' in sh
    assert 'mkdir "$OUT"' in sh and 'touch "$OUT/DONE"' in sh and 'SUMMARY.txt' in sh
    assert 'trap finish EXIT' in sh and 'set -euo pipefail' in sh
    assert 'CKPT_OVERRIDE' not in sh and 'LIVE_OPTIONS' not in sh
