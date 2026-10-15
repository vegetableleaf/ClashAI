"""Critic diagnostic (REWARD_ARCHITECTURE F2 acceptance check): how well does an RL checkpoint's value head V(s) = P(win) -
P(loss) predict the match outcome z (+1 win / -1 loss / 0 draw), split by opponent archetype and match phase?
Question: is the critic worse at judging beatdown matchups than the rest?  If not, a context-aware critic (F2/C2) is
unlikely to help.

How: N SIM matches are played through the TRAINER'S OWN rollout path (``Learner.rollout`` called on a duck-typed shim, so the
league sampler ``sample_matchups`` -> ``ActorPool.run('selfplay')`` -> ``actor_main`` -> ``e1_eval.run_selfplay_batch`` are the
code the run used; nothing is reimplemented) with the checkpoint as the learner, rows recorded (actor_cfg record=True, +
record_tick). Rows are collated by ``rl_royale.collate`` and scored by ``rl_royale.value_rows``.  Opponent mix = the
checkpoint's own end-of-run league state (ck['rl']['league']: snapshots + PFSP ratings + external exploiters) under the run
config's league keys.  Pure-numpy metrics at the top; ``--selftest`` checks them on synthetic numbers.

  python critic_diag.py --ckpt CKPT --config RUN.yaml --out OUT_DIR [--matches N] [--seed-start S] [--workers W] [--smoke]
         [--set key=value ...] [--allow-missing] [--device cpu|cuda] [--nboot 1000] | --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import types
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
for p in (REPO, REPO / "scratchpad" / "gauntlet" / "L74" / "weekend"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

PHASES = ("1x", "2x", "OT")                     # tick < 2400, 2400-3599, >= 3600
PHASE_EDGES = (2400, 3600)
EXTRA_BEATDOWN = {"threemusketeers"}


# ------------------------------------------------------------------------------------------------------
# metrics (pure numpy)
# ------------------------------------------------------------------------------------------------------
def auc(v, z) -> float:
    """P(V_win > V_loss) over decisive rows (z != 0), ties 0.5; nan when one class is missing."""
    v, z = np.asarray(v, float), np.asarray(z, float)
    k = z != 0
    v, y = v[k], z[k] > 0
    npos, nneg = int(y.sum()), int((~y).sum())
    if npos == 0 or nneg == 0:
        return float("nan")
    _, inv, cnt = np.unique(v, return_inverse=True, return_counts=True)
    ranks = (np.cumsum(cnt) - (cnt - 1) / 2.0)[inv]          # 1-based average ranks
    return float((ranks[y].sum() - npos * (npos + 1) / 2.0) / (npos * nneg))


def mse(v, z) -> float:
    return float(np.mean((np.asarray(v, float) - np.asarray(z, float)) ** 2)) if len(v) else float("nan")


def ev(v, z) -> float:
    """Explained variance 1 - Var(z - V) / Var(z); nan when z is constant."""
    v, z = np.asarray(v, float), np.asarray(z, float)
    vz = z.var() if len(z) else 0.0
    return float(1.0 - (z - v).var() / vz) if vz > 0 else float("nan")


def stats(v, z, m) -> dict:
    """One group's row: ``m`` = match id per row (matches = distinct ids; win rate over matches)."""
    v, z, m = np.asarray(v, float), np.asarray(z, float), np.asarray(m)
    if len(v) == 0:
        return {"matches": 0, "rows": 0}
    um, first = np.unique(m, return_index=True)
    return {"matches": int(len(um)), "rows": int(len(v)), "win_rate": float(np.mean(z[first] > 0)),
            "mean_V": float(v.mean()), "mean_z": float(z.mean()), "calib_gap": float(v.mean() - z.mean()),
            "mse": mse(v, z), "ev": ev(v, z), "auc": auc(v, z)}


def phase_of(tick) -> np.ndarray:
    return np.searchsorted(np.asarray(PHASE_EDGES), np.asarray(tick), side="right")     # 0=1x 1=2x 2=OT


