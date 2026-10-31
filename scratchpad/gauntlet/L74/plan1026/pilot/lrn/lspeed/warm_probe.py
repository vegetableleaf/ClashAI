"""LEARNER-SPEED: arm L's per-step KL on a SECOND update (Adam warmed by the first), per lr. Update 1 on matches [0, H),
update 2 on [H, 2H) with the same Adam; update 2's anchor = the model after update 1 (kl_ref_refresh_every 1). Both
batches were played by B0, so update 2's rows are one version stale (b: the step SIZES are what is measured here).
split_attn + trunk_graph on (bitwise / 1e-8 vs eager). Records each minibatch's KL to its anchor before its step.
    PY warm_probe.py --res A.pkl [B.pkl ...] --config CFG --lrs 2e-5,3e-5 --out OUT.json
"""
import argparse
import copy
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
sys.path[:0] = [str(HERE), str(HERE.parent)]
from gen_recs import learner  # noqa: E402
from pipeline import rl_royale as R  # noqa: E402
from pipeline.learner_attn import use_split_attn  # noqa: E402
from rec_identity import collate_kw  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", type=Path, nargs="+", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--lrs", default="2e-5,3e-5,4e-5")
    ap.add_argument("--minibatch", type=int, default=65536)
    ap.add_argument("--micro", type=int, default=1024)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    cfg, L = learner(a.config, ["mem_row_cache=true", "learner_device=cuda"], "warm")
    res = [r for f in a.res for r in pickle.loads(f.read_bytes())]
    H = len(res) // 2
    Bs = []
    for part in (res[:H], res[H:2 * H]):
        Bn, _ = R.collate(part, float(cfg["adv_clip"]), **collate_kw(cfg))
        B = R.to_device(Bn, L.dev)
        R.gae_batch(L.model, B, cfg)
        Bs.append(B)
    del res
    ac = R.adv_cfg(cfg)
    vf = {"coef": ac["vf_coef"], "clip": ac["vf_clip"], "policy": True, "trunk_grad": ac["vf_trunk_grad"]}
    out = {"matches_per_update": H, "rows": [len(B["A"]) for B in Bs], "minibatch": a.minibatch, "micro": a.micro, "lrs": {}}
    for lr in [float(x) for x in a.lrs.split(",")]:
        m = copy.deepcopy(L.model)
        use_split_attn(m)
        m.trunk_graph = a.micro
        ab = copy.deepcopy(L.ability_head)
        opt = torch.optim.Adam(m.parameters(), lr=lr)
        ab_opt = torch.optim.Adam(ab.parameters(), lr=float(cfg["ability_lr"]))
        pc = {**cfg, "minibatch": a.minibatch, "micro_batch": a.micro, "kl_stop_prev": 0.02, "lr": lr}
        ups = []
        for k, B in enumerate(Bs):
            ref = L.ref if k == 0 else copy.deepcopy(m).eval()
            for p in ref.parameters():
                p.requires_grad_(False)
            Rz = R.LazyRef(ref, B, cfg["tau"], cfg["T"], T_gate=cfg.get("T_gate"))
            B["_mem_cache"] = R.MemRowCache(len(B["A"]))
            kls, orig = [], R.accum_backward

            def rec(*args, **kw):
                loss, st = orig(*args, **kw)
                kls.append([st["kl_gate"], st["kl_card"], st["kl_cell"]])
                return loss, st
            R.accum_backward = rec
            t0 = time.perf_counter()
            try:
                u = R.ppo_update(m, opt, B, Rz, pc, 0.0, np.random.default_rng(1 + k), vf=vf,
                                 ability={"head": ab, "opt": ab_opt, "ent_coef": float(cfg["ability_ent_coef"])})
            finally:
                R.accum_backward = orig
            ups.append({"update": k + 1, "steps": u["steps"], "kl_stop": u.get("kl_stop"), "s": time.perf_counter() - t0,
                        "kl_pre_step": kls, "kl_pre_step_sum": [round(sum(x), 5) for x in kls],
                        "first_ratio_maxdev": (u.get("first") or {}).get("ratio_maxdev")})
            print(f"[warm] lr {lr:g} update {k + 1}: steps {u['steps']} stop {u.get('kl_stop')} KL after k steps "
                  f"{ups[-1]['kl_pre_step_sum']}", flush=True)
        out["lrs"][f"{lr:g}"] = ups
    a.out.write_text(json.dumps(out, indent=1))
    os._exit(0)


if __name__ == "__main__":
    main()
