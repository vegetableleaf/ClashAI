"""--probe-xbow-focus (owner 2026-10-15, SIM-ONLY measurement probe, never live): once an enemy princess is damaged, an
offensive X-Bow of ours that misses the weaker alive princess moves to the model's best cell reaching it.

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_probe_xbow_focus.py
"""
import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from pipeline.decision_options import (DecisionOptions, add_arguments, options_from_config, probe_xbow_focus_cell,
                                      probe_xbow_focus_princess, xbow_offensive_cells)
from pipeline.live_options import _decision_parser, add_live_options_arguments, parse_with_live_options

REPO = Path(__file__).resolve().parents[2]
LIVE_PLAY = REPO / 'scratchpad/gauntlet/L68/live_reader/live_play.py'
ALL = (True, True, True)


def cell(x, y):
    """Lattice cell at board tiles (x, y), my frame (enemy towers at the top)."""
    return int(round(y * 2)) * 36 + int(round(x * 2))


LOCK_L, LOCK_R = cell(2.5, 19.5), cell(15.5, 19.5)      # reach only the L / R princess
POCKET_L = cell(2.5, 12.5)                               # with L down: reaches the king only
DEFENSIVE = cell(9.0, 30.0)                              # reaches no enemy tower
MIDDLE = cell(9.0, 17.0)                                 # reaches both princesses


def reaches(c, focus):
    return bool(xbow_offensive_cells((False, focus == 1, focus == 2), 'lattice')[c])


def test_geometry_of_the_fixture_cells():
    assert reaches(LOCK_L, 1) and not reaches(LOCK_L, 2) and reaches(LOCK_R, 2) and not reaches(LOCK_R, 1)
    assert reaches(MIDDLE, 1) and reaches(MIDDLE, 2)
    assert not xbow_offensive_cells(ALL, 'lattice')[DEFENSIVE]
    assert xbow_offensive_cells((True, False, True), 'lattice')[POCKET_L] and not reaches(POCKET_L, 2)


@pytest.mark.parametrize('alive,hp,want', [
    (ALL, (1.0, 1.0), None), (ALL, (.96, .95), None),            # no princess below .95: no restriction
    (ALL, (.9, 1.0), 1), (ALL, (1.0, .5), 2), (ALL, (.94, .6), 2),  # the weaker one, not merely a damaged one
    (ALL, (.5, .5), None),                                       # exact tie: no restriction
    (ALL, (None, .9), 2),                                        # unknown hp counts as full
    ((True, False, True), (0.0, 1.0), 2), ((True, True, False), (1.0, 0.0), 1),   # one alive: it, damaged or not
    ((True, False, False), (0.0, 0.0), None)])                   # none alive: never the king
def test_focus_princess(alive, hp, want):
    assert probe_xbow_focus_princess(alive, hp) == want


def logits_with(**at):
    x = torch.zeros(36 * 64)
    for c, v in at.items():
        x[int(c[1:])] = v
    return x


def test_offensive_xbow_moves_to_the_best_cell_reaching_the_focus_princess():
    other = cell(3.5, 18.5)
    assert reaches(other, 1)
    lg = logits_with(**{f'c{LOCK_R}': 10.0, f'c{LOCK_L}': 5.0, f'c{other}': 3.0})
    got = probe_xbow_focus_cell(lg, LOCK_R, ALL, (.5, 1.0), 'lattice')
    assert got == LOCK_L and reaches(got, 1)


def test_king_only_cell_moves_to_the_alive_princess():
    lg = logits_with(**{f'c{POCKET_L}': 10.0, f'c{LOCK_R}': 2.0})
    assert probe_xbow_focus_cell(lg, POCKET_L, (True, False, True), (0.0, 1.0), 'lattice') == LOCK_R


@pytest.mark.parametrize('c,alive,hp', [
    (DEFENSIVE, ALL, (.5, 1.0)),          # defensive: never restricted
    (MIDDLE, ALL, (.5, 1.0)),             # already reaches the focus princess
    (LOCK_L, ALL, (.5, 1.0)),             # on the focus princess
    (LOCK_R, ALL, (1.0, 1.0)),            # nothing damaged yet
    (LOCK_R, ALL, (.5, .5))])             # tie
