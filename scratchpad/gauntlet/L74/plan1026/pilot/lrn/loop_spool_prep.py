"""LOOP-LRN loop_learner process smoke input: COPIES x the kept records (wver 0) into a spool, each row with traj v_old =
B0's V(s), i.e. what a LOOP-SRV server at weights version 0 stores, so `python -m pipeline.loop_learner` runs in stored
mode (pilot.yaml) for COPIES updates of E x G records without producers. Not an identity test (the copies repeat).

    source env.sh; cd $CB; $PY -u scratchpad/gauntlet/L74/plan1026/pilot/lrn/loop_spool_prep.py \
        --config scratchpad/gauntlet/L74/plan1026/pilot/ops/pilot.yaml --keep /workspace/lrn/id1/keep \
        --spool /dev/shm/lrn_loop/spool --copies 2
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stored_gate as SG  # noqa: E402
from stored_gate import R, LR  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--keep", type=Path, required=True)
    ap.add_argument("--spool", type=Path, required=True)
    ap.add_argument("--copies", type=int, default=2)
    a = ap.parse_args()
    a.spool.mkdir(parents=True, exist_ok=True)
    if any(a.spool.glob("*.rec")):
        raise SystemExit(f"{a.spool} is not empty")
    cfg = {**R.load_config(SG.REPO / a.config, [], smoke=False), "lazy_refine": False}
    res = [LR.to_result(LR.decode(p.read_bytes())) for p in sorted(a.keep.glob("*.rec"))]
    L = SG.learner(cfg, "spoolprep")
    res = SG.with_v(L, cfg, res)
    n = 0
    for _ in range(a.copies):
        for r in res:
            LR.put(a.spool, LR.from_result(r, 0))
            n += 1
    print(f"spool {a.spool}: {n} records ({len(res)} x {a.copies}), v_old from B0", flush=True)


if __name__ == "__main__":
    main()
