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
    out = decide(heads, np.asarray(p), allowed, stalled, tau=CFG["tau"], options=sample_rules(DecisionOptions()),
                  rngs=[None] * len(allowed), decode="sample",
                  sampler={"tau_r": None, "T": CFG["T"], "T_gate": CFG["T_gate"],
                           "heads": frozenset(("gate", "card", "cell")),
                           "rngs": [np.random.default_rng(s) for s in seeds]},
                  cell_logits=model_cell_logits(pol, enc, "cpu"))
    import torch
    from pipeline.rl_royale import value_scalar
    with torch.no_grad():
        v = value_scalar(pol.model.value_head(enc["g"])).numpy()
    for d, x in zip(out, v):
        d["v_old"] = float(x)
    return out


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


def _producer(client, block, q):
    arr, allowed, stalled, seeds = block
    out = client.decide(arr, allowed, stalled, [np.random.default_rng(s) for s in seeds])
    q.put([(d["play"], d["slot"], d["cell"], d["why"], d["lp_gate"], d["lp_card"], d["lp_cell"]) for d in out])
    client.close()


@pytest.mark.skipif(not (CK.is_file() and BATCH.is_file()), reason="CLXIII checkpoint / live batch fixture absent")
def test_procserver_decide_in_producers_equals_block_by_block():
    """S4b: four producer PROCESSES run the decide themselves (the server only forwards + answers cell calls); their
    blocks share forwards; every action equals the block-by-block decide, log-probs within 1e-5."""
    import multiprocessing as mp
    from pipeline import batched_rollout as BR
    from pipeline import e1_eval as E
    from pipeline.policy_server import ProcServer, row_spec
    pol, _ = E.load_policy(CK, "cpu")
    blocks = _blocks([5, 7, 3, 9], seed=1)
    want = [_reference(pol, *b) for b in blocks]
    keys = E.gen_row_keys(pol.model)
    srv = ProcServer(BR.LazyRefine(pol), row_spec(blocks[0][0], keys), len(blocks), 16, CFG, device="cpu",
                     max_batch=64, wait_ms=300.0)
    ctx = mp.get_context("spawn")          # spawn: a fork after torch started its CPU thread pool can hang the child
    q = ctx.Queue()
    procs = [ctx.Process(target=_producer, args=(srv.clients[i], b, q)) for i, b in enumerate(blocks)]
    for p in procs:
        p.start()
    srv.start()
    try:
        got = [q.get(timeout=120) for _ in blocks]
    finally:
        for p in procs:
            p.join(timeout=30)
        srv.close()
    assert srv.stats["rows"] == 24 and srv.stats["batches"] < 4                # blocks shared forwards
    by_len = {len(g): g for g in got}
    n_play = 0
    for w in want:
        g = by_len[len(w)]
        for x, y in zip(w, g):
            assert (x["play"], x["slot"], x["cell"], x["why"]) == y[:4]
            assert all(abs(a - b) < 1e-5 for a, b in zip((x["lp_gate"], x["lp_card"], x["lp_cell"]), y[4:]))
            n_play += x["play"]
    assert n_play >= 3


# ---- LOOP-SRV: several models in one server, weight-version swaps, the ability head, CUDA modes ---------------------------
CK_MEM = CK.parent / "ICEBOW_Mark_CLXIV_MEMORY.pt"          # memory v2: another architecture and row spec
_HAVE = CK.is_file() and BATCH.is_file() and CK_MEM.is_file()


def _with_memory(block, model, seed):
    """A memory model's block: random visible events over each row's own deck cards (MEM_KEYS added)."""
    from pipeline.match_memory import empty_rows
    arr, allowed, stalled, seeds = block
    n, r = len(allowed), np.random.default_rng(seed)
    m = empty_rows(n, model.mem.version)
    for i in range(n):
        k = int(r.integers(1, 40))
        m["mem_mask"][i, :k] = True
        m["mem_ev"][i, :k] = r.normal(0, 0.5, (k, m["mem_ev"].shape[2]))
        m["mem_card"][i, :k] = r.choice(arr["deck_card"][i], k)
        m["mem_form"][i, :k] = 0
    m["mem_summary"][:] = r.normal(0, 0.3, m["mem_summary"].shape)
    return {**arr, **m}, allowed, stalled, seeds


