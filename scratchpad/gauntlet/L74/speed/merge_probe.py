"""S1b (3) probe: can K same-architecture opponent policies share ONE GPU call? torch.func.stack_module_state +
vmap(functional_call) over K models x B rows each, vs K separate GenPolicy.forward_batch calls: outputs (max abs diff)
and wall time per round, on the 5 league externals of succ48_x_s101 (all GenModel fv6 d128 x 4, no cue / refine).
    python merge_probe.py --B 146 --out merge.json   (run from the repo root on the pod)"""
import argparse
import copy
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from pipeline import e1_eval as E  # noqa: E402

EXT = ["icebow/data/bench/rl_royale/wk_adapt_exp1/wk_adapt_exp1_u0015.pt",
       "icebow/data/bench/rl_royale/wk_adapt_exp2/wk_adapt_exp2_u0015.pt",
       "icebow/data/bench/rl_royale/wk_adapt_exp3/wk_adapt_exp3_u0015.pt",
       "icebow/data/bench/rl_royale/newsim_base_exp1/newsim_base_exp1_u0015.pt",
       "icebow/data/bench/rl_royale/newsim_base_exp2/newsim_base_exp2_u0015.pt"]


def rows(n, seed):
    sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "pipeline/tests"))
    from test_fast_obs import _rows
    r = _rows(n)
    rng = np.random.default_rng(seed)
    rng.shuffle(r)
    return r


class Heads(torch.nn.Module):
    def __init__(self, pol):
        super().__init__()
        self.model, self.pol = pol.model, pol

    def forward(self, b):
        enc, heads = self.pol.heads_t(b)
        return heads["gate"], heads["card"], enc["g"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=146)
    ap.add_argument("--reps", type=int, default=20)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    dev = "cuda"
    pols = [E.load_policy(p, dev)[0] for p in EXT]
    R = [rows(a.B, k) for k in range(len(pols))]
    keys = E.gen_row_keys(pols[0].model)
    bs = [{k: torch.from_numpy(np.stack([r[k] for r in rr])).to(dev) for k in keys} for rr in R]
    with torch.no_grad():
        ref = [Heads(p)(b) for p, b in zip(pols, bs)]
        torch.cuda.synchronize()
        t = time.perf_counter()
        for _ in range(a.reps):
            for p, rr in zip(pols, R):
                p.forward_batch(rr, dev)
        torch.cuda.synchronize()
        sep = (time.perf_counter() - t) / a.reps
    out = {"B_per_model": a.B, "K": len(pols), "separate_forward_batch_ms": round(sep * 1000, 2)}
    try:
        from torch.func import functional_call, stack_module_state
        mods = [Heads(p) for p in pols]
        params, buffers = stack_module_state(mods)
        base = copy.deepcopy(mods[0]).to("meta")
        base.pol = copy.copy(pols[0])
        base.pol.model = base.model

        def f(pr, bu, b):
            return functional_call(base, (pr, bu), (b,))
        stacked = {k: torch.stack([b[k] for b in bs]) for k in keys}
        with torch.no_grad():
            got = torch.vmap(f, in_dims=(0, 0, 0))(params, buffers, stacked)
            torch.cuda.synchronize()
            t = time.perf_counter()
            for _ in range(a.reps):
                stacked = {k: torch.from_numpy(np.stack([np.stack([r[k] for r in rr]) for rr in R])).to(dev) for k in keys}
                got = torch.vmap(f, in_dims=(0, 0, 0))(params, buffers, stacked)
                [g.cpu() for g in got]
            torch.cuda.synchronize()
            out["vmap_merged_ms"] = round((time.perf_counter() - t) / a.reps * 1000, 2)
        nz = torch.nan_to_num                                 # card logits carry -inf on empty hand slots
        out["max_abs_diff"] = {n: float(max((nz(g[k]) - nz(r[j])).abs().max() for k, r in enumerate(ref)))
                               for j, (n, g) in enumerate(zip(("gate", "card", "g"), got))}
    except Exception as exc:                                  # noqa: BLE001 -- the probe reports what fails
        out["vmap_error"] = repr(exc)[:600]
    print(json.dumps(out, indent=1))
    Path(a.out).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
