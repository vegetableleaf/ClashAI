"""Single-core speed of this box, in the only units that matter for S3: work per second.

Used to convert the local engine's measured 11.24 s per replay (L64u, hogeq drive) into an estimate for
the GCP VM before anything is ported there. Pure stdlib, no installs, identical source both sides.
"""
import time, hashlib, math

def bench():
    t = time.perf_counter(); h = hashlib.sha256(b"x")
    for i in range(400000):
        h.update(h.digest())
    a = time.perf_counter() - t
    t = time.perf_counter(); s = 0.0
    for i in range(1, 900001):
        s += math.sqrt(i) / (i + 1.0)
    b = time.perf_counter() - t
    return round(a, 3), round(b, 3)

if __name__ == "__main__":
    r = [bench() for _ in range(3)]
    print({"sha_s": min(x[0] for x in r), "float_s": min(x[1] for x in r)})
