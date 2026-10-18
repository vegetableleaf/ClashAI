"""S2-04 live-side fault audit: are the two live gaps (13k Hog overtime; non-Hog regulation) partly OUR live pipeline, not
opponent skill? Read-only. Rows = loss_review review.features (L74/loss_review/matches.jsonl + audit/rows35.jsonl, the 35
gated logs newer than that ledger, parsed ON A POD by parse_rows.py); results / band / OT / archetype = gate/live_targets.json
(ladder-graded, the gate's own rows).
Per LOSS, the deciding push = the threat episode (>= 7 elixir of enemy bodies on our half) in which the deciding tower fell
(OT loss: the first own tower down at >= 180 s; regulation loss: the last own tower down before 180 s); flags on it:
  stall      no confirmed own play in the 10 s before the push started (PLAN: "> 10 s without a play before the losing push")
  gate_stuck the gate sat below its threshold >= 3 s with an affordable card before our first answer (review 'below3')
  no_answer  no own play within 10 s of the push start            low_el  our elixir < 4 when the push arrived
  starved    a cpu_starved event (live loop over budget; audit/starved_ticks.txt, grep of the logs) from 10 s before the push
             start to 3 s after its end
per match (reported, not in the fault flag): reader = cpu_starved anywhere / reader_closed / >= 3 unconfirmed plays (a >= 5 s
  freeze at >= 9.5 elixir is not used at all: the first run showed it MORE often in wins, 43% vs 14% -- holding a lead).
decision latency = median decide_ms. OWN-SIDE FAULT = stall | gate_stuck | starved (low_el / no_answer reported apart:
they can be our over-commit OR the opponent's timing). Base rate = the same flags on the most damaging push of the WINS --
of the cell, and (stable n) of ALL wins of the same Mark / band (used for the explained share).
Explained share (upper bound) = excess fault losses / n  /  the cell's SIM-live gap (every excess fault loss turned into a win).
    icebow/.venv/Scripts/python.exe audit/live_side.py > audit/live_side.out"""
import ctypes, glob, json, os, statistics, sys
try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)
except Exception: pass
H = os.path.dirname(os.path.abspath(__file__)); R = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/"
sys.path.insert(0, R + "stage2/gate")
import gate_fit as G
X = [x for x in json.load(open(R + "stage2/gate/live_targets.json")) if x["src"] == "ladder" and x["start"] is not None]
sel = {x["file"]: x for x in X if (x["mark"] == "CXXXVIII" and x["start"] >= 13000) or (x["mark"] == "CXXIV" and 12000 <= x["start"] < 13000)}
F = {}
for l in open(R + "loss_review/matches.jsonl"):
    if l[10:60].split('"')[0] in sel: r = json.loads(l); F[r["file"]] = r
for l in open(os.path.join(H, "rows35.jsonl")):
    r = json.loads(l); F[r["file"]] = r
miss = sorted(set(sel) - set(F)); assert not miss, miss[:5]
ST = {}
for l in open(os.path.join(H, "starved_ticks.txt")):
    f_, t_ = l.split(); ST.setdefault(f_, []).append(int(t_))


def deciding(r, x):
    d = r.get("dead_s") or {}
    mine = sorted(v for k, v in d.items() if k[0] == "m" and v is not None)
    t = ([v for v in mine if v >= 180] or [None])[0] if x["ot"] else ([v for v in mine if v < 180] or [None])[-1]
    th = r.get("threats") or []
    if t is None:
        return max(th, key=lambda e: e.get("hp_lost") or 0) if th else None
    T = t * 20
    hit = [e for e in th if e["t"] <= T <= e["t_end"] + 60 and e.get("tower_fell")]
    return hit[-1] if hit else ([e for e in th if e["t"] <= T] or [None])[-1]


def flags(r, x, win):
    e = (max(r.get("threats") or [], key=lambda e: e.get("hp_lost") or 0, default=None) if win else deciding(r, x))
    rd = (r.get("starved") or 0) > 0 or (r.get("reader_closed") or 0) > 0 or (r.get("n_unconf") or 0) >= 3   # freeze >= 5 s dropped: it is MORE common in wins (holding a lead)
    f = dict(push=e is not None, stall=bool(e) and not e.get("pre_cards"), gate_stuck=bool(e) and bool(e.get("below3")),
             no_answer=bool(e) and e.get("rsp") is None, low_el=bool(e) and e.get("el") is not None and e["el"] < 4, reader=rd,
             starved=bool(e) and any(e["t"] - 200 <= t <= e["t_end"] + 60 for t in ST.get(r["file"], [])))
    f["fault"] = f["stall"] or f["gate_stuck"] or f["starved"]
    return f, r.get("decide_ms_med"), (e or {}).get("el")


CELLS = [("13k Hog overtime", "CXXXVIII", lambda x: x["cls"].startswith("Hog") and x["ot"]),
         ("12k Hog overtime (CXXIV, reference)", "CXXIV", lambda x: x["cls"].startswith("Hog") and x["ot"]),
         ("13k non-Hog regulation", "CXXXVIII", lambda x: not x["cls"].startswith("Hog") and not x["ot"]),
         ("12k non-Hog regulation", "CXXIV", lambda x: not x["cls"].startswith("Hog") and not x["ot"])]
