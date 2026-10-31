"""LEARNER-SPEED: tickets A (split_attn) and B (trunk_graph) on REAL pilot rows -- identity and speed of the whole PPO step.

One Learner from the pilot config (B0, memory v2, lazy_refine, mem_row_cache, ability head), the rows of a gen_recs.py
rollout wave, gae_batch + the lazy anchor prefilled (so a timed step = minibatch_loss + backward + clip + Adam, as
SCALE.md 7e). Arms: base / attn / graph / both, each from the same weights and the same minibatch sequence.
  identity: the first minibatch's loss + every gradient (model + ability head) vs base: bitwise count, worst per-tensor
            relative L2 difference, global relative difference; then ppo_update with kl_stop_prev 0.02 from the same
            start: steps, stop (epoch, minibatch, KL);
  speed:    wall ms / step (CUDA-synchronised median), CUDA kernels / step (profiler, 3 steps).
    PY step_bench.py --res RES.pkl --config pilot_noG.yaml --mb 256 --out OUT.json [k=v ...]
"""
import argparse
import copy
import gc
import json
import os
import pickle
import sys
import time
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import numpy as np  # noqa: E402
import torch  # noqa: E402

torch.use_deterministic_algorithms(True)
torch.backends.cudnn.benchmark = False
torch.backends.cuda.matmul.allow_tf32 = torch.backends.cudnn.allow_tf32 = False
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from gen_recs import learner  # noqa: E402
from pipeline import rl_royale as R  # noqa: E402
from pipeline import learner_graph as LG  # noqa: E402
from pipeline.learner_attn import use_split_attn  # noqa: E402
from rec_identity import collate_kw  # noqa: E402

ARMS = {"base": (False, False), "attn": (True, False), "graph": (False, True), "both": (True, True)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", type=Path, nargs="+", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--mb", type=int, default=256)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--arms", default="base,attn,graph,both")
    ap.add_argument("--ppo", action="store_true", help="also one whole ppo_update with kl_stop_prev 0.02 (fresh lazy anchor)")
    ap.add_argument("--ppo-mb", type=int, help="the ppo_update minibatch (default --mb)")
    ap.add_argument("--micro", type=int, help="the ppo_update micro_batch (arm L: 1024); trunk_graph = micro rows then")
    ap.add_argument("--ppo-lr", type=float, help="the ppo_update lr (default the config's)")
    ap.add_argument("--no-step", action="store_true", help="skip the per-step identity / timing part")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("overrides", nargs="*")
    a = ap.parse_args()
    cfg, L = learner(a.config, ["mem_row_cache=true", "learner_device=cuda"] + a.overrides, "bench")
    res = [r for f in a.res for r in pickle.loads(f.read_bytes())]
    t0 = time.perf_counter()
    Bn, _ = R.collate(res, float(cfg["adv_clip"]), **collate_kw(cfg))
    t_collate = time.perf_counter() - t0
    n_matches = len(res)
    del res
    torch.cuda.synchronize(); t0 = time.perf_counter()
    B = R.to_device(Bn, L.dev)
    B["_mem_cache"] = R.MemRowCache(len(B["A"]))
    R.gae_batch(L.model, B, cfg)
    torch.cuda.synchronize(); t_prep = time.perf_counter() - t0
    Rz = R.LazyRef(L.ref, B, cfg["tau"], cfg["T"], T_gate=cfg.get("T_gate"))
    N = len(B["A"])
    for s in range(0, N, 512):
        Rz.fill(torch.arange(s, min(s + 512, N), device=L.dev))
    ac = R.adv_cfg(cfg)
    vf = {"coef": ac["vf_coef"], "clip": ac["vf_clip"], "policy": True, "trunk_grad": ac["vf_trunk_grad"]}
    kw = dict(tau=cfg["tau"], T=cfg["T"], clip=cfg["clip"], beta=0.0, n_total=N, vf=vf, T_gate=cfg.get("T_gate"))
    seq = np.random.default_rng(0)
    idxs = [torch.from_numpy(seq.choice(N, a.mb, replace=False)).to(L.dev) for _ in range(a.steps + 6)]
    out = {"rows": N, "matches": n_matches, "played_frac": float(B["played"].float().mean()), "mb": a.mb, "arms": {},
           "device": torch.cuda.get_device_name(), "collate_s": t_collate, "to_device_gae_s": t_prep,
           "args": {k: str(v) for k, v in vars(a).items()}}
    print(f"[bench] rows {N} played {out['played_frac']:.3f} mb {a.mb}", flush=True)
    ref_g = ref_loss = None
    for arm in a.arms.split(","):
        attn, graph = ARMS[arm]
        m = copy.deepcopy(L.model)
        ab = copy.deepcopy(L.ability_head)
        if attn:
            use_split_attn(m)
        if graph:
            m.trunk_graph = a.mb
        opt = torch.optim.Adam(m.parameters(), lr=float(cfg["lr"]))
        ab_opt = torch.optim.Adam(ab.parameters(), lr=float(cfg["ability_lr"]))
        abl = {"head": ab, "opt": ab_opt, "ent_coef": float(cfg["ability_ent_coef"])}
        params = list(m.named_parameters()) + [("ability." + n, p) for n, p in ab.named_parameters()]

        def step(idx, timed):
            torch.cuda.synchronize(); t0 = time.perf_counter()
            loss, st = R.minibatch_loss(m, B, Rz, idx, ability=abl, **kw)
            opt.zero_grad(set_to_none=True); ab_opt.zero_grad(set_to_none=True)
            loss.backward()
            if timed is None:                                 # identity: the gradients before any step
                return loss.detach(), {n: p.grad.detach().clone() for n, p in params if p.grad is not None}
            torch.nn.utils.clip_grad_norm_(m.parameters(), float(cfg["grad_clip"]))
            torch.nn.utils.clip_grad_norm_(ab.parameters(), float(cfg["grad_clip"]))
            opt.step(); ab_opt.step()
            torch.cuda.synchronize()
            timed.append(time.perf_counter() - t0)

        r = {}
        if a.no_step:
            pass
        else:
            r = per_step(step, params, idxs, a, ref_g, ref_loss)
            ref_g, ref_loss = r.pop("_ref")
        if a.ppo:                                             # one whole update from the same start, fresh lazy anchor
            m2 = copy.deepcopy(L.model)
            ab2 = copy.deepcopy(L.ability_head)
            if attn:
                use_split_attn(m2)
            pmb = a.ppo_mb or a.mb
            if graph:
                m2.trunk_graph = a.micro if a.micro and a.micro < pmb else pmb
            lr = a.ppo_lr or float(cfg["lr"])
            o2 = torch.optim.Adam(m2.parameters(), lr=lr)
            ao2 = torch.optim.Adam(ab2.parameters(), lr=float(cfg["ability_lr"]))
            pc = {**cfg, "minibatch": pmb, "kl_stop_prev": 0.02, "lr": lr, **({"micro_batch": a.micro} if a.micro else {})}
            Rz2 = R.LazyRef(L.ref, B, cfg["tau"], cfg["T"], T_gate=cfg.get("T_gate"))
            B["_mem_cache"] = R.MemRowCache(N)                # cold, as at an update's start
            kls, name = [], "accum_backward" if a.micro and a.micro < pmb else "minibatch_loss"
            orig = getattr(R, name)

            def rec(*args, **kw):                             # each minibatch's KL to the anchor BEFORE its step
                loss, st = orig(*args, **kw)
                if kw.get("kl_w") is None:
                    kls.append([st["kl_gate"], st["kl_card"], st["kl_cell"]])
                return loss, st
            setattr(R, name, rec)
            torch.cuda.synchronize(); t0 = time.perf_counter()
            try:
                u = R.ppo_update(m2, o2, B, Rz2, pc, 0.0, np.random.default_rng(1), vf=vf,
                                 ability={"head": ab2, "opt": ao2, "ent_coef": float(cfg["ability_ent_coef"])})
            finally:
                setattr(R, name, orig)
            torch.cuda.synchronize()
            r["ppo"] = {"minibatch": pmb, "micro": a.micro, "lr": lr, "steps": u["steps"], "kl_stop": u.get("kl_stop"),
                        "s": time.perf_counter() - t0, "kl": [u["kl_gate"], u["kl_card"], u["kl_cell"]],
                        "nonfinite": u["nonfinite"], "peak_gb": torch.cuda.max_memory_allocated() / 2 ** 30,
                        "kl_pre_step": kls}                   # [gate, card, cell] before minibatch k = after k steps
            m2 = ab2 = o2 = ao2 = Rz2 = None
        out["arms"][arm] = r
        print(f"[bench] {arm}: {json.dumps(r)}", flush=True)
        m = ab = opt = ab_opt = params = None             # free this arm (and its graphs) before the next
        LG._CACHE.clear()
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
    a.out.write_text(json.dumps(out, indent=1))
    os._exit(0)