def boot_diff(v, z, m, flag, nboot: int, seed: int = 0) -> dict:
    """Match-clustered bootstrap (resample matches with replacement) of (flag - rest) in AUC and MSE; 95% percentile CI."""
    v, z, m, flag = (np.asarray(x) for x in (v, z, m, flag))
    um = np.unique(m)
    rows = {int(k): np.flatnonzero(m == k) for k in um}
    rng = np.random.default_rng(seed)

    def diff(idx):
        a, b = idx[flag[idx]], idx[~flag[idx]]
        return auc(v[a], z[a]) - auc(v[b], z[b]), mse(v[a], z[a]) - mse(v[b], z[b])
    full = np.arange(len(v))
    d_auc, d_mse = diff(full)
    ba, bm = [], []
    for _ in range(nboot):
        idx = np.concatenate([rows[int(k)] for k in rng.choice(um, size=len(um))])
        a, b = diff(idx)
        ba.append(a), bm.append(b)
    ci = (lambda x: [float(np.nanpercentile(x, 2.5)), float(np.nanpercentile(x, 97.5))] if np.isfinite(x).any() else [None, None])
    ba, bm = np.asarray(ba), np.asarray(bm)
    return {"auc_diff": float(d_auc), "auc_ci": ci(ba), "mse_diff": float(d_mse), "mse_ci": ci(bm), "nboot": nboot}


def analyse(V, z, tick, match, beat, arch, arch_names, nboot: int) -> dict:
    """V, z, tick, match, beat (bool), arch (int ids into arch_names): every row-level array of equal length."""
    V, z, tick, match, beat, arch = (np.asarray(x) for x in (V, z, tick, match, beat, arch))
    ph = phase_of(tick)
    S = lambda k: stats(V[k], z[k], match[k])
    out = {"overall": S(np.ones(len(V), bool)), "beatdown": S(beat), "rest": S(~beat),
           "phase": {PHASES[i]: S(ph == i) for i in range(3)},
           "archetype": {n: S(arch == i) for i, n in enumerate(arch_names)},
           "beatdown_x_phase": {f"{g}/{PHASES[i]}": S((beat == (g == "beatdown")) & (ph == i))
                                for g in ("beatdown", "rest") for i in range(3)}}
    out["boot"] = {"all": boot_diff(V, z, match, beat, nboot)}
    for i in range(3):
        k = ph == i
        out["boot"][PHASES[i]] = (boot_diff(V[k], z[k], match[k], beat[k], nboot) if k.any() and beat[k].any() and (~beat[k]).any()
                                  else None)
    return out


def verdict(res: dict) -> str:
    b, r, bo = res["beatdown"], res["rest"], res["boot"]["all"]
    if not b.get("rows") or not r.get("rows"):
        return "ANSWER: undetermined -- one of beatdown / rest has no rows."
    f = lambda x: "nan" if x is None or not np.isfinite(x) else f"{x:+.3f}"
    ci = lambda c: f"[{f(c[0])}, {f(c[1])}]"
    worse_auc = bo["auc_ci"][1] is not None and bo["auc_ci"][1] < 0
    worse_mse = bo["mse_ci"][0] is not None and bo["mse_ci"][0] > 0
    better = (bo["auc_ci"][0] is not None and bo["auc_ci"][0] > 0) or (bo["mse_ci"][1] is not None and bo["mse_ci"][1] < 0)
    call = ("YES, critic is worse on beatdown (CI excludes 0 on " + " and ".join(
        n for n, w in (("AUC", worse_auc), ("MSE", worse_mse)) if w) + ")" if (worse_auc or worse_mse) else
            "NO reliable difference (both CIs include 0): F2/C2 context-aware critic unlikely to help" if not better else
            "NO, critic is BETTER on beatdown (CI excludes 0 in the favourable direction)")
    return (f"ANSWER: beatdown ({b['matches']} matches, {b['rows']} rows) vs rest ({r['matches']}, {r['rows']}): AUC {f(b['auc'])[1:]}"
            f" vs {f(r['auc'])[1:]} (diff {f(bo['auc_diff'])}, 95% CI {ci(bo['auc_ci'])}); MSE {b['mse']:.3f} vs {r['mse']:.3f} "
            f"(diff {f(bo['mse_diff'])}, CI {ci(bo['mse_ci'])}); EV {f(b['ev'])} vs {f(r['ev'])}; calib gap {f(b['calib_gap'])} vs "
            f"{f(r['calib_gap'])} -> {call}.")