GAP = {"13k Hog overtime": None, "13k non-Hog regulation": None, "12k non-Hog regulation": None}
KEYS = ("fault", "stall", "gate_stuck", "starved", "reader", "no_answer", "low_el")
print("S2-04 live-side fault audit (ladder-graded gated matches; flags defined in the docstring)\n")
summary = {}
for name, mk, f in CELLS:
    Q = [x for x in sel.values() if x["mark"] == mk and f(x)]
    L = [x for x in Q if x["res"] != "WIN"]; W = [x for x in Q if x["res"] == "WIN"]
    fl = [flags(F[x["file"]], x, False) for x in L]; fw = [flags(F[x["file"]], x, True) for x in W]
    print(f"== {name}: {len(Q)} matches, {len(W)} won, {len(L)} lost (deciding push found in {sum(a['push'] for a, _, _ in fl)}/{len(L)})")
    for k in KEYS:
        nl, nw = sum(a[k] for a, _, _ in fl), sum(a[k] for a, _, _ in fw)
        print(f"   {k:10s} losses {nl:3d}/{len(L):3d} = {nl / max(1, len(L)):5.1%}   wins (most damaging push) {nw:3d}/{len(W):3d} = {nw / max(1, len(W)):5.1%}")
    dl = [m for _, m, _ in fl if m is not None]; dw = [m for _, m, _ in fw if m is not None]
    el = [e for _, _, e in fl if e is not None]; ew = [e for _, _, e in fw if e is not None]
    print(f"   decide_ms median: losses {statistics.median(dl) if dl else 'n/a'}  wins {statistics.median(dw) if dw else 'n/a'};  "
          f"own elixir at the push: losses {statistics.mean(el) if el else float('nan'):.2f}  wins {statistics.mean(ew) if ew else float('nan'):.2f}")
    AW = [x for x in sel.values() if x["mark"] == mk and x["res"] == "WIN"]
    fa = [flags(F[x["file"]], x, True)[0]["fault"] for x in AW]; base = sum(fa) / len(fa)
    nl = sum(a["fault"] for a, _, _ in fl)
    exc = max(0.0, nl - len(L) * base)
    print(f"   base rate (fault on the most damaging push of ALL {mk} wins in the band): {sum(fa)}/{len(fa)} = {base:.1%}")
    summary[name] = (len(Q), len(L), nl, exc)
# the gaps (SIM E4 baseline rows vs live) for the explained share
B = "C:/Users/benpe/pod_backup_weekend/pod1017_factorial/"
S = {"CXXXVIII": G.sim(B + "ref_cxxxviii/eval/ref_cxxxviii_74*/D3/matches.jsonl"), "CXXIV": G.sim(B + "ref_u250/eval/ref_u250_74*/D3/matches.jsonl")}
print("\n== explained share of each gap (upper bound: every EXCESS fault loss turned into a win)")
for name, mk, f in CELLS:
    if "reference" in name: continue
    n, nL, nf, exc = summary[name]
    Lr = [x for x in sel.values() if x["mark"] == mk and f(x)]; lw = sum(x["res"] == "WIN" for x in Lr) / len(Lr)
    hog, ot = name.split()[1] == "Hog", "overtime" in name
    Sr = [r for r in S[mk] if r[1].startswith("Hog") == hog and r[2] == ot]; sw = sum(r[0] for r in Sr) / len(Sr)
    gap = sw - lw; sh = (exc / n) / gap if gap > 0 else float("nan")
    print(f"   {name:24s} live win {lw:5.1%} (n {n})  SIM E4 {sw:5.1%} (n {len(Sr)})  gap {gap * 100:+5.1f} pp;  fault losses {nf}, excess over the all-wins rate "
          f"{exc:.1f} -> closes at most {exc / n * 100:4.1f} pp = {sh:5.1%} of the gap  -> {'LIVE-PATH TICKET (>= half)' if sh >= .5 else 'stays in Stage 2 (< half)'}")
# seat split of the regulation gap
print("\n== regulation by seat (all archetypes): our regulation WINS and regulation LOSSES, share of all matches")
for mk, band in (("CXXXVIII", "13k"), ("CXXIV", "12k")):
    Lv = G.live(mk, band); Sm = S[mk]
    rw = lambda R: sum(w and not ot for w, _, ot in R) / len(R); rl = lambda R: sum(not w and not ot for w, _, ot in R) / len(R)
    print(f"   {mk:9s} {band}: live reg-win {rw(Lv):5.1%} reg-loss {rl(Lv):5.1%} (n {len(Lv)})   SIM(E4) reg-win {rw(Sm):5.1%} reg-loss {rl(Sm):5.1%} (n {len(Sm)})")
print("   both seats under-take towers in the SIM if SIM reg-win < live reg-win AND SIM reg-loss < live reg-loss (-> engine-leaning)")
print("\nSIM comparison of the push-level flags: (b) the SIM rows (habit log) carry no per-push stall / elixir-at-push fields;"
      " the same review features would need SIM decision telemetry (cb_tel) -- not run.")
# reader-flag components (the flag fires in most WINS too -> which part is near-constant?)
print("\n== reader-flag components over all gated matches (share of matches): losses | wins")
for mk in ("CXXXVIII", "CXXIV"):
    Q = [x for x in sel.values() if x["mark"] == mk]
    for lab, g in (("cpu_starved > 0", lambda r: (r.get("starved") or 0) > 0), ("reader_closed > 0", lambda r: (r.get("reader_closed") or 0) > 0),
                   (">= 3 unconfirmed", lambda r: (r.get("n_unconf") or 0) >= 3), ("freeze >= 5 s", lambda r: (r.get("freeze_max_s") or 0) >= 5)):
        a = [g(F[x["file"]]) for x in Q if x["res"] != "WIN"]; b = [g(F[x["file"]]) for x in Q if x["res"] == "WIN"]
        print(f"   {mk:9s} {lab:18s} {sum(a) / len(a):5.1%} (n {len(a)}) | {sum(b) / len(b):5.1%} (n {len(b)})")
