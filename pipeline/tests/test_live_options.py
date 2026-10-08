"""LIVE_OPTIONS: deployed decision options for live_play.py; explicit flags win, --no-live-options ignores the file."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest

from pipeline.decision_options import add_arguments, config_from_args, options_from_config
from pipeline.live_options import add_live_options_arguments, parse_with_live_options, tau_check

REPO = Path(__file__).resolve().parents[2]
DEPLOYED = ('--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area '
            '--own-effects\n')


def parser(path):
    ap = argparse.ArgumentParser()
    add_arguments(ap)
    ap.add_argument('--tau', type=float, default=.35)
    ap.add_argument('--tau-alternate', type=float, nargs=2, default=None)
    add_live_options_arguments(ap, path)
    return ap


def parse(argv, path):
    a, record = parse_with_live_options(parser(path), argv)
    return options_from_config(config_from_args(a)), record


def test_checked_in_file_holds_the_deployed_options():
    assert (REPO / 'scratchpad/gauntlet/L70/live/LIVE_OPTIONS').read_text() == DEPLOYED


def test_file_present_applies_it(tmp_path):
    f = tmp_path / 'LIVE_OPTIONS'; f.write_text(DEPLOYED)
    opts, rec = parse(['--tau', '.4'], f)
    assert (opts.xbow_class, opts.xbow_class_floor, opts.tau_phase, opts.spell_aim) == \
        ('class_sample', .3, (.35, .45, .55), 'rocket_area')
    assert rec['file'] == str(f) and rec['explicit'] == [] and not rec['ignored']
    assert sorted(rec['from_file']) == ['own_effects', 'spell_aim', 'tau_phase', 'xbow_class', 'xbow_class_floor']


def test_file_absent_gives_plain_defaults(tmp_path):
    opts, rec = parse([], tmp_path / 'missing')
    assert not opts.active and rec['file'] is None and rec['from_file'] == {}
    assert rec['status'] == 'ABSENT' and rec['path'] == str(tmp_path / 'missing')
    assert rec['message'].startswith(f"LIVE_OPTIONS not found at {tmp_path / 'missing'}: running with PLAIN")


def test_explicit_flags_win_flag_by_flag(tmp_path):
    f = tmp_path / 'LIVE_OPTIONS'; f.write_text('# deployed\n' + DEPLOYED)
    opts, rec = parse(['--spell-aim', 'argmax', '--tau-phase', '.3', '.3', '.3', '--log-aim', 'log_barrel'], f)
    assert opts.spell_aim == 'argmax' and opts.tau_phase == (.3, .3, .3) and opts.log_aim == 'log_barrel'
    assert opts.xbow_class == 'class_sample' and opts.xbow_class_floor == .3      # still from the file
    assert rec['explicit'] == ['log_aim', 'spell_aim', 'tau_phase']
    assert sorted(rec['from_file']) == ['own_effects', 'xbow_class', 'xbow_class_floor']
    opts, _ = parse(['--spell-aim', 'rocket_area'], f)                          # explicit = file value: same result
    assert opts.spell_aim == 'rocket_area'


def test_no_live_options_ignores_the_file(tmp_path):
    f = tmp_path / 'LIVE_OPTIONS'; f.write_text(DEPLOYED)
    opts, rec = parse(['--no-live-options'], f)
    assert not opts.active and rec['ignored'] and rec['file'] is None
    opts, _ = parse(['--no-live-options', '--xbow-class', 'class_sample'], f)
    assert opts.xbow_class == 'class_sample' and opts.spell_aim == 'argmax'


def test_unknown_flag_in_the_file_refuses(tmp_path):
    f = tmp_path / 'LIVE_OPTIONS'; f.write_text('--tau 0.5\n')                 # not a decision option
    with pytest.raises(SystemExit):
        parse([], f)


@pytest.mark.parametrize('text', ['--tau 0.3 0.4 0.5\n',                      # abbreviation of --tau-phase
                                  '--spell-aim rocket_area --spell-aim argmax\n',
                                  '--xbow-class class_sample\n--xbow-class=argmax\n'])
def test_file_refuses_abbreviated_and_repeated_flags(tmp_path, text, capsys):
    f = tmp_path / 'LIVE_OPTIONS'; f.write_text(text)
    with pytest.raises(SystemExit) as e:
        parse([], f)
    assert e.value.code == 2 and str(f) in capsys.readouterr().err


def test_tau_alternate_with_tau_phase_refuses_and_plain_tau_gets_a_note(tmp_path):
    f = tmp_path / 'LIVE_OPTIONS'; f.write_text(DEPLOYED)
    a, _ = parse_with_live_options(parser(f), ['--tau-alternate', '.35', '.45'])
    refusal, note = tau_check(a)
    assert refusal.startswith('refusing: --tau-alternate') and '--no-live-options' in refusal and note is None
    a, _ = parse_with_live_options(parser(f), ['--tau-alternate', '.35', '.45', '--no-live-options'])
    assert tau_check(a) == (None, None)
    a, _ = parse_with_live_options(parser(f), ['--tau-alternate', '.35', '.45', '--tau-phase', '.3', '.4', '.5',
                                               '--no-live-options'])
    assert tau_check(a)[0] is not None                                        # an explicit tau_phase refuses too
    a, _ = parse_with_live_options(parser(f), ['--tau', '.35'])
    refusal, note = tau_check(a)
    assert refusal is None and 'not used by the gate (it equals the 1x value)' in note
    a, _ = parse_with_live_options(parser(f), ['--tau', '.5'])
    assert 'equals' not in tau_check(a)[1]
    a, _ = parse_with_live_options(parser(tmp_path / 'missing'), ['--tau', '.5'])
    assert tau_check(a) == (None, None)


CKPT = REPO / 'icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref.pt'


@pytest.mark.skipif(not CKPT.is_file(), reason='live checkpoint not present')
@pytest.mark.parametrize('extra,expect', [([], 'rocket_area'), (['--spell-aim', 'argmax'], 'argmax'),
                                          (['--no-live-options'], 'argmax')])
def test_check_json_reports_options_and_their_source(tmp_path, extra, expect):
    f = tmp_path / 'LIVE_OPTIONS'; f.write_text(DEPLOYED)
    out = subprocess.run([sys.executable, str(REPO / 'scratchpad/gauntlet/L68/live_reader/live_play.py'), '--check',
                          '--ckpt', str(CKPT), '--live-options-file', str(f), *extra],
                         capture_output=True, text=True, timeout=300, cwd=REPO)
    assert out.returncode == 0, out.stdout + out.stderr
    check = json.loads(out.stdout.strip().splitlines()[-1])
    assert check['check'] == 'LIVE_CHECK_PASS' and check['decision_options']['spell_aim'] == expect
    assert check['decision_options']['tau_phase'] == (None if extra == ['--no-live-options'] else [.35, .45, .55])
    assert check['live_options']['file'] == (None if extra == ['--no-live-options'] else str(f))
    status = 'ignored' if extra == ['--no-live-options'] else 'applied'
    assert check['live_options']['status'] == status
    assert ('[live] --no-live-options:' if status == 'ignored' else '[live] LIVE_OPTIONS applied from') in out.stdout


def run_live_play(*args):
    return subprocess.run([sys.executable, str(REPO / 'scratchpad/gauntlet/L68/live_reader/live_play.py'), *args],
                          capture_output=True, text=True, timeout=300, cwd=REPO)


@pytest.mark.skipif(not CKPT.is_file(), reason='live checkpoint not present')
def test_check_json_absent_file_is_loud(tmp_path):
    out = run_live_play('--check', '--ckpt', str(CKPT), '--live-options-file', str(tmp_path / 'missing'))
    assert out.returncode == 0, out.stdout + out.stderr
    assert f"[live] LIVE_OPTIONS not found at {tmp_path / 'missing'}: running with PLAIN decision defaults" in out.stdout
    check = json.loads(out.stdout.strip().splitlines()[-1])
    assert check['live_options']['status'] == 'ABSENT' and check['live_options']['path'] == str(tmp_path / 'missing')


def test_live_play_refuses_tau_alternate_under_tau_phase(tmp_path):
    f = tmp_path / 'LIVE_OPTIONS'; f.write_text(DEPLOYED)
    out = run_live_play('--check', '--tau-alternate', '.35', '.45', '--live-options-file', str(f))
    assert out.returncode == 2 and '[live] refusing: --tau-alternate' in out.stdout, out.stdout + out.stderr


def test_own_effects_deployable_from_the_file_and_explicit_wins(tmp_path):
    f = tmp_path / 'LIVE_OPTIONS'; f.write_text('--own-effects\n')
    ap = parser(f); ap.add_argument('--own-effects', action='store_true')
    a, rec = parse_with_live_options(ap, [])
    assert a.own_effects is True and rec['from_file'] == {'own_effects': True}
    a, rec = parse_with_live_options(ap, ['--no-live-options'])
    assert a.own_effects is False and rec['status'] == 'ignored'
    a, rec = parse_with_live_options(ap, ['--own-effects'])
    assert a.own_effects is True and rec['explicit'] == ['own_effects'] and rec['from_file'] == {}


GATE = '--gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --gate-hazard-quiet\n'


def test_gate_decode_flags_deployable_from_the_file(tmp_path):
    f = tmp_path / 'LIVE_OPTIONS'; f.write_text(DEPLOYED + GATE)
    opts, rec = parse([], f)
    assert (opts.gate_decode, opts.gate_hazard_min_elixir, opts.gate_hazard_quiet) == ('hazard_below_tau', 9.0, True)
    assert {'gate_decode', 'gate_hazard_min_elixir', 'gate_hazard_quiet'} <= set(rec['from_file'])
    opts, rec = parse(['--gate-decode', 'threshold'], f)                       # explicit wins
    assert opts.gate_decode == 'threshold' and rec['explicit'] == ['gate_decode']
    opts, _ = parse([], tmp_path / 'missing')
    assert (opts.gate_decode, opts.gate_hazard_min_elixir, opts.gate_hazard_quiet) == ('threshold', 0.0, False)


@pytest.mark.skipif(not CKPT.is_file(), reason='live checkpoint not present')
def test_check_json_reports_gate_decode(tmp_path):
    f = tmp_path / 'LIVE_OPTIONS'; f.write_text(DEPLOYED + GATE)
    out = run_live_play('--check', '--ckpt', str(CKPT), '--live-options-file', str(f))
    assert out.returncode == 0, out.stdout + out.stderr
    check = json.loads(out.stdout.strip().splitlines()[-1])
    assert {k: check['decision_options'][k] for k in ('gate_decode', 'gate_hazard_min_elixir', 'gate_hazard_quiet')} \
        == dict(gate_decode='hazard_below_tau', gate_hazard_min_elixir=9.0, gate_hazard_quiet=True)
    assert check['live_options']['from_file']['gate_decode'] == 'hazard_below_tau'


def test_iw_press_pstar_deployable_from_the_file_and_explicit_wins(tmp_path):
    f = tmp_path / 'LIVE_OPTIONS'; f.write_text('--iw-press-pstar 0.03\n')
    ap = parser(f); ap.add_argument('--iw-press-pstar', type=float, default=None)
    a, rec = parse_with_live_options(ap, [])
    assert a.iw_press_pstar == 0.03 and rec['from_file'] == {'iw_press_pstar': 0.03}
    a, rec = parse_with_live_options(ap, ['--no-live-options'])
    assert a.iw_press_pstar is None and rec['status'] == 'ignored'
    a, rec = parse_with_live_options(ap, ['--iw-press-pstar', '0.05'])
    assert a.iw_press_pstar == 0.05 and rec['explicit'] == ['iw_press_pstar'] and rec['from_file'] == {}
