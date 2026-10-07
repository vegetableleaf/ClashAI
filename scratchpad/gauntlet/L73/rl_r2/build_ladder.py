"""R2 (B): ladder-matched opponent deck file + its check through the REAL rl_royale sampling path.

  sim research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L73/rl_r2/build_ladder.py

1. classify every census deck (full deck, @form suffix stripped) with live_eval.classify / traits (imported, not copied)
2. target per primary class = live R1e class share; X-Bow/Mortar pinned to its live share INCLUDING the icebow mirror;
   classes whose live 95% CI upper bound < the overall live rate x1.5; renormalised over classes the census has
3. within a class: proportional to census sides ** 0.5; written as integer `sides` so deck_weights(alpha 1, floor 0)
   reproduces the target exactly (rl_royale.league_decks casts sides to int)
4. 20,000 matchups through rl_royale.sample_matchups with the R2 league config -> realized opponent class / trait mix
Writes loadable_decks_ladder.json and ladder_check.json next to this file.
"""
import os, sys, json, collections
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import numpy as np

REPO = "C:/Users/benpe/ClashBot/"
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
sys.path.insert(0, REPO + "scratchpad/gauntlet/L73/live_eval")
from live_eval import classify, traits                     # the live class rules, imported
from pipeline import rl_royale as RL

CENSUS = REPO + "scratchpad/gauntlet/L70/pool_forms/loadable_decks.json"
LIVE = REPO + "scratchpad/gauntlet/L73/live_eval/results_R1e.json"
OUT = HERE + "loadable_decks_ladder.json"
SCALE = 10_000_000          # integer sides resolution (target share 1e-7)
MULT = 1.5
XBOW = "X-Bow/Mortar"
R2 = {"league_icebow_share": 0.02, "league_learner_icebow_share": 1.0,
      "league_mix": {"latest": 0.35, "older": 0.25, "init": 0.2, "s1": 0.02},
      "league_deck_alpha": 1.0, "league_deck_floor": 0.0, "init": "INIT", "league_specialist": "S1"}
TRAITS = ("has Witch/Night Witch", "heavy tank", "MegaKnight card")


def base(cards): return {c.split("@")[0] for c in cards}
def cls(cards): return classify(base(cards))
def trs(cards):
    b = base(cards); t = traits(b); t["MegaKnight card"] = "MegaKnight" in b
    return t


def mix(decks_engine):
    n = len(decks_engine)
    c = collections.Counter(cls(e) for e in decks_engine)
    t = {k: sum(trs(e)[k] for e in decks_engine) / n for k in TRAITS}
    return {k: v / n for k, v in c.items()}, t


def simulate(census, p, n_snaps, n=20000, seed=0):
    snaps = [{"id": f"s{i}", "path": f"S{i}"} for i in range(n_snaps)]
    ms = RL.sample_matchups(np.random.default_rng(seed), n, 0, snaps, R2, census, p)
    opp = [m["opp_deck"] for m in ms]
    cm, tm = mix(opp)
    return {"n": n, "n_snapshots": n_snaps, "class": cm, "traits": tm,
            "icebow_mirror": sum(m["opp_deck_name"] == "icebow" for m in ms) / n,
            "opp_s1": sum(m["opp"]["type"] == "s1" for m in ms) / n,
            "learner_icebow": sum(m["learner_deck_name"] == "icebow" for m in ms) / n}


def tilt(p): return MULT * p / (MULT * p + 1 - p)          # x1.5 on the share, renormalised against the rest


def trait_targets(live, n_live, ov):
    """Opponent-level trait targets. Witch: the class weak rule (live win-rate CI upper < overall) -> x1.5. MK card: same
    rule on its Wilson CI. heavy tank: the lead fixed it at the live share (the rule alone would tilt it too: CI hi .48)."""
    from live_eval import wilson
    wt, mk = live["traits"]["has Witch/Night Witch"], live["cards"]["MegaKnight"]
    ht = live["traits"]["heavy tank"]
    mk_ci = wilson(round(mk["wr_present"] * mk["n_present"]), mk["n_present"])
    share = {"has Witch/Night Witch": wt["n"] / n_live, "heavy tank": ht["n"] / n_live, "MegaKnight card": mk["n_present"] / n_live}
    rule = {"has Witch/Night Witch": wt["ci"][1] < ov, "MegaKnight card": mk_ci[1] < ov, "heavy tank": False}
    tgt = {k: (tilt(v) if rule[k] else v) for k, v in share.items()}
    info = {"live_ci_hi": {"has Witch/Night Witch": wt["ci"][1], "heavy tank": ht["ci"][1], "MegaKnight card": mk_ci[1]},
            "tilted": rule, "heavy_tank_rule_would_tilt_to": tilt(share["heavy tank"]) if ht["ci"][1] < ov else None}
    return share, tgt, info


