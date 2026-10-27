"""pipeline.policy_server: blocks merged into one asynchronous batch get the same actions as the same decide
(decision_options.decide, decode 'sample', one forward per decision) run block by block -- fp32, on the real CLXIII
checkpoint (with its refine layers, through batched_rollout.LazyRefine) and a real fv6 live row fixture."""
import numpy as np
import pytest

from pipeline.tests.test_fast_obs import BATCH, CK, _rows

CFG = {"tau": 0.35, "T": 0.5, "T_gate": 0.3}


def _blocks(sizes, seed=0):
    rows = _rows(sum(sizes))
    r = np.random.default_rng(seed)
    out, o = [], 0
    for n in sizes:
        rr = rows[o:o + n]
        o += n
        arr = {k: np.stack([x[k] for x in rr]) for k in rr[0]}
        allowed = np.zeros((n, 8), bool)
        for i in range(n):
            allowed[i, r.choice(4, size=r.integers(1, 5), replace=False)] = True     # the 4 hand slots hold slots 0-3
        stalled = r.random(n) < 0.4                                   # forced plays: cell draws on enough rows
        out.append((arr, allowed, stalled, [100 * seed + 7 * o + i for i in range(n)]))
    return out


def _reference(pol, arr, allowed, stalled, seeds):
    from pipeline.decision_options import DecisionOptions, decide, model_cell_logits, sample_rules
    rows = [{k: v[i] for k, v in arr.items()} for i in range(len(allowed))]
    enc, heads, p, _ = pol.forward_batch(rows, "cpu")
    return decide(heads, np.asarray(p), allowed, stalled, tau=CFG["tau"], options=sample_rules(DecisionOptions()),
                  rngs=[None] * len(allowed), decode="sample",
                  sampler={"tau_r": None, "T": CFG["T"], "T_gate": CFG["T_gate"],
                           "heads": frozenset(("gate", "card", "cell")),
                           "rngs": [np.random.default_rng(s) for s in seeds]},
                  cell_logits=model_cell_logits(pol, enc, "cpu"))


@pytest.mark.skipif(not (CK.is_file() and BATCH.is_file()), reason="CLXIII checkpoint / live batch fixture absent")
def test_async_batch_equals_block_by_block():
    from pipeline import batched_rollout as BR
    from pipeline import e1_eval as E
    from pipeline.policy_server import AsyncPolicyServer
    pol, _ = E.load_policy(CK, "cpu")
    blocks = _blocks([5, 7, 3, 9])
    want = [_reference(pol, *b) for b in blocks]
    srv = AsyncPolicyServer(BR.LazyRefine(pol), CFG, device="cpu", max_batch=64, wait_ms=200.0)
    try:
        futs = [srv.submit(a, al, st, [np.random.default_rng(s) for s in seeds]) for a, al, st, seeds in blocks]
        got = [f.result(timeout=120) for f in futs]
    finally:
        srv.close()
    assert srv.stats["batches"] == 1 and srv.stats["rows"] == 24          # the four blocks shared ONE forward
    n_play = 0
    for w, g in zip(want, got):
        assert len(w) == len(g)
        for x, y in zip(w, g):
            assert (x["play"], x["slot"], x["cell"], x["why"]) == (y["play"], y["slot"], y["cell"], y["why"])
            for k in ("lp_gate", "lp_card", "lp_cell"):
                assert abs(x[k] - y[k]) < 1e-5, (k, x[k], y[k])
            n_play += x["play"]
    assert n_play >= 3


@pytest.mark.skipif(not (CK.is_file() and BATCH.is_file()), reason="CLXIII checkpoint / live batch fixture absent")
def test_graphs_and_compile_equal_eager_on_cuda():
    """Forward modes on the GPU: CUDA graphs (padded bucket) and torch.compile give eager's heads (fp32 noise only)."""
    import torch
    if not torch.cuda.is_available():
        pytest.skip("no CUDA")
    from pipeline import batched_rollout as BR
    from pipeline import e1_eval as E
    from pipeline.policy_server import Forward
    pol, _ = E.load_policy(CK, "cuda")
    arr, *_ = _blocks([40])[0]
    arr = {k: torch.from_numpy(v).pin_memory().numpy() for k, v in arr.items()}
    ref = Forward(BR.LazyRefine(pol), "cuda", "eager")(arr, 40)
    for mode in ("graphs", "compile"):
        got = Forward(BR.LazyRefine(pol), "cuda", mode)(arr, 40)
        nz = torch.nan_to_num
        assert torch.allclose(nz(got[1]["card"][:40]), nz(ref[1]["card"]), atol=1e-4), mode
        assert torch.allclose(got[2], ref[2], atol=1e-5), mode
        assert torch.equal(got[3], ref[3]), mode
