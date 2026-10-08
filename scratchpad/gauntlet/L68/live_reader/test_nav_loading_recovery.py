"""Loading-stuck recovery (2026-10-08 "Content Update" modal): fakes only, never a device.
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L68/live_reader/test_nav_loading_recovery.py"""
import sys
import tempfile
import time as _time
from pathlib import Path
from types import SimpleNamespace
import cv2
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ladder_nav  # noqa: E402
from ladder_nav import RELAUNCH, TARGETS, Classifier, LadderNav, LadderNavRunner, command_for  # noqa: E402

# the real 2026-10-08 frame: modal over the 94 % loading screen -> content_update, RESTART at its button
cu = Classifier().classify(cv2.imread(str(HERE / "fixtures" / "content_update.png")))
assert cu["screen"] == "content_update", cu["scores"]
assert abs(cu["restart"][0] - 144) <= 6 and abs(cu["restart"][1] - 876) <= 6, cu["restart"]
assert command_for("restart", cu["restart"]) == "input tap 144 876"

LOAD, UNK = {"screen": "loading", "scores": {}}, {"screen": "unknown", "scores": {}}
CU = {"screen": "content_update", "restart": (144, 876.5), "scores": {}}
def main(v=0):
    return {"screen": "main", "battle": (455, 1220), "bonus": True, "sig": np.full((80, 45), v, np.uint8), "scores": {}}

# planner: modal seen while loading -> RESTART at once; a second modal in the same episode is not tapped again
nav = LadderNav(0.0, {})
assert nav.plan(LOAD, 1)[0] == "wait" and nav.plan(CU, 20)[:2] == ("act", "restart")
nav.acted("restart", 21)
assert nav.plan(CU, 22)[0] == "wait" and nav.plan(LOAD, 80)[0] == "wait" and nav.plan(LOAD, 82)[0] == "stop"
# planner: loading 60 s, no modal -> relaunch; then no blind tap-through on unknown frames while the app restarts
nav = LadderNav(0.0, {})
assert nav.plan(LOAD, 1)[0] == "wait" and nav.plan(LOAD, 61.5) == ("act", "relaunch", None)
nav.acted("relaunch", 62)
assert all(nav.plan(UNK, t)[0] == "wait" for t in (63, 70, 100))
assert nav.plan(main(), 101)[0] == "wait" and not nav.recovered          # a known screen ends the episode
# planner: a committed transition (Play Again tapped) does not hand off on the modal; the restart un-commits it
nav = LadderNav(0.0, {})
nav.acted("play_again", 0.5)
assert nav.plan(CU, 1)[1] == "restart" and nav.plan(CU, 10)[1] == "restart"
nav.acted("restart", 10)
assert not nav.committed and nav.plan(LOAD, 20)[0] == "wait"


class Clock:                                    # fake time: sleep() advances it
    def __init__(self):
        self.t = 1000.0
    def time(self):
        return self.t
    def sleep(self, d):
        self.t += d
    strftime, perf_counter = staticmethod(_time.strftime), staticmethod(_time.perf_counter)


def run(screen_of):
    """screen_of(elapsed_s, shell_cmds) -> screen dict. -> (run() result, shell commands sent, stdout lines)."""
    clk, sent, out = Clock(), [], []
    real = (ladder_nav.time, ladder_nav.subprocess, ladder_nav.grab)
    ladder_nav.time, ladder_nav.grab = clk, (lambda adb: None)
    ladder_nav.subprocess = SimpleNamespace(run=lambda a, **k: sent.append(a[-1]))   # records `adb shell <cmd>`
    ladder_nav.print = lambda *a, **k: out.append(" ".join(map(str, a)))            # shadows the builtin
    try:
        with tempfile.TemporaryDirectory() as d:
            r = LadderNavRunner(["adb"], log_dir=Path(d), state_path=Path(d) / "st.json", trophy_log=False, seed=1,
                                alert=lambda *a: False)
            r.clf = SimpleNamespace(classify=lambda img: screen_of(clk.t - 1000.0, sent))
            res = r.run()
    finally:
        ladder_nav.time, ladder_nav.subprocess, ladder_nav.grab = real
        del ladder_nav.print
    return res, sent, out


# 1) loading 30 s, then the modal -> RESTART tapped -> loading 10 s -> menu -> Battle -> battle loading = handoff
st = {}
def s1(t, sent):
    if "input tap 455 1220" in sent:
        return UNK
    if "input tap 144 876" in sent:
        st.setdefault("r", t)
        return LOAD if t - st["r"] < 10 else main()
    return LOAD if t < 30 else CU
res, sent, out = run(s1)
assert res[0] and sent == ["input tap 144 876", "input tap 455 1220"], (res, sent)
assert "[ladder] loading stuck -> content-update RESTART tapped" in out, out

# 2) loading with no modal -> relaunch after 60 s (store overlays + game force-stopped, launcher intent) -> menu
st = {}
def s2(t, sent):
    if "input tap 455 1220" in sent:
        return UNK
    if RELAUNCH[-1] in sent:
        st.setdefault("r", t)
        return UNK if t - st["r"] < 20 else main()     # launcher / splash frames: waited out, never tapped
    return LOAD
res, sent, out = run(s2)
assert res[0] and sent == [*RELAUNCH, "input tap 455 1220"], (res, sent)
assert "[ladder] loading stuck -> relaunched app" in out, out

# 3) relaunch does not help -> exactly one recovery, then STOP as before (no loop)
res, sent, out = run(lambda t, sent: LOAD)
assert not res[0] and "after the loading-stuck recovery" in res[1] and sent == list(RELAUNCH), (res, sent)
assert sum("relaunched app" in o for o in out) == 1
assert TARGETS["restart"][0] <= 144 <= TARGETS["restart"][2]
print("loading-recovery checks passed")
