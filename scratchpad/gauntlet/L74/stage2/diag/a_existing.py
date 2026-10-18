"""S2-05(a): Hog x regulation/overtime 2x2, non-Hog regulation win, OT share and regulation-loss rate from EXISTING SIM rows
(E4 promotion rows; the grafted exploiter 862bfe92 rows: successor gap13k_ref_cxxxviii = CXXXVIII under promotion conditions,
pod1016 STRUGGLE = CXXIV, no live levels / tower troops) vs live (gate rows). Read-only."""
import ctypes, sys
try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)
except Exception: pass
sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/stage2/gate")
import gate_fit as G
B = "C:/Users/benpe/pod_backup_weekend/"
SETS = [("live CXXXVIII 13k", G.live("CXXXVIII", "13k")), ("live CXXIV 12k", G.live("CXXIV", "12k")),
        ("SIM E4 vs CXXXVIII", G.sim(B + "pod1017_factorial/ref_cxxxviii/eval/ref_cxxxviii_74*/D3/matches.jsonl")),
        ("SIM E4 vs CXXIV", G.sim(B + "pod1017_factorial/ref_u250/eval/ref_u250_74*/D3/matches.jsonl")),
        ("SIM expl vs CXXXVIII (gap13k)", G.sim(B + "pod1017_successor/gap13k_ref_cxxxviii/eval/gap13k_ref_cxxxviii_74*/D3/matches.jsonl")),
        ("SIM expl vs CXXIV (STRUGGLE)", G.sim(B + "pod1016_exploit/STRUGGLE/rlarm_exploit_74*/D3/matches.jsonl"))]
H = lambda r: r[1].startswith("Hog")
for name, R in SETS:
    c = lambda f: G.pc(*G.kn(R, f))
    print(f"{name:30s} n {len(R):4d} | Hog reg win {c(lambda r: H(r) and not r[2]):30s} Hog OT win {c(lambda r: H(r) and r[2]):30s} "
          f"non-Hog reg win {c(lambda r: not H(r) and not r[2]):30s} OT share {sum(r[2] for r in R) / len(R):5.1%} "
          f"reg-loss {sum(not r[0] and not r[2] for r in R) / len(R):5.1%}")