def _v1(pol):
    """Weight version 1 of ``pol``: every float tensor moved by seeded noise, plus a random B6 ability head, as
    rl_royale's actor message carries it -> (message, the perturbed GenPolicy, the head)."""
    import torch
    from pipeline import e1_eval as E
    from pipeline.rl_royale import ABILITY_SD, AbilityHead
    g = torch.Generator().manual_seed(11)
    sd = {k: v + 0.02 * torch.randn(v.shape, generator=g) if v.is_floating_point() else v.clone()
          for k, v in pol.model.state_dict().items()}
    head = AbilityHead(pol.model.value_head.in_features, n_feat=E.ABILITY_FEAT_N)
    with torch.no_grad():
        for p in head.parameters():
            p.copy_(torch.randn(p.shape, generator=g) * 0.3)
    new, _ = E.load_policy(CK, "cpu")
    new.model.load_state_dict(sd)
    return {**sd, **{ABILITY_SD + k: v for k, v in head.state_dict().items()}}, new, head.eval()


def _tup(d):
    return (d["play"], d["slot"], d["cell"], d["why"], d["lp_gate"], d["lp_card"], d["lp_cell"], d["wver"], d["v_old"])


def _mm_producer(client, rounds, q, go):
    """Per round: the learner's and the opponent's block sent at once, both decided here; round 1 also asks the
    ability head for learner rows 0, 2, 4 (the pushed version carries one). Waits for ``go`` between rounds."""
    for rnd, (bl, bo, feat) in enumerate(rounds):
        fl, fo = client.forward([("learner", bl[0], len(bl[1])), ("opp", bo[0], len(bo[1]))])
        out = [[_tup(d) for d in client.decide_fwd(f, al, st, [np.random.default_rng(s) for s in seeds])]
               for f, (_, al, st, seeds) in ((fl, bl), (fo, bo))]
        z = client.ability(fl, [0, 2, 4], feat) if rnd == 1 else None
        client.done([fl, fo])
        q.put((rnd, out, z))
        if rnd == 0:
            go.wait(300)
    client.close()


def _check(want, got):
    assert len(want) == len(got)
    for x, y in zip(want, got):
        assert (x["play"], x["slot"], x["cell"], x["why"]) == y[:4]
        assert all(abs(a - b) < 1e-5 for a, b in zip((x["lp_gate"], x["lp_card"], x["lp_cell"]), y[4:7])), (x, y)
        assert abs(x["v_old"] - y[8]) < 1e-5, (x["v_old"], y[8])       # the server's value = the CPU critic
    return sum(x["play"] for x in want)