def per_step(step, params, idxs, a, ref_g, ref_loss):
    """The first minibatch's gradients vs the base arm's, then the timed steps and the kernel count."""
    if True:
        step(idxs[0], None)
        step(idxs[0], None)                                   # graph: capture on the first call, a replay here
        loss1, g = step(idxs[0], None)
        r = {}
        if ref_g is None:
            ref_g, ref_loss = g, loss1
        else:
            rel = {n: float((ref_g[n] - g[n]).norm() / ref_g[n].norm().clamp(min=1e-30)) for n in ref_g}
            worst = max(rel, key=rel.get)
            num = sum(float((ref_g[n] - g[n]).double().norm() ** 2) for n in ref_g) ** 0.5
            den = sum(float(ref_g[n].double().norm() ** 2) for n in ref_g) ** 0.5
            r["identity"] = {"loss_bitwise": bool(torch.equal(ref_loss, loss1)),
                             "loss_rel": float((ref_loss - loss1).abs() / ref_loss.abs()),
                             "same_tensors": set(ref_g) == set(g),
                             "bitwise_tensors": f"{sum(torch.equal(ref_g[n], g[n]) for n in ref_g)}/{len(ref_g)}",
                             "worst_rel": rel[worst], "worst_tensor": worst, "global_rel": num / den,
                             "nonbitwise": {n: v for n, v in rel.items() if v > 0}}
        ts = []
        for i in range(3):
            step(idxs[1 + i], [])
        for i in range(a.steps):
            step(idxs[4 + i], ts)
        with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CUDA]) as prof:
            for i in range(3):
                step(idxs[1 + i], [])
        kern = [e for e in prof.events() if e.device_type == torch.autograd.DeviceType.CUDA]
        r["speed"] = {"ms_median": 1000 * float(np.median(ts)), "ms_p10": 1000 * float(np.percentile(ts, 10)),
                      "ms_p90": 1000 * float(np.percentile(ts, 90)), "kernels_per_step": len(kern) / 3,
                      "kernel_ms_per_step": sum(e.device_time for e in kern) / 3 / 1000,
                      "peak_gb": torch.cuda.max_memory_allocated() / 2 ** 30}
        r["_ref"] = (ref_g, ref_loss)
        return r


if __name__ == "__main__":
    main()
