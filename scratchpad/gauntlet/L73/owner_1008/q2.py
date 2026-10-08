"""Q2: Hero Ice Wizard ability presses, live vs pros (L70 crawl summary)."""
import collections, numpy as np, json
from common import *
from cards import NAME, COST, uval
IW_IDS = {26000023, 203000023}

def enemy_plays(m):
    """enemy plays = first sightings of enemy addresses, grouped per card id within 20 ticks"""
    s = m['side']; seen = set(); out = []
    for d in m['dec']:
        for b in d['rb']:
            if b[0] == s or b[3] == -1 or b[6] in seen: continue
            seen.add(b[6]); X, Y = own(s, b[1], b[2])
            if out and out[-1]['cid'] == b[3] and d['t'] - out[-1]['t'] <= 20: continue
            out.append(dict(t=d['t'], cid=b[3], X=X, Y=Y, cost=COST.get(b[3], 3)))
    return out

def at(m, t):
    best = None
    for d in m['dec']:
        if d['t'] <= t: best = d
        else: break
    return best

def press_rows(m):
    s = m['side']; ep = enemy_plays(m); rows = []
    my = [(c['t'], c['name']) for c in m['conf']]
    deploys = [t for t, n in my if n == 'IceWizard']
    for a in m['ab']:
        t = a['t']; d = at(m, t)
        if d is None: continue
        hero = [b for b in d['rb'] if b[0] == s and b[3] in IW_IDS]
        foes = [b for b in d['rb'] if b[0] != s and b[3] != -1]
        fo = [(own(s, b[1], b[2]), b) for b in foes]
        onhalf = [b for (X, Y), b in fo if Y < 16]
        near = []
        if hero:
            hx, hy = own(s, hero[0][1], hero[0][2])
            near = [b for (X, Y), b in fo if ((X - hx) ** 2 + (Y - hy) ** 2) ** .5 <= 6]
        threat = sum(uval(b[3]) for b in onhalf)
        mine_3 = [n for tt, n in my if t - 60 <= tt <= t and n != 'IceWizard']
        mine_5 = [n for tt, n in my if t - 100 <= tt <= t and n != 'IceWizard']
        cost = {'Knight': 3, 'Skeletons': 1, 'Log': 2, 'Tornado': 3, 'Tesla': 4, 'Xbow': 6, 'Rocket': 6, 'IceWizard': 3}
        committed5 = sum(cost.get(n, 3) for n in mine_5 if n not in ('Xbow', 'Rocket'))
        opp6 = [p for p in ep if t - 120 <= p['t'] <= t]
        dep = [x for x in deploys if x <= t]
        rows.append(dict(t=t, ph=PH(t), el=a['el'], why=a['why'].split(' ')[0], threat=threat, n_onhalf=len(onhalf), n_near=len(near),
                         own3=bool([tt for tt, n in my if t - 60 <= tt <= t]), committed5=committed5,
                         opp6_troopcost=sum(p['cost'] for p in opp6), opp6_myhalf=any(p['Y'] < 16 for p in opp6), opp6_any=bool(opp6),
                         since_dep=(t - dep[-1]) / 20 if dep else None))
    return rows, len(deploys)

if __name__ == '__main__':
    out = {}
    for g, L in (('R1e', load('R1e')), ('STACK_ALON', load('STACK_ALON')), ('STACK_OFF', load('STACK_ALOFF') + load('STACK_RA'))):
        R = []; ndep = 0; per = []
        for m in L:
            r, nd = press_rows(m); R += r; ndep += nd; per.append(len(r))
        n = len(R)
        def sh(f): k = sum(1 for r in R if f(r)); return '%d/%d=%.2f [%.2f,%.2f]' % (k, n, *wilson(k, n))
        print('==', g, 'matches', len(L), 'presses', n, 'IW deploys', ndep, 'presses/deploy %.2f' % (n / max(ndep, 1)),
              'presses/match %.2f' % np.mean(per))
        print('  by phase', collections.Counter(PHN[r['ph']] for r in R), ' branch', collections.Counter(r['why'] for r in R))
        print('  elixir at press median %.1f; own elixir>=5 %s; <=2 %s' % (np.median([r['el'] for r in R]), sh(lambda r: r['el'] >= 5), sh(lambda r: r['el'] <= 2)))
        print('  delay since IW deploy median %.1fs' % np.median([r['since_dep'] for r in R if r['since_dep'] is not None]))
        print('  [pro analog] own played last 3s %s | opp played on my half last 6s %s | opp troop cost last 6s>=4 %s | no opp play in 6s %s' % (
            sh(lambda r: r['own3']), sh(lambda r: r['opp6_myhalf']), sh(lambda r: r['opp6_troopcost'] >= 4), sh(lambda r: not r['opp6_any'])))
        print('  threat value on my half at press: median %.1f; <=3 elixir %s; <=2 %s' % (np.median([r['threat'] for r in R]), sh(lambda r: r['threat'] <= 3), sh(lambda r: r['threat'] <= 2)))
        print('  my non-IW elixir committed in last 5s >= threat %s ; OVERSPEND (threat<=3 OR committed>=threat) %s' % (
            sh(lambda r: r['committed5'] >= r['threat']), sh(lambda r: r['threat'] <= 3 or r['committed5'] >= r['threat'])))
        for b in ('iw_clump', 'iw_wincon'):
            Rb = [r for r in R if r['why'] == b]; k = sum(1 for r in Rb if r['threat'] <= 3 or r['committed5'] >= r['threat'])
            print('   branch %s overspend %d/%d=%.2f [%.2f,%.2f]' % (b, k, len(Rb), *wilson(k, len(Rb))))
        out[g] = R
    json.dump(out, open('q2_rows.json', 'w'))
