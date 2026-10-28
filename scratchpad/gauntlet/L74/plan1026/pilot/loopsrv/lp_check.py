"""LOOP-SRV: the server's numerics vs the CPU fp32 reference on B0, N rows (pod, cwd = the loopsrv tree).
The server path = PolicyServer's Forward (padded bucket, eager or graphs) + its cell call + the P1 decide on its heads;
the reference = GenPolicy.forward_batch on CPU + model_cell_logits on CPU + the same decide, same per-row rngs.
precision fp32 (TF32 off everywhere) and, for contrast, torch's defaults (cudnn TF32 on).
    python lp_check.py --out lp_check.json [--n 4096]"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path[:0] = [str(Path.cwd()), str(Path.cwd() / "pipeline/tests"), str(Path(__file__).resolve().parent)]
from srv_bench import POOL, rows_for  # noqa: E402

CFG = {"tau": 0.35, "T": 0.5, "T_gate": 0.3}


def run_decide(heads, p, cell_logits, n, seed0):
    from pipeline.decision_options import DecisionOptions, decide, sample_rules
    al = np.zeros((n, 8), bool)
    al[:, :4] = True
    st = np.zeros(n, bool)
    st[::3] = True
    return decide(heads, p, al, st, tau=CFG["tau"], options=sample_rules(DecisionOptions()), rngs=[None] * n,
                  decode="sample", sampler={"tau_r": None, "T": CFG["T"], "T_gate": CFG["T_gate"],
                                            "heads": frozenset(("gate", "card", "cell")),
                                            "rngs": [np.random.default_rng(seed0 + i) for i in range(n)]},
                  cell_logits=cell_logits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=4096)
    ap.add_argument("--block", type=int, default=512)
    a = ap.parse_args()
    from pipeline import batched_rollout as BR
    from pipeline import e1_eval as E
    from pipeline.decision_options import model_cell_logits
    from pipeline.policy_server import BUCKETS_FINE, Forward, configure
    ck = POOL[0][1]
    cpu = E.load_policy(ck, "cpu")[0]
    rows = rows_for(cpu.model, a.n, seed=3)
    ref = []
    for o in range(0, a.n, a.block):
        rr = [{k: v[i] for k, v in rows.items()} for i in range(o, o + a.block)]
        enc, heads, p, _ = cpu.forward_batch(rr, "cpu")
        ref += run_decide(heads, np.asarray(p), model_cell_logits(cpu, enc, "cpu"), a.block, o)
    res = {"ckpt": ck, "n": a.n, "block": a.block, "rows": []}
    for prec, mode in (("default", "eager"), ("fp32", "eager"), ("fp32", "graphs")):
        if prec == "fp32":
            configure("fp32")
        else:
            torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32 = False, True   # torch defaults
        pol = BR.LazyRefine(E.load_policy(ck, "cuda")[0]).split()
        fw = Forward(pol, "cuda", mode, buckets=BUCKETS_FINE, pad=True, graph_max=512)
        got = []
        for o in range(0, a.n, a.block):
            arr = {k: torch.from_numpy(np.ascontiguousarray(v[o:o + a.block])).pin_memory().numpy() for k, v in rows.items()}
            enc, heads, p, _ = fw(arr, a.block)
            if fw.last_graph:
                enc = {k: v[:a.block].clone() if torch.is_tensor(v) else v for k, v in enc.items()}
            h = {k: torch.from_numpy(v[:a.block].float().cpu().numpy()) for k, v in heads.items()}
            cl = fw.cell_logits(enc, a.block)
            got += run_decide(h, p.cpu().numpy(), lambda ids, slots: cl(ids, slots).float().cpu(), a.block, o)
        d = {k: max(abs(x[k] - y[k]) for x, y in zip(ref, got)) for k in ("lp_gate", "lp_card", "lp_cell")}
        act = sum((x["play"], x["slot"], x["cell"]) != (y["play"], y["slot"], y["cell"]) for x, y in zip(ref, got))
        over = sum(any(abs(x[k] - y[k]) >= 1e-5 for k in ("lp_gate", "lp_card", "lp_cell")) for x, y in zip(ref, got))
        r = dict(precision=prec, mode=mode, max_abs_diff={k: float(f"{v:.3g}") for k, v in d.items()}, action_diffs=act,
                 rows_lp_over_1e5=over, plays=sum(x["play"] for x in ref))
        print(json.dumps(r), flush=True)
        res["rows"].append(r)
    Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