def table(res: dict) -> str:
    hdr = f"{'group':<26}{'matches':>8}{'rows':>8}{'win%':>7}{'meanV':>8}{'meanZ':>8}{'gap':>8}{'MSE':>8}{'EV':>8}{'AUC':>8}"
    n = lambda x, w, d=3: f"{x:>{w}.{d}f}" if x is not None and np.isfinite(x) else f"{'nan':>{w}}"

    def row(name, s):
        if not s.get("rows"):
            return f"{name:<26}{0:>8}{0:>8}"
        return (f"{name:<26}{s['matches']:>8}{s['rows']:>8}{100 * s['win_rate']:>7.1f}{n(s['mean_V'], 8)}{n(s['mean_z'], 8)}"
                f"{n(s['calib_gap'], 8)}{n(s['mse'], 8)}{n(s['ev'], 8)}{n(s['auc'], 8)}")
    L = [hdr, row("ALL", res["overall"]), "", row("beatdown", res["beatdown"]), row("rest", res["rest"]), ""]
    L += [row("phase " + k, s) for k, s in res["phase"].items()] + [""]
    L += [row(k, s) for k, s in res["beatdown_x_phase"].items()] + [""]
    L += [row("arch " + k, s) for k, s in res["archetype"].items()] + ["", "bootstrap (match-clustered, beatdown - rest, 95% pct CI):"]
    fs = lambda x: f"{x:+.3f}" if x is not None and np.isfinite(x) else "  nan"
    for k, b in res["boot"].items():
        if b:
            L.append(f"  {k:<4} AUC diff {fs(b['auc_diff'])} [{fs(b['auc_ci'][0])}, {fs(b['auc_ci'][1])}]   "
                     f"MSE diff {fs(b['mse_diff'])} [{fs(b['mse_ci'][0])}, {fs(b['mse_ci'][1])}]   (nboot {b['nboot']})")
        else:
            L.append(f"  {k:<4} n/a (a side has no rows)")
    return "\n".join(L)


def selftest() -> None:
    z = np.array([1, 1, -1, -1, 1, -1.0])
    assert auc(z, z) == 1.0 and auc(-z, z) == 0.0 and auc(np.zeros(6), z) == 0.5
    assert auc([0.2, 0.9, 0.2, 0.5], [1, 1, -1, -1]) == 0.625 and np.isnan(auc([1, 2], [1, 1]))
    assert auc([0.1, 0.9, 5.0], [1, -1, 0]) == 0.0                                         # draws are excluded
    assert ev(z, z) == 1.0 and ev(np.zeros(6), z) <= 1e-12 and mse(z, z) == 0.0 and np.isnan(ev(z, np.ones(6)))
    assert abs(mse(np.zeros(6), z) - 1.0) < 1e-12
    assert list(phase_of([0, 2399, 2400, 3599, 3600, 9999])) == [0, 0, 1, 1, 2, 2]
    rng = np.random.default_rng(1)                      # 400 matches x 5 rows; rest = informative critic, beatdown = pure noise
    n = 400
    zm = rng.choice([1.0, -1.0], n)
    bm = rng.random(n) < 0.3
    vals = np.where(bm[:, None], rng.uniform(-1, 1, (n, 5)), np.clip(zm[:, None] * 0.6 + rng.normal(0, 0.3, (n, 5)), -1, 1))
    m = np.repeat(np.arange(n), 5)
    V, zz, bd = vals.ravel(), np.repeat(zm, 5), np.repeat(bm, 5)
    tick = np.tile([100, 1000, 2500, 3000, 4000], n)
    res = analyse(V, zz, tick, m, bd, np.where(bd, 1, 0), ("other", "golem"), 200)
    b = res["boot"]["all"]
    assert b["auc_diff"] < -0.2 and b["auc_ci"][1] < 0 and b["mse_ci"][0] > 0, b
    assert res["overall"]["rows"] == 2000 and res["phase"]["1x"]["rows"] == 800 and res["phase"]["OT"]["rows"] == 400
    assert res["beatdown"]["matches"] + res["rest"]["matches"] == n
    same = analyse(*(lambda Vq: (Vq, zz, tick, m, bd, np.zeros(len(V), int), ("other",), 200))(np.clip(zz * 0.6 + rng.normal(0, 0.3, len(V)), -1, 1)))
    assert same["boot"]["all"]["auc_ci"][0] < 0 < same["boot"]["all"]["auc_ci"][1], same["boot"]["all"]    # no true difference -> CI covers 0
    assert "NO reliable difference" in verdict(same) and "YES" in verdict(res)
    print("selftest OK")


