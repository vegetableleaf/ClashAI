"""SPEED2 (4) premise of the critic warm-up trunk cache: is a row's forward output (g, value, gate / card logits) at a
FIXED batch shape bitwise independent of which other rows share its batch and of its position? B0 (learner config:
fp32, TF32 off, deterministic algorithms), 1,024 fixture rows; batch A = rows 0..255, batch B = a random 256 of the
1,024 that contains rows 0..127 at shuffled positions; plus the same rows at shape 128 and 192 (the last partial
minibatch). usage (pod, repo root, env.sh): python rowinv.py OUT.json"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import numpy as np
import torch

REPO = Path.cwd()
sys.path[:0] = [str(REPO), str(REPO / "pipeline/tests"), str(REPO / "scratchpad/gauntlet/L74/plan1026/pilot/loopsrv")]


def main():
    from srv_bench import rows_for
    from pipeline import e1_eval as E
    torch.backends.cuda.matmul.allow_tf32 = torch.backends.cudnn.allow_tf32 = False
    torch.use_deterministic_algorithms(True)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    pol = E.load_policy(REPO / "icebow/data/bench/rl_royale/b0/b0_clxiii_s3aux_grafted.pt", dev)[0]
    rows = rows_for(pol.model, 1024, seed=3)
    keys = E.gen_row_keys(pol.model)

    def fwd(ids):
        b = {k: torch.from_numpy(np.ascontiguousarray(rows[k][ids])).to(dev) for k in keys}
        with torch.no_grad():
            enc, heads = pol.heads_t(b)
            out = {"g": enc["g"], **{k: heads[k] for k in ("gate", "card") if k in heads}}
            vh = getattr(pol.model, "value_head", None)
            if vh is not None:
                out["value"] = vh(enc["g"])
        return {k: v.double().cpu().numpy() for k, v in out.items()}

    rng = np.random.default_rng(0)
    A = np.arange(256)
    others = rng.choice(np.arange(256, 1024), 128, replace=False)
    Bi = rng.permutation(np.concatenate([np.arange(128), others]))
    fa, fb = fwd(A), fwd(Bi)
    pos = {int(r): j for j, r in enumerate(Bi)}
    common = np.arange(128)
    res = {"device": dev, "torch": torch.__version__}
    for k in fa:
        d = np.abs(fa[k][common] - fb[k][[pos[int(r)] for r in common]])
        res[f"shape256_{k}"] = {"max_abs": float(d.max()), "rows_bit_equal": int((d.reshape(len(common), -1).max(1) == 0).sum())}
    for n in (128, 192):
        fn = fwd(np.arange(n))
        for k in fa:
            d = np.abs(fa[k][:min(n, 128)] - fn[k][:min(n, 128)])
            res[f"shape{n}_vs256_{k}"] = {"max_abs": float(d.max()),
                                          "rows_bit_equal": int((d.reshape(min(n, 128), -1).max(1) == 0).sum())}
    res["n_common"] = len(common)
    print(json.dumps(res, indent=1))
    Path(sys.argv[1]).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
