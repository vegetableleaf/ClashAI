"""RX-X23: gap.py (the D2-G gate command: D3 = deployed LIVE_OPTIONS stack, all16 levels) with sim_worker.py as the worker.

    X23_POLICY=<policy> python run_x23.py <gap.py args, incl. --levels all16 --arms D3>
Only the worker entry of gap.command changes ([gap.py --worker-all16] -> [sim_worker.py --worker-x23]); the plan, seeds,
opponents and flags are gap.py's.
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[5] / "scratchpad/gauntlet/L74/gap"))
import gap  # noqa: E402

_command = gap.command


def command(*a, **k):
    cmd = _command(*a, **k)
    if cmd[1:3] != [str(gap.HERE / "gap.py"), "--worker-all16"]:
        raise ValueError("gap.command layout changed (run with --levels all16)")
    cmd[1:3] = [str(HERE / "sim_worker.py"), "--worker-x23"]
    return cmd


gap.command = command
_run = gap.subprocess.run


def run_retry(cmd, **kw):
    """a chunk that crashes (intermittent SIGSEGV in libtorch oneDNN inside the JPype JVM) is redone from scratch, up to 3
    tries; same seeds -> the same matches. Its per-chunk log keeps only the last try."""
    import shutil
    dest = Path(cmd[cmd.index("--out") + 1])
    for k in range(3):
        try:
            return _run(cmd, **kw)
        except gap.subprocess.CalledProcessError:
            if k == 2:
                raise
            shutil.rmtree(dest, ignore_errors=True)
            kw["stdout"].seek(0)
            kw["stdout"].truncate()


gap.subprocess.run = run_retry
SMOKE = os.environ.get("X23_SMOKE")          # "JxS": only the first J chunks with S seeds each (smoke test only)
if SMOKE:
    _prepare = gap.prepare
    nj, ns = map(int, SMOKE.split("x"))

    def prepare(*a, **k):
        plan = _prepare(*a, **k)
        plan["jobs"] = [dict(j, seeds=j["seeds"][:ns]) for j in plan["jobs"][:nj]]
        return plan
    gap.prepare = prepare
if __name__ == "__main__":
    raise SystemExit(gap.main())