# ------------------------------------------------------------------------------------------------------
# the run
# ------------------------------------------------------------------------------------------------------
class _Log:
    def __call__(self, msg):
        print(msg, flush=True)

    def json(self, rec):
        pass


def run(a) -> int:
    import torch
    from pipeline import rl_royale as R
    from pipeline import adaptive_opponents as AO
    from pipeline.eval_gen import load_model
    from pipeline.royale_runtime import activate
    import archetypes as AR

    t0 = time.time()
    ckpt, out_dir = Path(a.ckpt).resolve(), Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    runtime = activate()
    cfg = R.load_config(Path(a.config), a.set, False)
    N = 2 if a.smoke else int(a.matches)
    workers = 1 if a.smoke else int(a.workers)
    ck = torch.load(ckpt, map_location="cpu")
    if not ck.get("gen") or "rl" not in ck:
        raise SystemExit(f"{ckpt} is not a generalist RL checkpoint (needs 'gen' and 'rl')")
    ck_cfg = ck["rl"]["config"]
    cfg_diff = {k: (ck_cfg.get(k), v) for k, v in cfg.items() if k in ck_cfg and ck_cfg[k] != v and k not in
                ("init", "league_decks", "league_external", "n_actors", "max_updates")}
    ck_update = int(ck["rl"]["update"])
    # the checkpoint's own league state: snapshots + PFSP ratings (+ external exploiters), the opponent pool training sampled from
    league = json.loads(json.dumps(ck["rl"].get("league") or {"snapshots": []}))
    missing = []
    exists = lambda pth: (R.REPO / pth).exists()
    if not exists(cfg["init"]):
        missing.append(("init", cfg["init"]))
    if not exists(cfg["league_decks"]):
        missing.append(("league_decks", cfg["league_decks"]))
    if cfg.get("league_mix", {}).get("s1", 0) > 0 and not exists(cfg["league_specialist"]):
        missing.append(("league_specialist", cfg["league_specialist"]))
    for kind, lst in (("snapshot", [s["path"] for s in league["snapshots"]]), ("external", list(cfg.get("league_external") or []))):
        missing += [(kind, pth) for pth in lst if not exists(pth)]
    hard = [x for x in missing if x[0] in ("init", "league_decks", "league_specialist")]
    if hard:
        raise SystemExit(f"required files missing (fix the paths with --set key=value): {hard}")
    if missing:
        if not a.allow_missing:
            raise SystemExit(f"opponent files missing (the training mix cannot be reproduced; --allow-missing drops them): {missing}")
        league["snapshots"] = [s for s in league["snapshots"] if exists(s["path"])]
        cfg["league_external"] = [p for p in cfg.get("league_external") or [] if exists(p)]
        league["external"] = [p for p in league.get("external", []) if exists(p)]
        print(f"[critic_diag] --allow-missing dropped {len(missing)} opponent file(s): {missing}", flush=True)
    AO.sync_pool(league, cfg)
    pool_ids = [o["id"] for o in AO.opponent_pool(league["snapshots"], cfg, league)]

    cfg.update({"E": N, "G": 1, "n_actors": workers, "gae_gamma_unit": "tick",      # tick: actor_cfg record_tick (each row's tick)
                "seed": int(a.seed_start)})                                         # only feeds the (unused, frac 0) pipelining draw
    dev = torch.device(a.device)
    model = load_model(ckpt, dev)[0].eval()
    args = ck["args"]
    gen = {"d_c": int(ck["d_c"]), "card_vocab": list(ck["card_vocab"])}
    if int(args.get("feature_version", 1)) >= 3:
        gen["feature_version"] = int(args["feature_version"])
    shim = types.SimpleNamespace(cfg=cfg, init_meta={"args": dict(args)}, grid=str(args.get("grid", "lattice")), gen=gen,
                                 runtime=runtime, model=model, log=_Log(), league=league,
                                 rng=np.random.default_rng(int(a.seed_start)))
    shim.census = R.league_decks(R.REPO / cfg["league_decks"])
    shim.census_p = R.deck_weights([d["sides"] for d in shim.census], cfg["league_deck_alpha"], cfg["league_deck_floor"])
    base = R.Learner.actor_base(shim)                                              # rl_royale.py:2870 (the actors' exact base dict)
    pool = R.ActorPool(base, workers, shim.log, float(cfg["actor_timeout_s"]))      # :1787
    shim.actors = pool
    try:
        results, info = R.Learner.rollout(shim, int(a.seed_start))                  # :2562 league branch: sample_matchups -> actors.run
    finally:
        pool.close()
    t_play = time.time() - t0
    print(f"[critic_diag] played {len(results)} matches in {t_play:.0f}s", flush=True)

    # rows -> B (collate, :1149) -> V (value_rows, :1389)
    B, cst = R.collate(results, float(cfg["adv_clip"]))
    keep = [(r["traj"]["gate_sampled"] | r["traj"]["played"]) if len(r["traj"]["played"]) else np.zeros(0, bool) for r in results]
    use = [j for j, k in enumerate(keep) if k.sum()]
    tick = np.concatenate([results[j]["traj"]["tick"][keep[j]] for j in use])
    match = np.concatenate([np.full(int(keep[j].sum()), j) for j in use])
    assert len(tick) == len(B["A"]) and np.array_equal(match, B["match"]), "row order differs from collate"
    V = R.value_rows(model, R.to_device(B, dev)).double().cpu().numpy()
    assert V.shape == tick.shape and np.isfinite(V).all() and np.abs(V).max() <= 1 + 1e-6, (V.shape, float(np.abs(V).max()))

    zs = np.array([R.reward(r["outcome"]) for r in results])
    decks = [[AR.canon(c) for c in r["league"]["opp_deck"]] for r in results]
    beat_m = np.array([bool(set(d) & (AR.TANK | EXTRA_BEATDOWN)) for d in decks])
    arch_names = tuple(AR.ORDER) + ("other",)
    arch_m = np.array([arch_names.index(AR.classify(d)) for d in decks])
    z, beat, arch = zs[match], beat_m[match], arch_m[match]
    res = analyse(V, z, tick, match, beat, arch, arch_names, int(a.nboot))

    opp_n = {}
    for r in results:
        o = r["league"]["opp"]["id"]
        opp_n[o] = opp_n.get(o, 0) + 1
    setup = {
        "ckpt": str(ckpt), "ckpt_update": ck_update, "config": str(a.config), "set": a.set, "smoke": bool(a.smoke), "matches": len(results),
        "matches_with_rows": len(use), "rows": int(len(V)), "seed_start": int(a.seed_start), "workers": workers, "device": a.device,
        "runtime": runtime, "wall_s": round(time.time() - t0, 1),
        "sampler": {k: cfg.get(k) for k in ("T", "tau", "T_gate", "afford_mask", "stall_elixir", "decide_every", "obs", "noise_off",
                                            "opp_elixir", "action_delay_ticks", "extrapolate_ticks", "hero_abilities",
                                            "ability_policy", "forms_mode")},
        "opponents": {"league_pfsp": cfg.get("league_pfsp"), "league_mix": cfg.get("league_mix"), "league_opp_policy": cfg.get("league_opp_policy"),
                      "league_opp_T_effective": R.opp_T(cfg), "opp_style": cfg.get("opp_style"), "league_icebow_share": cfg.get("league_icebow_share"),
                      "league_learner_icebow_share": cfg.get("league_learner_icebow_share"), "league_decks": cfg["league_decks"],
                      "pool_ids": pool_ids, "ratings": league.get("ratings"), "matches_per_opponent": opp_n,
                      "dropped_missing": missing},
        "config_vs_checkpoint_config_diff": cfg_diff,
        "collate": cst,
        "draws": int((zs == 0).sum()), "wins": int((zs > 0).sum()), "losses": int((zs < 0).sum()),
    }
    full = {"setup": setup, "results": res, "verdict": verdict(res)}
    clean = lambda o: (None if isinstance(o, float) and not np.isfinite(o) else {k: clean(v) for k, v in o.items()} if isinstance(o, dict)
                       else [clean(v) for v in o] if isinstance(o, (list, tuple)) else o)       # NaN -> null (strict JSON)
    (out_dir / "critic_diag.json").write_text(json.dumps(clean(full), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)),
                                              encoding="utf-8")
    np.savez_compressed(out_dir / "critic_diag_rows.npz", match=match, tick=tick, V=V, z=z, beatdown=beat, archetype=arch,
                        arch_names=np.array(arch_names), m_outcome=zs, m_beatdown=beat_m, m_archetype=arch_m,
                        m_opp=np.array([r["league"]["opp"]["id"] for r in results]),
                        m_opp_deck=np.array([",".join(d) for d in decks]),
                        m_learner_side=np.array([r["league"]["learner_side"] for r in results]),
                        m_end_tick=np.array([r.get("end_tick", -1) for r in results]))
    sm = setup["sampler"]
    head = [f"critic_diag: {ckpt.name} (ckpt update {ck_update}); {len(results)} SIM matches, {len(V)} rows, {setup['wins']}W/"
            f"{setup['losses']}L/{setup['draws']}D, seeds from {a.seed_start}, {workers} worker(s), {setup['wall_s']}s",
            f"sampler (learner): policy=sample T={sm['T']} tau={sm['tau']} T_gate={sm['T_gate']} afford_mask={sm['afford_mask']} "
            f"decide_every={sm['decide_every']} obs={sm['obs']} noise_off={sm['noise_off']} opp_elixir={sm['opp_elixir']} "
            f"delay={sm['action_delay_ticks']} extrapolate={sm['extrapolate_ticks']}",
            f"opponents: league_pfsp={cfg.get('league_pfsp')} pool={pool_ids} drawn={opp_n} opp policy={cfg.get('league_opp_policy')} "
            f"T={R.opp_T(cfg)}; learner deck share icebow={cfg.get('league_learner_icebow_share')}; opp decks from {cfg['league_decks']} "
            f"(icebow share {cfg.get('league_icebow_share')})" + (f"; DROPPED missing: {[m[1] for m in missing]}" if missing else ""),
            "V = P(win) - P(loss) in [-1,1]; z = +1/-1/0; rows = gate-sampled or played decisions (what PPO trains on); gap = meanV - meanZ; "
            "AUC on decisive matches, rows weighted equally; beatdown = opp deck has a TANK card or threemusketeers", ""]
    (out_dir / "critic_diag.txt").write_text("\n".join(head) + table(res) + "\n\n" + full["verdict"] + "\n", encoding="utf-8")
    print((out_dir / "critic_diag.txt").read_text(encoding="utf-8"))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--ckpt")
    ap.add_argument("--config")
    ap.add_argument("--out")
    ap.add_argument("--matches", type=int, default=1000)
    ap.add_argument("--seed-start", type=int, default=745000, help="league rng seed AND the 'update' index (tags / obs seeds); pick unused")
    ap.add_argument("--workers", type=int, default=25)
    ap.add_argument("--smoke", action="store_true", help="2 matches, 1 worker")
    ap.add_argument("--set", action="append", default=[], metavar="key=value", help="config override (rl_royale.load_config)")
    ap.add_argument("--allow-missing", action="store_true", help="drop opponent snapshot/external files that do not exist (local runs)")
    ap.add_argument("--device", default="cpu", help="device for V(s) (actors use the config's actor_device)")
    ap.add_argument("--nboot", type=int, default=1000)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        selftest()
        return 0
    if not (a.ckpt and a.config and a.out):
        ap.error("--ckpt, --config, --out are required")
    return run(a)


if __name__ == "__main__":
    raise SystemExit(main())
