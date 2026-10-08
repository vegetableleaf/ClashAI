"""Manual startup and recording contract; all device operations are doubles."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_play as lp


def args(monkeypatch, tmp_path, *extra):
    checkpoint = tmp_path / 'accepted.pt'
    checkpoint.write_bytes(b'test model')
    pointer = tmp_path / 'CKPT_OVERRIDE'
    pointer.write_text(str(checkpoint))
    monkeypatch.setattr(sys, 'argv', ['live_play.py', '--ckpt-override-file', str(pointer), *extra])
    return checkpoint, pointer


def test_preflight_loads_default_without_adb(monkeypatch, tmp_path, capsys):
    checkpoint, _ = args(monkeypatch, tmp_path, '--check')
    loaded = []
    def pilot(path, **kw):
        loaded.append((path, kw))
        return SimpleNamespace(feature_version=4, decision_options=kw['decision_options'])
    monkeypatch.setattr(lp, 'GenPilot', pilot)
    monkeypatch.setattr(lp, 'screen_size', lambda: pytest.fail('Offline check touched ADB'))
    assert lp.main() == 0
    assert loaded[0][0] == str(checkpoint)
    kw = loaded[0][1]
    import torch                                    # owner 2026-10-08: default --device auto (GPU when available)
    assert kw['device'] == ('cuda' if torch.cuda.is_available() else 'cpu')
    assert kw['gate_tau'] == .35 and kw['public_audit']
    assert not kw['decision_options'].active
    assert 'LIVE_CHECK_PASS' in capsys.readouterr().out


def test_bad_selection_stops_before_device(monkeypatch, tmp_path):
    checkpoint, _ = args(monkeypatch, tmp_path)
    checkpoint.unlink()
    monkeypatch.setattr(lp, 'screen_size', lambda: pytest.fail('Bad checkpoint touched ADB'))
    assert lp.main() == 2


def test_manual_run_records_locally_and_explicit_wins(monkeypatch, tmp_path):
    checkpoint, pointer = args(monkeypatch, tmp_path)
    explicit = tmp_path / 'explicit.pt'
    explicit.write_bytes(b'override')
    monkeypatch.setattr(sys, 'argv', sys.argv + ['--ckpt', str(explicit)])
    monkeypatch.setattr(lp, 'screen_size', lambda: (900, 1600))
    monkeypatch.setattr(lp, 'GenPilot', lambda *a, **kw: object())
    observed = []
    def play(a, pilot, lay, device, renders, **kw):
        observed.append((a, kw))
        return 'battle_inactive'
    monkeypatch.setattr(lp, 'play_match', play)
    assert lp.main() == 0
    a, kw = observed[0]
    assert a.ckpt == str(explicit) and a.ckpt_source == 'explicit --ckpt'
    assert a.no_anti_leak and a.public_audit and not a.menu_guard and a.reader == 'v2'
    assert kw['record'] and kw['clip_caption'] is None


def test_full_elixir_wait_is_never_forced(monkeypatch, tmp_path):
    import test_friend_nav as fn
    original = fn.FakePilot.decide
    def wait(self, frame):
        decision = original(self, frame)
        return dict(decision, play=False, p_play=.1)
    monkeypatch.setattr(fn.FakePilot, 'decide', wait)
    lines = []
    for tick in range(150, 240, 2):
        f = json.loads(fn.rframe(tick))
        f['players'][0]['elixir_raw'] = 100000
        lines.append(json.dumps(f) + '\n')
    why, samplers, taps, pilot = fn.run_match(monkeypatch, tmp_path, lines, False, menu_guard=False,
        on_line=lambda i: None)
    assert pilot.decided and not taps
    events = [json.loads(line) for p in tmp_path.glob('live_play_*.jsonl') for line in p.read_text().splitlines()]
    assert not any(e['event'] == 'play' for e in events)
    assert any(e['event'] == 'decision' and not e['decision']['play'] for e in events)
