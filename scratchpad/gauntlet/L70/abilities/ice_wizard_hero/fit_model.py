"""Mine hero-Ice-Wizard deployments from crawl/ and fit the calibrated press model.  CPU, numpy only, no network.

Run: python fit_model.py        -> mining.json, contrasts.json, model_report.json, ../../../L68/live_reader/ability_ice_wizard_model.json
"""
import csv, json, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
CRAWL = HERE / "crawl"
LIVE = HERE.parents[2] / "L68" / "live_reader"
sys.path.insert(0, str(LIVE))
import ability_ice_wizard as M                                   # noqa: E402  (shared feature builder)

TPS = 20
CAP = 30 * TPS                                                   # decision window per deploy
HERO = "ice-wizard-hero"
CHAMPS = {"archer-queen", "golden-knight", "skeleton-king", "mighty-miner", "monk", "little-prince", "goblinstein", "boss-bandit"}
rng = np.random.default_rng(0)

STATS = json.loads(Path("C:/Users/benpe/ClashBot/icebow/config/cards_stats.json").read_text(encoding="utf-8"))["cards"]
UNKNOWN = Counter()


CARDS = {}
for _k, _v in STATS.items():
    if "elixir" not in _v:
        continue
    _slug = _k.replace("_", "-")
    _base = _slug[:-4] if _slug.endswith("-evo") else _slug
    if _slug.endswith("-hero") or (_slug.endswith("-evo") and _base in CARDS):
        continue
    CARDS.setdefault(_base, [_v["elixir"], _v.get("kind") or "troop", int(_v.get("count") or 1), float(_v.get("speed_tiles") or 0.0)])
    if not _slug.endswith("-evo"):
        CARDS[_slug] = CARDS[_base]


def card_info(slug):
    s = CARDS.get(slug)
    if s is None:
        UNKNOWN[slug] += 1
        return 3, "troop", 1
    return s[0], s[1], s[2]


# ------------------------------------------------------------------ load
battles = {r["replay_tag"]: r for r in csv.DictReader(open(CRAWL / "battles.csv", encoding="utf-8"))}
plays = defaultdict(list)
for r in csv.DictReader(open(CRAWL / "plays.csv", encoding="utf-8")):
    ab = r["attr_ability"] == "1"
    x = y = None
    if not ab and r["x_units"] not in ("None", ""):
        x, y = int(r["x_units"]), int(r["y_units"])
        if r["attr_i"] == "1":                                    # other seat's frame -> canonical (blue own half = y > 16000)
            x, y = 18000 - x, 32000 - y
    plays[r["replay_tag"]].append({"tick": int(r["tick"]), "side": r["attr_s"], "card": r["attr_card"], "ab": ab, "x": x, "y": y})
for v in plays.values():
    v.sort(key=lambda p: p["tick"])


def on_half(y, side):                                             # does a play at y sit on `side`'s own half?
    return (y > 16000) == (side == "blue")


BODY_SPELLS = {"barbarian-barrel", "royal-delivery", "clone", "graveyard", "goblin-barrel"}   # spells live sees as bodies (measured, 8 live logs)
sys.path.insert(0, "C:/Users/benpe/ClashBot")
from pipeline.opp_elixir_count import OppElixirCounter                  # noqa: E402  (the live counter: start 6.0, 1/2/3x at 2400/4800)
from bisect import bisect_left                                          # noqa: E402


def detectable(card):
    """Would the live PublicObserver report this opponent play? Bodies yes; body-less spells no (reader decodes no effects)."""
    return card_info(card)[1] != "spell" or card in BODY_SPELLS


def elixir_series(pl, side, opp):
    """Counter estimate at tick t, same semantics as PublicObserver.estimate_at (causal). opp=True: only plays live detects,
    unknown-cost cards (minion-giant) not charged, as live; own side: every play + 2 per press (live reads the true value)."""
    c = OppElixirCounter()
    ticks, ests = [], []
    for p in pl:
        if p["side"] != side:
            continue
        if p["ab"]:
            cost = None if opp else 2.0
        elif opp and not detectable(p["card"]):
            continue
        else:
            known = p["card"] in CARDS
            cost = float(card_info(p["card"])[0]) if known else None
            if cost is None and not opp:
                cost = 3.0
        c.play(p["tick"], p["card"], cost)
        ticks.append(p["tick"]); ests.append(c.est)
    def at(t):
        i = bisect_left(ticks, int(t)) - 1
        cc = OppElixirCounter()
        if i >= 0:
            cc.tick, cc.est = ticks[i], ests[i]
        return cc.at(int(t))
    return at


