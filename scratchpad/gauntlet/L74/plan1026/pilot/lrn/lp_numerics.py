"""Stored behaviour log-probs (CPU actors) vs the learner's recompute (rl_royale.policy_terms) on CPU fp32 and on CUDA
(deterministic), per head, on the first --n records of a keep dir. Separates "the recompute covers the grafted heads"
(CPU recompute == stored to ~1e-6) from float differences between devices.

    source env.sh; cd $CB; $PY -u scratchpad/gauntlet/L74/plan1026/pilot/lrn/lp_numerics.py --config CFG --keep DIR [--n 16]
"""
import argparse
import copy
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import numpy as np  # noqa: E402
import torch  # noqa: E402

torch.use_deterministic_algorithms(True)
if os.environ.get("LPNUM_NOTF32"):                          # cudnn convs default to TF32 (allow_tf32 True)
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False
REPO = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO))
from pipeline import rl_royale as R  # noqa: E402
from pipeline import loop_records as LR  # noqa: E402
from rec_identity import collate_kw  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--keep", type=Path, required=True)
    ap.add_argument("--n", type=int, default=16)
    a = ap.parse_args()
    cfg = R.load_config(REPO / a.config, [], smoke=False)
    run = f"lrn_lpnum_{int(time.time())}"
    for d in (R.RUN_ROOT / run, R.CKPT_ROOT / run):
        d.mkdir(parents=True, exist_ok=True)
    L = R.Learner(cfg, run, R.RUN_ROOT / run, R.CKPT_ROOT / run, R.Log(R.RUN_ROOT / run), False)
    res = [LR.to_result(LR.decode(p.read_bytes())) for p in sorted(a.keep.glob("*.rec"))[:a.n]]
    Bn, _ = R.collate(res, float(cfg["adv_clip"]), **collate_kw(cfg))
    out = {"rows": int(len(Bn["A"])), "played": int(Bn["played"].sum())}
    print("cudnn.allow_tf32", torch.backends.cudnn.allow_tf32, "matmul.allow_tf32", torch.backends.cuda.matmul.allow_tf32)
    for dev in ("cuda",):
        m = copy.deepcopy(L.model).to(dev).eval()
        B = R.to_device(Bn, dev)
        d = {k: [] for k in ("lp_gate", "lp_card", "lp_cell")}
        with torch.no_grad():
            for s in range(0, len(Bn["A"]), 512):
                idx = torch.arange(s, min(s + 512, len(Bn["A"])), device=dev)
                t = R.policy_terms(m, B, idx, cfg["tau"], cfg["T"], T_gate=cfg.get("T_gate"))
                for k in d:
                    d[k].append((t[k] - B[k][idx]).abs().cpu().numpy())
        out[dev] = {k: {"max": float(np.concatenate(v).max()), "p99": float(np.percentile(np.concatenate(v), 99)),
                        "median": float(np.median(np.concatenate(v)))} for k, v in d.items()}
        print(dev, json.dumps(out[dev]), flush=True)
    (a.keep.parent / "lp_numerics.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
