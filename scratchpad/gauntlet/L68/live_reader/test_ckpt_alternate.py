"""--ckpt-alternate: counter helper, offline --check with a real fv4 + fv5 pair, per-match pilot swap, start event."""
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_play as lp

MAIN = Path(r"C:\Users\benpe\ClashBot")
R1E = MAIN / "icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0155.pt"       # fv4
FV5 = MAIN / "icebow/data/pipeline/gen_v32_s0/gen_s0.pt"                               # fv5


def test_counter_alternates_and_survives_reread(tmp_path):
    st = tmp_path / "alt.json"
    assert [lp.next_alternate(st, ["A", "B"]) for _ in range(5)] == ["A", "B", "A", "B", "A"]
    assert json.loads(st.read_text()) == {"n": 5}                    # a fresh process re-reads this and goes on with B
    assert lp.next_alternate(st, ["A", "B"]) == "B"
    assert lp.next_alternate_tau(tmp_path / "t.json", (0.35, 0.45)) == 0.35


@pytest.mark.parametrize("extra", [["--tau-alternate", "0.3", "0.4"], ["--ckpt", "x.pt"]])
def test_refuses_combination(monkeypatch, tmp_path, capsys, extra):
    a, b = tmp_path / "a.pt", tmp_path / "b.pt"
    a.write_bytes(b"a"), b.write_bytes(b"b")
    monkeypatch.setattr(sys, "argv", ["live_play.py", "--check", "--ckpt-alternate", str(a), str(b), *extra])
    assert lp.main() == 2 and "refusing" in capsys.readouterr().out


def test_refuses_missing_and_identical(monkeypatch, tmp_path, capsys):
    a, b = tmp_path / "a.pt", tmp_path / "b.pt"
    a.write_bytes(b"a")
    monkeypatch.setattr(sys, "argv", ["live_play.py", "--check", "--ckpt-alternate", str(a), str(b)])
    assert lp.main() == 2 and "does not exist" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["live_play.py", "--check", "--ckpt-alternate", str(a), str(a)])
    assert lp.main() == 2 and "same checkpoint" in capsys.readouterr().out


@pytest.mark.skipif(not (R1E.is_file() and FV5.is_file()), reason="main-checkout checkpoints absent")
def test_check_loads_fv4_and_fv5_side_by_side(monkeypatch, capsys):
    import torch
    real = torch.set_num_threads
    monkeypatch.setattr(torch, "set_num_threads", lambda n: real(min(n, 2)))     # CPU budget while testing
    monkeypatch.setattr(lp, "screen_size", lambda: pytest.fail("Offline check touched ADB"))
    monkeypatch.setattr(sys, "argv", ["live_play.py", "--check", "--ckpt-alternate", str(R1E), str(FV5)])
    assert lp.main() == 0
    out = capsys.readouterr().out
    res = json.loads(out.strip().splitlines()[-1])
    assert res["check"] == "LIVE_CHECK_PASS"
    assert [c["feature_version"] for c in res["checkpoints"]] == [4, 5]
    assert [c["sha256"] for c in res["checkpoints"]] == [hashlib.sha256(p.read_bytes()).hexdigest() for p in (R1E, FV5)]
    assert all(c["sha256"] in out for c in res["checkpoints"])                  # both shas printed at startup


class FakePilot:
    def __init__(self, name, fv):
        self.name, self.feature_version, self.resets = name, fv, 0
        self.decision_options, self.match_seed = SimpleNamespace(), 0

    def reset_match(self):
        self.resets += 1


def test_pilot_swap_happens_before_play_match(monkeypatch, tmp_path):
    a, b = tmp_path / "a.pt", tmp_path / "b.pt"
    a.write_bytes(b"model a"), b.write_bytes(b"model b")
    sha = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (a, b)}
    fakes = {str(a): FakePilot("a", 4), str(b): FakePilot("b", 5)}
    monkeypatch.setattr(lp, "load_pilot", lambda args, cfg, ckpt=None: ("cpu", fakes[ckpt]))
    nav = SimpleNamespace(probe=lambda: None, run=lambda: (True, ""))
    import ladder_nav
    monkeypatch.setattr(ladder_nav, "LadderNavRunner", lambda *x, **k: nav)
    monkeypatch.setattr(lp, "screen_size", lambda: (900, 1600))
    monkeypatch.setattr(lp, "wait_inputs_quiet", lambda: None)
    seen = []

    def play(args, pilot, lay, device, renders, **kw):
        seen.append((pilot.name, pilot.resets, Path(args.ckpt).name, args.ckpt_sha256, args.ckpt_source))
        return "battle_inactive"
    monkeypatch.setattr(lp, "play_match", play)
    state = tmp_path / "state.json"
    argv = ["live_play.py", "--ladder", "--matches", "3", "--no-record", "--ckpt-alternate", str(a), str(b),
            "--ckpt-alternate-state", str(state)]
    monkeypatch.setattr(sys, "argv", argv)
    assert lp.main() == 0
    # match 1 -> a, 2 -> b, 3 -> a; each chosen pilot was reset right before its match; sha/path are the chosen file's
    assert seen == [("a", 1, "a.pt", sha["a.pt"], "--ckpt-alternate"), ("b", 1, "b.pt", sha["b.pt"], "--ckpt-alternate"),
                    ("a", 2, "a.pt", sha["a.pt"], "--ckpt-alternate")]
    monkeypatch.setattr(sys, "argv", argv[:5] + ["--matches", "1"] + argv[5:])   # a restarted supervisor goes on with b
    seen.clear()
    assert lp.main() == 0 and seen[0][0] == "b"


def test_start_event_carries_chosen_pilot_fields(monkeypatch, tmp_path):
    """The real play_match (reader stream empty): the start event holds the chosen ckpt / sha / feature_version."""
    monkeypatch.setattr(lp, "HERE", tmp_path)
    monkeypatch.setattr(lp, "adb", lambda *a, **k: "")
    monkeypatch.setattr(lp.time, "sleep", lambda s: None)
    monkeypatch.setattr(lp.subprocess, "Popen", lambda *a, **k: SimpleNamespace(
        stdout=iter(()), stderr=SimpleNamespace(read=lambda: ""), wait=lambda timeout=None: 0, terminate=lambda: None))
    args = SimpleNamespace(tau=.35, leak=9.5, dry_run=True, ckpt="/x/b.pt", extrapolate=26, no_opp_counter=False,
                           ckpt_source="--ckpt-alternate", ckpt_sha256="b" * 64, public_audit=True, menu_guard=False,
                           no_ability=True, reader="v2", interval_ms=100, max_seconds=5)
    lay = SimpleNamespace(w=900, h=1600)
    lp.play_match(args, FakePilot("b", 5), lay, "cpu", None, record=False)
    start = json.loads(next(tmp_path.glob("live_play_*.jsonl")).read_text().splitlines()[0])
    assert (start["event"], start["ckpt"], start["ckpt_sha256"], start["feature_version"]) == ("start", "/x/b.pt", "b" * 64, 5)
