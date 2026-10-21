"""W16 probe: does an actor's result for a job list depend on what that actor PROCESS ran before?
One actor (n_actors=1); the same selfplay job list A run fresh, then B, then A again -> per-match hashes A1 vs A2.
    python scratchpad/gauntlet/L74/distrib/history_probe.py CONFIG.yaml RUN [key=value ...]"""
import hashlib
import pickle
import sys
from pathlib import Path

from pipeline import rl_royale as RL


def mh(r):
    t = r.get("traj") or {}
    h = hashlib.sha256()
    for k in sorted(t):
        h.update(k.encode() + pickle.dumps(t[k]))
    return f"{r['tag']}:{r['k']} {r['outcome']} {h.hexdigest()[:12]}"


def main():
    cfg = RL.load_config(Path(sys.argv[1]), sys.argv[3:] + ["n_actors=1"], False)
    run = sys.argv[2]
    run_dir, ck_dir = RL.RUN_ROOT / run, RL.CKPT_ROOT / run
    run_dir.mkdir(parents=True, exist_ok=True)
    ck_dir.mkdir(parents=True, exist_ok=True)
    log = RL.Log(run_dir)
    L = RL.Learner(cfg, run, run_dir, ck_dir, log, False)
    L.start_actors()
    calls, orig = [], L.actors.run
    L.actors.run = lambda kind, update, sd, jobs, **kw: calls.append((kind, update, sd, jobs)) or orig(kind, update, sd, jobs, **kw)
    L.rollout(0)                                      # warms the actor + gives a real job list
    kind, u, sd, jobs = calls[0]
    A, B = jobs[:4], jobs[4:8]
    a1 = sorted(map(mh, orig(kind, u, sd, A)[0]))
    orig(kind, u, sd, B)
    a2 = sorted(map(mh, orig(kind, u, sd, A)[0]))
    for x, y in zip(a1, a2):
        print("SAME" if x == y else "DIFF", x, "|", y, flush=True)
    L.actors.close()


if __name__ == "__main__":
    main()
