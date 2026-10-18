"""Stage-2 scorer: runs the FROZEN gate (gate/gate_s2.py; FROZEN.txt hash checked first) on copied-back runs in
pod_backup_weekend/stage2/<JOB>/ and prints one table row per candidate + the full gate lines. Marks each look read in
ledger.jsonl (result_read true + read time). Read-only otherwise.
    python score_s2.py phaseB           -> B1..B6 (+ the E4 T .1 baseline rows), full gate
    python score_s2.py phaseC           -> C_<arm>_u<k> Hog gate per arm x checkpoint (both bands)"""
import ctypes, glob, hashlib, json, os, sys, time
try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)
except Exception: pass
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(H, "gate"))
want = open(os.path.join(H, "gate/FROZEN.sha")).read().split()[0]
assert hashlib.sha256(open(os.path.join(H, "gate/FROZEN.txt"), "rb").read()).hexdigest() == want, "FROZEN.txt changed"
for l in open(os.path.join(H, "gate/FROZEN.txt")):
    w = l.split()
    if len(w) == 2 and len(w[0]) == 64:   # every frozen file still has its frozen hash
        p = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/" + w[1]
        assert hashlib.sha256(open(p, "rb").read()).hexdigest() == w[0], f"frozen file changed: {w[1]}"
import gate_fit as G
import gate_s2 as S2
B = "C:/Users/benpe/pod_backup_weekend/stage2/"
E4 = {"CXXXVIII": "C:/Users/benpe/pod_backup_weekend/pod1017_factorial/ref_cxxxviii/eval/ref_cxxxviii_74*/D3/matches.jsonl",
      "CXXIV": "C:/Users/benpe/pod_backup_weekend/pod1017_factorial/ref_u250/eval/ref_u250_74*/D3/matches.jsonl"}
rows = lambda job: G.sim(B + f"{job}/{job}_74*/D3/matches.jsonl")
read = []


def diag(R):
    Hh = [r for r in R if S2.HOG(r)]
    return (f"Hog reg {G.kn(Hh, lambda r: not r[2])} OT {G.kn(Hh, lambda r: r[2])}; non-Hog reg {G.kn(R, lambda r: not S2.HOG(r) and not r[2])}; "
            f"OT share {sum(r[2] for r in R) / len(R):.1%}; reg-loss {sum(not r[0] and not r[2] for r in R) / len(R):.1%}; win {sum(r[0] for r in R) / len(R):.1%}")


L = S2.live_rows()
if sys.argv[1] == "phaseB":
    cands = [("B0 E4 T.1 (baseline, existing rows)", {k: G.sim(v) for k, v in E4.items()}, [])]
    for b in ("B1_e4T3", "B2_gen10", "B3_gen20", "B4_gen40", "B5_expl"):
        cands.append((b, {mk: rows(f"{b}_{mk}") for mk in ("CXXXVIII", "CXXIV")}, [f"{b}_CXXXVIII", f"{b}_CXXIV"]))
    b6 = rows("B6_e4_13k_CXXXVIII")
    if b6: cands.append(("B6 E4 T.1 + 13k levels (13k band; 12k = the E4 baseline rows)", {"CXXXVIII": b6, "CXXIV": G.sim(E4["CXXIV"])}, ["B6_e4_13k_CXXXVIII"]))
    for name, S, looks in cands:
        if not all(S.values()): print(f"== {name}: rows missing {[k for k, v in S.items() if not v]}"); continue
        ok, lines = S2.full(S, L); read += looks
        print(f"== {name}: {'GATE PASS' if ok else 'GATE FAIL'} (SIM {', '.join(f'{k} {len(v)}' for k, v in S.items())})")
        for mk in S: print(f"   diag {mk}: {diag(S[mk])}")
        print("\n".join(lines))
elif sys.argv[1] == "phaseC":
    for arm in ("il", "e4"):
        for u in ("0025", "0045", "0065"):
            S = {"CXXXVIII": rows(f"C_{arm}_u{u}_13k"), "CXXIV": rows(f"C_{arm}_u{u}_12k")}
            if not all(S.values()): print(f"== s2_hog_{arm} u{u}: rows missing"); continue
            ok, lines = S2.hog(S, L); read += [f"C_{arm}_u{u}_13k", f"C_{arm}_u{u}_12k"]
            print(f"== s2_hog_{arm} u{u}: HOG GATE {'PASS' if ok else 'FAIL'} (SIM {', '.join(f'{k} {len(v)}' for k, v in S.items())})")
            print("\n".join(lines))
LP = os.path.join(H, "ledger.jsonl"); X = [json.loads(l) for l in open(LP)]
for x in X:
    if x["look"] in read and not x.get("result_read"): x.update(result_read=True, read=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
open(LP, "w", newline="\n").write("".join(json.dumps(x) + "\n" for x in X))
