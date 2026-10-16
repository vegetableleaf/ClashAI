"""A3' (``reward_shaping.phi_trade2``, crown term included since 10-16) pre-flight, OFFLINE on recorded rows (no
engine, laptop minutes). The canonical audit (AUDIT_A3P.txt); it replaced preflight_a3p_crown.py, the variant's prototype.

A3' rows are rebuilt from rows the pod audits already recorded: trade2_record = tr_row + ts_row[:6] + [ts_row tick]
(tested in pipeline/tests/test_shaping_a3p.py), so every check below runs on the SAME matches A3 / A1 / A2 were audited
on. In these rows E_opp is the opponent's TRUE elixir (the scripted runner has no counter; measured counter error +0.3).

  python scratchpad/gauntlet/L74/reward/preflight_a3p.py [--audit DIR ...] [--rows ROWS.jsonl] [--set k=v ...]
     defaults: pod_backup_weekend/pod1015_s5/AUDIT_S5/{gen_v1_s0,newsim_r1}/matches.jsonl (7 policies x 100 seeds) and
               pod_backup_weekend/pod1015_s5/ROWS_R1/rows.jsonl (r1 il, 1000 matches: the TRADE2_B fit's own data)
  checks (verdict lines; exit 1 on any FAIL):
    0  harness: re-scores A3 (trade) and A1 (tower_score) on the same rows and must reproduce the pod audit.json paired t (|diff| < 1e-6)
    9.1 telescoping residual per match (gamma 1 and the gae arm's per-row gamma) < 1e-9
    9.2 bound: phi_bound <= 0.5; max |Phi| reached <= bound
    9.3 scripted audit (preflight_a1a2.py's rule): no degenerate policy with paired interior shaping credit t > 2 vs il
        while winning less (both checkpoints)
    i   per phase, corr(Phi, z) >= corr(tower margin, z): ROWS_R1 5-fold cross-fitted b (out of fold) + gen_v1 il
        (pinned b, another policy); 200 match-bootstrap CI of the difference
    ii  sign of dPhi on the standard trades (REWARD_ARCHITECTURE A3 Why / section 7 lesson 7 / the A3 failure diagnosis)
    iii return variance: lambda 1 return-to-go (the critic target) Var(shaped) <= Var(unshaped); lambda .95 (V = 0, the
        advantage the shaping adds) Var(shaping part) <= Var(terminal part)  [lesson 7: not louder than winning]
  w is a pure scale here: the clip acts on the log-odds BEFORE w, so every t / correlation / sign above is
  w-invariant; w only sets the magnitude (9.2, iii, swing).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(REPO), str(HERE)]
from pipeline import reward_shaping as RS                  # noqa: E402
from pipeline import rl_royale as RL                       # noqa: E402
import fit_rho                                             # noqa: E402
from preflight_a1a2 import GAMMA_TICK, INTERIOR_DROP, LAMS, lam_return   # noqa: E402

BK = Path.home() / "pod_backup_weekend/pod1015_s5"
AUDITS = [BK / "AUDIT_S5/gen_v1_s0", BK / "AUDIT_S5/newsim_r1"]
ROWS = BK / "ROWS_R1/rows.jsonl"
PHASES = ("1x", "2x", "OT")
MODES = ("trade2", "trade", "tower_score")                 # trade / tower_score: references (harness check, iii)


def t2rows(tr, ts):
    tr, ts = np.asarray(tr, float), np.asarray(ts, float)
    return np.c_[tr, ts[:, :6], ts[:, 10]]


def rows_of(m, mode):
    keep = np.asarray(m["keep"], bool)
    r = t2rows(m["tr_rows"], m["ts_rows"]) if mode == "trade2" else np.asarray(m[{"trade": "tr_rows",
                                                                                  "tower_score": "ts_rows"}[mode]], float)
    return r[keep], np.asarray(m["ticks"])[keep]


def load_audit(d):
    out = []
    for line in open(Path(d) / "matches.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r["kept_rows"]:
            out.append({k: r[k] for k in ("policy", "seed", "z", "keep", "ticks", "tr_rows", "ts_rows")})
    return out


def reduce(m, mode, p):
    """preflight_a1a2.reduce_mode for any RS.state_phi mode (rl_royale.shaping_rewards's arithmetic)."""
    rows, ticks = rows_of(m, mode)
    gam = RL.row_gammas(ticks, GAMMA_TICK)
    phi = RS.state_phi(mode, rows, p)
    F = np.asarray(RS.shaping_from_parts(phi.tolist(), [0.0] * len(phi), gam, (1.0, 0.0))["F"])
    F1 = np.asarray(RS.shaping_from_parts(phi.tolist(), [0.0] * len(phi), 1.0, (1.0, 0.0))["F"])
    T = len(rows)
    tele = max(abs(float((np.concatenate([[1.0], np.cumprod(gam[:-1])]) * F).sum() + phi[0])),
               abs(float(F1.sum() + phi[0])))
    term = np.zeros(T)
    term[-1] = m["z"]
    out = {"tele": tele, "max_abs_phi": float(np.abs(phi).max()), "phi": phi, "lam": {}}
    inner = slice(0, max(0, T - INTERIOR_DROP))
    for lam in LAMS:
        Gt, Gs = lam_return(term, gam * lam), lam_return(F, gam * lam)
        out["lam"][lam] = {"Gt": Gt, "Gs": Gs,
                           "shape_interior": float(Gs[inner].mean()) if T > INTERIOR_DROP else math.nan}
    return out


def scripted(ms, mode, p):
    """-> {policy: (n, z_mean, interior mean, paired t vs il)}, stop list, tele max, max |Phi|, reductions."""
    red = [(m, reduce(m, mode, p)) for m in ms]
    il = {m["seed"]: r for m, r in red if m["policy"] == "il"}
    il_z = np.mean([m["z"] for m, _ in red if m["policy"] == "il"])
    res, stop = {}, []
    for pol in dict.fromkeys(m["policy"] for m, _ in red):
        rs = [(m, r) for m, r in red if m["policy"] == pol]
        d = np.array([r["lam"][0.95]["shape_interior"] - il[m["seed"]]["lam"][0.95]["shape_interior"] for m, r in rs
                      if m["seed"] in il and not math.isnan(r["lam"][0.95]["shape_interior"])
                      and not math.isnan(il[m["seed"]]["lam"][0.95]["shape_interior"])])
        sd = float(d.std(ddof=1)) if d.size > 1 else 0.0
        t = float(d.mean() / (sd / math.sqrt(d.size))) if sd > 0 else None
        z = float(np.mean([m["z"] for m, _ in rs]))
        res[pol] = (len(rs), z, float(np.nanmean([r["lam"][0.95]["shape_interior"] for _, r in rs])), t, int(d.size))
        if pol != "il" and (t or 0) > 2 and z < il_z:
            stop.append(pol)
    return res, stop, max(r["tele"] for _, r in red), max(r["max_abs_phi"] for _, r in red), red


# ------------------------------------------------------------------------------------------------- check i
def corr_parts(x, y, mid):
    """Per-match sufficient sums of (x, y) for a pooled Pearson r that a match bootstrap can resample."""
    S = np.zeros((mid.max() + 1, 6))
    for j, v in enumerate((np.ones_like(x), x, y, x * x, y * y, x * y)):
        np.add.at(S[:, j], mid, v)
    return S


def pearson(S):
    n, sx, sy, sxx, syy, sxy = S.sum(axis=0)
    return (n * sxy - sx * sy) / math.sqrt((n * sxx - sx * sx) * (n * syy - sy * sy))


def corr_check(M, b_of, cap, rng, boot=200):
    """M = [(dE, dT, dC, phase, z, fold)] per decisive match; b_of(fold, phase) -> (b_e, b_t, b_c). Per phase: r(Phi, z),
    r(dT, z), their difference with a match-bootstrap 95% CI."""
    out = {}
    for ph in range(3):
        xs, ts, ys, ids = [], [], [], []
        for i, (dE, dT, dC, P, z, f) in enumerate(M):
            k = P == ph
            if not k.any():
                continue
            be, bt, bc = b_of(f, ph)
            xs.append(np.clip(be * dE[k] + bt * dT[k] + bc * dC[k], -cap, cap)); ts.append(dT[k])
            ys.append(np.full(k.sum(), z)); ids.append(np.full(k.sum(), i))
        x, t, y, mid = (np.concatenate(a) for a in (xs, ts, ys, ids))
        _, mid = np.unique(mid, return_inverse=True)
        Sp, St = corr_parts(x, y, mid), corr_parts(t, y, mid)
        rp, rt = pearson(Sp), pearson(St)
        bs = []
        for _ in range(boot):
            j = rng.integers(0, len(Sp), len(Sp))
            bs.append(pearson(Sp[j]) - pearson(St[j]))
        out[PHASES[ph]] = (rp, rt, rp - rt, *np.percentile(bs, [2.5, 97.5]), len(y))
    return out


def decisive(ms, fold_of=None):
    M = []
    for m in ms:
        if m["z"] == 0:
            continue
        rows, _ = rows_of(m, "trade2")
        dE, dT, dC, P = RS.trade2_parts(rows)
        M.append((dE, dT, dC, P, float(m["z"] > 0), fold_of(m) if fold_of else 0))
    return M


def crossfit(M, k=5):
    """b per (held-out fold, phase), fitted with fit_rho.logit on the other folds' rows."""
    B = {}
    for f in range(k):
        for ph in range(3):
            X = np.concatenate([np.c_[dE[P == ph], dT[P == ph], dC[P == ph]] for dE, dT, dC, P, z, g in M if g != f])
            y = np.concatenate([np.full((P == ph).sum(), z) for dE, dT, dC, P, z, g in M if g != f])
            B[f, ph] = tuple(fit_rho.logit(X, y)[1:])
    return B


# ------------------------------------------------------------------------------------------------- check ii
ROCKET_CT = 1232 * 0.23 / 3052   # level-11 Rocket 1232 dmg (stat sheet, NOT read from the SIM) x 23% crown-tower
#                                  damage (RoyaleSim data/derived/cards.json: crown_tower_damage_percent 23) / princess hp
HOG_HIT = 800 / 3052             # HANDOFF 10-15 05:45's example: a Hog that deals 800 hp before dying


def row(E=5, V=0, Eo=5, Vo=0, own=(1, 1, 1), foe=(1, 1, 1), tick=0):
    return [E, V, Eo, Vo, *own, *foe, tick]


# (name, before kwargs, after kwargs, expected sign of dPhi: +1 / -1 / 0). A destroyed princess in OT ends the match
# (sudden death; ROWS_R1 has no OT row with a crown margin): there the after-state is TERMINAL, the trainer sees
# r + gamma Phi(s') - Phi(s) = +1 + 0 - Phi(s), and that is what the OT column shows for the finisher.
TRADES = [
    ("neutral placement (4 elixir onto the board)", {}, {"E": 1, "V": 4}, 0),
    ("Log on nothing (-2, removes 0)", {}, {"E": 3}, -1),
    ("Fireball kills a 5-elixir Witch (4 for 5)", {"Vo": 5}, {"E": 1, "Vo": 0}, +1),
    ("8 elixir for 3 (C2: my 8 on board die killing their 3)", {"V": 8, "Vo": 3}, {"V": 0, "Vo": 0}, -1),
    ("4-elixir troop thrown at an undefended foe tower, dies dealing 0", {"V": 4}, {"V": 0}, -1),
    ("elixir leak at 10 (opponent gains 1 meanwhile)", {"E": 10}, {"E": 10, "Eo": 6}, -1),
    ("my TOWER kills their Hog after taking 800 (A3's hold_to_10 credit)", {"Vo": 4},
     {"Vo": 0, "own": (1, 1 - HOG_HIT, 1)}, -1),
    ("my Hog deals 800 then dies to their tower", {"V": 4}, {"V": 0, "foe": (1, 1 - HOG_HIT, 1)}, +1),
    (f"Rocket chip on a full princess (-6, {ROCKET_CT:.3f} tower)", {"E": 10}, {"E": 4, "foe": (1, 1 - ROCKET_CT, 1)}, -1),
    ("Rocket FINISHES a princess at 7% hp (a crown)", {"E": 10, "foe": (1, 0.07, 1)}, {"E": 4, "foe": (1, 0, 1)}, +1),
    ("hit the foe KING for 500 hp (doctrine: never the king; weight 0)", {},
     {"foe": (1 - 500 / 4824, 1, 1)}, 0),
    ("own king takes 500 hp", {}, {"own": (1 - 500 / 4824, 1, 1)}, -1),
]


def trades_check(p):
    out = []
    for name, a, b, want in TRADES:
        signs = []
        for tick in (1000, 3000, 4500):
            if tick >= RS.TRADE2_PHASE_TICKS[1] and "FINISHES" in name:
                d = 1.0 - float(RS.phi_trade2([row(**a, tick=tick)], p)[0])
            else:
                d = float(np.diff(RS.phi_trade2([row(**a, tick=tick), row(**b, tick=tick)], p))[0])
            signs.append(d)
        got = [int(np.sign(round(d, 12))) for d in signs]
        out.append((name, signs, want, all(g == want for g in got)))
    return out


# ------------------------------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--audit", action="append", help="AUDIT dir(s) with matches.jsonl + audit.json")
    ap.add_argument("--rows", default=str(ROWS))
    ap.add_argument("--set", action="append", help="key=value over STATE_PHI_DEFAULTS")
    a = ap.parse_args()
    p = dict(RS.STATE_PHI_DEFAULTS)
    for s in a.set or ():
        k, v = s.split("=", 1)
        p[k] = float(v)
    w, cap = float(p["shaping_t2_w"]), float(p["shaping_t2_cap"])
    fails, rng = [], np.random.default_rng(0)
    say = (lambda s: print(s, flush=True))
    say(f"A3' trade2: Phi = {w} x clip(b_e dE + b_t dT + b_c dC, +-{cap}); TRADE2_B {RS.TRADE2_B} at ticks {RS.TRADE2_PHASE_TICKS}")

    bound = RS.phi_bound("trade2", p)
    il_ms, var = {}, {mo: {lam: [[], []] for lam in LAMS} for mo in MODES}
    for d in a.audit or AUDITS:
        name = Path(d).name
        ms = load_audit(d)
        il_ms[name] = [m for m in ms if m["policy"] == "il"]
        ref = json.load(open(Path(d) / "audit.json", encoding="utf-8"))["modes"]
        for mode in MODES:
            res, stop, tele, mx, red = scripted(ms, mode, p)
            for m, r in red:
                if m["policy"] == "il":
                    for lam in LAMS:
                        var[mode][lam][0].append(r["lam"][lam]["Gt"]); var[mode][lam][1].append(r["lam"][lam]["Gs"])
            if mode != "trade2":                                   # check 0: our arithmetic = the pod audit's
                diff = max(abs((res[q][3] or 0) - (ref[mode]["per_policy"][q]["paired_interior_vs_il"]["t"] or 0))
                           for q in res)
                ok = diff < 1e-6
                say(f"[0] {name}: {mode} re-scored, max |t - pod audit.json t| = {diff:.1e} -> {'PASS' if ok else 'FAIL'}")
                fails += [] if ok else [f"0:{name}:{mode}"]
            tag = "" if mode == "trade2" else " (reference)"
            say(f"[9.3] {name} {mode}{tag}: " + "; ".join(
                f"{q} z {v[1]:+.2f} int {v[2]:+.5f} t {'n/a' if v[3] is None else f'{v[3]:+.2f}'}(n {v[4]})"
                for q, v in res.items()) + f" -> {'STOP ' + str(stop) if stop else 'PASS'}")
            if mode != "trade2":
                continue
            fails += [f"9.3:{name}:{q}" for q in stop]
            ok = tele < 1e-9
            say(f"[9.1] {name}: telescoping max residual {tele:.1e} (< 1e-9) -> {'PASS' if ok else 'FAIL'}")
            fails += [] if ok else [f"9.1:{name}"]
            ok = bound <= 0.5 and mx <= bound + 1e-12
            say(f"[9.2] {name}: max |Phi| {mx:.4f} <= bound {bound:.4f} <= 0.5 -> {'PASS' if ok else 'FAIL'}")
            fails += [] if ok else [f"9.2:{name}"]
            sw = [float(r["phi"].max() - r["phi"].min()) for m, r in red if m["policy"] == "il"]
            ma = [float(np.abs(r["phi"]).mean()) for m, r in red if m["policy"] == "il"]
            p0 = max(abs(float(r["phi"][0])) for m, r in red)
            say(f"[w] {name} il: per-match Phi swing (max - min) median {np.median(sw):.3f} p90 {np.percentile(sw, 90):.3f}"
                f" max {max(sw):.3f}; mean |Phi| {np.mean(ma):.4f}; max |Phi(s0)| {p0:.4f} (vs terminal +-1)")

    # i: correlation per phase
    R = [json.loads(line) for line in open(a.rows, encoding="utf-8")]
    R = [{"policy": r["policy"], "seed": r["seed"], "z": r["z"], "keep": r["keep"], "ticks": r["ticks"],
          "tr_rows": r["tr_rows"], "ts_rows": r["ts_rows"]} for r in R]
    M = decisive(R, fold_of=lambda m: m["seed"] % 5)
    B = crossfit(M)
    pinned = (lambda f, ph: RS.TRADE2_B[ph])
    for label, MM, bof in (("ROWS_R1 r1 il, 5-fold out-of-fold b", M, lambda f, ph: B[f, ph]),
                           ("ROWS_R1 r1 il, pinned b (in-sample)", M, pinned),
                           ("AUDIT_S5 gen_v1 il, pinned b (other policy)", decisive(il_ms.get("gen_v1_s0", [])), pinned)):
        if not MM:
            continue
        for ph, (rp, rt, dd, lo, hi, n) in corr_check(MM, bof, cap, rng).items():
            ok = dd >= 0
            say(f"[i] {label} {ph}: r(Phi, z) {rp:.4f} vs r(dT, z) {rt:.4f}: diff {dd:+.4f} [{lo:+.4f}, {hi:+.4f}] "
                f"rows {n} -> {'PASS' if ok else 'FAIL'}")
            fails += [] if ok else [f"i:{label}:{ph}"]
    say("[i] cross-fit b per fold (1x / 2x / OT): " + "; ".join(
        f"f{f} " + " ".join(f"{B[f, ph][0]:.3f}/{B[f, ph][1]:.2f}/{B[f, ph][2]:.2f}" for ph in range(3))
        for f in range(5)))

    # ii: trades
    for name, d, want, ok in trades_check(p):
        say(f"[ii] {name}: dPhi 1x {d[0]:+.4f} 2x {d[1]:+.4f} OT {d[2]:+.4f} (want {want:+d}) -> {'PASS' if ok else 'FAIL'}")
        fails += [] if ok else [f"ii:{name}"]
    for ph in range(3):
        be, bt, _ = RS.TRADE2_B[ph]
        say(f"[ii] {PHASES[ph]}: Rocket (6) breaks even at {6 * be / bt:.3f} princess tower = {6 * be / bt * 3052:.0f} hp "
            f"(level 11); 1 princess tower = {bt / be:.1f} elixir")

    # iii: variance (il rows of both checkpoints pooled)
    for mode in MODES:
        for lam in LAMS:
            Gt, Gs = (np.concatenate(x) for x in var[mode][lam])
            vt, vs, vsum = float(Gt.var()), float(Gs.var()), float((Gt + Gs).var())
            tag = "" if mode == "trade2" else " (reference)"
            if lam == 1.0:
                ok = vsum <= vt
                line = f"Var(shaped) {vsum:.4f} vs Var(unshaped) {vt:.4f} ratio {vsum / vt:.3f} (<= 1)"
            else:
                ok = vs <= vt
                line = f"Var(shaping part) {vs:.5f} vs Var(terminal part) {vt:.5f} ratio {vs / vt:.3f} (<= 1)"
            say(f"[iii] {mode}{tag} lambda {lam}: {line} rows {len(Gt)} -> {'PASS' if ok else 'FAIL'}")
            if mode == "trade2":
                fails += [] if ok else [f"iii:lam{lam}"]

    say(f"VERDICT {'PASS' if not fails else 'FAIL'} {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
