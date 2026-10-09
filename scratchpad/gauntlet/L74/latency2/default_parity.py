"""Default byte-identity check: the pre-change live_play.py (git rev given as argv[1], default HEAD) and the working copy,
both driven through the same fake matches of the existing tests (test_fast_input.play / test_afford_release helpers);
every log event (wall-clock fields stripped) and every adb tap command must be equal.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/latency2/default_parity.py [REV]
Needs CLASHBOT_READER_CONFIG pointing at the local reader config (the tests' READERS lookup)."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
LP_DIR = REPO / "scratchpad/gauntlet/L68/live_reader"
sys.path.insert(0, str(LP_DIR))
sys.path.insert(0, str(REPO))
import pytest  # noqa: E402

rev = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
old_src = subprocess.run(["git", "show", f"{rev}:scratchpad/gauntlet/L68/live_reader/live_play.py"], cwd=REPO,
                         capture_output=True, text=True, check=True).stdout
old_path = LP_DIR / "_live_play_old_tmp.py"
old_path.write_text(old_src, encoding="utf-8", newline="\n")
try:
    spec = importlib.util.spec_from_file_location("_live_play_old_tmp", old_path)
    old = importlib.util.module_from_spec(spec)
    sys.modules["_live_play_old_tmp"] = old
    spec.loader.exec_module(old)
    import live_play as new
    import test_fast_input as tfi
    import test_afford_release as tar

    DROP = {"t_dev", "decide_ms", "tap_ms", "recv_age_ms", "sample_age_ms", "tap_end_ms", "latency_s", "seconds",
            "frame_age_backlog", "backlog", "log"}

    def norm(ev):
        return [{k: v for k, v in e.items() if k not in DROP} for e in ev if e["event"] != "reader_closed"]

    def scenarios(mod, tmp: Path):
        """name -> (tap commands, events) on module ``mod``."""
        out = {}
        tfi.lp = tar.lp = mod
        mod.INPUTS.update(in_flight=0, last_t=0.0, timed_out=False)
        cases = {
            "default_lock": dict(),
            "gap0": dict(tap_gap_ms=0),
            "early_release": dict(early_release_margin=8, pilot=tar.SeqPilot(), frames=[
                (t, tar.frame(t, slot0=0 if t < 200 else 4)) for t in range(150, 260, 2)]),
            "two_released": dict(early_release_margin=8, pilot=tar.SeqPilot(), frames=[
                (t, tar.frame(t, slot0=0 if t < 240 else 4)) for t in range(150, 260, 2)]),
            "rotating_hand": dict(),
            "five_unconfirmed": dict(frames=[(t, tar.frame(t)) for t in range(150, 620, 2)]),     # never rotates -> stop
            "five_unconfirmed_early": dict(early_release_margin=8, frames=[(t, tar.frame(t)) for t in range(150, 620, 2)]),
        }
        for name, kw in cases.items():
            with pytest.MonkeyPatch.context() as mp:
                d = tmp / name
                d.mkdir()
                kw = dict(kw)
                if name == "rotating_hand":
                    kw["frames"] = [(t, tfi.rframe(t)) for t in range(150, 330, 2)]
                taps, ev = tfi.play(mp, d, pace=0.02, **kw)
                out[name] = (taps, norm(ev))
        return out

    with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
        a = scenarios(old, Path(t1))
        b = scenarios(new, Path(t2))
    bad = 0
    for name in a:
        same = a[name] == b[name]
        bad += not same
        print(f"{name:15s} taps {len(a[name][0]):3d}/{len(b[name][0]):3d} events {len(a[name][1]):3d}/{len(b[name][1]):3d} "
              f"{'IDENTICAL' if same else 'DIFFERENT'}")
        if not same:
            for i, (x, y) in enumerate(zip(a[name][1], b[name][1])):
                if x != y:
                    print("   first diff at event", i, "\n    old", json.dumps(x, default=str)[:300], "\n    new", json.dumps(y, default=str)[:300])
                    break
    print("DEFAULT_PARITY_PASS" if not bad else f"DEFAULT_PARITY_FAIL {bad}")
    raise SystemExit(1 if bad else 0)
finally:
    old_path.unlink(missing_ok=True)
