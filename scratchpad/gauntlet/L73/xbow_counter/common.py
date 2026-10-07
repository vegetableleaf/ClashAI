"""Shared loaders/helpers for the X-Bow counter study (L73). Read-only on pipeline/ and on xbow_switch outputs."""
import sys, pickle, json, math, re, bisect, ctypes
import numpy as np
try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception: pass
HERE = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_counter/"
XS = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_switch/"
sys.path.insert(0, XS); sys.path.insert(0, "C:/Users/benpe/ClashBot")
import analyze as A
from pipeline.opp_elixir_count import card_cost, card_db, OppElixirCounter
RNG = np.random.default_rng(11); B = 2000
def norm(s): return re.sub(r"[^a-z]", "", s.lower().split("@")[0])

_cv = None
def cv():
    global _cv
    if _cv is None: _cv = pickle.load(open(HERE + "rows.pkl", "rb"))["CV"]
    return _cv
def cost_of(name):
    try: c = card_cost(name.replace("-", "_")); return float(c) if c is not None else None
    except Exception: return None
_cost = {}
def cost_n(nm):  # by normalised name
    if not _cost:
        for c in cv():
            if c != "<pad>": _cost[norm(c)] = cost_of(c)
    return _cost.get(nm)
_spell = {}
def is_spell(nm):
    if not _spell:
        for c in cv():
            if c == "<pad>": continue
            try: _spell[norm(c)] = card_db().kind(c.replace("-", "_")) == "spell"
            except Exception: _spell[norm(c)] = False
    return _spell.get(nm, False)

def load_all():
    P = pickle.load(open(XS + "pros.pkl", "rb")); Bt = pickle.load(open(XS + "bot.pkl", "rb"))
    for M in Bt:
        for p in M["plays"]: p["x"] = math.floor(p["x"]) + 0.5; p["y"] = math.floor(p["y"]) + 0.5
    X = pickle.load(open(XS + "xrows.pkl", "rb"))
    return P, Bt, X["pros_all"], X["bot"]

# ---------- public cycle / availability (exactly the opp_cycle semantics: distinct cards latest first, plays_since = later opp plays)
def cycle_from_plays(plays, tick):
    """plays: sorted [(tick, card, ...)]. returns [(norm_card, plays_since)] latest first, up to 8 distinct."""
    ts = [p[0] for p in plays]; n = bisect.bisect_left(ts, tick)
    seen = set(); out = []
    for j in range(n - 1, -1, -1):
        c = norm(plays[j][1])
        if c in seen: continue
        if len(seen) == 8: break
        seen.add(c); out.append((c, sum(1 for t in ts[:n] if t > ts[j])))
    return out

def est_bot(o, t):
    T, E = o["ticks"], o["estimates"]; i = bisect.bisect_left(T, int(t)) - 1
    c = OppElixirCounter()
    if i >= 0: c.tick, c.est = T[i], E[i]
    return float(c.at(int(t)))

def avail(cyc, est, Cn):
    """cyc [(norm, plays_since)], est = public elixir estimate, Cn = set of normalised counter names.
    group: A1 known-in-hand & affordable; A2 known-in-hand but est < cost; A0k no C known in hand and all 8 cards seen;
    A0u no C known in hand and < 8 seen (an unseen C card could be in hand)."""
    nseen = len(cyc); status = "known" if nseen >= 8 else ("partly" if nseen >= 4 else "unknown")
    inhand = [(c, ps) for c, ps in cyc if c in Cn and ps >= 4]
    if inhand:
        aff = [c for c, ps in inhand if est >= (cost_n(c) or 99)]
        g = "A1" if aff else "A2"
    else: g = "A0k" if nseen >= 8 else "A0u"
    return {"group": g, "status": status, "nseen": nseen, "C": [c for c, _ in inhand]}

# ---------- bootstrap
def rows_to_arrays(U, rows):
    idx = {c: i for i, c in enumerate(U)}; num = np.zeros(len(U)); den = np.zeros(len(U))
    for c, n, d in rows: num[idx[c]] += n; den[idx[c]] += d
    return num, den
def rci(U, rows):
    num, den = rows_to_arrays(U, rows)
    return _ci(num, den, np.arange(len(U)))
def _ci(num, den, _):
    if den.sum() == 0: return [None, None, None, 0, 0]
    S = RNG.integers(0, len(num), (B, len(num))); dn = den[S].sum(1); ok = dn > 0
    r = num[S].sum(1)[ok] / dn[ok]
    return [float(num.sum() / den.sum()), float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5)), float(num.sum()), float(den.sum())]
