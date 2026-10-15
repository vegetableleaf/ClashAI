"""Step-3 pre-flight (REWARD_ARCHITECTURE.md section 9) for ``shaping: solvency`` (A2) and ``shaping: tower_score``
(A1 + A1b), the potentials in pipeline/reward_shaping.py, at the weights the arms pin (STATE_PHI_DEFAULTS, or --set).
10-15: + ``shaping: trade`` (A3, step 5). In the AUDIT its E_opp is the opponent's TRUE elixir standing in for the
public counter (the scripted runner has no counter; measured counter error +0.3); training reads the counter only.

  offline (laptop, seconds, no engine):
    python scratchpad/gauntlet/L74/reward/preflight_a1a2.py offline [--set shaping_solv_w=0.05 ...]
      9.2 bound: phi_bound per mode <= 0.5 x terminal, and the max |Phi| actually reached on an exhaustive tower grid
          (through tower_score_record on synthetic raw() states, both tower levels) / adversarial solvency rows;
          the shaping_critic_scale each needs (1 + bound; the arms keep 1.5).
      9.1 telescoping on synthetic rows through rl_royale.shaping_rewards: sum F = -Phi(s0) at gamma 1 and the
          per-row-gamma discounted sum = -Phi(s0).                                       exit 1 if either fails.
  audit (POD, SIM rollouts; L69/rshape/common.py's scripted runner, our side = --ckpt under the plain live rule vs
         frozen gen_v1 at tau .27 on census decks, every policy on the same seeds):
    PYTHONPATH=. python scratchpad/gauntlet/L74/reward/preflight_a1a2.py audit --out DIR --ckpt CKPT \
        --matches 100 --workers 13 [--policies il,never,...] [--threads 1]
      records BOTH modes' rows at every decision of ours (state_record's own code, one memory per match), on
      training's KEPT rows with the gae arm's discount (gamma_tick 0.99994 ** ticks between kept rows):
      9.1 telescoping residual per match (gamma 1 and discounted), 9.2 max / mean |Phi| on the IL matches,
      9.3 scripted audit: per policy, lambda-returns with V = 0 split into terminal / shaping parts (lambda 1 and
          0.95). The shaping part at lambda = gae_lambda is EXACTLY what the potential adds to every decision's
          advantage whatever the critic (A = GAE(r, Phi + s v) = GAE(r, s v) + GAE(F, 0)); its end-of-match rows carry
          -Phi(s_T) (Phi forced to 0), so the verdict uses the INTERIOR rows (all but the last 60 kept rows, ~3 GAE
          horizons). STOP (exit 2) if a degenerate policy gets more interior shaping credit than il (paired t > 2)
          while winning less (z mean below il's): the potential would credit, decision by decision, play that loses.
      Smoke (laptop, 1 match, < 2 min): audit --out <tmp> --matches 1 --policies il --threads 1
Policies: il, never, spend_immediately, hold_to_10 (new here), spam_one_card, never_buildings, never_spells.
Writes <out>/audit.json + <out>/matches.jsonl.
"""
from __future__ import annotations

import argparse
import itertools
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(REPO), str(REPO / "scratchpad/gauntlet/L69/rshape")]
from pipeline import reward_shaping as RS                  # noqa: E402
from pipeline import rl_royale as RL                       # noqa: E402

MODES = {"solvency": "solv_rows", "tower_score": "ts_rows", "trade": "tr_rows"}
POLICIES = ("il", "never", "spend_immediately", "hold_to_10", "spam_one_card", "never_buildings", "never_spells")
GAMMA_TICK, LAMS, INTERIOR_DROP = 0.99994, (1.0, 0.95), 60


def params(sets) -> dict:
    import yaml
    p = dict(RS.STATE_PHI_DEFAULTS)
    for s in sets or ():
        k, v = s.split("=", 1)
        if k not in p:
            raise SystemExit(f"unknown key {k}; keys {sorted(p)}")
        p[k] = yaml.safe_load(v)
    for m in MODES:                                         # rl_royale's own validation (scale 1.5 as the arms)
        RL.adv_cfg({"advantage": "gae", "critic_warmup_updates": 5, "shaping": m, "opp_elixir": "counter", **p})
    return p


