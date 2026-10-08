"""L74 econ2 Q4 step 1: input-swap diagnostic for the live gate's excess eagerness (no training; model passes on the VM CPU).

LIVE rows: every logged decision of the towerref_w2 live logs rebuilt by L73/lethal_rocket/rebuild.py (main's pipeline,
isolated copy ~/econ2/repo_main). SIM rows: the learner's GenModel input row at every decision of a SIM run with the same
checkpoint + deployed options (dump_patch.py, ~/econ2/rows). State classes from econ2's compact data (fixed body values):
tank = nothing on my half, an enemy unit worth >= 5 on theirs; form = inside an opponent-commit -> push-start window.
Swap ONE input group at a time: LIVE rows -> SIM-like value (does the excess go away?) and SIM rows -> live-like value
(does it appear?). Metric: P(p > tau_phase) and mean p at model elixir 2-6.9, plus the top-card change rate.

  cd ~/econ2/repo_main && CB_REPO=$PWD nice ~/venv/bin/python ~/econ2/econ2/swap.py collect   -> ~/econ2/swap_rows.pkl
                                          nice ~/venv/bin/python ~/econ2/econ2/swap.py swap      -> printed tables
"""
import os, sys, glob, json, pickle, bisect, collections
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("CB_REPO", os.path.expanduser("~/econ2/repo_main"))
sys.path.insert(0, REPO); sys.path.insert(0, REPO + "/scratchpad/gauntlet/L73/lethal_rocket"); sys.path.insert(0, HERE)
CKPT = "/home/clashbot-gauntlet/probe_rocket/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt"   # sha 41b52a83 = live
LOGS = os.path.expanduser("~/econ2/live_logs")
SIMDIR = os.path.expanduser("~/econ2/sim")
OUT = os.path.expanduser("~/econ2/swap_rows.pkl")
TAU = (.35, .45, .55)
INT_KEYS = ("hand_card", "hand_form", "next_card", "next_form", "deck_card", "deck_form", "unit_form")
KEYS = ("tok", "mask", "sc", "past", "hand_card", "hand_form", "next_card", "next_form", "deck_card", "deck_form", "unit_form",
        "opp_past", "opp_cycle", "own_ability", "projectiles", "effects")


def pidx(t): return 0 if t < 2400 else (1 if t < 3600 else 2)


def classes(m):
    """tick -> (trigger, in formation window) from an econ2 compact match."""
    import econ2 as E
    win = [(tc, tp) for tp, tc in zip(m["ps"], m["cm"]) if tc is not None]
    out = {}
    for i, t in enumerate(m["T"]):
        out[t] = (E.trigger(m["vm"][i], m["vt"][i], m["tk"][i]), any(a <= t < b for a, b in win))
    return out, m["T"]


def cls_at(cl, T, t):
    k = max(0, bisect.bisect_right(T, t) - 1); return cl[T[k]]


def live_one(f):
    import torch, rebuild as RB
    import econ2 as E
    torch.set_num_threads(1)
    comp = {m["file"]: m for m in E.load("live")}
    m = RB.Match(os.path.join(LOGS, f), CKPT, "cpu")
    cl, T = classes(comp[f])
    rows = []
    for i, d in enumerate(m.dec):
        p = d["public"]; el = float(p["model_own_elixir"])
        if not (2 <= el < 7) or d["decision"].get("p_play") is None: continue
        b, info = m.batch(i)
        with torch.no_grad():
            pr = float(torch.sigmoid(m.model(b)["gate"][0]))
        trig, form = cls_at(cl, T, d["tick"])
        rows.append(dict(src="live", file=f, tick=d["tick"], ph=pidx(d["tick"]), el=el, trig=trig, form=form, p_log=float(d["decision"]["p_play"]),
                         p=pr, allowed=info["allowed"], b={k: b[k].squeeze(0).numpy() if b[k].dim() > 0 else b[k].numpy() for k in KEYS}))
    return rows


def sim_rows():
    import econ2 as E
    comp = {m["file"]: m for m in E.load("sim_d_rows")}
    rows = []
    for s in ("evo", "lad"):
        for l in open(f"{SIMDIR}/d_rows_{s}/matches.jsonl"):
            r = json.loads(l)
            if "lr_rows_file" not in r: continue
            cl, T = classes(comp[f"{s}:{r['tag']}"])
            for t, p, row in pickle.load(open(r["lr_rows_file"], "rb")):
                el = float(row["sc"][3]) * 10
                if not (2 <= el < 7): continue
                trig, form = cls_at(cl, T, t)
                rows.append(dict(src="sim", file=f"{s}:{r['tag']}", tick=t, ph=pidx(t), el=el, trig=trig, form=form, p_log=p, p=None,
                                 b={k: row[k] for k in KEYS}))
    return rows


