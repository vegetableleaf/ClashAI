"""LEARNER-SCALE step 1: gradient noise scale B_simple = tr(Sigma) / |G|^2 (McCandlish et al. 2018) of the pilot learner's
loss on real records, at the start of a policy update (ratio = 1), per loss component.

Components (one forward, one backward each; parameters = every model parameter, the AbilityHead excluded):
  gate / card / cell  -sum w A lp_head  (= the PPO-clip L_pg gradient at ratio 1, split by head; checked vs minibatch_loss)
  value               vf_coef x the clipped value loss (as minibatch_loss, v = v_old at the update start)
  combos: policy = gate + card + cell, total = policy + value.
Units, all scaled so their mean is the full-batch gradient G_fin = sum_i g_i (g_i = row i's term of the full-batch loss):
  MATCH  h_m = M sum_{i in m} g_i (the update's sampling unit). tr(Sigma_m) = sample variance of h_m (M-1 dof);
         |G|^2_U = |h_bar|^2 - tr(Sigma_m) / M (unbiased for the TRUE gradient, i.e. over fresh matches);
         B_match = tr(Sigma_m) / |G|^2_U in matches. CI: delete-one-group jackknife over K match groups.
  ROW    G_b = (N / b) sum_{i in b} g_i over b random rows of this batch (no replacement):
         E|G_b - G_fin|^2 = tr(Sigma_row) / b (N - b) / (N - 1) -> tr(Sigma_row); B_row = tr(Sigma_row) / |G|^2_U in rows
         (the noise of a minibatch of b rows drawn from a large pool of fresh matches). SE over the repeats.
Critic: --warm DIR runs --warm-updates critic warm-up updates (stored mode) on OTHER records first, so the measured batch's
advantages come from a critic that never saw it.

    source env.sh; cd $CB; $PY -u scratchpad/gauntlet/L74/plan1026/pilot/lrn/noise_scale.py \
        --config scratchpad/gauntlet/L74/plan1026/pilot/ops/pilot.yaml --keep /workspace/lrn/id1/keep --T-gate 0.3 \
        [--warm /workspace/lrn/id0_freshhead/keep --warm-updates 3] --out /workspace/lrn/noise/ns_X.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stored_gate as SG  # noqa: E402  (deterministic, TF32 off)
from stored_gate import R, LR, torch  # noqa: E402
import numpy as np  # noqa: E402

COMP = ("gate", "card", "cell", "value")
COMBOS = {"gate": [1, 0, 0, 0], "card": [0, 1, 0, 0], "cell": [0, 0, 1, 0], "value": [0, 0, 0, 1],
          "policy": [1, 1, 1, 0], "total": [1, 1, 1, 1]}


def unit_grads(L, B, idx, cfg, params, chunk):
    """[4, P] float64: sum over rows ``idx`` of each component's per-row gradient (chunked, summed)."""
    out = torch.zeros(4, sum(p.numel() for p in params), dtype=torch.float64, device=B["A"].device)
    vfc, vclip = float(R.adv_cfg(cfg)["vf_coef"]), float(R.adv_cfg(cfg)["vf_clip"])
    for s in range(0, len(idx), chunk):
        ii = idx[s:s + chunk]
        t = R.policy_terms(L.model, B, ii, cfg["tau"], cfg["T"], value=True, T_gate=cfg.get("T_gate"))
        A, w = B["A"][ii], B["w"][ii]
        v, v_old, ret = t["v"], B["v_old"][ii], B["ret"][ii]
        v_clip = v_old + (v - v_old).clamp(-vclip, vclip)
        losses = [-(w * A * t["lp_gate"]).sum(), -(w * A * t["lp_card"]).sum(), -(w * A * t["lp_cell"]).sum(),
                  vfc * (w * 0.5 * torch.max((v - ret) ** 2, (v_clip - ret) ** 2)).sum()]
        live = [c for c, loss in enumerate(losses) if loss.requires_grad]   # a chunk without played / gate rows: 0
        for c in live:
            gs = torch.autograd.grad(losses[c], params, retain_graph=c != live[-1], allow_unused=True)
            out[c] += torch.cat([(g if g is not None else torch.zeros_like(p)).reshape(-1).double()
                                 for g, p in zip(gs, params)])
    return out


