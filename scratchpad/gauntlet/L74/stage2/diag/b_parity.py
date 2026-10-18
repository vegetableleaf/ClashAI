"""S2-05(b): per-archetype SIM-live win gap (E4 promotion rows vs live, CXXIV 12k: the only band with >= 10 live matches in
~13 styles) vs per-archetype opponent-card fight parity (FIN9 strict scoreboard 'opp <card>' anchor outcome_agree, n >= 10;
else the mean of all opp anchors), each deck weighted by its live count in mix/decks_live_eval.json. Spearman over styles.
WEAK by construction (~13 points, parity is per card not per matchup). Read-only."""
import collections, ctypes, json, sys
try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)
except Exception: pass
sys.path[:0] = ["C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/stage2/gate", "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/live_eval"]
import gate_fit as G
from live_eval import classify
SB = json.load(open("C:/Users/benpe/pod_backup_weekend/parity1016/FIN9_stamped/scoreboard_strict.json"))["groups"]
anc = {g["group"][4:]: g for g in SB if g["kind"] == "anchor" and g["group"].startswith("opp ") and g["n"] >= 10}
mean_opp = sum(g["outcome_agree"] * g["n"] for g in anc.values()) / sum(g["n"] for g in anc.values())
def card_par(c):
    base, _, form = c.partition("@")
    k = base + {"evolution": " evo", "hero": " hero"}.get(form, "")
    return anc[k]["outcome_agree"] if k in anc else anc[base]["outcome_agree"] if base in anc else mean_opp
P = json.load(open("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/mix/decks_live_eval.json"))["decks"]
par, w = collections.defaultdict(float), collections.Counter()
for d in P:
    s = classify([c.split("@")[0] for c in d["engine"]]); par[s] += d["n_live"] * sum(map(card_par, d["engine"])) / 8; w[s] += d["n_live"]
Lv = G.live("CXXIV", "12k"); Sm = G.sim("C:/Users/benpe/pod_backup_weekend/pod1017_factorial/ref_u250/eval/ref_u250_74*/D3/matches.jsonl")
pts = []
for s, n in collections.Counter(r[1] for r in Lv).items():
    k, m = G.kn(Sm, lambda r: r[1] == s)
    if n < 10 or m < 10: continue
    lw = sum(r[0] for r in Lv if r[1] == s) / n; pts.append((s, k / m - lw, par[s] / w[s] if w[s] else mean_opp, n))
def rank(v):   # average ranks (ties share)
    o = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v)
    for x in set(v):
        idx = [i for i in range(len(v)) if v[i] == x]; pos = [o.index(i) for i in idx]; m = sum(pos) / len(pos)
        for i in idx: r[i] = m
    return r
ra, rb = rank([p[1] for p in pts]), rank([p[2] for p in pts])
n = len(pts); rho = 1 - 6 * sum((ra[i] - rb[i]) ** 2 for i in range(n)) / (n * (n * n - 1))
for s, g, pa, nl in sorted(pts, key=lambda p: p[1]):
    print(f"  {s[:28]:28s} live n {nl:3d}  SIM-live gap {g * 100:+6.1f} pp   opp-card parity {pa:.3f}")
print(f"Spearman rho (gap vs parity) = {rho:+.2f} over {n} styles (|rho| > 0.59 needed for two-sided p < .05 at n = 12): "
      f"{'a NEGATIVE rho = worse parity, bigger SIM optimism' if rho < 0 else 'no support for parity driving the gap'}")