def collect():
    from multiprocessing import Pool
    fs = sorted(os.listdir(LOGS)); L = []
    with Pool(16) as pool:
        for r in pool.imap_unordered(live_one, fs): L += r
    S = sim_rows()
    pickle.dump(dict(live=L, sim=S), open(OUT, "wb"))
    err = np.abs([r["p"] - r["p_log"] for r in L])
    print("live rows", len(L), "sim rows", len(S), "| rebuild |p - logged p| median %.4f p90 %.4f" % (np.median(err), np.percentile(err, 90)))


# ------------------------------------------------------------------ swaps (each returns a modified COPY of one row's dict)
def _c(b): return {k: np.array(v, copy=True) for k, v in b.items()}


def own_tok(b): return (b["tok"][:, 1] == 1) & b["mask"]


def f_forms_base(b, d=None):          # hero (form 2) -> base form 0 in my hand / next / deck / own history / my units
    b = _c(b)
    for k in ("hand_form", "next_form", "deck_form"): b[k][b[k] == 2] = 0
    b["past"][:, 1][b["past"][:, 1] == 2] = 0
    uf = b["unit_form"]; uf[(uf == 2) & own_tok(b)] = 0
    return b


def f_ability_zero(b, d=None): b = _c(b); b["own_ability"][:] = 0; return b
def f_opp_minus(b, d=None): b = _c(b); b["sc"][5] = max(0.0, b["sc"][5] - .034); return b
def f_opp_plus(b, d=None): b = _c(b); b["sc"][5] = min(1.0, b["sc"][5] + .034); return b
def donor(key):
    def f(b, d):
        b = _c(b); b[key] = np.array(d[key], copy=True); return b
    f.__name__ = "donor_" + key; return f


def f_hist(b, d):
    b = _c(b); b["opp_past"] = np.array(d["opp_past"]); b["opp_cycle"] = np.array(d["opp_cycle"]); return b


def f_unit_attr(b, d):                # deploying / age / conf columns of every unit token -> the donor's per-column mean convention
    b = _c(b); m = b["mask"]; dm = d["mask"]
    for c in (8, 9, 10, 11, 12):
        if dm.any(): b["tok"][m, c] = d["tok"][dm, c].mean()
    return b


def f_unit_conf1(b, d=None): b = _c(b); b["tok"][b["mask"], 12] = 1.0; return b
def hero_on(iw):
    def f(b, d=None):                 # SIM -> live-like: the Ice Wizard card is the hero form (2), as in the live deck
        b = _c(b)
        for kc, kf in (("hand_card", "hand_form"), ("next_card", "next_form"), ("deck_card", "deck_form")): b[kf][b[kc] == iw] = 2
        b["past"][:, 1][b["past"][:, 0] == iw] = 2
        return b
    return f


def run_model(model, rows, fn=None, donors=None):
    import torch
    out = []
    for i in range(0, len(rows), 256):
        chunk = rows[i:i + 256]
        bs = [fn(r["b"], donors[i + j] if donors else None) if fn else r["b"] for j, r in enumerate(chunk)]
        b = {}
        for k in KEYS:
            a = np.stack([x[k] for x in bs])
            b[k] = torch.from_numpy(a.astype(np.int64) if k in INT_KEYS else (a.astype(bool) if k == "mask" else a.astype(np.float32)))
        with torch.no_grad():
            o = model(b)
        p = torch.sigmoid(o["gate"].reshape(-1)).numpy(); top = o["card"].argmax(-1).numpy()
        out += list(zip(p, top))
    return out


