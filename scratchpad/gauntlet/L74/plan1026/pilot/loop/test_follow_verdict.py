"""FASTLOOP-FIX: CfTrain.verdict (the follow-up port's Java rule list) == e1_eval.follow_up_verdict on a planted grid,
incl. the 1e-6 affordability edge. Pod, cmp_mfl.sh's env (CRFORGE_FACADE_BUILD = a jbuild holding CfTrain):
    python test_follow_verdict.py
"""
from __future__ import annotations

import itertools
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[5]), str(HERE)]


def main() -> None:
    import jpype
    from pipeline import crforge_core as cc
    from pipeline.e1_eval import follow_up_verdict
    from producer import JVM_FLAGS
    jpype.startJVM(*JVM_FLAGS, classpath=sorted(str(p) for p in cc.LIB.glob("*.jar")) + [os.environ["CRFORGE_FACADE_BUILD"]])
    V = jpype.JClass("CfTrain").verdict
    code = {"wait": 0, "cancel": 1, "fire": 2}
    due, expire, n, seen = 10, 30, 0, set()
    for ff, sc, t, busy, n_out, (have, cost) in itertools.product(
            (False, True), (False, True), (8, 10, 12, 30, 31), (False, True), (0, 1, 2, 3),
            ((5.0, 3.0), (3.0, 3.0), (3.0 - 5e-7, 3.0), (3.0 - 2e-6, 3.0), (0.0, 1.0))):
        act, why = follow_up_verdict(tick=t, due=due, expire=expire, blocked=None, first_failed=ff, slot_changed=sc,
                                     slot_busy=busy, n_out=n_out, have=have, cost=cost)
        j = int(V(ff, sc, t, due, expire, busy, n_out, have, cost))
        assert code[act] == j, (ff, sc, t, busy, n_out, have, cost, act, why, j)
        n += 1
        seen.add(why or "fire")
    assert len(seen) == 8, seen                              # every branch of the rule list was planted
    print(f"OK {n} planted cases, branches {sorted(seen)}")


if __name__ == "__main__":
    main()