# ------------------------------------------------------------------ deployments
deploys, unattributed = [], Counter()
for tag, b in battles.items():
    pl = plays[tag]
    if not pl:
        continue
    end = pl[-1]["tick"]
    for S in b["hero_side"].split("+"):
        deck = (b["team_deck"] if S == "blue" else b["opponent_deck"]).split(",")
        n_ab = sum(c.endswith("-hero") or c in CHAMPS for c in deck)
        owner = (b["team_tags"] if S == "blue" else b["opponent_tags"]).split(",")[0]
        dep = [p["tick"] for p in pl if p["side"] == S and p["card"] == "ice-wizard" and not p["ab"]]
        prs = [p["tick"] for p in pl if p["side"] == S and p["ab"]]
        pressed = {}
        for t in prs:                                              # latest unspent deploy before the press
            cand = [d for d in dep if d <= t and d not in pressed]
            if cand:
                pressed[cand[-1]] = t
            else:
                unattributed[tag] += 1
        for i, d in enumerate(dep):
            nxt = dep[i + 1] if i + 1 < len(dep) else 10 ** 9
            wend = min(nxt, d + CAP, end)
            pt = pressed.get(d)
            deploys.append({"tag": tag, "side": S, "owner": owner, "pro": b["team_tags"].split(",")[0], "amb": n_ab > 1, "n_ab": n_ab,
                            "dep": d, "press": pt, "wend": wend, "nxt": nxt, "idx": i, "result": b["result"],
                            "press_in_window": pt is not None and pt < wend + 1, "late": pt is not None and pt - d > CAP})
print("deploys", len(deploys), "battles", len({d["tag"] for d in deploys}), "ambiguous", sum(d["amb"] for d in deploys),
      "unattributed presses", sum(unattributed.values()))

# ------------------------------------------------------------------ rows (hazard grid)
rows, el_cache = [], {}
def play_dicts(pl, side, S, t_tick):
    return [M.make_play(p["card"], p["tick"], p["x"], p["y"], t_tick, S == "blue", CARDS) for p in pl
            if p["side"] == side and not p["ab"] and p["tick"] <= t_tick and p["x"] is not None]


def clump_value(opp_recent):
    """Largest elixir value of a >=2-body group of estimated-on-my-half troops within 2.5 tiles (0 if none)."""
    tr = [p for p in opp_recent if p["mine"] and p["kind"] == "troop"]
    best = 0.0
    for c in tr:
        g = [p for p in tr if (p["x"] - c["x"]) ** 2 + (p["y"] - c["y"]) ** 2 <= 2500 ** 2]
        if sum(p["n"] for p in g) >= 2:
            best = max(best, sum(p["cost"] for p in g))
    return best


for di, d in enumerate(deploys):
    if d["amb"]:
        continue
    pl, S = plays[d["tag"]], d["side"]
    O = "red" if S == "blue" else "blue"
    for key in (S, O):
        if (d["tag"], key) not in el_cache:
            el_cache[(d["tag"], key)] = elixir_series(pl, key, key == O)
    own_el, opp_el = el_cache[(d["tag"], S)], el_cache[(d["tag"], O)]
    kp = None if d["press"] is None else (d["press"] - d["dep"]) // TPS
    k = 0
    while d["dep"] + TPS * k + TPS <= d["wend"] or (kp is not None and k <= kp and d["dep"] + TPS * k < d["wend"]):
        t = d["dep"] + TPS * k
        opp = [p for p in play_dicts(pl, O, S, t) if detectable(p["card"])]
        own = [p for p in play_dicts(pl, S, S, t) if p["card"] != "ice-wizard"]
        f = M.build_features(k, t / TPS, own_el(t), opp_el(t), opp, own)
        rec = [p for p in opp if t / TPS - p["t"] <= 8]
        rows.append({"di": di, "k": k, "t": t, "f": f, "y": 1 if kp is not None and k == kp and d["press"] < d["wend"] + 1 else 0,
                     "risk": kp is None or k <= kp, "cards5": {p["card"] for p in opp if t / TPS - p["t"] <= 5},
                     "cv": clump_value(rec), "clump": clump_value(rec) >= 4.0, "wincon": f["opp_wincon_mine10"] > 0})
        k += 1
print("rows", len(rows), "at-risk", sum(r["risk"] for r in rows), "positives", sum(r["y"] for r in rows),
      "unknown cards", dict(UNKNOWN))
