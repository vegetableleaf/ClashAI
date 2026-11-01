"""MGPU: a 20-second check of the collectives the data-parallel learner uses, on the real devices / backend, before any replay:
group init (backend + the gloo object group), all_gather_object, the flat state broadcast (float32 / int64 / bool-as-uint8), the

    python -m pipeline.learner_dp_selftest --devices cuda:0,cuda:1,cuda:2,cuda:3 --backend nccl [--gb 1.0] [--out r.json]
Exit code 0 = every check passed. cpu devices + gloo run the same code anywhere.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path

import torch
import torch.distributed as dist

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

P = 2_004_016                                                 # the learner's trainable parameters (SCALE.md 5)


def rank_main(rank, world, url, backend, devices, gb, out_q):
    from pipeline import learner_dp as DP
    dev = devices[rank]
    res = {"rank": rank, "ok": True, "checks": {}}
    try:
        if dev.startswith("cuda"):
            torch.cuda.set_device(torch.device(dev))
        t0 = time.perf_counter()
        group, cpu = DP.init_group(backend, url, rank, world, dev)
        ctx = DP.DPCtx(rank, world, group, cpu)
        res["init_s"] = time.perf_counter() - t0
        sync = (lambda: torch.cuda.synchronize(torch.device(dev))) if dev.startswith("cuda") else (lambda: None)
        objs = ctx.gather({"r": rank})
        res["checks"]["gather_objects"] = objs == [{"r": r} for r in range(world)]
        # state broadcast: mixed dtypes, a bool buffer, a CPU tensor
        g = torch.Generator().manual_seed(7 + (0 if rank == 0 else rank))
        mk = (lambda t: t.to(dev))
        ts = [mk(torch.randn(1000, generator=g)), mk(torch.randint(0, 9, (50,), generator=g)),
              mk(torch.rand(30, generator=g) > 0.5), torch.randn(5, generator=g)]
        DP.bcast_tensors(ts, ctx)
        sync()
        r0 = torch.Generator().manual_seed(7)
        w = [torch.randn(1000, generator=r0), torch.randint(0, 9, (50,), generator=r0), torch.rand(30, generator=r0) > 0.5,
             torch.randn(5, generator=r0)]
        res["checks"]["bcast_tensors"] = all(torch.equal(a.cpu(), b) for a, b in zip(ts, w))
        # reduce_grads: rank 1 has no grad for p1; only rank 0 touches p2; p3 nobody
        ps = [torch.nn.Parameter(torch.zeros(P // 4, device=dev)), torch.nn.Parameter(torch.zeros(7, device=dev)),
              torch.nn.Parameter(torch.zeros(3, device=dev)), torch.nn.Parameter(torch.zeros(2, device=dev))]
        gg = torch.Generator().manual_seed(100 + rank)
        ps[0].grad = torch.randn(P // 4, generator=gg).to(dev)
        if rank != 1 or world == 1:
            ps[1].grad = torch.randn(7, generator=gg).to(dev)
        if rank == 0:
            ps[2].grad = torch.ones(3, device=dev)
        ctx.reduce_grads(ps)
        sync()
        gs = [torch.Generator().manual_seed(100 + r) for r in range(world)]
        e0 = [torch.randn(P // 4, generator=x) for x in gs]
        exp0 = e0[0]
        for x in e0[1:]:
            exp0 = exp0 + x
        e1 = [torch.randn(7, generator=gs[r]) for r in range(world) if r != 1 or world == 1]
        exp1 = e1[0]
        for x in e1[1:]:
            exp1 = exp1 + x
        res["checks"]["reduce_values"] = bool(torch.equal(ps[0].grad.cpu(), exp0) and torch.equal(ps[1].grad.cpu(), exp1)
                                              and torch.equal(ps[2].grad.cpu(), torch.ones(3)) and ps[3].grad is None)
        h = ctx.gather(DP.hashlib.sha1(ps[0].grad.cpu().numpy().tobytes()).hexdigest()[:12])
        res["checks"]["reduce_bit_identical_across_ranks"] = len(set(h)) == 1
        # timings: the learner's gradient size, then a batch-sized broadcast
        flatp = [torch.nn.Parameter(torch.zeros(P, device=dev))]
        ts_ = []
        for i in range(25):
            flatp[0].grad = torch.randn(P, device=dev)
            sync()
            t = time.perf_counter()
            ctx.reduce_grads(flatp)
            sync()
            ts_.append(time.perf_counter() - t)
        res["reduce_ms_p50"] = 1000 * sorted(ts_[5:])[len(ts_[5:]) // 2]
        big = torch.zeros(int(gb * 2**30 // 4), device=dev)
        if rank == 0:
            big.fill_(1.0)
        sync()
        t = time.perf_counter()
        DP._bc(big, 0, group)
        sync()
        res["bcast_gbps"] = gb / (time.perf_counter() - t)
        res["checks"]["bcast_big"] = bool(big[::1000003].eq(1.0).all())
        dist.barrier(group=cpu)
        res["ok"] = all(res["checks"].values())
        dist.destroy_process_group()
    except BaseException as e:
        import traceback
        res["ok"], res["error"] = False, traceback.format_exc()[-1500:]
    out_q.put(res)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--devices", default="cpu,cpu")
    ap.add_argument("--backend", default=None, choices=("nccl", "gloo"))
    ap.add_argument("--gb", type=float, default=0.25)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    devs = [x.strip() for x in a.devices.split(",") if x.strip()]
    backend = a.backend or ("nccl" if devs[0].startswith("cuda") else "gloo")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        url = f"tcp://127.0.0.1:{s.getsockname()[1]}"
    import torch.multiprocessing as tmp
    ctx = tmp.get_context("spawn")
    q = ctx.Queue()
    ps = [ctx.Process(target=rank_main, args=(r, len(devs), url, backend, devs, a.gb, q)) for r in range(len(devs))]
    for p in ps:
        p.start()
    got = [q.get(timeout=600) for _ in ps]
    for p in ps:
        p.join(30)
    got.sort(key=lambda r: r["rank"])
    ok = all(r["ok"] for r in got)
    r0 = got[0]
    summary = {"ok": ok, "backend": backend, "devices": devs, "torch": torch.__version__,
               "nccl": ".".join(map(str, torch.cuda.nccl.version())) if backend == "nccl" else None,
               "init_s": r0.get("init_s"), "reduce_ms_p50_8MB": r0.get("reduce_ms_p50"), "bcast_GBps": r0.get("bcast_gbps"),
               "checks": {r["rank"]: r["checks"] for r in got}, "errors": [r.get("error") for r in got if r.get("error")]}
    print(json.dumps(summary, default=str), flush=True)
    if a.out:
        Path(a.out).write_text(json.dumps(summary, indent=1, default=str))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
