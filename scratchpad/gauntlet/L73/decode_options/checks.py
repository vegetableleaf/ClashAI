"""L73 decode options: offline teacher-forced checks for tau_phase and xbow_class (R1e u0155, gen_v31_public VAL icebow rows).
Uses the worktree's pipeline/decision_options.py functions (phase_index, xbow_offensive_cells, xbow_class_choice) so the
offline numbers exercise the shipped decision code. Inputs (read-only, main checkout):
  rocket_lead/model_rk.pkl   p_play of every VAL deck-90 row (same ckpt + npz); re-verified here on the X-Bow rows
  forward_xbow.py output     forced X-Bow cell logits on pro X-Bow VAL rows
  xbow_counter/rows.pkl + xbow_switch/pros.pkl / xrows.pkl   replay match -> alive enemy towers, HP lead, pro class
CIs: 2000-draw cluster bootstrap over replays (dataset rep). Below-normal priority, CPU only."""
import json, pickle, sys, zipfile
from pathlib import Path
import numpy as np, torch
WT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(WT))
from pipeline.decision_options import phase_index, xbow_offensive_cells, xbow_class_choice
from pipeline.opp_elixir_count import card_cost
HERE = Path(__file__).resolve().parent
MAIN = Path("C:/Users/benpe/ClashBot")
L73 = MAIN / "scratchpad/gauntlet/L73"
NPZ = MAIN / "icebow/data/pipeline/gen_dataset_v31_public.npz"
XL = Path("C:/Users/benpe/AppData/Local/Temp/claude/C--Users-benpe-ClashBot/f4e7cd66-2122-4134-a1d2-d45291b5bc2a/scratchpad/xbow_logits.npz")
B = 2000
PH = ["1x", "2x", "OT"]; HB = ["deficit(<-10%)", "even", "lead(>+10%)"]
TAUS = {"ctl_.35": (.35, .35, .35), "ctl_.45": (.45, .45, .45), "A(.40,.45,.50)": (.40, .45, .50),
        "B(.35,.45,.55)": (.35, .45, .55), "C(.45,.50,.55)": (.45, .50, .55)}
FLOORS = (0.15, 0.2, 0.3)
OUT, LINES = {}, []
def say(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); LINES.append(s)


def take(zf, name, idx):
    """Chunked row gather (copied from L73/xbow_counter/model_forward.py): never holds the full column."""
    idx = np.asarray(idx)
    with zf.open(name + ".npy") as f:
        ver = np.lib.format.read_magic(f)
        shape, _, dt = (np.lib.format.read_array_header_1_0(f) if ver == (1, 0) else np.lib.format.read_array_header_2_0(f))
        rb = int(np.prod(shape[1:], dtype=np.int64)) * dt.itemsize
        out = np.empty((len(idx),) + tuple(shape[1:]), dt); step = max(1, (96 << 20) // max(rb, 1)); o = 0
        for lo in range(0, shape[0], step):
            n = min(step, shape[0] - lo); buf = bytearray()
            while len(buf) < n * rb:
                c = f.read(n * rb - len(buf))
                if not c: raise EOFError(name)
                buf += c
            a, b = np.searchsorted(idx, [lo, lo + n])
            if b > a:
                out[o:o + b - a] = np.frombuffer(buf, dt).reshape((n,) + tuple(shape[1:]))[idx[a:b] - lo]; o += b - a
    return out


class Boot:
    """Cluster bootstrap: per-cluster sums, one shared resample matrix (paired comparisons share draws)."""
    def __init__(self, clusters, seed):
        self.u, self.ci = np.unique(clusters, return_inverse=True)
        rng = np.random.default_rng(seed)
        S = rng.integers(0, len(self.u), (B, len(self.u)))
        self.W = np.zeros((B, len(self.u)))
        np.add.at(self.W, (np.repeat(np.arange(B), len(self.u)), S.ravel()), 1)
    def sums(self, v):
        return np.bincount(self.ci, weights=np.asarray(v, float), minlength=len(self.u))
    def ratio(self, num, den):
        n, d = self.sums(num), self.sums(den)
        if d.sum() == 0: return [None, None, None, 0]
        bn, bd = self.W @ n, self.W @ d; ok = bd > 0; r = bn[ok] / bd[ok]
        return [float(n.sum() / d.sum()), float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5)), int(round(d.sum()))]
    def diff(self, na, da, nb, db):
        a, b_, c, d = (self.sums(x) for x in (na, da, nb, db))
        if b_.sum() == 0 or d.sum() == 0: return [None, None, None]
        A, Bd, C, D = (self.W @ x for x in (a, b_, c, d)); ok = (Bd > 0) & (D > 0); r = A[ok] / Bd[ok] - C[ok] / D[ok]
        return [float(a.sum() / b_.sum() - c.sum() / d.sum()), float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))]
    def median(self, v, mask):
        v, m = np.asarray(v, float)[mask], np.asarray(mask)
        ci = self.ci[m]; o = np.argsort(v); v, ci = v[o], ci[o]
        def wmed(w):
            c = np.cumsum(w); return v[np.searchsorted(c, c[-1] / 2)] if c[-1] > 0 else np.nan
        bs = np.array([wmed(self.W[b, ci]) for b in range(B)])
        return [float(np.median(v)), float(np.nanpercentile(bs, 2.5)), float(np.nanpercentile(bs, 97.5)), int(m.sum())]


