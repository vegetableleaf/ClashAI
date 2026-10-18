"""S2-02: the gate's FALSE-FAIL rate for a PERFECT opponent set (parametric bootstrap). Truth = the observed live rows of each
band; each replicate draws a fresh live set (live n, with replacement) AND a SIM set (n_sim per Mark) from that same truth,
then scores gate_s2 on them. The fail fraction = how often a perfect opponent would still fail (no multiplicity correction).
    python falsefail.py REPS   -> full gate at n_sim 960 / 1920 per Mark, hog gate at 960 Hog games per Mark"""
import ctypes, os, random, sys
try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)   # IDLE (live play runs here)
except Exception: pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_s2 as S2

reps = int(sys.argv[1]) if len(sys.argv) > 1 else 500
L = S2.live_rows()
rnd = random.Random(20261018)
draw = lambda rows, n: [rows[rnd.randrange(len(rows))] for _ in range(n)]
out = []
for kind, n_sim in (("full", 960), ("full", 1920), ("hog", 960)):
    fails = 0
    for _ in range(reps):
        Lb = {mk: draw(v, len(v)) for mk, v in L.items()}
        if kind == "hog":
            Sb = {mk: draw([r for r in v if S2.HOG(r)], n_sim) for mk, v in L.items()}
            fails += not S2.hog(Sb, Lb)[0]
        else:
            Sb = {mk: draw(v, n_sim) for mk, v in L.items()}
            fails += not S2.full(Sb, Lb)[0]
    p = fails / reps; se = (p * (1 - p) / reps) ** .5
    out.append(f"{kind} gate, SIM n {n_sim} per Mark: false-fail {fails}/{reps} = {p:.1%} (+- {1.96 * se:.1%})")
    print(out[-1], flush=True)