def _mm_run(device, mode, **kw):
    """Two producer processes x two rounds against learner CLXIII (swappable) + opponent CLXIV (memory v2); version
    1 is pushed between the rounds. -> (srv, results by producer, references)."""
    import multiprocessing as mp
    import torch
    from pipeline import batched_rollout as BR
    from pipeline import e1_eval as E
    from pipeline.policy_server import PolicyServer, row_spec
    pol_l, _ = E.load_policy(CK, "cpu")
    pol_o, _ = E.load_policy(CK_MEM, "cpu")
    msg, pol_l1, head = _v1(pol_l)
    feat = np.random.default_rng(5).normal(0, 1, (3, E.ABILITY_FEAT_N)).astype(np.float32)
    rounds, want = [], []
    for j in range(2):
        bl = _blocks([7 + 3 * j], seed=20 + j)[0]
        bo = _with_memory(_blocks([5 + 4 * j], seed=30 + j)[0], pol_o.model, 40 + j)
        rounds.append([(bl, bo, feat), (bl, bo, feat)])        # the same blocks in both rounds: old vs new weights
        rows1 = [{k: v[i] for k, v in bl[0].items()} for i in range(len(bl[1]))]
        g1 = pol_l1.forward_batch(rows1, "cpu")[0]["g"]
        with torch.no_grad():
            z1 = head(g1[[0, 2, 4]], torch.from_numpy(feat)).double().numpy()
        want.append([(_reference(pol_l, *bl), _reference(pol_o, *bo)), (_reference(pol_l1, *bl), _reference(pol_o, *bo)),
                     z1])
    keys_l, keys_o = E.gen_row_keys(pol_l.model), E.gen_row_keys(pol_o.model)
    on_dev = (lambda ck: BR.LazyRefine(E.load_policy(ck, device)[0])) if device != "cpu" else None
    models = [{"name": "learner", "policy": on_dev(CK) if on_dev else BR.LazyRefine(pol_l),
               "spec": row_spec(rounds[0][0][0][0], keys_l), "cfg": CFG, "swap": True},
              {"name": "opp", "policy": on_dev(CK_MEM) if on_dev else BR.LazyRefine(pol_o),
               "spec": row_spec(rounds[0][0][1][0], keys_o), "cfg": CFG}]
    srv = PolicyServer(models, n_clients=2, block_max=16, device=device, max_batch=64, wait_ms=300.0, mode=mode, **kw)
    ctx = mp.get_context("spawn")
    q, go = ctx.Queue(), ctx.Event()
    procs = [ctx.Process(target=_mm_producer, args=(srv.clients[i], rounds[i], q, go)) for i in range(2)]
    for p in procs:
        p.start()
    srv.start(warm={"learner": rounds[0][0][0][0], "opp": rounds[0][0][1][0]} if device != "cpu" else None)
    try:
        r0 = [q.get(timeout=300) for _ in procs]
        assert srv.version("learner") == 0
        srv.push("learner", 1, msg)
        assert srv.version("learner") == 1 and srv.version("opp") == 0
        go.set()
        r1 = [q.get(timeout=300) for _ in procs]
    finally:
        for p in procs:
            p.join(timeout=30)
        srv.close()
    got = {}
    for rnd, out, z in r0 + r1:                       # a producer is known by its learner block's length
        got.setdefault(len(out[0]), {})[rnd] = (out, z)
    return srv, got, want


def _mm_assert(srv, got, want):
    n_play = 0
    for j in range(2):
        g = got[7 + 3 * j]
        for rnd in range(2):
            out, _ = g[rnd]
            wl, wo = want[j][rnd]
            n_play += _check(wl, out[0]) + _check(wo, out[1])
            assert {y[7] for y in out[0]} == {rnd} and {y[7] for y in out[1]} == {0}     # learner v0 -> v1, opp v0
        assert np.allclose(g[1][1], want[j][2], atol=1e-5, rtol=0)                      # ability z, version 1
        assert any(abs(a[4] - b[4]) > 1e-4 for a, b in zip(g[0][0][0], g[1][0][0]))     # the push changed the policy
    assert n_play >= 3
    pm = srv.stats["per_model"]
    assert pm["learner"]["rows"] == 2 * (7 + 10) and pm["opp"]["rows"] == 2 * (5 + 9) and srv.stats["pushes"] == 1


@pytest.mark.skipif(not _HAVE, reason="CLXIII / CLXIV checkpoint or live batch fixture absent")
def test_two_models_and_a_weight_push_equal_block_by_block():
    """LOOP-SRV: one server, two architectures (CLXIII; CLXIV with memory v2 inputs), two producer processes sending
    a block to each model at once; version 1 (new weights + an ability head) pushed between rounds. Every decision
    equals the block-by-block decide with the weights of the version it is tagged with (wver), log-probs within 1e-5;
    the ability head's z on version 1 within 1e-5."""
    _mm_assert(*_mm_run("cpu", "eager"))


@pytest.mark.skipif(not _HAVE, reason="CLXIII / CLXIV checkpoint or live batch fixture absent")
@pytest.mark.parametrize("mode", ["eager", "graphs"])
def test_cuda_server_equals_cpu_block_by_block(mode):
    """The same on CUDA (fp32: no TF32 in matmuls or cuDNN convs), padded to a bucket: eager, and CUDA graphs warmed
    at start (both weight copies). Reference = the CPU block-by-block decide (rl_royale's actor path)."""
    import torch
    if not torch.cuda.is_available():
        pytest.skip("no CUDA")
    _mm_assert(*_mm_run("cuda", mode))