def fit(wi, ci, T):
    """Scale wi by one factor f, each capped at ci, so the group sums to T (exact, sorted breakpoints)."""
    if T <= 0: return np.zeros_like(wi)
    if ci.sum() <= T: return ci.copy()
    r = ci / wi; o = np.argsort(r); rs, ws, cs = r[o], wi[o], ci[o]
    capsum = np.concatenate([[0.0], np.cumsum(cs)])[:-1]           # capped mass of the first k (sorted) decks
    rest = np.cumsum(ws[::-1])[::-1]                                # uncapped weight from k on
    f = (T - capsum) / rest
    ok = (f <= rs) & np.concatenate([[True], f[1:] >= rs[:-1]])
    return np.minimum(f[np.argmax(ok)] * wi, ci)


def rake(W0, C, ctarget, TR, want, iters=3000, tol=1e-6):
    """Capped IPF over the class partition + each binary trait (yes / no). -> (weights, converged, max margin error)."""
    w, cap = W0.copy(), 3.0 * W0
    groups = [(C == k, v) for k, v in ctarget.items() if (C == k).any()]
    for k, v in want.items(): groups += [(TR[k], v), (~TR[k], 1.0 - v)]
    for it in range(iters):
        for m, T in groups: w[m] = fit(w[m], cap[m], T)
        err = max(abs(w[m].sum() - T) for m, T in groups)
        if err < tol: return w, True, err
    return w, False, err


def rake_feasible(W0, C, ctarget, TR, want, mk_floor):
    """Full targets if feasible; else the priority order below (bisection, 16 steps each). A first version moved all three
    traits together (one lambda): Witch 25.3% / MK card 10.1% / heavy 49.6% of opponent games -- the alternative point."""
    cur = {k: float(W0[TR[k]].sum()) for k in want}
    w, ok, err = rake(W0, C, ctarget, TR, want)
    info = {"stage1_census": cur, "want_census": want, "mode": "full"}
    if not ok:
        # priority: heavy tank exact; Witch as high as feasible with MK card at its LIVE share (floor); then MK card as
        # high as feasible (up to its tilted target) with Witch held there
        def best(make):
            lo, hi, bw = 0.0, 1.0, None
            for _ in range(16):
                mid = (lo + hi) / 2; ww, k_ok, _e = rake(W0, C, ctarget, TR, make(mid))
                if k_ok: lo, bw = mid, ww
                else: hi = mid
            return lo, bw
        Wt, M = "has Witch/Night Witch", "MegaKnight card"
        lam_w, bw = best(lambda x: {**want, M: mk_floor, Wt: cur[Wt] + x * (want[Wt] - cur[Wt])})
        if bw is None: raise SystemExit("raking infeasible: heavy tank exact + MK card at live share + Witch at stage-1")
        w_wt = cur[Wt] + lam_w * (want[Wt] - cur[Wt])
        lam_m, bm = best(lambda x: {**want, Wt: w_wt, M: mk_floor + x * (want[M] - mk_floor)})
        info.update(mode="priority: heavy exact > Witch max (MK at live) > MK max", lambda_witch=lam_w, lambda_mk=lam_m)
        w = bm if bm is not None else bw
    info["realized_census"] = {k: float(w[TR[k]].sum()) for k in want}
    info["max_ratio_to_stage1"] = float((w / W0).max()); info["n_at_cap"] = int((w >= 3 * W0 * (1 - 1e-9)).sum())
    def half(x): s = np.sort(x)[::-1]; return int(np.searchsorted(np.cumsum(s) / s.sum(), 0.5) + 1)
    info["decks_for_50pct_mass"] = {"stage1": half(W0), "raked": half(w), "of": int(len(w))}
    return w, info