def f3(t, pct=True):
    if t is None or t[0] is None: return "n/a"
    g = (lambda v: f"{100*v:5.1f}%") if pct else (lambda v: f"{v:5.2f}")
    return f"{g(t[0])} [{g(t[1])},{g(t[2])}]" + (f" n={t[3]}" if len(t) > 3 else "")


# ======================================================================== data
zf = zipfile.ZipFile(NPZ); z = np.load(NPZ, allow_pickle=False)
CV = json.loads(str(z["meta"]))["card_vocab"]; RK, XB = CV.index("rocket"), CV.index("x-bow")
val = np.flatnonzero((z["deck_id"] == 90) & (z["split"] == 1))
MR = pickle.load(open(L73 / "rocket_lead/model_rk.pkl", "rb"))
assert np.array_equal(MR["sel"], val), "model_rk.pkl rows are not the VAL deck-90 rows"
yg, yc, tick, rep, side = (take(zf, k, val).astype(np.int64) for k in ("y_gate", "y_card", "tick", "rep", "side"))
hand = take(zf, "hand_card", val).astype(np.int64); el = np.floor(take(zf, "sc", val)[:, 3] * 10 + 1e-3)
say(f"VAL deck-90 rows {len(val)}, replays {len(np.unique(rep))}, elixir range {el.min():.0f}..{el.max():.0f}")
COST = np.zeros(len(CV))
for i, c in enumerate(CV):
    if i: COST[i] = card_cost(c.replace("-", "_")) or 0.0
any_aff = ((hand > 0) & (COST[hand] <= el[:, None] + 1e-6)).any(1)
assert np.array_equal(any_aff, MR["any_aff"]), "affordability differs from model_rk.pkl"
p = MR["p_play"]; ph = phase_index(tick / 20.0)
rk_elig = (hand == RK).any(1) & (el >= 6)

# ======================================================================== A. tau_phase
say("\n===== A. tau_phase (teacher-forced gate on every VAL row; PLAY = an affordable card and P(play) > tau of the row's phase;"
    " anti-stall not modelled offline)")
order = np.lexsort((tick, side, rep)); seq = rep * 2 + side
inv = np.empty_like(order); inv[order] = np.arange(len(order))
def next_true(flag):
    """index (original) of the first row at or after each row in the same (rep, side) game where flag holds, else -1"""
    f, s = flag[order], seq[order]; nxt = np.full(len(order), -1); cur = -1
    for k in range(len(order) - 1, -1, -1):
        if k == len(order) - 1 or s[k] != s[k + 1]: cur = -1
        if f[k]: cur = k
        nxt[k] = cur
    out = np.where(nxt >= 0, order[np.maximum(nxt, 0)], -1)
    return out[inv]
last = np.empty(len(order), np.int64); s_ = seq[order]
for k in range(len(order) - 1, -1, -1):
    last[k] = order[k] if (k == len(order) - 1 or s_[k] != s_[k + 1]) else last[k + 1]