def sanity(L, B, cfg, params, N):
    """sum of the 4 components == minibatch_loss's gradient (policy update, beta 0, no ability) on 256 rows."""
    idx = torch.arange(0, 256, device=B["A"].device)
    ac = R.adv_cfg(cfg)
    vf = {"coef": ac["vf_coef"], "clip": ac["vf_clip"], "policy": True, "trunk_grad": ac["vf_trunk_grad"]}
    Rz = R.LazyRef(L.ref, B, cfg["tau"], cfg["T"], T_gate=cfg.get("T_gate"))
    loss, st = R.minibatch_loss(L.model, B, Rz, idx, tau=cfg["tau"], T=cfg["T"], clip=cfg["clip"], beta=0.0, n_total=N,
                                vf=vf, T_gate=cfg.get("T_gate"))
    gs = torch.autograd.grad(loss, params, allow_unused=True)
    ref = torch.cat([(g if g is not None else torch.zeros_like(p)).reshape(-1).double() for g, p in zip(gs, params)])
    mine = unit_grads(L, B, idx, cfg, params, 256).sum(0) * (N / 256)
    return {"rel_diff": float((mine - ref).norm() / ref.norm()), "ratio_maxdev": st["ratio_maxdev"],
            "grad_norm_mb256": float(ref.norm())}


