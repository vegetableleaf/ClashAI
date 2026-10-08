"""W1: speed profile of enemy bodies near the Frosty Fella target around a confirmed press (live frames).

Target = the enemy nearest my hero Ice Wizard (<= 5.5 tiles) at the confirm frame (hero_button.py's reading of the
ability: snowman behind the IW's target, freezes every enemy within 2.5 tiles). Bodies within 2.5 tiles of it that
moved >= 20 millitiles/tick in the 10 ticks before: median / share-still of their per-frame speed by ticks after confirm.
"""
import collections

import numpy as np

from freeze_probe import GROUPS, HERO, load

if __name__ == '__main__':
    prof = collections.defaultdict(list)
    n_ev = 0
    for g in GROUPS:
        for m in load(g):
            F = m['frames']
            if not F:
                continue
            s = m['side']
            T = np.array([f[0] for f in F])
            for a in m['abc']:
                i = int(np.searchsorted(T, a['t']))
                if i < 8 or i + 70 >= len(F):
                    continue
                hero = [e for e in F[i][2] if e[0] == s and e[3] in HERO]
                foes = [e for e in F[i][2] if e[0] != s and e[3] >= 0]
                if not hero or not foes:
                    continue
                hx, hy = hero[0][1], hero[0][2]
                tgt = min(foes, key=lambda e: np.hypot(e[1] - hx, e[2] - hy))
                if np.hypot(tgt[1] - hx, tgt[2] - hy) > 5500:
                    continue
                n_ev += 1
                tr = collections.defaultdict(dict)
                for j in range(i - 8, i + 70):
                    for e in F[j][2]:
                        if e[0] != s:
                            tr[e[6]][F[j][0]] = (e[1], e[2])
                for e in foes:
                    if np.hypot(e[1] - tgt[1], e[2] - tgt[2]) > 2500:
                        continue
                    pts = tr[e[6]]
                    ts = sorted(pts)
                    b = [t for t in ts if a['t'] - 12 <= t < a['t'] - 2]
                    if len(b) < 2 or np.hypot(pts[b[-1]][0] - pts[b[0]][0], pts[b[-1]][1] - pts[b[0]][1]) / (b[-1] - b[0]) < 20:
                        continue
                    for k in range(1, len(ts)):
                        dt = ts[k] - ts[k - 1]
                        if dt <= 0:
                            continue
                        v = np.hypot(pts[ts[k]][0] - pts[ts[k - 1]][0], pts[ts[k]][1] - pts[ts[k - 1]][1]) / dt
                        prof[(ts[k] - a['t']) // 4 * 4].append(v)
    print('presses with a target within 5.5 tiles:', n_ev)
    for k in sorted(prof):
        v = np.array(prof[k])
        print('ticks %+4d..%+4d  n %4d  median speed %6.1f  share still(<3) %.2f' % (k, k + 3, len(v), np.median(v), np.mean(v < 3)))