Y_ALL = np.array([r["y"] for r in rows])

# ------------------------------------------------------------------ descriptive mining + clustered bootstrap
U = [d for d in deploys if not d["amb"]]
def stat(sub):
    pr = np.array([(d["press"] - d["dep"]) / TPS for d in sub if d["press"] is not None])
    return {"share": len(pr) / len(sub) if sub else float("nan"),
            "p25": float(np.percentile(pr, 25)) if len(pr) else None, "p50": float(np.percentile(pr, 50)) if len(pr) else None,
            "p75": float(np.percentile(pr, 75)) if len(pr) else None, "p10": float(np.percentile(pr, 10)) if len(pr) else None,
            "p90": float(np.percentile(pr, 90)) if len(pr) else None}
def boot(sub, cluster, B=2000):
    groups = defaultdict(list)
    for d in sub:
        groups[d[cluster]].append(d)
    keys = list(groups)
    out = defaultdict(list)
    for _ in range(B):
        samp = [d for k in rng.integers(0, len(keys), len(keys)) for d in groups[keys[k]]]
        for kk, v in stat(samp).items():
            if v is not None:
                out[kk].append(v)
    return {kk: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for kk, v in out.items()}
phase_of = lambda t: min(3, int(t // (60 * TPS)))
mining = {"battles": len({d["tag"] for d in deploys}), "deploys_all": len(deploys), "deploys_ambiguous_2ability_side": sum(d["amb"] for d in deploys),
          "deploys_used": len(U), "battles_used": len({d["tag"] for d in U}), "hero_owner_players": len({d["owner"] for d in U}),
          "pro_history_owners": len({d["pro"] for d in U}), "hero_side_counts": Counter(d["side"] for d in U),
          "presses_unattributed": sum(unattributed.values()), "presses_after_30s_window": sum(d["late"] for d in U)}
mining["overall"] = {**stat(U), "n": len(U), "ci_battle": boot(U, "tag"), "ci_owner": boot(U, "owner")}
mining["by_phase_of_deploy"] = {}
for ph, nm in enumerate(["0-60s", "60-120s", "120-180s", "OT"]):
    sub = [d for d in U if phase_of(d["dep"]) == ph]
    mining["by_phase_of_deploy"][nm] = {**stat(sub), "n": len(sub), "ci_battle": boot(sub, "tag", 600) if len(sub) > 20 else None}
mining["by_deploy_index"] = {}
for nm, f in (("first_deploy", lambda d: d["idx"] == 0), ("later", lambda d: d["idx"] > 0)):
    sub = [d for d in U if f(d)]
    mining["by_deploy_index"][nm] = {**stat(sub), "n": len(sub)}
mining["by_hero_user"] = {s: {**stat([d for d in U if d["side"] == s]), "n": sum(d["side"] == s for d in U)} for s in ("blue", "red")}
mining["presses_per_match_hero_side"] = float(np.mean([sum(1 for d in U if d["tag"] == t and d["side"] == s and d["press"] is not None)
                                                      for t, s in {(d["tag"], d["side"]) for d in U}]))
mining["delay_hist_s"] = dict(Counter(int((d["press"] - d["dep"]) // TPS) for d in U if d["press"] is not None and d["press"] - d["dep"] < CAP))
# deploy->press when window shorter than 30 s is right-censored by redeploy; report pressed share among windows >= 10 s too
mining["share_windows_ge10s"] = stat([d for d in U if d["wend"] - d["dep"] >= 10 * TPS])["share"]
mining["median_window_s"] = float(np.median([(d["wend"] - d["dep"]) / TPS for d in U]))

# ------------------------------------------------------------------ contrasts (press row vs no-press at-risk rows, age >= 1)
R = [r for r in rows if r["risk"] and r["k"] >= 1]
def feat_inds():
    return {"opp_played_in_last_3s": lambda r: r["f"]["opp_n3"] > 0,
            "opp_played_on_my_half_last_3s": lambda r: r["f"]["opp_since_mine"] <= 3,
            "opp_played_on_my_half_last_6s": lambda r: r["f"]["opp_mine_cost6"] > 0,
            "opp_cost_last_6s>=6": lambda r: r["f"]["opp_cost6"] >= 6,
            "opp_troop_cost_last_6s>=4": lambda r: r["f"]["opp_troop6"] >= 4,
            "opp_spell_last_6s": lambda r: r["f"]["opp_spell6"] > 0,
            "opp_building_last_6s": lambda r: r["f"]["opp_bld6"] > 0,
            "opp_wincon_on_my_half_last_10s": lambda r: r["f"]["opp_wincon_mine10"] > 0,
            "own_played_last_3s": lambda r: r["f"]["own_n3"] > 0,
            "own_elixir>=5": lambda r: r["f"]["own_elixir"] >= 5,
            "own_elixir<=2": lambda r: r["f"]["own_elixir"] <= 2,
            "opp_elixir<=3": lambda r: r["f"]["opp_elixir"] <= 3,
            "overtime": lambda r: r["f"]["overtime"] > 0,
            "rule_proxy_clump(>=2 bodies,>=4 elixir, last 8s, my half)": lambda r: r["clump"],
            "rule_proxy_wincon_on_my_half(10s)": lambda r: r["wincon"],
            "rule_proxy_clump_or_wincon": lambda r: r["clump"] or r["wincon"]}
cards_pos = Counter(c for r in R if r["y"] for c in r["cards5"])
top_cards = [c for c, _ in (cards_pos + Counter(c for r in R[::7] for c in r["cards5"])).most_common(14)]
inds = feat_inds()
for c in top_cards:
    inds["opp_played_%s_last_5s" % c] = (lambda c: lambda r: c in r["cards5"])(c)
by_battle = defaultdict(list)
for r in R:
    by_battle[deploys[r["di"]]["tag"]].append(r)
btags = list(by_battle)
tab = {name: np.zeros((len(btags), 4)) for name in inds}       # per battle: pos_n, pos_feat, neg_n, neg_feat
for bi, t in enumerate(btags):
    for r in by_battle[t]:
        for name, fn in inds.items():
            v = fn(r)
            if r["y"]:
                tab[name][bi, 0] += 1; tab[name][bi, 1] += v
            else:
                tab[name][bi, 2] += 1; tab[name][bi, 3] += v
contrasts = {}
idx_b = [rng.integers(0, len(btags), len(btags)) for _ in range(1000)]
for name, a in tab.items():
    def rates(A):
        s = A.sum(0)
        return s[1] / max(s[0], 1), s[3] / max(s[2], 1)
    p, q = rates(a)
    bs = [rates(a[i]) for i in idx_b]
    diff = [x - y for x, y in bs]
    ratio = [x / y for x, y in bs if y > 0]
    contrasts[name] = {"press_rate": p, "nopress_rate": q, "diff_pp": 100 * (p - q),
                       "diff_ci": [100 * float(np.percentile(diff, 2.5)), 100 * float(np.percentile(diff, 97.5))],
                       "ratio": p / q if q else None,
                       "ratio_ci": [float(np.percentile(ratio, 2.5)), float(np.percentile(ratio, 97.5))] if ratio else None,
                       "n_press": int(a[:, 0].sum()), "n_nopress": int(a[:, 2].sum())}
# exact press-tick context: last opponent play before the press
last = Counter(); gaps = []; since_mine = []
for d in U:
    if d["press"] is None:
        continue
    O = "red" if d["side"] == "blue" else "blue"
    opp = [p for p in play_dicts(plays[d["tag"]], O, d["side"], d["press"]) if detectable(p["card"])]
    rec = [p for p in opp if d["press"] / TPS - p["t"] <= 6]
    if rec:
        last[rec[-1]["card"]] += 1; gaps.append(d["press"] / TPS - rec[-1]["t"])
    else:
        last["(nothing in 6s)"] += 1
    m = [d["press"] / TPS - p["t"] for p in opp if p["mine"]]
    since_mine.append(min(m) if m else 99)
mining["last_opp_play_before_press_top"] = last.most_common(12)
mining["median_gap_last_opp_play_to_press_s"] = float(np.median(gaps)) if gaps else None
mining["median_since_opp_play_on_my_half_at_press_s"] = float(np.median(since_mine))
json.dump(mining, open(HERE / "mining.json", "w"), indent=1, default=str)
json.dump(contrasts, open(HERE / "contrasts.json", "w"), indent=1)

# ------------------------------------------------------------------ interim rule proxy vs pro timing
prox = {}
for nm, fn in (("clump_proxy", lambda r: r["clump"]), ("wincon_proxy_(Tesla assumed unavailable)", lambda r: r["wincon"]),
               ("clump_or_wincon", lambda r: r["clump"] or r["wincon"])):
    byd = defaultdict(list)
    for r in rows:
        byd[r["di"]].append(r)
    fires = pro_after = rule_hold = both = rule_only = pro_only = 0; lead = []
    n_dep = n_pressed = 0
    for di, rs in byd.items():
        d = deploys[di]
        f = [r["k"] for r in rs if fn(r) and r["k"] >= 1]
        n_dep += 1
        p = d["press"] is not None
        n_pressed += p
        if f and p:
            both += 1; lead.append(((d["press"] - d["dep"]) / TPS) - f[0])
        elif f:
            rule_only += 1
        elif p:
            pro_only += 1
    prox[nm] = {"deploys": n_dep, "rule_fires_in_window": both + rule_only, "pro_pressed": n_pressed,
                "both": both, "rule_only(pros_hold)": rule_only, "pro_only(rule_silent)": pro_only,
                "recall_of_pro_presses": both / max(n_pressed, 1), "precision_vs_pro": both / max(both + rule_only, 1),
                "median_pro_press_minus_rule_first_fire_s": float(np.median(lead)) if lead else None,
                "row_fire_rate_press_rows": contrasts.get({"clump_proxy": "rule_proxy_clump(>=2 bodies,>=4 elixir, last 8s, my half)",
                                                           "wincon_proxy_(Tesla assumed unavailable)": "rule_proxy_wincon_on_my_half(10s)",
                                                           "clump_or_wincon": "rule_proxy_clump_or_wincon"}[nm], {}).get("press_rate"),
                "row_fire_rate_nopress_rows": contrasts.get({"clump_proxy": "rule_proxy_clump(>=2 bodies,>=4 elixir, last 8s, my half)",
                                                             "wincon_proxy_(Tesla assumed unavailable)": "rule_proxy_wincon_on_my_half(10s)",
                                                             "clump_or_wincon": "rule_proxy_clump_or_wincon"}[nm], {}).get("nopress_rate")}
json.dump(prox, open(HERE / "rule_proxy.json", "w"), indent=1)

# ------------------------------------------------------------------ model
def sigmoid(z):
    return 1 / (1 + np.exp(-np.clip(z, -40, 40)))
def logistic(x, y, penalty):
    mean = x.mean(0); scale = x.std(0); scale[scale < 1e-8] = 1
    z = np.column_stack([np.ones(len(x)), (x - mean) / scale]); y = y.astype(float)
    w = np.zeros(z.shape[1]); w[0] = np.log((y.sum() + .5) / (len(y) - y.sum() + .5))
    reg = np.full(len(w), penalty); reg[0] = 0
    loss = lambda w: float(np.sum(np.logaddexp(0, z @ w) - y * (z @ w)) + .5 * np.dot(reg * w, w))  # noqa: E731
    for it in range(80):
        p = sigmoid(z @ w); g = z.T @ (p - y) + reg * w
        h = z.T @ (z * (p * (1 - p))[:, None]) + np.diag(reg + 1e-8)
        step = np.linalg.solve(h, g); a = 1.; old = loss(w)
        while a > 1e-7 and loss(w - a * step) > old:
            a *= .5
        w -= a * step
        if np.max(np.abs(a * step)) < 1e-7:
            break
    return {"mean": mean, "scale": scale, "b": float(w[0]), "w": w[1:], "penalty": penalty}
def predict(m, x):
    return sigmoid(((x - m["mean"]) / m["scale"]) @ m["w"] + m["b"])
def auc(y, p):
    y = np.asarray(y); n1 = int(y.sum()); n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return None
    order = np.argsort(p, kind="stable"); ps = p[order]
    _, first, cnt = np.unique(ps, return_index=True, return_counts=True)
    ranks = np.repeat(first + (cnt + 1) / 2, cnt)
    return float((np.dot(ranks, y[order]) - n1 * (n1 + 1) / 2) / (n1 * n0))
def ece(y, p, bins=8):
    q = np.quantile(p, np.linspace(0, 1, bins + 1)); q[-1] += 1e-9
    out = []; tot = 0.0
    for i in range(bins):
        m = (p >= q[i]) & (p < q[i + 1])
        if m.sum():
            out.append({"pred": float(p[m].mean()), "obs": float(y[m].mean()), "n": int(m.sum())})
            tot += m.sum() * abs(p[m].mean() - y[m].mean())
    return float(tot / len(p)), out

NAMES = M.FEATURE_NAMES
X = np.array([[r["f"][n] for n in NAMES] for r in rows])
tags_all = np.array([deploys[r["di"]]["tag"] for r in rows])
owner_all = np.array([deploys[r["di"]]["owner"] for r in rows])
risk = np.array([r["risk"] for r in rows])
ub = sorted(set(tags_all)); perm = rng.permutation(len(ub))
test_tags = {ub[i] for i in perm[: int(round(0.2 * len(ub)))]}
test = np.array([t in test_tags for t in tags_all]); train = ~test
timing_cols = [i for i, n in enumerate(NAMES) if n.startswith("age_hat")]
def fit_cv(cols, mask):
    best = None
    tb = sorted(set(tags_all[mask & risk])); folds = np.arange(len(tb)) % 5; rng2 = np.random.default_rng(1); rng2.shuffle(folds)
    fold_of = dict(zip(tb, folds))
    f_row = np.array([fold_of.get(t, -1) for t in tags_all])
    for pen in (0.1, 0.3, 1, 3, 10, 30, 100, 300):
        ll = 0.0
        for k in range(5):
            tr = mask & risk & (f_row != k); va = mask & risk & (f_row == k)
            m = logistic(X[tr][:, cols], Y_ALL[tr], pen); p = np.clip(predict(m, X[va][:, cols]), 1e-9, 1 - 1e-9)
            ll += -np.sum(Y_ALL[va] * np.log(p) + (1 - Y_ALL[va]) * np.log1p(-p))
        if best is None or ll < best[0]:
            best = (ll, pen)
    return best[1]
all_cols = list(range(len(NAMES)))
res = {"n_rows_at_risk_train": int((train & risk).sum()), "n_rows_at_risk_test": int((test & risk).sum()),
       "test_battles": len(test_tags), "train_battles": len(ub) - len(test_tags),
       "test_positives": int(Y_ALL[test & risk].sum()), "train_positives": int(Y_ALL[train & risk].sum()),
       "test_owner_players": len(set(owner_all[test])), "train_owner_players": len(set(owner_all[train])),
       "test_owners_also_in_train": len(set(owner_all[test]) & set(owner_all[train]))}
models = {}; PT = {}
for label, cols in (("full", all_cols), ("timing_only", timing_cols)):
    pen = fit_cv(cols, train)
    m = logistic(X[train & risk][:, cols], Y_ALL[train & risk], pen); models[label] = (m, cols)
    pt = predict(m, X[test & risk][:, cols]); yt = Y_ALL[test & risk]
    PT[label] = pt
    e, bins = ece(yt, pt)
    pp = np.clip(pt, 1e-9, 1 - 1e-9)
    res[label] = {"penalty": pen, "holdout_auc": auc(yt, pt), "log_loss": float(-np.mean(yt * np.log(pp) + (1 - yt) * np.log1p(-pp))),
                  "brier": float(np.mean((pt - yt) ** 2)), "mean_pred": float(pt.mean()), "mean_obs": float(yt.mean()),
                  "hazard_ECE": e, "hazard_calibration_bins": bins}
    # grouped-by-player 5-fold AUC (all data)
    own = sorted(set(owner_all)); fo = {o: i % 5 for i, o in enumerate(own)}
    f_row = np.array([fo[o] for o in owner_all]); oof = np.zeros(len(rows)); ok = risk.copy()
    for k in range(5):
        tr = risk & (f_row != k); va = risk & (f_row == k)
        if Y_ALL[tr].sum() and va.sum():
            oof[va] = predict(logistic(X[tr][:, cols], Y_ALL[tr], pen), X[va][:, cols])
    res[label]["player_grouped_5fold_auc"] = auc(Y_ALL[risk], oof[risk])
    # deployment-level share + delay (full windows, held-out battles)
    tdi = sorted({r["di"] for r, tt in zip(rows, test) if tt})
    pmf_total = np.zeros(CAP // TPS + 1); sh_pred = []; sh_obs = []; obs_delays = []
    ph_all = predict(m, X[:, cols])
    by_di = defaultdict(list)
    for i, r in enumerate(rows):
        if test[i]:
            by_di[r["di"]].append(i)
    for di in by_di:
        idx = sorted(by_di[di], key=lambda i: rows[i]["k"]); h = ph_all[idx]
        surv = np.cumprod(np.concatenate([[1], 1 - h[:-1]])); pmf = h * surv
        for j, i in enumerate(idx):
            pmf_total[rows[i]["k"]] += pmf[j]
        sh_pred.append(float(pmf.sum()))
        d = deploys[di]; sh_obs.append(1.0 if d["press"] is not None and d["press"] - d["dep"] < CAP else 0.0)
        if sh_obs[-1]:
            obs_delays.append((d["press"] - d["dep"]) / TPS)
    cdf = np.cumsum(pmf_total) / pmf_total.sum(); grid = np.arange(len(cdf) + 1.0)
    cdf0 = np.concatenate([[0], cdf])
    qs = {q: float(np.interp(q, cdf0, grid)) for q in (.25, .5, .75)}
    oq = {q: float(np.percentile(obs_delays, 100 * q)) for q in (.25, .5, .75)}
    res[label]["heldout_deploys"] = len(sh_obs)
    res[label]["share_pred"] = float(np.mean(sh_pred)); res[label]["share_obs"] = float(np.mean(sh_obs))
    res[label]["share_error_pp"] = 100 * (res[label]["share_pred"] - res[label]["share_obs"])
    res[label]["delay_pred_s"] = qs; res[label]["delay_obs_s"] = oq
    res[label]["delay_error_s"] = {str(q): qs[q] - oq[q] for q in qs}
    # bootstrap SE of observed share / median (battle clusters) for context
    dd = [(deploys[di]["tag"], o, s) for di, o, s in zip(sorted(by_di), [None] * len(by_di), sh_obs)]
    bt = defaultdict(list)
    for (t, _, s) in dd:
        bt[t].append(s)
    ks = list(bt); bs = [np.mean([x for k in rng.integers(0, len(ks), len(ks)) for x in bt[ks[k]]]) for _ in range(1000)]
    res[label]["share_obs_battle_boot_se_pp"] = 100 * float(np.std(bs))
# held-out AUC CIs, battle-clustered bootstrap (and the gain of context over timing-only)
tt = tags_all[test & risk]; yt_ = Y_ALL[test & risk]; tg = sorted(set(tt)); ix = {t: np.where(tt == t)[0] for t in tg}
A = {"full": [], "timing_only": [], "gain": []}
for _ in range(1000):
    ii = np.concatenate([ix[tg[k]] for k in rng.integers(0, len(tg), len(tg))])
    a1, a0 = auc(yt_[ii], PT["full"][ii]), auc(yt_[ii], PT["timing_only"][ii])
    if a1 is not None:
        A["full"].append(a1); A["timing_only"].append(a0); A["gain"].append(a1 - a0)
for k, v in A.items():
    res["full" if k != "timing_only" else k][("auc_ci" if k != "gain" else "auc_gain_over_timing_ci") if k != "gain" else "auc_gain_over_timing_ci"] = [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
# ------------------------------------------------------------------ combined policy: hazard gate AND geometry
PRO_SHARE = 0.316
VMINS = (2.0, 3.0, 4.0)
PGRID = np.geomspace(0.002, 0.3, 80)
by_di_rows = defaultdict(list)
for i, r in enumerate(rows):
    by_di_rows[r["di"]].append(i)
for di in by_di_rows:
    by_di_rows[di].sort(key=lambda i: rows[i]["k"])
CV = np.array([r["cv"] for r in rows]); WC = np.array([r["wincon"] for r in rows]); KK = np.array([r["k"] for r in rows])
def policy_eval(h, dis, P, V):
    """First grid row k>=1 where h>=P and (clump value>=V or wincon on my half); P=0 -> geometry only (the current rule)."""
    n = fired = pressed = both = 0; lead = []
    for di in dis:
        idx = [i for i in by_di_rows[di] if KK[i] >= 1]
        n += 1
        d = deploys[di]; pro = d["press"] is not None and d["press"] - d["dep"] < CAP
        pressed += pro
        f = [KK[i] for i in idx if h[i] >= P and (CV[i] >= V or WC[i])]
        fired += bool(f)
        if f and pro:
            both += 1; lead.append(f[0] - (d["press"] - d["dep"]) / TPS)
    lead = np.array(lead)
    return {"deploys": n, "share": fired / n, "pro_share": pressed / n, "recall": both / max(pressed, 1),
            "precision": both / max(fired, 1), "timing_median_s": float(np.median(lead)) if len(lead) else None,
            "timing_mad_s": float(np.median(np.abs(lead - np.median(lead)))) if len(lead) else None,
            "within_2s_of_pro": float(np.mean(np.abs(lead) <= 2)) if len(lead) else None,
            "recall_within_2s": float(np.sum(np.abs(lead) <= 2) / max(pressed, 1)) if len(lead) else 0.0}
def choose(h, dis):
    best = None
    for V in VMINS:
        for P in PGRID:
            m = policy_eval(h, dis, P, V)
            if abs(m["share"] - PRO_SHARE) <= 0.03 and (best is None or (m["recall"], m["precision"]) > (best[2]["recall"], best[2]["precision"])):
                best = (float(P), V, m)
    return best
used_di = sorted(by_di_rows)
tr_di = [di for di in used_di if deploys[di]["tag"] not in test_tags]; te_di = [di for di in used_di if deploys[di]["tag"] in test_tags]
mtr, ctr = models["full"]
h_tr = predict(mtr, X[:, ctr])                       # train-fit model on every row
bt = choose(h_tr, tr_di)
pol = {"pro_share_target": PRO_SHARE, "chosen_on_train": {"P_STAR": bt[0], "V_MIN": bt[1], "train_metrics": bt[2]},
       "holdout_policy": policy_eval(h_tr, te_di, bt[0], bt[1]),
       "holdout_current_rule_geometry_only_V4": policy_eval(h_tr, te_di, 0.0, 4.0),
       "train_current_rule": policy_eval(h_tr, tr_di, 0.0, 4.0),
       "holdout_hazard_only_same_P": policy_eval(h_tr, te_di, bt[0], 0.0 - 1.0),
       "per_V_best_on_train": {}}
for V in VMINS:
    best = None
    for P in PGRID:
        m = policy_eval(h_tr, tr_di, P, V)
        if abs(m["share"] - PRO_SHARE) <= 0.03 and (best is None or (m["recall"], m["precision"]) > (best[2]["recall"], best[2]["precision"])):
            best = (float(P), V, m)
    if best:
        pol["per_V_best_on_train"][str(V)] = {"P": best[0], "train": best[2], "holdout": policy_eval(h_tr, te_di, best[0], V)}
# shipped threshold: same rule, shipped (all-rows) model, all deploys
mfin_all = logistic(X[risk], Y_ALL[risk], res["full"]["penalty"])
h_fin = predict(mfin_all, X)
bf = choose(h_fin, used_di)
pol["shipped"] = {"P_STAR": bf[0], "V_MIN": bf[1], "all_data_metrics": bf[2]}
res["policy"] = pol
json.dump(pol, open(HERE / "policy.json", "w"), indent=1)
print("POLICY", json.dumps({k: pol[k] for k in ("chosen_on_train", "holdout_policy", "holdout_current_rule_geometry_only_V4", "shipped")}, indent=1, default=str))
# refit full on ALL at-risk rows with the CV'd penalty and ship it
pen = res["full"]["penalty"]
mfin = logistic(X[risk], Y_ALL[risk], pen)
res["shipped"] = {"fit_on": "all %d at-risk rows (%d positives)" % (int(risk.sum()), int(Y_ALL[risk].sum())), "penalty": pen,
                  "in_sample_mean_pred": float(predict(mfin, X[risk]).mean()), "in_sample_mean_obs": float(Y_ALL[risk].mean())}
coef = sorted(zip(NAMES, mfin["w"]), key=lambda x: -abs(x[1]))
res["top_standardized_coefficients"] = [(n, round(float(w), 3)) for n, w in coef[:12]]
json.dump(res, open(HERE / "model_report.json", "w"), indent=1)
model_json = {"description": "Frosty Fella press hazard (P press within next 1 s | alive, unspent); numpy logistic, L2 on standardized features",
              "fit": res["shipped"], "feature_names": NAMES, "mean": mfin["mean"].tolist(), "scale": mfin["scale"].tolist(),
              "intercept": mfin["b"], "coefficients": mfin["w"].tolist(), "calibration_shift": 0.0,
              "heldout_report": {k: res["full"][k] for k in ("holdout_auc", "share_error_pp", "delay_error_s", "hazard_ECE")},
              "knots_s": M.KNOTS, "policy": {"P_STAR": pol["shipped"]["P_STAR"], "V_MIN": pol["shipped"]["V_MIN"]},
              "cards": CARDS, "data": "crawl/ battles.csv plays.csv, %d battles" % len(ub)}
(LIVE / "ability_ice_wizard_model.json").write_text(json.dumps(model_json, indent=1), encoding="utf-8")
print(json.dumps({k: res[k] for k in ("full", "timing_only")}, indent=1, default=str)[:6000])
print(json.dumps(mining, indent=1, default=str)[:5000])
print("rule proxy", json.dumps(prox, indent=1))