def estimates(gram_m, GG, n_k, M):
    """B_match per combo + jackknife. gram_m [K, 4, 4] = per-group sum of per-match Gram; GG [K, 4, K, 4] group sums' Gram."""
    out = {}
    K = len(n_k)
    for name, c in COMBOS.items():
        c = np.asarray(c, float)
        hm2_k = np.einsum("i,kij,j->k", c, gram_m, c)                  # per group: sum |h_m|^2
        Gc = np.einsum("i,kilj,j->kl", c, GG, c)                        # group sums' Gram for this combo

        def est(keep):
            Mk = n_k[keep].sum()
            hbar2 = Gc[np.ix_(keep, keep)].sum() / Mk ** 2
            tr = (hm2_k[keep].sum() - Mk * hbar2) / (Mk - 1)
            g2 = hbar2 - tr / Mk
            return tr, g2, hbar2
        allk = np.arange(K)
        tr, g2, hbar2 = est(allk)
        jk = np.array([est(np.delete(allk, k)) for k in range(K)])
        se = lambda x: float(np.sqrt((K - 1) / K * ((x - x.mean()) ** 2).sum()))
        b_j = jk[:, 0] / jk[:, 1]
        out[name] = {"tr_sigma_match": tr, "G2_unbiased": g2, "G2_fin": hbar2, "G2_se": se(jk[:, 1]),
                     "tr_se": se(jk[:, 0]), "B_match": tr / g2 if g2 > 0 else None,
                     "B_match_jk_se": se(b_j) if (jk[:, 1] > 0).all() else None,
                     "B_match_lo": tr / (g2 + 2 * se(jk[:, 1])) if g2 + 2 * se(jk[:, 1]) > 0 else None,
                     "B_match_hi": tr / (g2 - 2 * se(jk[:, 1])) if g2 - 2 * se(jk[:, 1]) > 0 else None}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--keep", type=Path, required=True)
    ap.add_argument("--T-gate", type=float, required=True, help="the T_gate the records were SAMPLED at")
    ap.add_argument("--warm", type=Path, default=None)
    ap.add_argument("--warm-updates", type=int, default=3)
    ap.add_argument("--groups", type=int, default=32)
    ap.add_argument("--row-b", default="256,2048")
    ap.add_argument("--row-reps", type=int, default=40)
    ap.add_argument("--max-matches", type=int, default=0)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    cfg = {**R.load_config(SG.REPO / a.config, [], smoke=False), "T_gate": a.T_gate, "stored_values": True,
           "ent_init_rows": None}
    L = SG.learner(cfg, "ns")
    res_out = {"config": {"T_gate": a.T_gate, "keep": str(a.keep), "warm": str(a.warm), "warm_updates": a.warm_updates,
                          "lazy_refine": cfg.get("lazy_refine"), "lr": cfg["lr"], "grad_clip": cfg["grad_clip"]}}
    t0 = time.perf_counter()
    if a.warm is not None:                                    # critic warm-up on disjoint records (u < critic_warmup_updates)
        wres = [LR.to_result(LR.decode(p.read_bytes())) for p in sorted(a.warm.glob("*.rec"))]
        assert a.warm_updates <= int(cfg["critic_warmup_updates"])
        for u in range(a.warm_updates):
            rec = SG.run_update(L, u, SG.with_v(L, cfg, wres), {})
            print("warm", u, json.dumps({k: rec.get(k) for k in ("steps",)} | {"gae": {k: (rec.get("gae") or {}).get(k)
                  for k in ("l_v", "explained_var", "value_mae")}}), flush=True)
        del wres
    res = [LR.to_result(LR.decode(p.read_bytes())) for p in sorted(a.keep.glob("*.rec"))]
    if a.max_matches:
        res = res[:a.max_matches]
    Bn, _ = R.collate(res, float(cfg["adv_clip"]), **SG.collate_kw(cfg))
    del res
    B = R.to_device(Bn, L.dev)
    assert "cf" not in B
    gst = R.gae_batch(L.model, B, cfg)                        # A (normalised), ret, v_old from the current critic
    res_out["gae"] = gst
    L.model.lazy_refine = bool(cfg.get("lazy_refine"))
    params = [p for p in L.model.parameters() if p.requires_grad]
    N, P = len(B["A"]), sum(p.numel() for p in params)
    match = B["match"]
    M = int(match.max()) + 1
    res_out.update(rows=N, matches=M, params=P, rows_per_match=N / M)
    res_out["sanity"] = sanity(L, B, cfg, params, N)
    print("sanity", res_out["sanity"], flush=True)
    K = a.groups
    S = torch.zeros(K, 4, P, dtype=torch.float64, device=L.dev)     # group sums of h_m
    gram_m = np.zeros((K, 4, 4))
    n_k = np.zeros(K, int)
    order = torch.argsort(match, stable=True)
    bounds = torch.searchsorted(match[order], torch.arange(M + 1, device=L.dev))
    t1 = time.perf_counter()
    for m in range(M):
        idx = order[bounds[m]:bounds[m + 1]]
        h = unit_grads(L, B, idx, cfg, params, 256) * M
        k = m % K
        S[k] += h
        gram_m[k] += (h @ h.T).cpu().numpy()
        n_k[k] += 1
        if m % 64 == 0:
            print(f"match {m}/{M} {time.perf_counter() - t1:.0f}s", flush=True)
    res_out["match_pass_s"] = time.perf_counter() - t1
    Sf = S.reshape(K * 4, P)
    GG = (Sf @ Sf.T).cpu().numpy().reshape(K, 4, K, 4)
    est = estimates(gram_m, GG, n_k, M)
    Gfin = S.sum(0) / M                                       # [4, P] = sum_i g_i per component
    del S, Sf
    rng = np.random.default_rng(1028)
    rows = {}
    for b in [int(x) for x in a.row_b.split(",")]:
        d2 = []
        for _ in range(a.row_reps):
            idx = torch.from_numpy(np.sort(rng.choice(N, b, replace=False))).to(L.dev)
            D = unit_grads(L, B, idx, cfg, params, 256) * (N / b) - Gfin
            d2.append((D @ D.T).cpu().numpy())
        d2 = np.array(d2)
        fpc = b * (N - 1) / (N - b)
        rows[b] = {}
        for name, c in COMBOS.items():
            c = np.asarray(c, float)
            x = np.einsum("i,rij,j->r", c, d2, c) * fpc                    # per repeat: tr(Sigma_row) estimate
            g2 = est[name]["G2_unbiased"]
            gf = float(c @ (Gfin @ Gfin.T).cpu().numpy() @ c)
            rows[b][name] = {"tr_sigma_row": float(x.mean()), "tr_se": float(x.std(ddof=1) / np.sqrt(len(x))),
                             "B_row": float(x.mean()) / g2 if g2 > 0 else None,
                             "noise_to_signal_at_b": float(x.mean()) / b / g2 if g2 > 0 else None,
                             "grad_norm_b_mean": float(np.sqrt(x.mean() / fpc + gf))}
        print("rows b", b, json.dumps({k: rows[b][k]["B_row"] for k in COMBOS}), flush=True)
    for name in COMBOS:
        e = est[name]
        e["design_effect"] = (e["B_match"] * N / M / rows[256][name]["B_row"]) if e["B_match"] and rows.get(256, {}).get(name, {}).get("B_row") else None
        e["B_match_in_rows"] = e["B_match"] * N / M if e["B_match"] else None
    res_out["match"] = est
    res_out["rows"] = rows
    res_out["G_fin_norm"] = {n: float(np.sqrt(est[n]["G2_fin"])) for n in COMBOS}
    res_out["wall_s"] = time.perf_counter() - t0
    a.out.write_text(json.dumps(res_out, indent=1, default=float))
    for name in COMBOS:
        e = est[name]
        print(f"{name:7s} B_match {e['B_match']} [{e['B_match_lo']}, {e['B_match_hi']}] (~{e['B_match_in_rows']} rows) "
              f"B_row(256) {rows.get(256, {}).get(name, {}).get('B_row')} G2_U {e['G2_unbiased']:.4g} +- {e['G2_se']:.2g} "
              f"tr {e['tr_sigma_match']:.4g}", flush=True)


if __name__ == "__main__":
    main()