def swap():
    import torch
    from pipeline.model_gen import load_model
    torch.set_num_threads(8)
    D = pickle.load(open(OUT, "rb")); L, S = D["live"], D["sim"]
    model, st = load_model(CKPT, torch.device("cpu")); model.eval()
    gid = {k: i for i, k in enumerate(st["card_vocab"])}
    from pipeline.dataset_gen import card_key
    iw = gid[card_key("IceWizard")]
    rng = np.random.default_rng(7)
    def key(r): return (min(r["ph"], 1), int(r["el"]), r["trig"])
    def pick(pool_rows, rows):          # one matched donor per row from the other source (phase group, int elixir, trigger)
        idx = collections.defaultdict(list)
        for j, r in enumerate(pool_rows): idx[key(r)].append(j)
        return [pool_rows[idx[key(r)][rng.integers(len(idx[key(r)]))]]["b"] if idx.get(key(r)) else r["b"] for r in rows]
    sets = {"tank": lambda r: r["trig"] == "their_tank", "form": lambda r: r["form"], "all 2-7": lambda r: True}
    base_L = run_model(model, L); base_S = run_model(model, S)
    for r, (p, t) in zip(S, base_S): r["p"] = p
    print("SIM dump check |model p - logged p| median %.5f" % np.median([abs(r["p"] - r["p_log"]) for r in S]))
    def stats(rows, res, sel):
        ii = [i for i, r in enumerate(rows) if sel(rows[i])]
        if not ii: return None
        fire = np.mean([res[i][0] > TAU[rows[i]["ph"]] for i in ii]); pm = np.mean([res[i][0] for i in ii])
        return fire, pm, ii
    def matched_excess(sel):
        """live vs SIM P(p > tau) with SIM re-weighted to live's (phase group, int elixir, trigger) mix."""
        cl = collections.defaultdict(list); cs = collections.defaultdict(list)
        for r, (p, t) in zip(L, base_L):
            if sel(r): cl[key(r)].append(p > TAU[r["ph"]])
        for r, (p, t) in zip(S, base_S):
            if sel(r): cs[key(r)].append(p > TAU[r["ph"]])
        n = sum(len(v) for k, v in cl.items() if len(cs.get(k, [])) >= 10)
        fl = sum(sum(v) for k, v in cl.items() if len(cs.get(k, [])) >= 10) / max(1, n)
        fs = sum(len(v) * np.mean(cs[k]) for k, v in cl.items() if len(cs.get(k, [])) >= 10) / max(1, n)
        return fl, fs, n
    # input-group distributions in the selected states
    def desc(rows):
        b = [r["b"] for r in rows]
        return dict(hero_form=np.mean([(x["hand_form"] == 2).any() for x in b]), ability_rows=np.mean([(np.abs(x["own_ability"]).sum(-1) > 0).sum() for x in b]),
                    opp_el=np.mean([x["sc"][5] * 10 for x in b]), proj=np.mean([(np.abs(x["projectiles"]).sum(-1) > 0).sum() for x in b]),
                    eff=np.mean([(np.abs(x["effects"]).sum(-1) > 0).sum() for x in b]), units=np.mean([x["mask"].sum() for x in b]),
                    deploying_known=np.mean([x["tok"][x["mask"], 9].mean() if x["mask"].any() else 0 for x in b]),
                    deploying=np.mean([x["tok"][x["mask"], 8].mean() if x["mask"].any() else 0 for x in b]),
                    age_known=np.mean([x["tok"][x["mask"], 11].mean() if x["mask"].any() else 0 for x in b]),
                    age=np.mean([x["tok"][x["mask"], 10].mean() if x["mask"].any() else 0 for x in b]),
                    conf=np.mean([x["tok"][x["mask"], 12].mean() if x["mask"].any() else 0 for x in b]),
                    opp_past=np.mean([(np.abs(x["opp_past"]).sum(-1) > 0).sum() for x in b]), past=np.mean([(x["past"][:, 0] > 0).sum() for x in b]))
    for nm, sel in sets.items():
        dl = desc([r for r in L if sel(r)]); ds = desc([r for r in S if sel(r)])
        print(f"\n[{nm}] input groups live vs SIM: " + ", ".join(f"{k} {dl[k]:.3f}/{ds[k]:.3f}" for k in dl))
    # swaps
    donS = pick(S, L); donL = pick(L, S)
    LIVE_SW = [("hero forms -> base", f_forms_base, None), ("own_ability -> 0", f_ability_zero, None), ("opp elixir -0.34", f_opp_minus, None),
               ("projectiles <- SIM", donor("projectiles"), donS), ("effects <- SIM", donor("effects"), donS),
               ("opp_past+opp_cycle <- SIM", f_hist, donS), ("own past <- SIM", donor("past"), donS),
               ("unit deploying/age/conf <- SIM mean", f_unit_attr, donS), ("unit conf -> 1", f_unit_conf1, None)]
    SIM_SW = [("Ice Wizard -> hero form", hero_on(iw), None), ("opp elixir +0.34", f_opp_plus, None), ("projectiles <- live", donor("projectiles"), donL), ("effects <- live", donor("effects"), donL),
              ("opp_past+opp_cycle <- live", f_hist, donL), ("own past <- live", donor("past"), donL),
              ("own_ability <- live", donor("own_ability"), donL), ("unit deploying/age/conf <- live mean", f_unit_attr, donL)]
    res = {}
    for nm, sel in sets.items():
        fl, fs, n = matched_excess(sel)
        print(f"\n## [{nm}] matched P(p > tau): live {fl:.4f} vs SIM {fs:.4f} (n live {n}) -> excess {fl - fs:+.4f} ({(fl / fs - 1) * 100 if fs else 0:+.1f}%)")
        bl = stats(L, base_L, sel); bsm = stats(S, base_S, sel)
        print(f"| swap | rows | P(p>tau) before -> after | change | share of the live excess | mean p change | top card changed |")
        for side, rows, base, SW in (("LIVE", L, base_L, LIVE_SW), ("SIM", S, base_S, SIM_SW)):
            b0 = stats(rows, base, sel)
            if b0 is None: continue
            for snm, fn, don in SW:
                out = run_model(model, rows, fn, don)
                a = stats(rows, out, sel)
                dch = a[0] - b0[0]; share = (-dch if side == "LIVE" else dch) / (fl - fs) if fl != fs else float("nan")
                tc = np.mean([out[i][1] != base[i][1] for i in b0[2]])
                print(f"| {side}: {snm} | {len(b0[2])} | {b0[0]:.4f} -> {a[0]:.4f} | {dch:+.4f} | {share * 100:+.0f}% | {a[1] - b0[1]:+.4f} | {tc * 100:.1f}% |")
                res[f"{nm}|{side}|{snm}"] = dict(before=b0[0], after=a[0], dp=a[1] - b0[1], share=share, top_changed=tc)
        res[f"{nm}|excess"] = dict(live=fl, sim=fs, n=n)
    json.dump(res, open(os.path.expanduser("~/econ2/swap_results.json"), "w"), indent=1, default=float)