last = last[inv]
nxt_pro = next_true(yg == 1)
bootA = Boot(rep, 11)
res = {}
pro_wait = yg == 0
for name, taus in TAUS.items():
    play = any_aff & (p > np.asarray(taus)[ph])
    nm = next_true(play)
    end = np.where(nxt_pro >= 0, nxt_pro, last)                  # window closes at the pro's next play
    within = (nm >= 0) & (inv[np.maximum(nm, 0)] <= inv[end])
    j = np.where(within, nm, end)
    proxy, cens = el[j], ~within
    r = {}
    for k, lab in [(None, "all")] + list(enumerate(PH)):
        m = np.ones(len(p), bool) if k is None else ph == k
        w = m & pro_wait
        r[lab] = {"play_rate": bootA.ratio(play & m, m), "pro_play_rate": bootA.ratio((yg == 1) & m, m),
                  "play_rate_minus_pro": bootA.diff(play & m, m, (yg == 1) & m, m),
                  "agreement": bootA.ratio((play == (yg == 1)) & m, m), "pro_play_kept": bootA.ratio(play & (yg == 1) & m, (yg == 1) & m),
                  "wait_rows_next_play_elixir": bootA.ratio(np.where(w, proxy, 0), w), "wait_rows_proxy_censored": bootA.ratio(cens & w, w),
                  "wait_rows_proxy_rocket_eligible": bootA.ratio(w & rk_elig[j], w),
                  "rocket_eligible_at_play": bootA.ratio(play & rk_elig & m, play & m),
                  "pro_rocket_eligible_at_play": bootA.ratio((yg == 1) & rk_elig & m, (yg == 1) & m)}
    res[name] = r
OUT["A_tau_phase"] = res
# paired differences vs the .35 control for agreement and kept
ctl = any_aff & (p > .35)
for name, taus in TAUS.items():
    play = any_aff & (p > np.asarray(taus)[ph])
    for k, lab in [(None, "all")] + list(enumerate(PH)):
        m = np.ones(len(p), bool) if k is None else ph == k
        res[name][lab]["agreement_minus_ctl.35"] = bootA.diff((play == (yg == 1)) & m, m, (ctl == (yg == 1)) & m, m)
for lab in ["all"] + PH:
    say(f"--- phase {lab}: pros PLAY rate {f3(res['ctl_.35'][lab]['pro_play_rate'])}; pros Rocket-eligible at play {f3(res['ctl_.35'][lab]['pro_rocket_eligible_at_play'])}")
    say(f"{'set':16s} {'PLAY rate':26s} {'minus pros (pp)':24s} {'agree w/ pros':26s} {'agree - ctl.35':24s} {'pro-PLAY kept':26s} {'wait rows: next-play elixir':30s} {'censored':24s} {'Rocket-elig at play':26s}")
    for name in TAUS:
        d = res[name][lab]
        say(f"{name:16s} {f3(d['play_rate'])[:26]:26s} {f3(d['play_rate_minus_pro']):24s} {f3(d['agreement'])[:26]:26s} {f3(d['agreement_minus_ctl.35']):24s} "
            f"{f3(d['pro_play_kept'])[:26]:26s} {f3(d['wait_rows_next_play_elixir'], False)[:30]:30s} {f3(d['wait_rows_proxy_censored'])[:24]:24s} {f3(d['rocket_eligible_at_play'])[:26]:26s}")

# ======================================================================== B. xbow_class
say("\n===== B. xbow_class on pro X-Bow VAL rows (card forced to X-Bow; classes from alive enemy towers, reach 13.0384+1e-4 tiles)")
X = np.load(XL)
assert np.all(np.isin(X["sel"], val))
pos = np.searchsorted(val, X["sel"])
dp = float(np.abs(X["p_play"] - p[pos]).max()); say(f"p_play re-verified on {len(pos)} X-Bow rows: max |diff| vs model_rk.pkl = {dp:.2e}")
assert dp < 1e-4
R = pickle.load(open(L73 / "xbow_counter/rows.pkl", "rb")); P = pickle.load(open(L73 / "xbow_switch/pros.pkl", "rb"))
XP = pickle.load(open(L73 / "xbow_switch/xrows.pkl", "rb"))["pros_all"]
inv_name = {"Skeletons": "skeletons", "IceWizard": "ice-wizard", "Knight": "knight", "Log": "the-log", "Tesla": "tesla", "Xbow": "x-bow", "Tornado": "tornado", "Rocket": "rocket"}
sig = {}
for i in np.flatnonzero(R["y_gate"] == 1):
    sig.setdefault((int(R["rep"][i]), int(R["side"][i])), []).append((int(R["tick"][i]), R["CV"][int(R["y_card"][i])]))
sigidx = {tuple(v[:6]): k for k, v in sig.items()}
game = {}
for M in P:
    k = sigidx.get(tuple((q["tick"], inv_name[q["name"]]) for q in M["plays"][:6]))
    if k is not None: game[k] = M
def hp_at(M, k, t):
    i = int(np.searchsorted(M["T"], t, "right")) - 1
    return float(M["MX"][k]) if i < 0 else float(M["HP"][k][i])
