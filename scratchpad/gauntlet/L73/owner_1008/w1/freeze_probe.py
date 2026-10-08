"""W1: measure the Hero Ice Wizard ability (Frosty Fella) freeze on live frames: which enemy bodies stop, for how long."""
import collections
import pickle

import numpy as np

D = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/owner_1008/'
HERO = (26000023, 203000023)
GROUPS = ('R1e', 'R1e_late', 'STACK_ALON', 'STACK_ALOFF', 'STACK_RA')


def load(g):
    return pickle.load(open(D + f'live_{g}.pkl', 'rb'))


if __name__ == '__main__':
    dur, dist_frozen, dist_free = [], [], []
    for g in GROUPS:
        for m in load(g):
            F = m['frames']
            if not F:
                continue
            s = m['side']
            T = np.array([f[0] for f in F])
            for a in m['abc']:
                i = int(np.searchsorted(T, a['t']))
                if i < 6 or i + 60 >= len(F):
                    continue
                hero = [e for e in F[i][2] if e[0] == s and e[3] in HERO]
                if not hero:
                    continue
                hx, hy = hero[0][1], hero[0][2]
                tr = collections.defaultdict(dict)
                for j in range(i - 6, i + 60):
                    for e in F[j][2]:
                        if e[0] != s:
                            tr[e[6]][F[j][0]] = (e[1], e[2])
                for pts in tr.values():
                    ts = sorted(pts)
                    before = [t for t in ts if t < a['t'] - 2]
                    if len(before) < 2 or before[-1] == before[0]:
                        continue
                    p0, p1 = pts[before[0]], pts[before[-1]]
                    if np.hypot(p1[0] - p0[0], p1[1] - p0[1]) / (before[-1] - before[0]) < 20:
                        continue                                  # was moving >= 20 millitiles / tick
                    after = [t for t in ts if t >= a['t'] - 2]
                    still = [t for k, t in enumerate(after[1:])
                             if np.hypot(pts[t][0] - pts[after[k]][0], pts[t][1] - pts[after[k]][1]) < 5]
                    d = np.hypot(p1[0] - hx, p1[1] - hy) / 1000
                    run = []
                    for k, t in enumerate(after[1:]):
                        if np.hypot(pts[t][0] - pts[after[k]][0], pts[t][1] - pts[after[k]][1]) < 5:
                            run.append(t)
                        elif run:
                            break
                    if len(run) >= 3:
                        dur.append((run[0] - a['t'], run[-1] - a['t']))
                        dist_frozen.append(d)
                    else:
                        dist_free.append(d)
    dur = np.array(dur); dist_frozen = np.array(dist_frozen)
    print("stop-start histogram (ticks after confirm, 2-tick bins)", np.histogram(dur[:, 0], bins=range(-2, 40, 2)))
    k = (dur[:, 0] >= 0) & (dur[:, 0] <= 12)
    print("onset 0..12: n", k.sum(), "length pct 10/25/50/75/90", np.percentile(dur[k, 1] - dur[k, 0], [10, 25, 50, 75, 90]), "dist", np.percentile(dist_frozen[k], [10, 50, 90]))
    print('moving enemy bodies around a confirmed press: stopped >= 3 frames', len(dur), 'kept moving', len(dist_free))
    print('stop start (ticks after confirm) pct 10/50/90', np.percentile(dur[:, 0], [10, 50, 90]))
    print('stop end   (ticks after confirm) pct 10/50/90', np.percentile(dur[:, 1], [10, 50, 90]))
    print('stop length pct 10/50/90', np.percentile(dur[:, 1] - dur[:, 0], [10, 50, 90]))
    print('dist to hero (tiles) stopped pct 10/50/90', np.percentile(dist_frozen, [10, 50, 90]),
          'kept moving', np.percentile(dist_free, [10, 50, 90]))
