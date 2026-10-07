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


def main():
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

    new_sides = {}
    for k, ds in by_cls.items():
        tk = census_target.get(k, 0.0)                     # a census class with no live share -> 0
        s = np.array([d["sides"] for d in ds], dtype=np.float64) ** 0.5
        for d, w in zip(ds, s / s.sum() * tk):
            new_sides[d["name"]] = max(1, int(round(w * SCALE))) if tk > 0 else 0
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
                     "live_classes_absent_from_census": absent, "census_classes_absent_live": census_only}
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1)

    # ---- checks through the real path: league_decks -> deck_weights -> sample_matchups
    lad = RL.league_decks(OUT)
    p = RL.deck_weights([d["sides"] for d in lad], R2["league_deck_alpha"], R2["league_deck_floor"])
    assert len(lad) == len(census) and [d["name"] for d in lad] == [d["name"] for d in census]
    got = collections.defaultdict(float)
    for d, pi in zip(lad, p): got[cls(d["engine"])] += pi
    assert all(abs(got[k] - census_target.get(k, 0)) < 1e-4 for k in got), (dict(got), census_target)
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
           "opponent_target": t, "census_target": census_target, "sim": sims}
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
    P(f"{'trait':30s}{'':6s} {'cen#':>7s}  {'':8s}  {'R1eTrain':>7s}{'live':>7s} {'':7s} {'R2 s8':>7s} {'R2 s0':>7s}")
    for k in TRAITS:
        P(f"{k:30s}{'':6s} {100 * cen_t[k]:6.1f}%  {'':8s}  {100 * old_t[k]:6.1f}%{100 * (live_tr[k] or 0):6.1f}% {'':7s} "
          f"{100 * S['traits'][k]:6.1f}% {100 * sims['snaps0']['traits'][k]:6.1f}%")
    for s in ("snaps0", "snaps1", "snaps8"):
        P(f"{s}: icebow mirror {sims[s]['icebow_mirror']:.4f}  opp s1 {sims[s]['opp_s1']:.4f}  learner icebow {sims[s]['learner_icebow']:.3f}")


if __name__ == "__main__":
    main()
