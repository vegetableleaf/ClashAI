"""OPP-LEARN-A: a compare.py message with P2 timing-head opponents: a dumped fastloop message (MSG.pkl) whose jobs[:N] get
the timing checkpoint as their opponent on every ``--every``-th job (the others keep theirs: both card-id universes in one
producer). opp_style is turned off in the base (e1_eval.timing_cfg refuses a styled timing seat, in production as here).

    python msg_p2.py MSG.pkl OUT.pkl --ckpt /workspace/opp/cbs/opp_ckpt/opp_m10_s0_sim.pt [--jobs 32] [--every 2]
"""
from __future__ import annotations

import argparse
import pickle
from pathlib import Path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("msg")
    ap.add_argument("out")
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--jobs", type=int, default=32)
    ap.add_argument("--every", type=int, default=2, help="1 = every job plays the timing opponent, 0 = none")
    a = ap.parse_args(argv)
    base, update, sd, jobs = pickle.loads(Path(a.msg).read_bytes())
    base = {**base, "opp_style": "off"}
    out = []
    for n, job in enumerate(jobs[:a.jobs]):
        i, spec, k, *rest = job
        if a.every > 0 and n % a.every == 0:                 # --every 0: none (the regression run, opp_style still off)
            spec = {**spec, "opp": {"id": "p2_timing", "path": str(Path(a.ckpt).resolve()), "type": "p2"}}
        out.append((i, spec, k, *rest))
    Path(a.out).write_bytes(pickle.dumps((base, update, sd, out)))
    print({"jobs": len(out), "p2_jobs": sum(j[1]["opp"]["id"] == "p2_timing" for j in out), "update": update})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
