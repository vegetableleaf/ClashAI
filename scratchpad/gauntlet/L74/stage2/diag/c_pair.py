"""S2-08 pair readout: s2_hog_il minus s2_hog_e4 at the same checkpoint, PAIRED by seed (same learner, same seeds -> same
decks / sides), per band: our win rate and the OT share. 10,000 bootstrap resamples of seeds. Read-only."""
import ctypes, glob, json, random
try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)
except Exception: pass
B = "C:/Users/benpe/pod_backup_weekend/stage2/"
load = lambda j: {(r["seed"], r["census"], r["learner_side"]): r for f in glob.glob(B + f"{j}/{j}_74*/D3/matches.jsonl") for r in map(json.loads, open(f)) }
rnd = random.Random(7)
for u in ("0025", "0045", "0065"):
    for band in ("13k", "12k"):
        a, b = load(f"C_il_u{u}_{band}"), load(f"C_e4_u{u}_{band}")
        S = sorted(set(a) & set(b)); assert len(S) == 960 and all(a[s]["opp_deck"] == b[s]["opp_deck"] for s in S)
        for name, f in (("our win", lambda r: r["outcome"] == "win"), ("OT share", lambda r: (r["end_tick"] or 0) > 3600)):
            d = [f(a[s]) - f(b[s]) for s in S]; m = sum(d) / len(d)
            bs = sorted(sum(d[rnd.randrange(len(d))] for _ in d) / len(d) for _ in range(2000))
            print(f"u{u} {band} {name:9s} il {sum(f(a[s]) for s in S) / 960:6.1%}  e4 {sum(f(b[s]) for s in S) / 960:6.1%}  "
                  f"il - e4 {m * 100:+5.1f} pp [{bs[50] * 100:+5.1f}, {bs[1949] * 100:+5.1f}]")