# ------------------------------------------------------------------------------------------------------ offline
def offline(p: dict) -> int:
    ok = True
    g = (0.0, 0.01, 0.3, 0.7, 1.0)
    st_rows = []
    for level, (KG, PR) in ((11, (4824, 3052)), (15, (6408, 4424))):
        for own, foe, tick in itertools.product(itertools.product((0.01, 0.5, 1.0), g, g),
                                                itertools.product((0.01, 1.0), g, g), (0, 3000, 4800, 6000, 7000)):
            tw = [{"side": s, "type": typ, "hp": round(f * mx), "max_hp": mx, "destroyed": round(f * mx) <= 0}
                  for s, fr in ((0, own), (1, foe)) for typ, mx, f in zip(("king", "princess", "princess"), (KG, PR, PR), fr)]
            st_rows.append(RS.tower_score_record({"tick": tick, "episode": {"crown_towers": tw}}, 0))
    rng = np.random.default_rng(0)
    solv = np.concatenate([rng.uniform(0, 30, (20000, 4)), rng.uniform(0, 10, (20000, 1))], axis=1)
    solv = np.vstack([solv, [[40, 40, 0, 0, 0], [0, 0, 0, 0, 0]]])
    trade = np.vstack([rng.uniform(0, 30, (20000, 4)), [[10, 40, 0, 0], [0, 0, 10, 40]]])
    reach = {"tower_score": RS.phi_tower_score(st_rows, p), "solvency": RS.phi_solvency(solv, p),
             "trade": RS.phi_trade(trade, p)}
    print(f"[offline] weights {p}")
    for m, ph in reach.items():
        b = RS.phi_bound(m, p)
        good = b <= 0.5 + 1e-12 and float(np.abs(ph).max()) <= b + 1e-12
        ok &= good
        print(f"[offline] 9.2 {m:11s} bound |Phi| <= {b:.4f} (budget 0.5); reached {float(np.abs(ph).max()):.4f} on "
              f"{len(ph)} states (min {ph.min():+.4f} max {ph.max():+.4f}); critic scale needs >= {1 + b:.4f}"
              f" -> {'OK' if good else 'FAIL'}")
    for m, rows in (("solvency", solv[:300]), ("tower_score", np.asarray(st_rows[:300])), ("trade", trade[:300])):
        phi0 = float(RS.state_phi(m, rows[:1], p)[0])
        r1 = float(RL.shaping_rewards(rows, {"mode": m, "gamma": 1.0, "params": p})["F"].sum()) + phi0
        gam = rng.uniform(0.99, 1.0, len(rows))
        F = RL.shaping_rewards(rows, {"mode": m, "gamma": gam, "params": p})["F"]
        rd = float((np.concatenate([[1.0], np.cumprod(gam[:-1])]) * F).sum()) + phi0
        good = abs(r1) < 1e-9 and abs(rd) < 1e-9
        ok &= good
        print(f"[offline] 9.1 {m:11s} telescoping residual gamma 1 {r1:+.2e}, per-row gamma {rd:+.2e} "
              f"-> {'OK' if good else 'FAIL'}")
    print(f"[offline] {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


# ------------------------------------------------------------------------------------------------------ audit (SIM)
import common as C                                         # noqa: E402  L69 rshape: runner, play_all, cli
from pipeline import e1_eval as E                          # noqa: E402
from pipeline import search_s0 as S                        # noqa: E402


def snap(env):
    """Full raw() + the engine's crowns at each of our decisions (replaces common.snap: state_record needs bodies)."""
    st = env.core.state()
    return {**env.raw(), "crowns": [int(st.players[0].crowns), int(st.players[1].crowns)]}


class AuditRunner(C.ShapeRunner):
    """common.ShapeRunner + hold_to_10 + both modes' rows per decision (state_record, one memory per match)."""

    def decide(self, policy, s, p, enc, heads, hand):
        if policy != "hold_to_10":
            return super().decide(policy, s, p, enc, heads, hand)
        el, allowed, _ = s.pre(hand)
        if el < 10 or not allowed.any():
            return C.wait("hold")
        return {**S.shortlist(s.model, enc, heads, allowed, 1, 1)[0], "why": "hold_to_10"}

    def play_policy(self, policy, m):
        rec = super().play_policy(policy, m)
        L, mem = rec["learner_side"], {}
        rec["ticks"] = [int(x["tick"]) for x in rec["_states"]]
        rec["solv_rows"] = [RS.state_record("solvency", x, L, m.env, mem) for x in rec["_states"]]
        rec["ts_rows"] = [RS.state_record("tower_score", x, L, m.env, mem) for x in rec["_states"]]
        rec["tr_rows"] = []
        for x in rec["_states"]:                       # audit only: the true opp elixir stands in for the counter
            mem["opp_est"] = next(float(q["elixir_exact"]) for q in x["players"] if int(q["side"]) != int(L))
            rec["tr_rows"].append(RS.state_record("trade", x, L, m.env, mem))
        rec["unknown_card_bodies"] = sum(int(e["card_id"]) not in mem["cards"] for x in rec["_states"]
                                         for e in x.get("entities") or ())
        return rec


def init_worker(args):
    """common.init_worker with our side = $A1A2_CKPT (spawn children inherit the environment)."""
    import os
    import torch
    torch.set_num_threads(max(1, int(args["threads"])))
    from pipeline.rl_royale import league_decks
    from pipeline.royale_env import RoyaleSelfPlayEnv
    dev, cap = args["device"], int(args["tail_cap"])
    gen, gi = E.load_policy(REPO / os.environ["A1A2_CKPT"], dev)
    og, oi = E.load_policy(REPO / S.GEN_CKPT, dev)
    run = AuditRunner(gen, {"gen": (og, S.live_cfg(S.TAU_OPP, oi["grid"], dev))}, S.live_cfg(S.TAU_PLAIN, gi["grid"], dev),
                      lambda: RoyaleSelfPlayEnv(decision_ticks=10, tail_cap=cap))
    run.fixed_cell, run.spam_card = int(args["fixed_cell"]), str(args["spam_card"])
    C._W["runner"] = run
    C._W["census"] = league_decks(REPO / "scratchpad/gauntlet/L68/selfplay/loadable_decks.json")


C.snap, C.init_worker = snap, init_worker                   # module level: spawn workers re-import this file


def lam_return(r, g):
    G, out = 0.0, np.zeros(len(r))
    for t in range(len(r) - 1, -1, -1):
        G = r[t] + (g[t] * G if t + 1 < len(r) else 0.0)
        out[t] = G
    return out


def reduce_mode(rec, mode, p):
    keep = np.asarray(rec["keep"], bool)
    rows = np.asarray(rec[MODES[mode]], dtype=np.float64)[keep]
    if not len(rows):
        return None
    gam = RL.row_gammas(np.asarray(rec["ticks"])[keep], GAMMA_TICK)
    sh = RL.shaping_rewards(rows, {"mode": mode, "gamma": gam, "params": p})
    phi, F, T = sh["phi"], sh["F"], len(rows)
    tele_d = float((np.concatenate([[1.0], np.cumprod(gam[:-1])]) * F).sum() + phi[0])
    tele_1 = float(RL.shaping_rewards(rows, {"mode": mode, "gamma": 1.0, "params": p})["F"].sum() + phi[0])
    term = np.zeros(T)
    term[-1] = rec["z"]
    out = {"tele": max(abs(tele_d), abs(tele_1)), "max_abs_phi": float(np.abs(phi).max()),
           "mean_abs_phi": float(np.abs(phi).mean()), "nonzero_share": float((phi != 0).mean()), "lam": {}}
    inner = slice(0, max(0, T - INTERIOR_DROP))
    for lam in LAMS:
        Gt, Gs = lam_return(term, gam * lam), lam_return(F, gam * lam)
        out["lam"][lam] = {"term": float(Gt.mean()), "shape": float(Gs.mean()),
                           "shape_interior": float(Gs[inner].mean()) if T > INTERIOR_DROP else math.nan}
    return out


def audit(a, p) -> int:
    import os
    os.environ["A1A2_CKPT"] = a.ckpt
    pols = [x for x in a.policies.split(",") if x]
    if "il" not in pols or any(x not in POLICIES for x in pols):
        raise SystemExit(f"--policies must include il and be drawn from {POLICIES}")

    def reduce(rec):
        out = {"policy": rec["policy"], "seed": rec["seed"], "z": rec["z"], "kept": rec["kept_rows"],
               "plays": rec["plays_accepted"], "unknown": rec["unknown_card_bodies"],
               **{m: reduce_mode(rec, m, p) for m in MODES}}
        if a.dump_rows:                     # raw rows for fitting Phi weights offline (A3' tower exchange rate)
            out["rows"] = {"ticks": rec["ticks"], "keep": [bool(k) for k in rec["keep"]],
                           **{MODES[m]: np.asarray(rec[MODES[m]], dtype=float).round(4).tolist() for m in MODES}}
        return out

    played = [r for r in C.play_all(a, pols, reduce) if r["kept"]]
    if a.dump_rows:
        import json
        with open(a.out / "rows.jsonl", "w", encoding="utf-8") as fh:
            for r in played:
                fh.write(json.dumps({"policy": r["policy"], "seed": r["seed"], "z": r["z"], **r.pop("rows")}) + "\n")
    report = {"ckpt": a.ckpt, "weights": p, "gamma_tick": GAMMA_TICK, "interior_drop": INTERIOR_DROP,
              "unknown_card_bodies": sum(r["unknown"] for r in played), "modes": {}}
    stop = []
    il_z = C.mean(r["z"] for r in played if r["policy"] == "il")
    for m in MODES:
        rows = [r for r in played if r[m] is not None]
        il = {r["seed"]: r for r in rows if r["policy"] == "il"}
        mm = {"telescoping_max_residual": max(r[m]["tele"] for r in rows),
              "max_abs_phi_il": max((r[m]["max_abs_phi"] for r in rows if r["policy"] == "il"), default=None),
              "max_abs_phi_all": max(r[m]["max_abs_phi"] for r in rows), "bound": RS.phi_bound(m, p), "per_policy": {}}
        for pol in pols:
            rs = [r for r in rows if r["policy"] == pol]
            if not rs:
                continue
            q = {"matches": len(rs), "z_mean": C.mean(r["z"] for r in rs), "plays_mean": C.mean(r["plays"] for r in rs),
                 "mean_abs_phi": C.mean(r[m]["mean_abs_phi"] for r in rs),
                 "nonzero_share": C.mean(r[m]["nonzero_share"] for r in rs)}
            for lam in LAMS:
                q[f"lam{lam}"] = {k: C.mean(r[m]["lam"][lam][k] for r in rs) for k in ("term", "shape", "shape_interior")}
            d = np.array([r[m]["lam"][0.95]["shape_interior"] - il[r["seed"]][m]["lam"][0.95]["shape_interior"]
                          for r in rs if r["seed"] in il and not math.isnan(r[m]["lam"][0.95]["shape_interior"])
                          and not math.isnan(il[r["seed"]][m]["lam"][0.95]["shape_interior"])])
            sd = float(d.std(ddof=1)) if d.size > 1 else 0.0
            q["paired_interior_vs_il"] = {"n": int(d.size), "mean": float(d.mean()) if d.size else None,
                                          "t": float(d.mean() / (sd / math.sqrt(d.size))) if sd > 0 else None}
            if pol != "il" and (q["paired_interior_vs_il"]["t"] or 0) > 2 and q["z_mean"] < il_z:
                stop.append(f"{m}:{pol}")
            mm["per_policy"][pol] = q
            print(f"[audit] {m:11s} {pol:17s} n {q['matches']:3d} z {q['z_mean']:+.3f} plays {q['plays_mean']:.1f} "
                  f"|Phi| {q['mean_abs_phi']:.4f} nz {q['nonzero_share']:.2f} | lam .95 shape {q['lam0.95']['shape']:+.4f} "
                  f"interior {q['lam0.95']['shape_interior']:+.4f} (vs il t {q['paired_interior_vs_il']['t']}) | "
                  f"lam 1 term {q['lam1.0']['term']:+.3f} shape {q['lam1.0']['shape']:+.4f}", flush=True)
        print(f"[audit] {m}: telescoping max residual {mm['telescoping_max_residual']:.2e}; max |Phi| il "
              f"{mm['max_abs_phi_il']} all {mm['max_abs_phi_all']:.4f} (bound {mm['bound']:.4f})", flush=True)
        if mm["telescoping_max_residual"] > 1e-9 or mm["max_abs_phi_all"] > mm["bound"] + 1e-12:
            stop.append(f"{m}:identity")
        report["modes"][m] = mm
    report["verdict"] = "STOP: redesign" if stop else "pass"
    report["stop"] = stop
    print(f"[audit] verdict {report['verdict']} {stop}; unknown-card bodies {report['unknown_card_bodies']}", flush=True)
    C.write(a.out, "audit.json", report)
    return 2 if stop else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    off = sub.add_parser("offline")
    off.add_argument("--set", action="append", help="key=value over STATE_PHI_DEFAULTS")
    au = sub.add_parser("audit", parents=[C.cli(__doc__)], add_help=False)
    au.add_argument("--ckpt", default="icebow/data/pipeline/gen_v1_s0/gen_s0.pt", help="our side's policy (il)")
    au.add_argument("--policies", default=",".join(POLICIES))
    au.add_argument("--set", action="append")
    au.add_argument("--dump-rows", action="store_true", help="also write every match's raw rows to <out>/rows.jsonl")
    a = ap.parse_args()
    p = params(a.set)
    return offline(p) if a.cmd == "offline" else audit(a, p)


if __name__ == "__main__":
    raise SystemExit(main())