def main():
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)   # below normal
    raw = json.load(open(CENSUS, encoding="utf-8"))
    live = json.load(open(LIVE, encoding="utf-8"))["matchups"]
    n_live, ov = live["n"], live["overall_wr"]
    live_share = {k: v["n"] / n_live for k, v in live["classes"].items()}
    weak = sorted(k for k, v in live["classes"].items() if v["ci"][1] < ov)

    census = RL.league_decks(CENSUS)                         # icebow removed exactly as training does
    keep = {d["name"] for d in census}
    by_cls = collections.defaultdict(list)
    for d in census:
        by_cls[cls(d["engine"])].append(d)
    absent = sorted(set(live_share) - set(by_cls))
    census_only = sorted(set(by_cls) - set(live_share))

    # icebow-mirror share of opponent decks under R2 at steady state (>= 2 snapshots): s1 + (1 - s1) * icebow_share
    m = RL.opponent_mix(8, R2["league_mix"])
    mirror = m["s1"] + (1 - m["s1"]) * R2["league_icebow_share"]

    t = {k: v * (MULT if k in weak else 1.0) for k, v in live_share.items() if k in by_cls}
    x_live = live_share.get(XBOW, 0.0)
    rest = sum(v for k, v in t.items() if k != XBOW)
    t = {k: (x_live if k == XBOW else v / rest * (1 - x_live)) for k, v in t.items()}   # overall opponent target
    # census share needed: X-Bow total = mirror + (1 - mirror) * census_xbow
    cx = max(0.0, (t.get(XBOW, 0.0) - mirror) / (1 - mirror))
    oth = {k: v for k, v in t.items() if k != XBOW}
    so = sum(oth.values())
    census_target = {k: v / so * (1 - cx) for k, v in oth.items()}
    if XBOW in by_cls: census_target[XBOW] = cx

    w0 = {}                                                # stage 1: class target, within class ~ sides ** 0.5
    for k, ds in by_cls.items():
        tk = census_target.get(k, 0.0)                     # a census class with no live share -> 0
        s = np.array([d["sides"] for d in ds], dtype=np.float64) ** 0.5
        for d, w in zip(ds, s / s.sum() * tk):
            w0[d["name"]] = w
    # stage 2 (lead follow-up): rake per-deck weights to class x trait margins, cap 3x stage-1 weight
    names = [d["name"] for d in census]
    W0 = np.array([w0[n] for n in names])
    C = np.array([cls(d["engine"]) for d in census])
    TR = {k: np.array([trs(d["engine"])[k] for d in census]) for k in TRAITS}
    live_tr, trait_target, trait_rule = trait_targets(live, n_live, ov)
    want = {k: v / (1 - mirror) for k, v in trait_target.items()}          # icebow carries none of the three traits
    W, rake_info = rake_feasible(W0, C, census_target, TR, want, live_tr["MegaKnight card"] / (1 - mirror))
    new_sides = {n: (max(1, int(round(w * SCALE))) if w > 0 else 0) for n, w in zip(names, W)}
    out = dict(raw)
    out["decks"] = []
    for x in raw["decks"]:
        y = dict(x); y["sides_census"] = x["sides"]
        name = f"r{x['rank']}"
        y["sides"] = new_sides[name] if name in keep else x["sides"]   # the icebow entry (dropped by league_decks) unchanged
        y["ladder_class"] = cls(x["engine"])
        out["decks"].append(y)
    out["ladder"] = {"note": "R2 ladder-matched opponent mix: sides = target weight (use league_deck_alpha 1.0, floor 0.0); "
                             "sides_census = the original census count. Built by build_ladder.py.",
                     "source_census": CENSUS, "live": LIVE, "weak_x1.5": weak, "overall_live_wr": ov,
                     "opponent_target": t, "census_target": census_target, "icebow_mirror_expected": mirror,
                     "live_classes_absent_from_census": absent, "census_classes_absent_live": census_only,
                     "trait_target_opponent": trait_target, "trait_rule": trait_rule, "rake": rake_info,
                     "stage": "2: class shares then capped IPF to trait margins (cap 3x stage-1 deck weight)"}
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1)

    # ---- checks through the real path: league_decks -> deck_weights -> sample_matchups
    lad = RL.league_decks(OUT)
    p = RL.deck_weights([d["sides"] for d in lad], R2["league_deck_alpha"], R2["league_deck_floor"])
    assert len(lad) == len(census) and [d["name"] for d in lad] == [d["name"] for d in census]
    got = collections.defaultdict(float)
    for d, pi in zip(lad, p): got[cls(d["engine"])] += pi
    assert all(abs(got[k] - census_target.get(k, 0)) < 1e-4 for k in got), (dict(got), census_target)
    for k in TRAITS:
        tk = sum(pi for d, pi in zip(lad, p) if trs(d["engine"])[k])
        assert abs(tk - rake_info["realized_census"][k]) < 1e-4, (k, tk, rake_info["realized_census"][k])
    sims = {f"snaps{s}": simulate(lad, p, s) for s in (0, 1, 8)}

    # the census as R1e trained on it (alpha .5 floor .5, icebow share .2, s1 .2) -> cross-check vs q12 (X-Bow 38.4%)
    old_cfg = {**R2, "league_icebow_share": 0.2, "league_mix": {"latest": 0.35, "older": 0.25, "init": 0.2, "s1": 0.2}}
    p_old = RL.deck_weights([d["sides"] for d in census], 0.5, 0.5)
    snaps = [{"id": f"s{i}", "path": f"S{i}"} for i in range(8)]
    ms = RL.sample_matchups(np.random.default_rng(0), 20000, 0, snaps, old_cfg, census, p_old)
    old_c, old_t = mix([m_["opp_deck"] for m_ in ms])

    cen_dc = {k: len(v) / len(census) for k, v in by_cls.items()}
    tot = sum(d["sides"] for d in census)
    cen_sides = {k: sum(d["sides"] for d in v) / tot for k, v in by_cls.items()}
    cen_t = {k: sum(trs(d["engine"])[k] for d in census) / len(census) for k in TRAITS}
    live_tr = {"has Witch/Night Witch": live["traits"]["has Witch/Night Witch"]["n"] / n_live,
               "heavy tank": live["traits"]["heavy tank"]["n"] / n_live,
               "MegaKnight card": live["cards"]["MegaKnight"]["n_present"] / n_live if "MegaKnight" in live["cards"] else None}
    chk = {"weak": weak, "overall_wr": ov, "mirror_expected": mirror, "absent_from_census": absent,
           "census_only": census_only, "n_census_decks": len(census), "decks_per_class": {k: len(v) for k, v in by_cls.items()},
           "live": live_share, "live_traits": live_tr, "census_deckcount": cen_dc, "census_sides": cen_sides,
           "census_traits_deckcount": cen_t, "r1e_training_sim": {"class": old_c, "traits": old_t},
           "opponent_target": t, "census_target": census_target, "trait_target_opponent": trait_target,
           "trait_rule": trait_rule, "rake": rake_info, "sim": sims}
    json.dump(chk, open(HERE + "ladder_check.json", "w"), indent=1)

    P = print
    P(f"weak classes x{MULT}: {weak} (overall live {ov:.3f}); expected mirror share {mirror:.4f}; "
      f"census decks {len(census)}; live classes absent from census {absent}; census classes absent live {census_only}")
    S = sims["snaps8"]
    rows = sorted(set(live_share) | set(by_cls), key=lambda k: -live_share.get(k, 0))
    P(f"{'class':30s}{'decks':>6s}{'cen#':>7s}{'cenSides':>9s}{'R1eTrain':>9s}{'live':>7s}{'target':>8s}{'R2 s8':>8s}{'R2 s0':>8s}")
    for k in rows:
        f = lambda d: f"{100 * d.get(k, 0):6.1f}%"
        P(f"{k:30s}{len(by_cls.get(k, [])):6d} {f(cen_dc)}  {f(cen_sides)}  {f(old_c)}{f(live_share)} {f(t)} {f(S['class'])} {f(sims['snaps0']['class'])}")
    P(f"rake: {json.dumps(rake_info)}")
    P(f"trait opponent targets {json.dumps(trait_target)} rule {json.dumps(trait_rule)}")
    P(f"{'trait':30s}{'':6s} {'cen#':>7s}  {'':8s}  {'R1eTrain':>7s}{'live':>7s} {'':7s} {'R2 s8':>7s} {'R2 s0':>7s}")
    for k in TRAITS:
        P(f"{k:30s}{'':6s} {100 * cen_t[k]:6.1f}%  {'':8s}  {100 * old_t[k]:6.1f}%{100 * (live_tr[k] or 0):6.1f}% {100 * trait_target[k]:6.1f}% "
          f"{100 * S['traits'][k]:6.1f}% {100 * sims['snaps0']['traits'][k]:6.1f}%")
    for s in ("snaps0", "snaps1", "snaps8"):
        P(f"{s}: icebow mirror {sims[s]['icebow_mirror']:.4f}  opp s1 {sims[s]['opp_s1']:.4f}  learner icebow {sims[s]['learner_icebow']:.3f}")


if __name__ == "__main__":
    main()
