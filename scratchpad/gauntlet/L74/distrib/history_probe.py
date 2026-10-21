"""W16 probe: does an actor's result for a share depend on what that actor PROCESS ran before?
Two actors, same weights. u0 job list J0, a league snapshot, u1 job list J1, both dealt over 8 slots (as an 8-actor run).
Actor 0 runs J0[slot 5] then J1[slot 5] (the 8-actor history); actor 1 runs J0[slot 1] then J1[slot 5] (the failover
history). Per-match hashes of J1[slot 5] are compared.
    python scratchpad/gauntlet/L74/distrib/history_probe.py CONFIG.yaml RUN [key=value ...]"""
import sys
from pathlib import Path

from pipeline import rl_royale as RL


def mh(r):
    return f"{r['tag']}:{r['k']} {r['outcome']} {RL.batch_sha(r.get('traj') or {})}"


def main():
    cfg = RL.load_config(Path(sys.argv[1]), [a for a in sys.argv[3:] if "=" in a] + ["n_actors=2"], False)
    run = sys.argv[2]
    run_dir, ck_dir = RL.RUN_ROOT / run, RL.CKPT_ROOT / run
    run_dir.mkdir(parents=True, exist_ok=True)
    ck_dir.mkdir(parents=True, exist_ok=True)
    L = RL.Learner(cfg, run, run_dir, ck_dir, RL.Log(run_dir), False)
    L.start_actors()
    calls, orig = [], L.actors.run
    L.actors.run = lambda kind, update, sd, jobs, **kw: calls.append((kind, update, sd, jobs)) or ([], [], {})
    L.rollout(0)
    L.update = 1
    L._snapshot()
    L.rollout(1)
    (k0, u0, sd, J0), (k1, u1, _, J1) = calls
    N = 8
    res, _, _ = orig(k0, u0, sd, [], shares={0: J0[5::N], 1: J0[1::N]})
    print("u0 done", len(res), flush=True)
    if "--same-update" in sys.argv:                       # v3: actor 1 first runs u1 slot 1 (the failover order)
        orig(k1, u1, sd, [], shares={1: J1[1::N]})
        print("u1 slot1 done on actor 1", flush=True)
    res, _, _ = orig(k1, u1, sd, [], shares={0: J1[5::N], 1: J1[5::N]})
    by = {}
    for r in res:
        by.setdefault(mh(r), 0)
        by[mh(r)] += 1
    for h, c in sorted(by.items()):
        print("SAME" if c == 2 else "DIFF", h, flush=True)
    L.actors.close()


if __name__ == "__main__":
    main()