def test_unchanged(c, alive, hp):
    lg = logits_with(**{f'c{LOCK_L}': 50.0})
    assert probe_xbow_focus_cell(lg, c, alive, hp, 'lattice') == c


def test_empty_mask_keeps_the_model_cell():
    reach_l = torch.as_tensor(xbow_offensive_cells((False, True, False), 'lattice'))
    lg = logits_with(**{f'c{LOCK_R}': 10.0}).masked_fill(reach_l, -torch.inf)
    assert probe_xbow_focus_cell(lg, LOCK_R, ALL, (.5, 1.0), 'lattice') == LOCK_R


# ---- search_s0 wiring --------------------------------------------------------------------------------------------
S = pytest.importorskip('pipeline.search_s0')


def side(lhp, rhp, logits, card='Xbow'):
    towers = [SimpleNamespace(alive=True, hp_frac=1.0)] * 3 + [
        SimpleNamespace(alive=True, hp_frac=1.0), SimpleNamespace(alive=lhp > 0, hp_frac=lhp),
        SimpleNamespace(alive=rhp > 0, hp_frac=rhp)]
    return SimpleNamespace(deck=SimpleNamespace(cards=['Knight', 'Log', 'Rocket', card]), _cur=(0, SimpleNamespace(towers=towers)),
                           model=SimpleNamespace(cell_logits=lambda enc, slot: logits[None]),
                           cfg={'grid': 'lattice', 'device': 'cpu'})


def test_runner_probe_moves_and_counts():
    st = dict(probe_xbow_focus_xbows=0, probe_xbow_focus_changed=0)
    lg = logits_with(**{f'c{LOCK_R}': 10.0, f'c{LOCK_L}': 5.0})
    d = {'play': True, 'slot': 3, 'cell': LOCK_R, 'why': 'gate'}
    got = S.Runner.probe_xbow(None, side(.5, 1.0, lg), {}, d, st)
    assert got == {**d, 'cell': LOCK_L} and d['cell'] == LOCK_R and st == dict(probe_xbow_focus_xbows=1, probe_xbow_focus_changed=1)
    assert S.Runner.probe_xbow(None, side(1.0, 1.0, lg), {}, d, st) is d                       # nothing damaged
    assert S.Runner.probe_xbow(None, side(.5, 1.0, lg, card='Tesla'), {}, d, st) is d          # not an X-Bow: not counted
    assert st == dict(probe_xbow_focus_xbows=2, probe_xbow_focus_changed=1)


def stub_main(argv, tmp_path):
    """search_s0.main with the worker stubbed -> (run.json, wargs)."""
    seen = {}
    o_init, o_job = S._init_worker, S._run_job
    S._init_worker = lambda args: seen.update(args)
    S._run_job = lambda job: {'arm': job[0], 'opp': job[1], 'seed': job[2], 'skipped': 'stub'}
    try:
        S.main(['--out', str(tmp_path / 'o'), '--seeds', '0:1', '--opps', 'gen', '--arms', 'plain', *argv])
    finally:
        S._init_worker, S._run_job = o_init, o_job
    return json.loads((tmp_path / 'o' / 'run.json').read_text()), seen


def test_default_off_run_json_and_worker_args_unchanged(tmp_path):
    assert S.Runner.probe_xbow_focus is False
    run, wargs = stub_main([], tmp_path / 'a')
    assert 'probe_xbow_focus' not in run and 'probe_xbow_focus' not in wargs
    run, wargs = stub_main(['--probe-xbow-focus'], tmp_path / 'b')
    assert run['probe_xbow_focus'] is True and wargs['probe_xbow_focus'] is True


def test_refused_outside_the_plain_live_policy(tmp_path):
    with pytest.raises(SystemExit):
        stub_main(['--probe-xbow-focus', '--arms', 'plain,search'], tmp_path / 'a')
    with pytest.raises(SystemExit):
        stub_main(['--probe-xbow-focus', '--learner-policy', 'sample'], tmp_path / 'b')


