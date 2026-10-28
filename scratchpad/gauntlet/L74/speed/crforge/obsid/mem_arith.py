"""LOOP-MEM: CfMem's CPython / numpy arithmetic vs the real thing on this interpreter, bit for bit.

pySum = builtin sum() of floats (start 0), pyHypot = math.hypot, the lock head's 1 / (1 + exp(-z)) = numpy's, roundCost =
np.round(float64(float32(c / 10)) * 10, 1). Inputs: random values shaped like match_memory's (tower HP fractions and their
differences, own-frame coordinate differences x 18 / 32, lock-head scores, card costs), plus adversarial sums.

usage: python -I mem_arith.py BUILD_DIR [N]   (BUILD_DIR = the compiled CfMem classes; CRFORGE_LIB jars on the classpath)
"""
import math
import os
import sys
from pathlib import Path

sys.path[:0] = ["/workspace/cfspeed/pylib"]               # jpype on the pods (as obs_id.py)
import jpype  # noqa: E402
import numpy as np  # noqa: E402


def main():
    build, n = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 1_000_000
    lib = Path(os.environ.get("CRFORGE_LIB", "/workspace/cfspeed/crforge/env/build/install/env/lib"))
    jpype.startJVM(classpath=sorted(str(p) for p in lib.glob("*.jar")) + [build])
    C = jpype.JClass("CfMem")
    D, I = jpype.JArray(jpype.JDouble), jpype.JArray(jpype.JInt)
    rng = np.random.default_rng(1028)
    out = {}
    # hypot: own-frame differences (x in [0, 1] x 18 tiles, y x 32), plus exact-zero / equal components
    ax, ay, bx, by = (rng.random(n) for _ in range(4))
    dx, dy = (ax - bx) * 18.0, (ay - by) * 32.0
    dx[: n // 20] = 0.0
    dy[n // 20: n // 10] = 0.0
    j = np.array(C.hypots(D(dx.tolist()), D(dy.tolist())))
    p = np.array([math.hypot(u, v) for u, v in zip(dx.tolist(), dy.tolist())])
    out["hypot"] = int((j.view(np.uint64) != p.view(np.uint64)).sum())
    # sum(): 1..6 floats of mixed scale and sign (tower fractions, damage, value / elixir), adversarial cancellations
    lens = rng.integers(1, 7, n // 4)
    flat = rng.random(int(lens.sum())) * rng.choice([1e-3, 1.0, 1e3], int(lens.sum())) * rng.choice([-1.0, 1.0], int(lens.sum()))
    js = np.array(C.sums(D(flat.tolist()), I(lens.tolist())))
    ps, o = [], 0
    for k in lens.tolist():
        ps.append(sum(flat[o:o + k].tolist()))
        o += k
    ps = np.array(ps)
    out["sum"] = int((js.view(np.uint64) != ps.view(np.uint64)).sum())
    hard = [[1e16, 1.0, -1e16], [0.1, 0.2, 0.3], [-0.0], [1.0, -1.0], [1e308, 1e308], [0.1] * 6]
    out["sum_hard"] = sum(int(np.float64(sum(h)).view(np.uint64) != np.float64(C.sums(D(h), I([len(h)]))[0]).view(np.uint64))
                          for h in hard)
    # the lock head's sigmoid, float64 and after the float32 cast the summary stores
    z = rng.normal(0, 3, n)
    jz = np.array(C.sigmoids(D(z.tolist())))
    pz = np.array([1.0 / (1.0 + np.exp(-np.array([v]))) for v in z.tolist()]).reshape(-1)
    out["sigmoid_f64"] = int((jz.view(np.uint64) != pz.view(np.uint64)).sum())
    out["sigmoid_f32"] = int((jz.astype(np.float32).view(np.uint32) != pz.astype(np.float32).view(np.uint32)).sum())
    # cost rounding: every cost a card / press can have (0 .. 10 by 0.5) and random ones
    c = np.concatenate([np.arange(0, 10.5, 0.5), rng.random(n // 10) * 10])
    jc = np.array(C.roundCosts(D(c.tolist())))
    pc = np.round(np.array([np.float32(v / 10) for v in c.tolist()], np.float32).astype(np.float64) * 10, 1)
    out["round_cost"] = int((jc.view(np.uint64) != pc.view(np.uint64)).sum())
    out["n"] = n
    out["python"] = sys.version.split()[0]
    out["numpy"] = np.__version__
    print(out)
    bad = {k: v for k, v in out.items() if k not in ("n", "python", "numpy", "sigmoid_f64") and v}
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