def diff_ci(U, ra, rb):
    """ratio_a - ratio_b with shared cluster resampling."""
    na, da = rows_to_arrays(U, ra); nb, db = rows_to_arrays(U, rb)
    if da.sum() == 0 or db.sum() == 0: return [None, None, None]
    S = RNG.integers(0, len(U), (B, len(U)))
    A_, B_ = da[S].sum(1), db[S].sum(1); ok = (A_ > 0) & (B_ > 0)
    d = na[S].sum(1)[ok] / A_[ok] - nb[S].sum(1)[ok] / B_[ok]
    return [float(na.sum() / da.sum() - nb.sum() / db.sum()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]
def mean_ci(U, rows):  # rows (cluster, value) -> mean with cluster bootstrap
    return rci(U, [(c, v, 1) for c, v in rows])
def fm(t, pct=True):
    if t is None or t[0] is None: return "n/a"
    f = (lambda v: f"{100*v:.0f}%") if pct else (lambda v: f"{v:.2f}")
    return f"{f(t[0])} [{f(t[1])},{f(t[2])}] n={int(t[4])}" if len(t) > 4 else f"{f(t[0])} [{f(t[1])},{f(t[2])}]"

def indep_diff(U1, r1, U2, r2):
    """ratio1 - ratio2 for two independent cluster universes (different sources)."""
    n1, d1 = rows_to_arrays(U1, r1); n2, d2 = rows_to_arrays(U2, r2)
    if d1.sum() == 0 or d2.sum() == 0: return [None, None, None]
    S1 = RNG.integers(0, len(U1), (B, len(U1))); S2 = RNG.integers(0, len(U2), (B, len(U2)))
    a, b = d1[S1].sum(1), d2[S2].sum(1); ok = (a > 0) & (b > 0)
    d = n1[S1].sum(1)[ok] / a[ok] - n2[S2].sum(1)[ok] / b[ok]
    return [float(n1.sum() / d1.sum() - n2.sum() / d2.sum()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]

def std_diff(U, rows_a, rows_b, key_ph, weights=None):
    """Phase-standardised difference of ratios. rows_*: (cluster, phase, num, den). Weights = pooled den share per phase (a+b)."""
    PH = ["1x", "2x", "OT"]; idx = {c: i for i, c in enumerate(U)}
    arr = np.zeros((len(U), 3, 2, 2))
    for g, rows in enumerate((rows_a, rows_b)):
        for c, ph, n, d in rows: arr[idx[c], PH.index(ph), g, 0] += n; arr[idx[c], PH.index(ph), g, 1] += d
    def est(a):
        tot = a.sum(0)  # [3,2,2]
        w = tot[:, :, 1].sum(1); ok = (tot[:, 0, 1] > 0) & (tot[:, 1, 1] > 0)
        if not ok.any(): return np.nan
        r = tot[:, 0, 0] / np.where(tot[:, 0, 1] > 0, tot[:, 0, 1], 1) - tot[:, 1, 0] / np.where(tot[:, 1, 1] > 0, tot[:, 1, 1], 1)
        return float((r * w * ok).sum() / (w * ok).sum())
    pt = est(arr); S = RNG.integers(0, len(U), (B, len(U)))
    bs = np.array([est(arr[s]) for s in S[:1000]]); bs = bs[~np.isnan(bs)]
    return [pt, float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]

def mh_rr(U, rows_a, rows_b):
    """Mantel-Haenszel risk/rate ratio A/B stratified by phase, cluster bootstrap. rows: (cluster, phase, events, exposure)."""
    PH3 = ["1x", "2x", "OT"]; idx = {c: i for i, c in enumerate(U)}
    arr = np.zeros((len(U), 3, 2, 2))
    for g, rows in enumerate((rows_a, rows_b)):
        for c, ph, n, d in rows: arr[idx[c], PH3.index(ph), g, 0] += n; arr[idx[c], PH3.index(ph), g, 1] += d
    def est(a):
        t = a.sum(0); T = t[:, 0, 1] + t[:, 1, 1]; T = np.where(T > 0, T, 1)
        num = (t[:, 0, 0] * t[:, 1, 1] / T).sum(); den = (t[:, 1, 0] * t[:, 0, 1] / T).sum()
        return num / den if den > 0 else np.nan
    pt = est(arr); S = RNG.integers(0, len(U), (1000, len(U)))
    bs = np.array([est(arr[s]) for s in S]); bs = bs[~np.isnan(bs)]
    return [float(pt), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
