"""Summarise iwdeploy output: the cube's offset from the hero, crforge (lines R+1, R+2) vs the game (first recorded frames).
python3 iwd_sum.py IWD.jsonl"""
import collections, json, sys
c = collections.Counter()
ex = []
for l in open(sys.argv[1]):
    d = json.loads(l)
    sim = {int(t): v for t, v in d['sim'].items()}
    R = d['R']

    def off(rows):
        h = [r for r in rows if r[0] == 'IceWizardHero']
        q = [r for r in rows if r[0] == 'IceWizardHeroFloatingCube']
        return (q[0][1] - h[0][1], q[0][2] - h[0][2]) if h and q else None
    s1, s2 = off(sim.get(R + 1, [])), off(sim.get(R + 2, []))
    rec = {int(t): v for t, v in d['rec'].items()}
    # game: two new rows at the play (hero + cube); their offset on each recorded frame (same gen order: lower gen = hero)
    gf = []
    for t in sorted(rec):
        rows = sorted(rec[t], key=lambda g: g[3])
        if len(rows) >= 2:
            gf.append((t - R, rows[1][0] - rows[0][0], rows[1][1] - rows[0][1]))
    g1 = next(((dt, ox, oy) for dt, ox, oy in gf if dt == 1), None)
    g2 = next(((dt, ox, oy) for dt, ox, oy in gf if dt == 2), None)
    c[('sim R+1', s1, 'game R+1', g1[1:] if g1 else 'no frame')] += 1
    if g1 is None and g2 is None:
        c['game: no frame at R+1 or R+2'] += 1
    ex.append((d['match'][10:], R, s1, s2, gf[:3]))
for k, v in c.most_common(20):
    print(v, k)
for e in ex[:12]:
    print(e)