def test_gap_d3_extra_carries_the_flag(tmp_path):
    """gap.py --extra=--probe-xbow-focus (the '=' form: argparse refuses a bare value starting with '--') -> the D3
    worker command, run through search_s0.main: the flag parses and reaches the worker on the live stack."""
    spec = importlib.util.spec_from_file_location('gap', REPO / 'scratchpad/gauntlet/L74/gap/gap.py')
    gap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gap)
    ap = argparse.ArgumentParser(); ap.add_argument('--extra', default='')
    extra = ap.parse_args(['--extra=--probe-xbow-focus']).extra.split()
    job = dict(seeds=[741200], checkpoint=S.GEN_CKPT, opponent=dict(path=S.GEN_CKPT, temperature=.1), fast=False)
    cmd = gap.command('D3', job, 'census.json', tmp_path / 'o', 'python', extra=extra)
    assert cmd[-1] == '--probe-xbow-focus' and '--xbow-dead-lane' in cmd
    argv = cmd[cmd.index('--worker') + 1:]
    assert argv[:2] == ['--out', str(tmp_path / 'o')]
    run, wargs = stub_main(argv[2:], tmp_path / 'w')       # stub_main sets --out itself
    assert run['probe_xbow_focus'] is True and wargs['probe_xbow_focus'] and wargs['decision_options']['xbow_dead_lane'] == 'block'


def test_default_off_never_calls_the_probe_in_a_real_match(monkeypatch):
    pytest.importorskip('pipeline.royale_env')   # pins the Royale runtime first
    from pipeline.tests.test_search_s0 import HOGEQ, runner
    run = runner(tail_cap=600)
    monkeypatch.setattr(S.Runner, 'probe_xbow', lambda *a, **k: pytest.fail('probe called with the flag off'))
    rec = run.play('plain', run.setup('gen', 3, HOGEQ))
    assert not any(k.startswith('probe_') for k in rec) and rec['decisions'] > 0


# ---- live cannot take it -----------------------------------------------------------------------------------------
def test_not_a_decision_option():
    assert not any('probe' in f for f in DecisionOptions.__dataclass_fields__)
    assert options_from_config({'probe_xbow_focus': True}) == DecisionOptions()     # a cfg key is ignored, never applied


def test_shared_decision_parser_and_live_options_parser_reject_it():
    ap = argparse.ArgumentParser(); add_arguments(ap)
    with pytest.raises(SystemExit):
        ap.parse_args(['--probe-xbow-focus'])
    with pytest.raises(SystemExit):
        _decision_parser('LIVE_OPTIONS', allow_abbrev=False).parse_args(['--probe-xbow-focus'])


def test_live_options_file_refuses_it(tmp_path):
    f = tmp_path / 'LIVE_OPTIONS'
    f.write_text('--xbow-dead-lane block --probe-xbow-focus\n')
    ap = argparse.ArgumentParser(); add_arguments(ap); add_live_options_arguments(ap, f)
    with pytest.raises(SystemExit) as e:
        parse_with_live_options(ap, [])
    assert e.value.code == 2


def test_live_play_source_never_names_it():
    src = LIVE_PLAY.read_text(encoding='utf-8').lower()
    assert 'probe-xbow' not in src and 'probe_xbow' not in src


@pytest.mark.skipif(not (REPO / 'icebow/data/reader_config.json').is_file(), reason='live reader config not present')
def test_live_play_parser_rejects_it():
    out = subprocess.run([sys.executable, str(LIVE_PLAY), '--check', '--probe-xbow-focus'],
                         capture_output=True, text=True, timeout=300, cwd=REPO)
    if 'ModuleNotFoundError' in out.stderr:
        pytest.skip('live_play imports need the icebow venv')
    assert out.returncode == 2 and 'unrecognized arguments: --probe-xbow-focus' in out.stderr, out.stdout + out.stderr
