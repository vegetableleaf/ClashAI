"""OPP-LEARN-D: what timing_pg K (K slot rows per match) costs in timing-gradient noise, on one recorded rollout.

    python tpg_var.py RECORDS_PKL INIT_PT [K ...]      (cwd = a tree with pipeline/; CPU)

RECORDS_PKL = fastloop FASTLOOP_RECORDS records_u0000.pkl of a timing_pg rollout (every slot row carries lp_th). At the
init (ratio 1) the timing term's gradient is g = -sum_rows w_th A grad lp_th. Prints |g_all| (every slot row), and for
each K and 3 subsample draws |g_K|, cos(g_K, g_all), |g_K - g_all| / |g_all|; plus the match-sampling noise for scale:
cos between g_all of two random halves of the matches (2 splits).
"""
import pickle
import sys
import zlib

import numpy as np
import torch

from pipeline import model_gen
from pipeline import rl_royale as RL


def grad_th(model, B, chunk=256):
    model.zero_grad(set_to_none=True)
    N = len(B["A"])
    for s in range(0, N, chunk):
        idx = torch.arange(s, min(s + chunk, N))
        t = RL.policy_terms(model, B, idx, 0.35, 1.0)
        (-(B["w_th"][idx] * B["A"][idx] * t["lp_th"]).sum()).backward()
    return torch.cat([p.grad.flatten() for p in model.parameters() if p.grad is not None]).double()


def batch(res, k, seed):
    orig = RL.th_sample
    if k is not None:
        def ths(slot, k_, r):
            if int(slot.sum()) <= k_:
                return slot
            rng = np.random.default_rng(zlib.crc32(f"var{seed}:{RL.row_key(r)}".encode()))
            out = np.zeros_like(slot)
            out[rng.choice(np.flatnonzero(slot), int(k_), replace=False)] = True
            return out
        RL.th_sample = ths
    try:
        B = RL.to_device(RL.collate(res, timing_rows=k)[0], "cpu")
    finally:
        RL.th_sample = orig
    keep = B["w_th"] > 0                                       # the timing rows only (the gradient needs no others)
    return RL.row_subset(B, keep.nonzero().squeeze(-1))


def main():
    res = [r for r in pickle.load(open(sys.argv[1], "rb"))["results"] if "traj" in r and "lp_th" in r["traj"]]
    model = model_gen.load_model(sys.argv[2], torch.device("cpu"))[0]
    model.eval()
    ks = [int(x) for x in sys.argv[3:]] or [32]
    cos = lambda a, b: float(a @ b / (a.norm() * b.norm()))   # noqa: E731
    g = grad_th(model, batch(res, None, 0))
    n_slot = sum(int((r["traj"]["th_j"] >= -1).sum()) for r in res)
    print(f"matches {len(res)} slot rows {n_slot} |g_all| {float(g.norm()):.4e}")
    for k in ks:
        for sd in range(3):
            gk = grad_th(model, batch(res, k, sd))
            print(f"K {k} draw {sd}: |g_K| {float(gk.norm()):.4e} cos {cos(gk, g):.3f} rel_err {float((gk - g).norm() / g.norm()):.3f}")
    rng = np.random.default_rng(0)
    for sp in range(2):
        perm = rng.permutation(len(res))
        h = [grad_th(model, batch([res[i] for i in perm[j::2]], None, 0)) for j in (0, 1)]
        print(f"match halves split {sp}: cos(g_half1, g_half2) {cos(h[0], h[1]):.3f}")


if __name__ == "__main__":
    main()
