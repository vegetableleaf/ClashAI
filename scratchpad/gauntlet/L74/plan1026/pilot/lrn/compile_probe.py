"""LEARNER-SCALE2 step 3 probe: does torch.compile (fp32, TF32 off) of the pilot's PPO minibatch loss speed the step, and
how far are its loss / gradients from eager? A MEASUREMENT, not an adoption (nothing in pipeline/ changes).
Same step as prof_mod.py (mem_row_cache on, lazy anchor filled outside). For each --mbs size: eager vs compiled
(torch.compile(R.minibatch_loss, dynamic=True); graph breaks allowed) on the SAME minibatch rows from the SAME weights
(no optimizer step between the two, so the gradients are directly comparable): step ms (median of --steps fresh minibatches,
after --warm compiled warm-up steps), loss rel diff, max |g_c - g_e| / max|g_e| per parameter tensor and overall.
Deterministic algorithms OFF here (inductor's generated kernels need it off for some ops; eager is measured both ways).

    source env.sh; cd $CB; $PY -u scratchpad/gauntlet/L74/plan1026/pilot/lrn/compile_probe.py --config CFG --keep DIR \
        --T-gate 0.3 --mbs 256,1024 --out /workspace/lrn/prof2/compile.json
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

torch.backends.cudnn.allow_tf32 = False
torch.backends.cuda.matmul.allow_tf32 = False
torch.set_float32_matmul_precision("highest")
REPO = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import rl_royale as R  # noqa: E402
from pipeline import loop_records as LR  # noqa: E402
from pipeline import loop_learner as LL  # noqa: E402
from rec_identity import collate_kw  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--keep", type=Path, required=True)
    ap.add_argument("--T-gate", type=float, required=True)
    ap.add_argument("--mbs", default="256,1024")
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--warm", type=int, default=4)
    ap.add_argument("--mode", default="default")
    ap.add_argument("--target", default="loss", help="loss = torch.compile(minibatch_loss, dynamic=True); "
                    "encoders = compile model.encoder + model.mem.encoder only (dynamic=None), eager loss")
    ap.add_argument("--max-matches", type=int, default=128)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    cfg = {**R.load_config(REPO / a.config, [], smoke=False), "T_gate": a.T_gate}
    run = f"lrn_compile_{int(time.time())}"
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
    params = [p for p in list(L.model.parameters()) + list(L.ability_head.parameters()) if p.requires_grad]
    names = [n for n, p in list(L.model.named_parameters()) + [("ab." + n, p) for n, p in L.ability_head.named_parameters()]
             if p.requires_grad]
    kw = dict(tau=cfg["tau"], T=cfg["T"], clip=cfg["clip"], beta=0.0, n_total=N, vf=vf, T_gate=cfg.get("T_gate"), ability=abl)
    md = None if a.mode == "default" else a.mode
    if a.target == "loss":
        comp = torch.compile(R.minibatch_loss, dynamic=True, mode=md)
    else:                                                     # swap compiled encoders in / out around each call
        eager_mods = (L.model.encoder, L.model.mem.encoder)
        comp_mods = tuple(torch.compile(m, mode=md) for m in eager_mods)

        def comp(*x, **k):
            L.model.encoder, L.model.mem.encoder = comp_mods
            try:
                return R.minibatch_loss(*x, **k)
            finally:
                L.model.encoder, L.model.mem.encoder = eager_mods

    def run_step(fn, idx):
        for p in params:
            p.grad = None
        torch.cuda.synchronize(); t = time.perf_counter()
        loss, st = fn(L.model, B, Rz, idx, **kw)
        loss.backward()
        torch.cuda.synchronize()
        return time.perf_counter() - t, float(loss.detach()), [p.grad.detach().clone() if p.grad is not None else None
                                                              for p in params]

    rng = np.random.default_rng(0)
    out = {"mode": a.mode, "target": a.target, "torch": torch.__version__, "mb": {}}
    for mb in [int(x) for x in a.mbs.split(",")]:
        draws = [torch.from_numpy(rng.choice(N, mb, replace=False)).to(L.dev) for _ in range(a.warm + a.steps)]
        for idx in draws:
            Rz.fill(idx)
        t0 = time.perf_counter()
        for idx in draws[:a.warm]:
            run_step(comp, idx)
        compile_s = time.perf_counter() - t0
        te, tc, lrel, grel, worst = [], [], [], [], []
        for idx in draws[a.warm:]:
            s_e, l_e, g_e = run_step(R.minibatch_loss, idx)
            s_c, l_c, g_c = run_step(comp, idx)
            te.append(s_e); tc.append(s_c)
            lrel.append(abs(l_c - l_e) / max(abs(l_e), 1e-30))
            gmax = max(float(g.abs().max()) for g in g_e if g is not None)
            per = [(float((c - e).abs().max()) / max(float(e.abs().max()), 1e-30), n) for n, e, c in zip(names, g_e, g_c)
                   if e is not None and c is not None]
            grel.append(max(float((c - e).abs().max()) for e, c in zip(g_e, g_c) if e is not None and c is not None) / gmax)
            worst.append(max(per))
        out["mb"][mb] = {"eager_ms": 1000 * float(np.median(te)), "compiled_ms": 1000 * float(np.median(tc)),
                         "speedup": float(np.median(te) / np.median(tc)), "compile_warm_s": compile_s,
                         "loss_rel_max": max(lrel), "grad_rel_to_global_max": max(grel),
                         "worst_tensor_rel": max(worst)}
        print(mb, json.dumps(out["mb"][mb]), flush=True)
        a.out.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
