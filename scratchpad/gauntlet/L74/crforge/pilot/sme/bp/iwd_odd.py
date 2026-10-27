"""The odd hero IW deploys of an iwdeploy file: sim cube offset at R+1 missing, or not equal to the game's."""
import json, sys
for l in open(sys.argv[1]):
    d = json.loads(l)
    sim = {int(t): v for t, v in d['sim'].items()}
    R = d['R']
    rec = {int(t): sorted(v, key=lambda g: g[3]) for t, v in d['rec'].items()}

    def off(rows):
        h = [r for r in rows if r[0] == 'IceWizardHero']
        q = [r for r in rows if r[0] == 'IceWizardHeroFloatingCube']
        return (q[0][1] - h[0][1], q[0][2] - h[0][2]) if h and q else None
    s1 = off(sim.get(R + 1, []))
    g = rec.get(R + 1, [])
    g1 = (g[1][0] - g[0][0], g[1][1] - g[0][1]) if len(g) >= 2 else None
    if g1 is not None and s1 != g1:
        print(d['match'][10:], 'R', R, 'side', d['side'], 'sim R+1', sim.get(R + 1), 'rec R+1', g, 'sim R+2', sim.get(R + 2))
