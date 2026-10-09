"""--tau-threatened SIM A/B summary: vm_ab.sh output <dir>/{arm}_{evo,lad}/matches.jsonl, paired with base by (census, tag).
    python3 sim_summary.py ~/tau_threat/sim_a
Wins: win 1, draw .5. Deltas are arm - base per pair with a 2000-resample bootstrap 95% interval; sign test on win/loss flips.
Non-inferiority margin on wins: -3 wins per 100 (lower bound of the interval).  M4 = tau_tel.py (10-tick states, STRICT)."""
import json, math, os, random, sys

O = sys.argv[1]
ARMS = [a for a in ("base", "x10", "x15", "x20", "x25") if os.path.isdir(f"{O}/{a}_evo") or os.path.isdir(f"{O}/{a}_lad")]
random.seed(0)


def load(arm):
    out = {}
    for s in ("evo", "lad"):
        p = f"{O}/{arm}_{s}/matches.jsonl"
        if os.path.exists(p):
            for line in open(p):
                r = json.loads(line)
                if r.get("arm") == "plain" and r.get("tau_ok", True):
                    out[(s, r["tag"])] = r
    return out


def score(r): return {"win": 1.0, "draw": 0.5}.get(r["outcome"], 0.0)


def sign_p(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


def boot(v, B=2000):
    v = list(v)
    if not v: return (float("nan"),) * 3
    m = sorted(sum(random.choices(v, k=len(v))) / len(v) for _ in range(B))
    return sum(v) / len(v), m[int(.025 * B)], m[int(.975 * B)]


def fmt(t, d=3): return f"{t[0]:+.{d}f} [{t[1]:+.{d}f},{t[2]:+.{d}f}]"


def tau(r, k): return (r["behaviour"].get("tau") or {}).get(k, 0) or 0


def cards_of(r):
    c = {}
    for ph in (r["behaviour"].get("phase_cards") or {}).values():
        for k, v in ph.items(): c[k] = c.get(k, 0) + v
    return c


def per_match(r):
    pu = r["behaviour"].get("push") or {}
    ec = r["behaviour"].get("economy") or {}
    n_pl = sum(v["plays"] for v in ec.values())
    return dict(win=score(r), hp_lost=tau(r, "hp_lost"), falls=tau(r, "falls"), king=tau(r, "king_fell"),
                lost3=float(r["outcome"] == "loss" and r["crowns_against"] >= 3),
                runover_loss=float(r["outcome"] == "loss" and tau(r, "runover_falls") > 0), runover=tau(r, "runover_falls"),
                m4=tau(r, "m4_strict"), m4_all=tau(r, "m4_all"), m4_s=tau(r, "m4_strict_s"), m4_hp=tau(r, "m4_strict_hp"),
                plays=r["plays_accepted"], tower_diff=r["tower_hp_diff"], mins=r["end_tick"] / 1200.0,
                el_play=(sum(v["plays"] * v["elixir_at_play"] for v in ec.values() if v.get("elixir_at_play") is not None) / n_pl) if n_pl else None,
                push_el=pu.get("big_elixir_at_start", []), cards=cards_of(r), ph1=sum((r["behaviour"].get("economy") or {}).get("1x", {}).get("plays", 0) for _ in (0,)))


D = {a: load(a) for a in ARMS}
base = D["base"]
print(f"base matches {len(base)}; arms: " + ", ".join(f"{a} {len(D[a])}" for a in ARMS))
for a in ARMS:
    if a == "base": continue
    keys = sorted(set(base) & set(D[a]))
    if not keys: continue
    A = [per_match(base[k]) for k in keys]; B = [per_match(D[a][k]) for k in keys]
    up = sum(y["win"] > x["win"] for x, y in zip(A, B)); dn = sum(y["win"] < x["win"] for x, y in zip(A, B))
    dw = boot([y["win"] - x["win"] for x, y in zip(A, B)])
    print(f"\n=== {a} (X={int(a[1:]) / 100:.2f}) vs base, paired n={len(keys)} "
          f"(evo {sum(k[0] == 'evo' for k in keys)}, lad {sum(k[0] == 'lad' for k in keys)})")
    print(f"wins base {sum(x['win'] for x in A):.1f} -> {sum(y['win'] for y in B):.1f} ({sum(y['win'] for y in B) - sum(x['win'] for x in A):+.1f}) | "
          f"better {up} worse {dn} sign p={sign_p(up, dn):.3f} | delta win rate {fmt(dw)}  non-inferior(-0.03): {dw[1] > -0.03}")
    for cen in ("evo", "lad"):
        ks = [i for i, k in enumerate(keys) if k[0] == cen]
        u = sum(B[i]["win"] > A[i]["win"] for i in ks); d = sum(B[i]["win"] < A[i]["win"] for i in ks)
        print(f"   {cen}: base {sum(A[i]['win'] for i in ks):.1f} arm {sum(B[i]['win'] for i in ks):.1f} better {u} worse {d}")
    for name, lab in (("hp_lost", "my tower HP lost / match"), ("falls", "my towers fallen / match"), ("lost3", "three-crown losses / match"),
                      ("runover_loss", "run-over losses / match (proxy)"), ("runover", "run-over falls / match (proxy)"),
                      ("m4", "M4 STRICT runs / match"), ("m4_s", "M4 STRICT seconds / match"), ("m4_hp", "HP lost inside M4 runs / match"),
                      ("plays", "card plays / match"), ("tower_diff", "tower HP diff (for - against) / match")):
        ba = sum(x[name] for x in A) / len(A); bb = sum(y[name] for y in B) / len(B)
        d = boot([y[name] - x[name] for x, y in zip(A, B)])
        print(f"   {lab:42s} base {ba:8.3f} arm {bb:8.3f} delta {fmt(d)}")
    ma, mb = sum(x["mins"] for x in A), sum(y["mins"] for y in B)
    print(f"   M4 STRICT runs per 10 min: base {sum(x['m4'] for x in A) / ma * 10:.2f} arm {sum(y['m4'] for y in B) / mb * 10:.2f}")
    pa = [e for x in A for e in x["push_el"]]; pb = [e for y in B for e in y["push_el"]]
    ea = [x["el_play"] for x in A if x["el_play"] is not None]; eb = [y["el_play"] for y in B if y["el_play"] is not None]
    print(f"   elixir at big-push start: base {sum(pa) / max(len(pa), 1):.2f} (n={len(pa)}) arm {sum(pb) / max(len(pb), 1):.2f} (n={len(pb)}); "
          f"elixir at my plays: base {sum(ea) / max(len(ea), 1):.2f} arm {sum(eb) / max(len(eb), 1):.2f}")
    allc = sorted({c for x in A + B for c in x["cards"]})
    print("   plays per match by card (base -> arm): " + ", ".join(
        f"{c} {sum(x['cards'].get(c, 0) for x in A) / len(A):.2f}->{sum(y['cards'].get(c, 0) for y in B) / len(B):.2f}" for c in allc))
