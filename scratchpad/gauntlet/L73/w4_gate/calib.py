"""W4 step 2: gate calibration on pro rows (icebow deck 90, gen_dataset_v32_fv5) from extract.py output.
  python calib.py rows_live.npz [rows_other.npz ...]
Per context (enemy-empty board, elixir >= E, phase, t >= 7.5 s):
  * row level: pro play fraction f vs the model's mean p (the gate is trained on these rows: calibration check);
  * rates: WAIT rows are sampled every 40 ticks (2 s) and dropped within 20 ticks before a play, so for a play rate
    lam (1/s) the row odds are p/(1-p) = 2 lam exp(lam * 1 s)  ->  lam = W(odds / 2) (Lambert W);
  * same-state episodes: maximal runs of consecutive in-context rows of one (replay, side); the pro's event = its
    play row; the MODEL under (a) the live threshold rule plays at the first row with p > tau_phase, (b) hazard
    decoding plays at rate lam(p) between rows; both censored where the pro's episode ends. Kaplan-Meier P(<= 5 s)."""
import sys
import numpy as np

TAU = np.array([0.35, 0.45, 0.55])
RNG = np.random.default_rng(0)


def lam_of(p):
    """Lambert-W inversion of odds = 2 lam e^lam (Newton, monotone)."""
    o = np.clip(p, 1e-6, 1 - 1e-6); o = o / (1 - o); x = np.log1p(o / 2)
    for _ in range(30):
        f = 2 * x * np.exp(x) - o; x = x - f / (2 * np.exp(x) * (1 + x))
    return np.maximum(x, 0)


def km(d, e, T=5.0):
    """d durations (s), e event flags -> 1 - S(T), median."""
    o = np.lexsort((~e, d)); d, e = d[o], e[o]; S, n, med = 1.0, len(d), np.inf
    i = 0
    while i < len(d):
        j = i; ev = 0
        while j < len(d) and d[j] == d[i]: ev += e[j]; j += 1
        if d[i] > T: break
        S *= 1 - ev / n; n -= j - i; i = j
    return 1 - S


def km_med(d, e):
    o = np.lexsort((~e, d)); d, e = d[o], e[o]; S, n = 1.0, len(d)
    for k in range(len(d)):
        if e[k]: S *= 1 - 1 / n
        n -= 1
        if S <= 0.5: return d[k]
    return np.inf


def boot(eps, f, B=300):
    v = [f(eps)]; idx = np.arange(len(eps))
    for _ in range(B):
        v.append(f([eps[i] for i in RNG.choice(idx, len(idx))]))
    a = np.array(v[1:]); return v[0], np.nanpercentile(a, 2.5), np.nanpercentile(a, 97.5)


def episodes(R, ctx):
    o = np.lexsort((R["tick"], R["side"], R["rep"])); eps = []; cur = []
    def close():
        if cur: eps.append(np.array(cur))
    for k in range(len(o)):
        i = o[k]
        if ctx[i]:
            if cur:
                j = cur[-1]
                if R["rep"][j] != R["rep"][i] or R["side"][j] != R["side"][i] or R["tick"][i] - R["tick"][j] > 60 or R["gate"][j] == 1:
                    close(); cur = []
            cur.append(i)
        else:
            close(); cur = []
    close()
    return eps


def ep_times(ep, R, p, tau):
    t = (R["tick"][ep] - R["tick"][ep[0]]) / 20.0; end = t[-1]; pro_ev = bool(R["gate"][ep[-1]] == 1)
    hit = np.flatnonzero(p[ep] > tau[ep])
    thr = (t[hit[0]], True) if len(hit) else (end, False)
    lam = lam_of(p[ep])
    # hazard decoding: piecewise-constant rate lam_k on [t_k, t_{k+1}); draw the first play time
    u = -np.log(RNG.random()); cum = np.concatenate([[0], np.cumsum(lam[:-1] * np.diff(t))]) if len(t) > 1 else np.array([0.0])
    k = np.searchsorted(cum, u, side="right") - 1
    if k < len(t) - 1:
        haz = (t[k] + (u - cum[k]) / max(lam[k], 1e-9), True)
    else:
        haz = (end, False)
    both = min(thr, haz, key=lambda x: (x[0], not x[1])) if thr[1] or haz[1] else (end, False)
    return (end, pro_ev), thr, haz, both


def report(path):
    z = np.load(path); R = {k: z[k] for k in z.files}
    p = 1 / (1 + np.exp(-R["z"].astype(np.float64))); ph = np.where(R["tick"] >= 3600, 2, np.where(R["tick"] >= 2400, 1, 0))
    tau = TAU[ph]; print("==", path, str(R["ckpt"]))
    for split_name, sm in (("val", R["split"] == 1), ("all", np.ones(len(p), bool))):
        print(f"-- split {split_name}  rows {sm.sum()}  overall: pro play frac {R['gate'][sm].mean():.3f}  mean p {p[sm].mean():.3f}"
              f"  NLL {-np.mean(np.where(R['gate'][sm]==1, np.log(p[sm]), np.log(1-p[sm]))):.4f}"
              f"  acc@.5 {np.mean((p[sm]>.5)==(R['gate'][sm]==1)):.4f}")
        for key, base in (("enemy_empty", R["n_en"] == 0), ("any", np.ones(len(p), bool))):
            for E in (9, 7):
                for k, nm in enumerate(("1x", "2x", "OT")):
                    ctx = sm & base & (R["el"] >= E - 1e-3) & (R["tick"] >= 150) & (ph == k)
                    n = ctx.sum()
                    if n < 30: continue
                    f, mp = R["gate"][ctx].mean(), p[ctx].mean()
                    lam_pro = lam_of(np.array([f]))[0]; lam_mod = lam_of(p[ctx]).mean()
                    eps = episodes(R, ctx); T = [ep_times(e, R, p, tau) for e in eps]
                    def P5(col):
                        return lambda es: km(np.array([x[col][0] for x in es]), np.array([x[col][1] for x in es]))
                    pro5, thr5, haz5, both5 = (boot(T, P5(c)) for c in range(4))
                    med = [km_med(np.array([x[c][0] for x in T]), np.array([x[c][1] for x in T])) for c in range(4)]
                    print(f"{key:11s} E>={E} {nm} rows {n:6d} f {f:.3f} p {mp:.3f} p>tau {np.mean(p[ctx] > tau[ctx]):.3f}"
                          f" | lam pro {lam_pro:.3f}/s model {lam_mod:.3f}/s | eps {len(eps):5d} P5 pro {pro5[0]:.2f} [{pro5[1]:.2f},{pro5[2]:.2f}]"
                          f" thr {thr5[0]:.2f} [{thr5[1]:.2f},{thr5[2]:.2f}] haz {haz5[0]:.2f} [{haz5[1]:.2f},{haz5[2]:.2f}] thr+haz {both5[0]:.2f} [{both5[1]:.2f},{both5[2]:.2f}]"
                          f" | med s pro {med[0]:.1f} thr {med[1]:.1f} haz {med[2]:.1f} thr+haz {med[3]:.1f}")
        # reliability by p bin (all contexts)
        bins = np.array([0, .05, .1, .2, .3, .35, .45, .55, .7, .85, 1.0])
        b = np.digitize(p[sm], bins) - 1
        print("   reliability p-bin: " + "  ".join(f"[{bins[i]:.2f},{bins[i+1]:.2f}) n{(b==i).sum()} f{R['gate'][sm][b==i].mean():.3f}" for i in range(len(bins) - 1) if (b == i).sum()))


if __name__ == "__main__":
    for f in sys.argv[1:]:
        report(f)