def ability_col(c):
    def f(b, d=None):
        b = _c(b); live = np.abs(b["own_ability"]).sum(-1) > 0; b["own_ability"][live, c] = 0.0; return b
    f.__name__ = f"ability_col{c}"; return f


def hero_pkg_off(b, d=None): return f_ability_zero(f_forms_base(b))


def follow():
    """Follow-up on the dominant group: (1) the live excess split by whether my Hero Ice Wizard controller is present (no swap);
    (2) the whole hero package (forms + ability) swapped together, both directions; (3) which ability column carries it."""
    import torch
    from pipeline.model_gen import load_model
    from pipeline.dataset_gen import card_key
    from pipeline.own_ability import ABILITY_COLS
    torch.set_num_threads(16)
    D = pickle.load(open(OUT, "rb")); L, S = D["live"], D["sim"]
    model, st = load_model(CKPT, torch.device("cpu")); model.eval()
    iw = {k: i for i, k in enumerate(st["card_vocab"])}[card_key("IceWizard")]
    rng = np.random.default_rng(7)
    def key(r): return (min(r["ph"], 1), int(r["el"]), r["trig"])
    def fire(rows, res): return np.mean([p > TAU[r["ph"]] for r, (p, t) in zip(rows, res)]) if rows else float("nan")
    sets = {"tank": lambda r: r["trig"] == "their_tank", "form": lambda r: r["form"], "all 2-7": lambda r: True}
    hero = lambda r: bool((np.abs(r["b"]["own_ability"]).sum(-1) > 0).any())
    for nm, sel in sets.items():
        Ls = [r for r in L if sel(r)]; Ss = [r for r in S if sel(r)]
        base_L = run_model(model, Ls); base_S = run_model(model, Ss)
        cs = collections.defaultdict(list)
        for r, (p, t) in zip(Ss, base_S): cs[key(r)].append(p > TAU[r["ph"]])
        def matched(rows, res):         # SIM re-weighted to these live rows' (phase, int elixir, trigger) mix
            k = [(r, p) for r, (p, t) in zip(rows, res) if len(cs.get(key(r), [])) >= 10]
            return np.mean([p > TAU[r["ph"]] for r, p in k]), np.mean([np.mean(cs[key(r)]) for r, p in k]), len(k)
        print(f"\n## [{nm}] live rows with my Hero Ice Wizard controller present vs absent (matched SIM, no swap)")
        for lab, f in (("present", hero), ("absent", lambda r: not hero(r))):
            idx = [i for i, r in enumerate(Ls) if f(r)]
            fl, fs, n = matched([Ls[i] for i in idx], [base_L[i] for i in idx])
            print(f"| {lab} | n {n} | live {fl:.4f} vs SIM {fs:.4f} | excess {fl - fs:+.4f} ({(fl / fs - 1) * 100:+.0f}%) |")
        fl, fs, n = matched(Ls, base_L); ex = fl - fs
        print(f"| all | n {n} | live {fl:.4f} vs SIM {fs:.4f} | excess {ex:+.4f} |")
        b0L, b0S = fire(Ls, base_L), fire(Ss, base_S)
        a = fire(Ls, run_model(model, Ls, hero_pkg_off)); print(f"| LIVE: hero package off (forms base + ability 0) | {b0L:.4f} -> {a:.4f} | share {(b0L - a) / ex * 100:+.0f}% |")
        idx = collections.defaultdict(list)
        for j, r in enumerate(Ls): idx[key(r)].append(j)
        don = [Ls[idx[key(r)][rng.integers(len(idx[key(r)]))]]["b"] if idx.get(key(r)) else r["b"] for r in Ss]
        def pkg_on(b, d): return donor("own_ability")(hero_on(iw)(b), d)
        a = fire(Ss, run_model(model, Ss, pkg_on, don)); print(f"| SIM: hero package on (IW hero form + live ability rows) | {b0S:.4f} -> {a:.4f} | share {(a - b0S) / ex * 100:+.0f}% |")
        for c in range(2, len(ABILITY_COLS)):
            a = fire(Ls, run_model(model, Ls, ability_col(c)))
            print(f"| LIVE: ability column '{ABILITY_COLS[c]}' -> 0 | {b0L:.4f} -> {a:.4f} | share {(b0L - a) / ex * 100:+.0f}% |")
        sys.stdout.flush()


