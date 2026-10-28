"""LEARNER-SCALE2 step 3: WHERE the GPU time of one pilot PPO step goes, after mem_row_cache (gen_batch off the path).
Same step as prof_step.py (minibatch_loss + backward + clip + Adam; lazy anchor filled outside; fp32, TF32 off, det 1),
pilot.yaml as is (lazy_refine on) + mem_row_cache. Adds:
  1. forward GPU time per model submodule (record_function around every module at depth <= --depth, via forward hooks;
     the table rows "mod:<name>"), and the gen_rows / policy_terms / loss tail split;
  2. the Python stacks that launch aten::fill_ / zero_ / copy_ / index_put_ / clone (group_by_stack_n 6) -> who makes the
     ~3,000 small kernels;
  3. the kernel count and GPU-busy ms per step (sum of kernel time) vs the wall ms: the launch / idle share.
Writes OUT (json) + OUT_stem_{mod,stack,kern}_mbN.txt.

    source env.sh; cd $CB; $PY -u scratchpad/gauntlet/L74/plan1026/pilot/lrn/prof_mod.py --config CFG --keep DIR \
        --T-gate 0.1 --mbs 256,1024 --out /workspace/lrn/prof/prof_mod.json
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import numpy as np  # noqa: E402
import torch  # noqa: E402

torch.use_deterministic_algorithms(True)
torch.backends.cudnn.benchmark = False
torch.backends.cudnn.allow_tf32 = False
torch.backends.cuda.matmul.allow_tf32 = False
REPO = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import rl_royale as R  # noqa: E402
from pipeline import loop_records as LR  # noqa: E402
from pipeline import loop_learner as LL  # noqa: E402
from rec_identity import collate_kw  # noqa: E402
from torch.profiler import ProfilerActivity, profile, record_function  # noqa: E402

CUDA = torch.autograd.DeviceType.CUDA


def hook_modules(model, depth):
    """record_function("mod:<name>") around the forward of every submodule at depth <= depth."""
    hs = []
    for name, m in model.named_modules():
        if not name or name.count(".") >= depth:
            continue
        def pre(mod, inp, name=name):
            mod._rf = record_function(f"mod:{name}")
            mod._rf.__enter__()
        def post(mod, inp, out):
            mod._rf.__exit__(None, None, None)
        hs += [m.register_forward_pre_hook(pre), m.register_forward_hook(post)]
    return hs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--keep", type=Path, required=True)
    ap.add_argument("--T-gate", type=float, required=True)
    ap.add_argument("--mbs", default="256,1024")
    ap.add_argument("--steps", type=int, default=10)
    ap.add_argument("--prof-steps", type=int, default=3)
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--max-matches", type=int, default=128)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    cfg = {**R.load_config(REPO / a.config, [], smoke=False), "T_gate": a.T_gate}
    run = f"lrn_profmod_{int(time.time())}"
    for d in (R.RUN_ROOT / run, R.CKPT_ROOT / run):
        d.mkdir(parents=True, exist_ok=True)
    L = R.Learner(cfg, run, R.RUN_ROOT / run, R.CKPT_ROOT / run, R.Log(R.RUN_ROOT / run), False)
    LL.adopt_init_ability_head(L)
    res = [LR.to_result(LR.decode(p.read_bytes())) for p in sorted(a.keep.glob("*.rec"))[:a.max_matches]]
    Bn, _ = R.collate(res, float(cfg["adv_clip"]), **collate_kw(cfg))
    del res
    B = R.to_device(Bn, L.dev)
    B["_mem_cache"] = R.MemRowCache(len(B["A"]))
    R.gae_batch(L.model, B, cfg)
    Rz = R.LazyRef(L.ref, B, cfg["tau"], cfg["T"], T_gate=cfg.get("T_gate"))
    ac = R.adv_cfg(cfg)
    vf = {"coef": ac["vf_coef"], "clip": ac["vf_clip"], "policy": True, "trunk_grad": ac["vf_trunk_grad"]}
    abl = {"head": L.ability_head, "opt": L.ability_opt, "ent_coef": float(cfg["ability_ent_coef"])}
    N = len(B["A"])
    rng = np.random.default_rng(0)
    out = {"rows": N, "lazy_refine": bool(getattr(L.model, "lazy_refine", False)),
           "params": sum(p.numel() for p in L.model.parameters()),
           "modules": {n: sum(p.numel() for p in m.parameters()) for n, m in L.model.named_children()}, "mb": {}}
    print("model", json.dumps(out["modules"]), flush=True)

    def step(mb, split):
        idx = torch.from_numpy(rng.choice(N, mb, replace=False)).to(L.dev)
        Rz.fill(idx)
        torch.cuda.synchronize(); t0 = time.perf_counter()
        with record_function("forward"):
            loss, st = R.minibatch_loss(L.model, B, Rz, idx, tau=cfg["tau"], T=cfg["T"], clip=cfg["clip"], beta=0.0,
                                        n_total=N, vf=vf, T_gate=cfg.get("T_gate"), ability=abl)
        torch.cuda.synchronize(); t1 = time.perf_counter()
        L.opt.zero_grad(set_to_none=True); L.ability_opt.zero_grad(set_to_none=True)
        with record_function("backward"):
            loss.backward()
        torch.cuda.synchronize(); t2 = time.perf_counter()
        with record_function("clip_optim"):
            torch.nn.utils.clip_grad_norm_(L.model.parameters(), float(cfg["grad_clip"]))
            torch.nn.utils.clip_grad_norm_(L.ability_head.parameters(), float(cfg["grad_clip"]))
            L.opt.step(); L.ability_opt.step()
        torch.cuda.synchronize(); t3 = time.perf_counter()
        if split is not None:
            split.append({"forward": t1 - t0, "backward": t2 - t1, "clip_optim": t3 - t2, "total": t3 - t0})

    for mb in [int(x) for x in a.mbs.split(",")]:
        for _ in range(3):
            step(mb, None)                                   # warm (and fills the MEM cache for most rows)
        sp = []
        for _ in range(a.steps):
            step(mb, sp)
        med = {k: 1000 * float(np.median([s[k] for s in sp])) for k in sp[0]}
        hs = hook_modules(L.model, a.depth)
        with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA], with_stack=True, record_shapes=False) as prof:
            for _ in range(a.prof_steps):
                step(mb, None)
        for h in hs:
            h.remove()
        ka = prof.key_averages()
        kern = [e for e in prof.events() if e.device_type == CUDA]
        busy = sum(e.device_time for e in kern) / a.prof_steps / 1000
        mods = sorted(((e.key, e.device_time_total / a.prof_steps / 1000, e.count / a.prof_steps) for e in ka
                       if e.key.startswith("mod:") or e.key in ("forward", "backward", "clip_optim")), key=lambda x: -x[1])
        stem = a.out.parent / a.out.stem
        Path(f"{stem}_mod_mb{mb}.txt").write_text("\n".join(f"{k:60s} {ms:9.2f} ms  x{c:.0f}" for k, ms, c in mods))
        st = prof.key_averages(group_by_stack_n=6)
        small = [e for e in st if e.key in ("aten::fill_", "aten::zero_", "aten::copy_", "aten::index_put_", "aten::clone",
                                            "aten::zeros", "aten::cat", "aten::index", "aten::masked_fill")]
        small.sort(key=lambda e: -e.count)
        Path(f"{stem}_stack_mb{mb}.txt").write_text("\n\n".join(
            f"{e.key} calls/step {e.count / a.prof_steps:.0f} cuda ms/step {e.device_time_total / a.prof_steps / 1000:.2f}\n  "
            + "\n  ".join(e.stack) for e in small[:40]))
        Path(f"{stem}_kern_mb{mb}.txt").write_text(ka.table(sort_by="device_time_total", row_limit=40,
                                                            max_name_column_width=80))
        out["mb"][mb] = {"ms_median": med, "ms_per_row": med["total"] / mb, "kernels_per_step": len(kern) / a.prof_steps,
                         "gpu_busy_ms_per_step": busy, "busy_share": busy / med["total"],
                         "mods_ms": {k: ms for k, ms, _ in mods}}
        print(mb, json.dumps({k: v for k, v in out["mb"][mb].items() if k != "mods_ms"}), flush=True)
    a.out.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
