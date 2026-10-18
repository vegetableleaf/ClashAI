"""Phase B paired deltas vs the E4 T .1 baseline rows (same learner, same seeds/census/side -> same decks): our win rate,
OT share and regulation-loss rate, per Mark; 2,000 bootstrap resamples. Read-only."""
import ctypes, glob, json, random
try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)
except Exception: pass
B = "C:/Users/benpe/pod_backup_weekend/"
load = lambda g: {(r["seed"], r["census"], r["learner_side"]): r for f in glob.glob(B + g) for r in map(json.loads, open(f))}
base = {"CXXXVIII": load("pod1017_factorial/ref_cxxxviii/eval/ref_cxxxviii_74*/D3/matches.jsonl"),
        "CXXIV": load("pod1017_factorial/ref_u250/eval/ref_u250_74*/D3/matches.jsonl")}
F = {"win": lambda r: r["outcome"] == "win", "OT share": lambda r: (r["end_tick"] or 0) > 3600,
     "reg-loss": lambda r: r["outcome"] != "win" and (r["end_tick"] or 0) <= 3600}
rnd = random.Random(3)
for c in ("B1_e4T3", "B2_gen10", "B3_gen20", "B4_gen40", "B5_expl", "B6_e4_13k"):
    for mk in ("CXXXVIII", "CXXIV"):
        j = f"{c}_{mk}"; a = load(f"stage2/{j}/{j}_74*/D3/matches.jsonl")
        if not a: continue
        b = base[mk]; S = sorted(set(a) & set(b)); assert len(S) == 960 and all(a[s]["opp_deck"] == b[s]["opp_deck"] for s in S)
        out = []
        for n, f in F.items():
            d = [f(a[s]) - f(b[s]) for s in S]; bs = sorted(sum(d[rnd.randrange(960)] for _ in d) / 960 for _ in range(2000))
            out.append(f"{n} {sum(f(a[s]) for s in S) / 9.6:5.1f}% ({sum(d) / 9.6:+5.1f} [{bs[50] * 100:+5.1f}, {bs[1949] * 100:+5.1f}])")
        print(f"{c:10s} {mk:9s} " + "  ".join(out))
