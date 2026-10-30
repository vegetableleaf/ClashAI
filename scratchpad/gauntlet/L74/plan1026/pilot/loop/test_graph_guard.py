"""ROLLOUT-SPEED planted test of policy_server.Forward's graph-capture guard (GPU; pod env as bench.sh):
a capture that fails (a planted torch.cuda.synchronize inside the capture of bucket 128) must (1) leave that bucket eager
with the eager result (within 1e-5), (2) restore the thread's stream, (3) NOT poison later captures (bucket 256 captures into a fresh
pool and matches eager), (4) a frozen Forward never captures a missing bucket.

    python test_graph_guard.py [CKPT]     (default: the pilot's B0) -> prints PASS or raises
"""
import sys
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
sys.path[:0] = [str(REPO), str(HERE)]


def main():
    from pipeline import batched_rollout as BR
    from pipeline import e1_eval as E
    from pipeline import policy_server as PS
    from serve import spec_for
    ck = sys.argv[1] if len(sys.argv) > 1 else "icebow/data/bench/rl_royale/b0/b0_clxiii_s3aux_grafted.pt"
    PS.configure("fp32")                      # TF32 off, as PolicyServer (eager runs then repeat to ~1e-6, not bitwise)
    pol, _ = E.load_policy(REPO / ck, "cuda")
    rng = np.random.default_rng(0)
    arr = {k: (np.ones if np.dtype(dt) == np.bool_ else np.zeros)((512, *shape), dt) for k, (shape, dt) in spec_for(pol).items()}
    for k, v in arr.items():
        if v.dtype == np.float32:
            v[:] = rng.normal(size=v.shape).astype(np.float32) * 0.1
    ref = PS.Forward(BR.LazyRefine(pol), "cuda", "eager", buckets=PS.BUCKETS_FINE, pad=True)
    fw = PS.Forward(BR.LazyRefine(pol), "cuda", "graphs", buckets=PS.BUCKETS_FINE, pad=True, graph_max=512,
                    pool=torch.cuda.graph_pool_handle())
    pool0, fn = fw.pool, fw.fn

    def planted(b):                           # bucket 128 only: an illegal call inside the capture
        if torch.cuda.is_current_stream_capturing() and next(iter(b.values())).shape[0] == 128:
            torch.cuda.synchronize()
        return fn(b)
    fw.fn = planted
    same = lambda x, y, n: all(torch.allclose(x[1][k][:n], y[1][k][:n], atol=1e-5, rtol=0) for k in x[1])  # noqa: E731
    stream0 = torch.cuda.current_stream()
    out = fw(arr, 100)
    assert fw.graphs.get(128, "missing") is None and not fw.last_graph, "failed bucket must be recorded as eager"
    assert torch.cuda.current_stream() == stream0, "stream not restored after the failed capture"
    assert same(out, ref(arr, 100), 100), "eager fallback differs from eager"
    assert fw.pool != pool0 and PS._POOL_NEXT.get(pool0) == fw.pool, "pool not replaced"
    out = fw(arr, 200)                        # a later capture into the replacement pool
    assert fw.graphs.get(256) is not None and fw.last_graph, "capture after a failure failed (cascade)"
    o2 = {k: v[:200].clone() for k, v in out[1].items()}
    assert same((None, o2), ref(arr, 200), 200), "graph replay differs from eager"
    fw.frozen = True
    fw(arr, 300)
    assert 384 not in fw.graphs and not fw.last_graph, "a frozen Forward captured a new bucket"
    print("PASS test_graph_guard: failed capture -> eager (equal), stream restored, fresh pool captures, frozen = eager")


if __name__ == "__main__":
    main()
