"""Stop each A/B arm at a target episode count, with a hard wall-clock deadline behind it.

`--matches` is fixed when a run starts, so lowering the target on a run already in flight means
stopping it from outside. Two things make that safe here: the trainer checkpoints every 50
episodes, so a forced stop loses at most 50 episodes of policy; and the EVAL HISTORY -- the only
thing the comparison actually needs -- lives in the log, which is never lost.

The deadline matters as much as the target. The two arms do not run at the same speed (a third of
the drill arm's episodes are 20-step drills against a match's ~187), so the control arm reaches any
given episode count later. It also speeds up once the drill arm exits and stops competing for
cores. If the deadline arrives first, the arms are stopped wherever they are and the comparison is
made at the highest eval point they SHARE -- which is the honest comparison either way, since
matching episode counts is what makes the two numbers mean the same thing.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
RE_PROG = re.compile(r"\[train-sim-ppo\]\s+(\d+)\s+episodes:")


def episodes(log):
    try:
        with io.open(os.path.join(DATA, log), encoding="utf-8", errors="replace") as fh:
            hits = RE_PROG.findall(fh.read())
        return int(hits[-1]) if hits else 0
    except FileNotFoundError:
        return 0


def alive(pid):
    out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid], capture_output=True, text=True)
    return str(pid) in (out.stdout or "")


def kill(pid, why):
    print("[ab-stop] %s  killing pid %d (%s)" % (time.strftime("%H:%M:%S"), pid, why), flush=True)
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=2000, help="stop each arm at this episode count")
    ap.add_argument("--deadline-min", type=float, default=110.0,
                    help="minutes from now after which anything still running is stopped")
    ap.add_argument("--drill-pid", type=int, required=True)
    ap.add_argument("--control-pid", type=int, required=True)
    a = ap.parse_args()

    arms = [("DRILL", a.drill_pid, "ppo_drill.log"), ("CONTROL", a.control_pid, "ppo_control.log")]
    end = time.time() + a.deadline_min * 60.0
    print("[ab-stop] target %d episodes/arm; hard deadline %s"
          % (a.target, time.strftime("%H:%M:%S", time.localtime(end))), flush=True)
    done = set()
    while len(done) < len(arms):
        now = time.time()
        for name, pid, log in arms:
            if name in done:
                continue
            if not alive(pid):
                print("[ab-stop] %s already exited at %d episodes" % (name, episodes(log)), flush=True)
                done.add(name)
                continue
            n = episodes(log)
            if n >= a.target:
                kill(pid, "%s reached %d >= %d" % (name, n, a.target))
                done.add(name)
            elif now >= end:
                kill(pid, "%s hit the wall-clock deadline at %d episodes" % (name, n))
                done.add(name)
        if len(done) < len(arms):
            time.sleep(20)
    print("[ab-stop] both arms stopped: %s"
          % ", ".join("%s@%d" % (n, episodes(l)) for n, _, l in arms), flush=True)


if __name__ == "__main__":
    main()
