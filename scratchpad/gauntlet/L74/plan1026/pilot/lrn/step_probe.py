"""LOOP-LRN DDP decision probe: wall time of ONE PPO step (minibatch_loss forward + backward + clip + Adam) at minibatch
sizes 256 / 128 / 64 / 32 on real records, policy mode with the value loss, deterministic CUDA. With N-GPU DDP at the fixed
minibatch 256 each GPU runs 256 / N rows per step, so step(256 / N) + the gradient all-reduce bounds the DDP step.

    source env.sh; cd $CB; $PY -u scratchpad/gauntlet/L74/plan1026/pilot/lrn/step_probe.py --config CFG --keep DIR [--steps 40]
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
REPO = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO))
from pipeline import rl_royale as R  # noqa: E402
from pipeline import loop_records as LR  # noqa: E402
from pipeline import loop_learner as LL  # noqa: E402
from rec_identity import collate_kw  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--keep", type=Path, required=True)
    ap.add_argument("--steps", type=int, default=40)
    a = ap.parse_args()
    cfg = R.load_config(REPO / a.config, [], smoke=False)
    run = f"lrn_probe_{int(time.time())}"
    for d in (R.RUN_ROOT / run, R.CKPT_ROOT / run):
        d.mkdir(parents=True, exist_ok=True)
    L = R.Learner(cfg, run, R.RUN_ROOT / run, R.CKPT_ROOT / run, R.Log(R.RUN_ROOT / run), False)
    LL.adopt_init_ability_head(L)
    res = [LR.to_result(LR.decode(p.read_bytes())) for p in sorted(a.keep.glob("*.rec"))]
    t = time.perf_counter()
    Bn, _ = R.collate(res, float(cfg["adv_clip"]), **collate_kw(cfg))
    t_col = time.perf_counter() - t
    del res
    B = R.to_device(Bn, L.dev)
    R_ = R.ref_terms(L.ref, B, cfg["tau"], cfg["T"], T_gate=cfg.get("T_gate"))
    R.gae_batch(L.model, B, cfg)
    ac = R.adv_cfg(cfg)
    vf = {"coef": ac["vf_coef"], "clip": ac["vf_clip"], "policy": True, "trunk_grad": ac["vf_trunk_grad"]}
    abl = {"head": L.ability_head, "opt": L.ability_opt, "ent_coef": float(cfg["ability_ent_coef"])}
    N = len(B["A"])
    rng = np.random.default_rng(0)
    out = {"rows": N, "collate_s": t_col, "params": sum(p.numel() for p in L.model.parameters()), "ms_per_step": {}}
    for mb in (256, 128, 64, 32):
        ts = []
        for i in range(a.steps + 3):
            idx = torch.from_numpy(rng.choice(N, mb, replace=False)).to(L.dev)
            torch.cuda.synchronize()
            t = time.perf_counter()
            loss, st = R.minibatch_loss(L.model, B, R_, idx, tau=cfg["tau"], T=cfg["T"], clip=cfg["clip"], beta=0.0,
                                        n_total=N, vf=vf, T_gate=cfg.get("T_gate"), ability=abl)
            L.opt.zero_grad(set_to_none=True); L.ability_opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(L.model.parameters(), float(cfg["grad_clip"]))
            L.opt.step(); L.ability_opt.step()
            torch.cuda.synchronize()
            if i >= 3:
                ts.append(1000 * (time.perf_counter() - t))
        out["ms_per_step"][mb] = {"p50": float(np.median(ts)), "p90": float(np.percentile(ts, 90))}
        print(mb, out["ms_per_step"][mb], flush=True)
    steps_512 = int(cfg["ppo_epochs"]) * -(-N // int(cfg["minibatch"]))
    out["steps_per_update"] = steps_512
    out["update_ppo_s_1gpu"] = steps_512 * out["ms_per_step"][256]["p50"] / 1000
    for n in (2, 4, 8):
        out[f"update_ppo_s_ddp{n}_compute_only"] = steps_512 * out["ms_per_step"][256 // n]["p50"] / 1000
    print(json.dumps(out, indent=1), flush=True)
    (a.keep.parent / "step_probe.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