def known(ready, charges, cd):
    def f(b, d=None):                 # Hero IW controller rows with KNOWN readiness (the training convention: ready_known 1, cd >= 0)
        b = _c(b); live = np.abs(b["own_ability"]).sum(-1) > 0
        b["own_ability"][live, 3:7] = (ready, 1.0, charges, cd); return b
    return f


def known_test():
    """Live rows: the unknown-sentinel Hero IW controller rows re-encoded as KNOWN (ready / on cooldown), vs matched SIM."""
    import torch
    from pipeline.model_gen import load_model
    torch.set_num_threads(16)
    D = pickle.load(open(OUT, "rb")); L, S = D["live"], D["sim"]
    model, st = load_model(CKPT, torch.device("cpu")); model.eval()
    def key(r): return (min(r["ph"], 1), int(r["el"]), r["trig"])
    for nm, sel in {"tank": lambda r: r["trig"] == "their_tank", "form": lambda r: r["form"], "all 2-7": lambda r: True}.items():
        Ls = [r for r in L if sel(r)]; Ss = [r for r in S if sel(r)]
        cs = collections.defaultdict(list)
        for r, (p, t) in zip(Ss, run_model(model, Ss)): cs[key(r)].append(p > TAU[r["ph"]])
        def matched(res):
            k = [(r, p) for r, (p, t) in zip(Ls, res) if len(cs.get(key(r), [])) >= 10]
            return np.mean([p > TAU[r["ph"]] for r, p in k]), np.mean([np.mean(cs[key(r)]) for r, p in k])
        fl, fs = matched(run_model(model, Ls)); print(f"\n## [{nm}] live {fl:.4f} vs SIM {fs:.4f} (excess {fl - fs:+.4f})")
        for lab, fn in (("known, ready (1 charge, cd 0)", known(1.0, 1.0, 0.0)), ("known, on cooldown 10 s (0 charges)", known(0.0, 0.0, 10.0)),
                        ("known, ready, 2 charges", known(1.0, 2.0, 0.0))):
            a, _ = matched(run_model(model, Ls, fn))
            print(f"| {lab} | live {fl:.4f} -> {a:.4f} | excess left {a - fs:+.4f} ({(a - fs) / (fl - fs) * 100:.0f}% of it) |")
        sys.stdout.flush()


if __name__ == "__main__":
    {"collect": collect, "swap": swap, "follow": follow, "known": known_test}[sys.argv[1]]()
