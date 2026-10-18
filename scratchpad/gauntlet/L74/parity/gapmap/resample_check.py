"""Check trigger.py's Wilson-with-design-effect projection by brute force: fix random misses of CARD until its mean reaches P,
grow the cohort to n' by drawing matches with replacement, and take the match-bootstrap lower CI (B 400); mean over R draws.
usage: python resample_check.py ROWS.tsv CARD P DAYS [R]   (CARD 'OVERALL' = every fight)"""
import random, sys
from collections import defaultdict
from trigger import load, boot_ci

rows, card, P, days = load(sys.argv[1]), sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
R = int(sys.argv[5]) if len(sys.argv) > 5 else 8
M = len({r['stem'] for r in rows})
xs = [r for r in rows if card == 'OVERALL' or r['card'] == card]
mean = lambda v: sum(v)/len(v) if v else None
los, ps = [], []
for rep in range(R):
    rng = random.Random(100 + rep)
    v = [[r['stem'], r['aK']] for r in xs]
    bad = [i for i, x in enumerate(v) if x[1] < 1]
    rng.shuffle(bad)
    for i in bad:
        if mean([x[1] for x in v]) >= P:
            break
        v[i][1] = 1.
    by = defaultdict(list)
    for k, a in v:
        by[k].append(a)
    keys = sorted(by)
    m2 = round(len(keys)*(M + days*240)/M)
    pick = [rng.choice(keys) for _ in range(m2)]
    items = [(j, a) for j, k in enumerate(pick) for a in by[k]]
    ps.append(mean([a for _, a in items]))
    los.append(boot_ci(items, mean, B=400, seed=rep)[0])
print(f"{card} target p {P} +{days}d: n' ~{round(len(xs)*(M+days*240)/M)}, synthetic mean p {mean(ps):.4f}, "
      f"mean lower CI {mean(los):.4f} (min {min(los):.4f}, max {max(los):.4f}); goal hit in {sum(l >= (0.975 if card == 'OVERALL' else 0.95) for l in los)}/{R}")
