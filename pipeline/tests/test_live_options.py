"""LIVE_OPTIONS: deployed decision options for live_play.py; explicit flags win, --no-live-options ignores the file."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest

from pipeline.decision_options import add_arguments, config_from_args, options_from_config
from pipeline.live_options import add_live_options_arguments, parse_with_live_options

REPO = Path(__file__).resolve().parents[2]
DEPLOYED = '--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area\n'


def parse(argv, path):
    ap = argparse.ArgumentParser()
    add_arguments(ap)
    ap.add_argument('--tau', type=float, default=.35)
    add_live_options_arguments(ap, path)
    a, record = parse_with_live_options(ap, argv)
    return options_from_config(config_from_args(a)), record


def test_checked_in_file_holds_the_deployed_options():
    assert (REPO / 'scratchpad/gauntlet/L70/live/LIVE_OPTIONS').read_text() == DEPLOYED


def test_file_present_applies_it(tmp_path):
    f = tmp_path / 'LIVE_OPTIONS'; f.write_text(DEPLOYED)
    opts, rec = parse(['--tau', '.4'], f)
    assert (opts.xbow_class, opts.xbow_class_floor, opts.tau_phase, opts.spell_aim) == \
        ('class_sample', .3, (.35, .45, .55), 'rocket_area')
    assert rec['file'] == str(f) and rec['explicit'] == [] and not rec['ignored']
    assert sorted(rec['from_file']) == ['spell_aim', 'tau_phase', 'xbow_class', 'xbow_class_floor']


def test_file_absent_gives_plain_defaults(tmp_path):
    opts, rec = parse([], tmp_path / 'missing')
    assert not opts.active and rec['file'] is None and rec['from_file'] == {}


def test_explicit_flags_win_flag_by_flag(tmp_path):
    f = tmp_path / 'LIVE_OPTIONS'; f.write_text('# deployed\n' + DEPLOYED)
    opts, rec = parse(['--spell-aim', 'argmax', '--tau-phase', '.3', '.3', '.3', '--log-aim', 'log_barrel'], f)
    assert opts.spell_aim == 'argmax' and opts.tau_phase == (.3, .3, .3) and opts.log_aim == 'log_barrel'
    assert opts.xbow_class == 'class_sample' and opts.xbow_class_floor == .3      # still from the file
    assert rec['explicit'] == ['log_aim', 'spell_aim', 'tau_phase']
    assert sorted(rec['from_file']) == ['xbow_class', 'xbow_class_floor']
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
    assert '[live] decision options:' in out.stdout
