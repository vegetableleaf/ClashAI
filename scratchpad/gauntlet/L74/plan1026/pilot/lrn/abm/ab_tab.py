"""LEARNER-SCALE3 SIM A/B table (SCALE.md 7f) from the ab_m.sh logs: per training run the per-update W/L/D (win rate vs the
fixed pool, on-policy), steps and kl_stop; per eval checkpoint the u0000 W/L/D of 1,024 matches per eval seed, the pooled
win rate (W + D/2) / N with a binomial se, and each arm's difference vs B0 on the same eval seeds.

    python ab_tab.py LOGDIR
"""
import math
import re
import sys
from pathlib import Path

U = re.compile(r"^\[rl\] u(\d{4}) W/L/D (\d+)/(\d+)/(\d+)")
KL = re.compile(r"kl_stop e\d+ mb\d+ KL ([0-9.]+)")
ST = re.compile(r" steps (\d+) ")


def lines(p):
    out = []
    for t in p.read_text(errors="replace").splitlines():
        m = U.match(t)
        if m:
            k, s = KL.search(t), ST.search(t)
            out.append(m.groups() + (k and k.group(1), s and s.group(1)))
    return out


def wr(w, l, d):
    n = w + l + d
    p = (w + 0.5 * d) / n
    return p, math.sqrt(p * (1 - p) / n), n


d = Path(sys.argv[1])
print("## training runs: per update  u: win rate (n) steps stopKL")
for p in sorted(d.glob("abm_s*_e*.log")):
    row = []
    for u, w, l, dr, kl, st in lines(p):
        r, _, n = wr(int(w), int(l), int(dr))
        row.append(f"u{int(u)} {r:.3f} ({n}) {st or '-'} {kl or '-'}")
    print(p.stem, " | ".join(row))
print("\n## eval (u0000 of init = checkpoint, 1,024 matches per eval seed)")
ev = {}
for p in sorted(d.glob("abm_ev*_*.log")):
    m = re.match(r"abm_ev(\d+)_(.+)", p.stem)
    ls = lines(p)
    if m and ls:
        ev.setdefault(m.group(2), {})[m.group(1)] = tuple(int(x) for x in ls[0][1:4])
base = ev.get("b0", {})
for arm, by in sorted(ev.items()):
    W = [sum(x) for x in zip(*by.values())]
    r, se, n = wr(*W)
    out = f"{arm:16s} seeds {sorted(by)} WR {r:.4f} +- {se:.4f} (n {n})"
    if arm != "b0" and base:
        common = [s for s in by if s in base]
        if common:
            a = [sum(by[s][i] for s in common) for i in range(3)]
            b = [sum(base[s][i] for s in common) for i in range(3)]
            ra, sa, _ = wr(*a)
            rb, sb, _ = wr(*b)
            out += f"  vs B0 {100 * (ra - rb):+.2f} pp +- {100 * math.hypot(sa, sb):.2f} (unpaired se)"
    print(out)