rows = []
for r in range(len(pos)):
    key = (int(X["rep"][r]), int(X["side"][r])); M = game.get(key)
    if M is None or X["y_cell"][r] < 0: continue
    t = int(X["tick"][r]); a = {k: hp_at(M, k, t) > 0 for k in ("eK", "eL", "eR")}
    hl = (sum(hp_at(M, k, t) for k in ("mK", "mL", "mR")) - sum(hp_at(M, k, t) for k in ("eK", "eL", "eR"))) / sum(M["MX"][k] for k in ("eK", "eL", "eR"))
    xc = {q["tick"]: q["cls"] for q in XP.get(M["id"], [])}.get(t)
    rows.append((r, a, hl, xc))
say(f"pro X-Bow VAL rows {len(pos)}; replay-matched with a pro cell {len(rows)}")
# frame check: the dataset cell frame vs the replay's L/R labels (model_forward used x = 18 - cx/2, i.e. mirrored)
def cls_geo(alive_board, cell): return not xbow_offensive_cells(alive_board, "lattice")[cell]
for lab, f in (("mirrored (K, eR, eL)", lambda a: (a["eK"], a["eR"], a["eL"])), ("unmirrored (K, eL, eR)", lambda a: (a["eK"], a["eL"], a["eR"]))):
    ok = [(cls_geo(f(a), int(X["y_cell"][r])) == (xc == "def")) for r, a, hl, xc in rows if xc in ("off", "def")]
    say(f"pro class from y_cell, tower frame {lab}: agreement with xbow_switch label {np.mean(ok):.4f} (n={len(ok)})")
    OUT.setdefault("frame_check", {})[lab] = [float(np.mean(ok)), len(ok)]
