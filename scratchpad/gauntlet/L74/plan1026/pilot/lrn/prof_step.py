"""LEARNER-SCALE step 2: where one PPO step's time goes (4090, fp32, TF32 off, deterministic as the learner).
Per minibatch size: CUDA-synchronised split gen_batch (CPU memory features + H2D) / forward (policy_terms + loss) /
backward / clip / Adam; then one torch.profiler pass (CPU + CUDA, with_flops) over --prof-steps steps -> the top CUDA
kernels table, kernel launches per step, profiler FLOPs per step (matmul / conv only) -> achieved FLOP/s.
Variants (--det): 1 = torch.use_deterministic_algorithms(True), cudnn.benchmark False (the learner today); 0 = both off
(what a non-deterministic cuDNN algorithm choice would buy; NOT an adoption, a measurement).

    source env.sh; cd $CB; $PY -u scratchpad/gauntlet/L74/plan1026/pilot/lrn/prof_step.py --config CFG --keep DIR \
        --T-gate 0.3 --mbs 64,256,1024 --det 1 --out /workspace/lrn/prof/prof_det1.json
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
DET = "--det" not in sys.argv or sys.argv[sys.argv.index("--det") + 1] == "1"
import numpy as np  # noqa: E402
import torch  # noqa: E402

torch.use_deterministic_algorithms(DET)
torch.backends.cudnn.benchmark = not DET
torch.backends.cudnn.allow_tf32 = False
torch.backends.cuda.matmul.allow_tf32 = False
REPO = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import rl_royale as R  # noqa: E402
from pipeline import e1_eval as E  # noqa: E402
from pipeline import loop_records as LR  # noqa: E402
from pipeline import loop_learner as LL  # noqa: E402
from rec_identity import collate_kw  # noqa: E402
from torch.profiler import ProfilerActivity, profile, record_function  # noqa: E402

T_GB = {"gen": 0.0}
_real_gen = E.gen_batch


def timed_gen(model, B, idx):
    torch.cuda.synchronize()
    t = time.perf_counter()
    with record_function("gen_batch"):
        out = _real_gen(model, B, idx)
    torch.cuda.synchronize()
    T_GB["gen"] += time.perf_counter() - t
    return out


E.gen_batch = timed_gen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--keep", type=Path, required=True)
    ap.add_argument("--T-gate", type=float, required=True)
    ap.add_argument("--mbs", default="64,256,1024")
    ap.add_argument("--steps", type=int, default=12)
    ap.add_argument("--prof-steps", type=int, default=3)
    ap.add_argument("--det", default="1")
    ap.add_argument("--max-matches", type=int, default=128)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    cfg = {**R.load_config(REPO / a.config, [], smoke=False), "T_gate": a.T_gate}
    run = f"lrn_prof_{int(time.time())}"
    for d in (R.RUN_ROOT / run, R.CKPT_ROOT / run):
        d.mkdir(parents=True, exist_ok=True)
    L = R.Learner(cfg, run, R.RUN_ROOT / run, R.CKPT_ROOT / run, R.Log(R.RUN_ROOT / run), False)
    LL.adopt_init_ability_head(L)
    res = [LR.to_result(LR.decode(p.read_bytes())) for p in sorted(a.keep.glob("*.rec"))[:a.max_matches]]
    Bn, _ = R.collate(res, float(cfg["adv_clip"]), **collate_kw(cfg))
    del res
    B = R.to_device(Bn, L.dev)
    R.gae_batch(L.model, B, cfg)
    Rz = R.LazyRef(L.ref, B, cfg["tau"], cfg["T"], T_gate=cfg.get("T_gate"))
    ac = R.adv_cfg(cfg)
    vf = {"coef": ac["vf_coef"], "clip": ac["vf_clip"], "policy": True, "trunk_grad": ac["vf_trunk_grad"]}
    abl = {"head": L.ability_head, "opt": L.ability_opt, "ent_coef": float(cfg["ability_ent_coef"])}
    N = len(B["A"])
    rng = np.random.default_rng(0)
    out = {"det": DET, "rows": N, "lazy_refine": bool(getattr(L.model, "lazy_refine", False)),
           "params": sum(p.numel() for p in L.model.parameters()), "mb": {}}

    def step(mb, split):
        idx = torch.from_numpy(rng.choice(N, mb, replace=False)).to(L.dev)
        Rz.fill(idx)                                          # the lazy anchor (no grad), timed apart from the step
        sync = torch.cuda.synchronize
        sync(); T_GB["gen"] = 0.0; t0 = time.perf_counter()
        with record_function("forward"):
            loss, st = R.minibatch_loss(L.model, B, Rz, idx, tau=cfg["tau"], T=cfg["T"], clip=cfg["clip"], beta=0.0,
                                        n_total=N, vf=vf, T_gate=cfg.get("T_gate"), ability=abl)
        sync(); t1 = time.perf_counter()
        L.opt.zero_grad(set_to_none=True); L.ability_opt.zero_grad(set_to_none=True)
        with record_function("backward"):
            loss.backward()
        sync(); t2 = time.perf_counter()
        with record_function("clip"):
            torch.nn.utils.clip_grad_norm_(L.model.parameters(), float(cfg["grad_clip"]))
            torch.nn.utils.clip_grad_norm_(L.ability_head.parameters(), float(cfg["grad_clip"]))
        sync(); t3 = time.perf_counter()
        with record_function("optim"):
            L.opt.step(); L.ability_opt.step()
        sync(); t4 = time.perf_counter()
        if split is not None:
            split.append({"gen_batch": T_GB["gen"], "forward_ex_gen": t1 - t0 - T_GB["gen"], "backward": t2 - t1,
                          "clip": t3 - t2, "optim": t4 - t3, "total": t4 - t0})

    for mb in [int(x) for x in a.mbs.split(",")]:
        try:
            torch.cuda.reset_peak_memory_stats()
            for _ in range(3):
                step(mb, None)
            sp = []
            for _ in range(a.steps):
                step(mb, sp)
            med = {k: 1000 * float(np.median([s[k] for s in sp])) for k in sp[0]}
            peak = torch.cuda.max_memory_allocated() / 2 ** 20
            with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA], with_flops=True) as prof:
                for _ in range(a.prof_steps):
                    step(mb, None)
            ka = prof.key_averages()
            kern = [e for e in prof.events() if e.device_type == torch.autograd.DeviceType.CUDA]
            flops = sum(e.flops for e in ka if e.flops) / a.prof_steps
            cuda_us = sum(e.device_time_total for e in ka if e.device_type == torch.autograd.DeviceType.CUDA) / a.prof_steps
            tab = ka.table(sort_by="device_time_total", row_limit=30, max_name_column_width=70)
            (a.out.parent / f"{a.out.stem}_mb{mb}_table.txt").write_text(tab)
            out["mb"][mb] = {"ms_median": med, "rows_per_s": mb / (med["total"] / 1000), "ms_per_row": med["total"] / mb,
                             "peak_mb": peak, "kernels_per_step": len(kern) / a.prof_steps,
                             "gpu_kernel_ms_per_step": cuda_us / 1000, "prof_flops_per_step": flops,
                             "achieved_tflops": flops / (med["total"] / 1000) / 1e12}
            print(mb, json.dumps(out["mb"][mb]), flush=True)
        except torch.OutOfMemoryError as exc:
            out["mb"][mb] = {"oom": str(exc)[:160]}
            print(mb, "OOM", flush=True)
            torch.cuda.empty_cache()
    a.out.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