board = lambda a: (a["eK"], a["eR"], a["eL"])
n = len(rows); ri = np.array([r for r, *_ in rows])
logits = torch.from_numpy(X["logits"][ri]).double()
pro_cell = X["y_cell"][ri].astype(int); clus = X["rep"][ri]
phx = phase_index(X["tick"][ri] / 20.0); hlv = np.array([hl for _, _, hl, _ in rows]); hb = np.where(hlv < -.1, 0, np.where(hlv > .1, 2, 1))
offm = np.stack([xbow_offensive_cells(board(a), "lattice") for _, a, _, _ in rows])
prob = logits.softmax(-1).numpy()
D = (prob * ~offm).sum(1)
pro_def = ~offm[np.arange(n), pro_cell]
xs_def = np.array([xc == "def" for *_, xc in rows]); xs_ok = np.array([xc in ("off", "def") for *_, xc in rows])
arg_cell = logits.argmax(1).numpy(); arg_def = ~offm[np.arange(n), arg_cell]
def tiles(c): return np.stack([c % 36, c // 36], 1) / 2.0
dist = lambda c: np.hypot(*(tiles(c) - tiles(pro_cell)).T)
ordr = np.lexsort((X["tick"][ri], X["side"][ri], clus))
cidx = {c: i for i, c in enumerate(np.unique(clus))}
arms = {"argmax": dict(cell=arg_cell, dfn=arg_def, exp=arg_def.astype(float), samp=np.zeros(n, bool))}
for f in FLOORS:
    rngs = {c: np.random.default_rng([2026, i]) for c, i in cidx.items()}
    cell = np.zeros(n, int); dfn = np.zeros(n, bool); samp = np.zeros(n, bool)
    for r in ordr:                       # game order inside each replay: one seeded stream per replay
        cell[r], dfn[r], samp[r] = xbow_class_choice(logits[r], offm[r], f, rngs[clus[r]])
    exp = np.where(samp, D, (D > .5).astype(float))
    arms[f"class_sample f={f}"] = dict(cell=cell, dfn=dfn, exp=exp, samp=samp)
bootB = Boot(clus, 12)
one = np.ones(n, bool)
res = {"n_rows": n, "replays": len(cidx), "pros_def_share_geometric": bootB.ratio(pro_def, one),
       "pros_def_share_xbow_switch_label": bootB.ratio(xs_def & xs_ok, xs_ok), "model_def_mass_mean": bootB.ratio(D, one),
       "share_rows_min_class_mass_ge": {str(f): bootB.ratio(np.minimum(D, 1 - D) >= f, one) for f in FLOORS}, "arms": {}}
say(f"rows {n}, replays {len(cidx)} | pros def share (geometric, y_cell) {f3(res['pros_def_share_geometric'])} | (xbow_switch label) {f3(res['pros_def_share_xbow_switch_label'])}"
    f" | model mean defensive mass D {f3(res['model_def_mass_mean'])}")
say("rows with min(D,1-D) >= f: " + ", ".join(f"f={f}: {f3(res['share_rows_min_class_mass_ge'][str(f)])}" for f in FLOORS))
say(f"{'arm':22s} {'class agree w/ pro':27s} {'minus argmax (pp)':24s} {'expected agree':26s} {'def share':27s} {'median dist (tiles)':26s} {'<=1 tile':26s} {'changed vs argmax':26s} {'minority drawn, mass<.3':26s}")
for name, a in arms.items():
    agree = a["dfn"] == pro_def; eagree = np.where(pro_def, a["exp"], 1 - a["exp"])
    chosen_mass = np.where(a["dfn"], D, 1 - D); minority = a["samp"] & (chosen_mass < .5) & (chosen_mass < .3)
    d = dist(a["cell"])
    a_res = {"class_agreement": bootB.ratio(agree, one), "agreement_minus_argmax": bootB.diff(agree, one, arg_def == pro_def, one),
             "expected_agreement": bootB.ratio(eagree, one), "def_share": bootB.ratio(a["dfn"], one), "expected_def_share": bootB.ratio(a["exp"], one),
             "median_dist_tiles": bootB.median(d, one), "within_1_tile": bootB.ratio(d <= 1.0 + 1e-9, one),
             "within_1_tile_minus_argmax": bootB.diff(d <= 1.0 + 1e-9, one, dist(arg_cell) <= 1.0 + 1e-9, one),
             "changed_vs_argmax": bootB.ratio(a["cell"] != arg_cell, one), "class_changed_vs_argmax": bootB.ratio(a["dfn"] != arg_def, one),
             "minority_drawn_mass_lt_.3": bootB.ratio(minority, one), "sampled_rows": bootB.ratio(a["samp"], one), "bins": {}}
    for h in range(3):
        for k in range(-1, 3):
            m = (hb == h) & ((phx == k) if k >= 0 else True)
            a_res["bins"][f"{HB[h]}|{'all' if k < 0 else PH[k]}"] = {"def": bootB.ratio(a["dfn"] & m, m), "expected_def": bootB.ratio(np.where(m, a["exp"], 0), m),
                                                                     "pros_def": bootB.ratio(pro_def & m, m), "minus_pros": bootB.diff(a["dfn"] & m, m, pro_def & m, m),
                                                                     "model_D": bootB.ratio(np.where(m, D, 0), m)}
    for k in range(3):
        m = phx == k
        a_res["bins"][f"all|{PH[k]}"] = {"def": bootB.ratio(a["dfn"] & m, m), "expected_def": bootB.ratio(np.where(m, a["exp"], 0), m), "pros_def": bootB.ratio(pro_def & m, m),
                                         "minus_pros": bootB.diff(a["dfn"] & m, m, pro_def & m, m), "model_D": bootB.ratio(np.where(m, D, 0), m)}
    res["arms"][name] = a_res
    say(f"{name:22s} {f3(a_res['class_agreement']):27s} {f3(a_res['agreement_minus_argmax']):24s} {f3(a_res['expected_agreement'])[:26]:26s} {f3(a_res['def_share']):27s} "
        f"{f3(a_res['median_dist_tiles'], False)[:26]:26s} {f3(a_res['within_1_tile'])[:26]:26s} {f3(a_res['changed_vs_argmax'])[:26]:26s} {f3(a_res['minority_drawn_mass_lt_.3'])[:26]:26s}")
say("\n--- realized defensive share by tower-HP lead x phase (pros = geometric class of the pro cell; D = model defensive mass)")
keys = list(res["arms"]["argmax"]["bins"])
say(f"{'bin':24s} {'pros':26s} {'model D':26s} " + " ".join(f"{nm:27s}" for nm in arms))
for key in keys:
    b0 = res["arms"]["argmax"]["bins"][key]
    say(f"{key:24s} {f3(b0['pros_def']):26s} {f3(b0['model_D'])[:26]:26s} " + " ".join(f"{f3(res['arms'][nm]['bins'][key]['def']):27s}" for nm in arms))
OUT["B_xbow_class"] = res
json.dump(OUT, open(HERE / "results.json", "w"), indent=1)
(HERE / "show_out.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")
say("saved results.json + show_out.txt")
