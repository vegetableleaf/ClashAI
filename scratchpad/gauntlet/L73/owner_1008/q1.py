"""Q1: initiative on an empty board. Exposure-based hazard + Kaplan-Meier episode times, live groups vs pros."""
import numpy as np, pickle, collections, json, sys
from common import *
CAP = 12  # ticks: decisions are logged every >=10 ticks; longer gaps are pending-play windows (cannot play)

def live_samples(m):
    s = m['side']; out = []
    for d in m['dec']:
        if d['el'] is None: continue
        en = [b for b in d['rb'] if b[3] != -1]
        out.append(dict(t=d['t'], el=d['el'], e_empty=not any(b[0] != s for b in en), a_empty=not en,
                        play=bool(d['play']), name=d['name'], xy=d['xy'], forced=bool(d.get('forced'))))
    return out

def pro_samples(r):
    last = max(p['t'] for p in r['plays']) + 20   # the re-drive runs on after the real match's last play: cut there
    fr = [F for F in r['frames'] if F[0] <= last]; mp = sorted([p for p in r['plays'] if p['me'] and not p['ability']], key=lambda p: p['t'])
    out = []; j = 0
    for i, (t, el, mine, opp) in enumerate(fr):
        t2 = fr[i + 1][0] if i + 1 < len(fr) else t + 10
        while j < len(mp) and mp[j]['t'] < t: j += 1
        ps = []
        while j < len(mp) and mp[j]['t'] < t2: ps.append(mp[j]); j += 1
        o = dict(t=t, el=el, e_empty=not opp, a_empty=not opp and not mine, play=bool(ps))
        if ps: o['name'] = ps[0]['card']; o['XY'] = (ps[0]['X'], ps[0]['Y'])
        out.append(o)
    return out

def classify(name, XY):
    n = str(name).lower().replace('-', '')
    if n == 'xbow': return 'Xbow_off' if XY[1] >= 11 else 'Xbow_def'
    if n == 'rocket': return 'Rocket_tower' if XY[1] >= 23 else 'Rocket_other'
    return {'thelog': 'Log', 'icewizard': 'IceWizard'}.get(n, str(name).capitalize() if n.islower() else str(name))

def per_match(S, key, E, ph):
    """exposure seconds, n plays, episodes [(dur_s, event)], plays list"""
    exp = 0.0; n = 0; eps = []; plays = []; cur = None
    for i, x in enumerate(S):
        ok = x[key] and x['el'] >= E and x['t'] >= 150
        dt = min((S[i + 1]['t'] - x['t']) if i + 1 < len(S) else 10, CAP) / 20.0
        if ok and PH(x['t']) == ph:
            exp += dt
            if cur is None: cur = [x['t'], None]
            if x['play']:
                n += 1; plays.append(x)
                if cur[1] is None: cur[1] = x['t']
        else:
            if cur is not None: eps.append(((cur[1] - cur[0]) / 20 if cur[1] is not None else (S[i]['t'] - cur[0]) / 20, cur[1] is not None)); cur = None
    if cur is not None: eps.append(((cur[1] - cur[0]) / 20 if cur[1] is not None else (S[-1]['t'] - cur[0]) / 20, cur[1] is not None))
    return exp, n, eps, plays

def km(eps, ts=(5, 10)):
    if not eps: return [float('nan')] * len(ts) + [float('nan')]
    d = sorted(eps); S = 1.0; nrisk = len(d); curve = []
    i = 0
    while i < len(d):
        t = d[i][0]; ev = 0; c = 0
        while i < len(d) and d[i][0] == t: ev += d[i][1]; c += 1; i += 1
        if ev: S *= 1 - ev / nrisk
        curve.append((t, S)); nrisk -= c
    def F(T):
        s = 1.0
        for t, v in curve:
            if t <= T: s = v
        return 1 - s
    med = next((t for t, v in curve if v <= 0.5), float('inf'))
    return [F(T) for T in ts] + [med]

def analyse(groups):
    res = {}; lines = []
    for g, S_all in groups.items():
        for key in ('e_empty', 'a_empty'):
            for E in (7, 9):
                for ph in (0, 1, 2):
                    pm = [per_match(S, key, E, ph) for S in S_all]
                    pm = [x for x in pm if x[0] > 0]
                    rate = lambda u: sum(x[1] for x in u) / max(1e-9, sum(x[0] for x in u))
                    r = boot(pm, rate, B=500)
                    eps = [e for x in pm for e in x[2]]
                    k = km(eps)
                    kb5 = boot(pm, lambda u: km([e for x in u for e in x[2]])[0], B=300)
                    kb10 = boot(pm, lambda u: km([e for x in u for e in x[2]])[1], B=300)
                    row = dict(g=g, key=key, E=E, ph=PHN[ph], matches=len(pm), exp_s=round(sum(x[0] for x in pm), 1), plays=sum(x[1] for x in pm),
                               rate_per_s=r, p5_from_rate=[1 - np.exp(-5 * v) for v in r], p10_from_rate=[1 - np.exp(-10 * v) for v in r],
                               episodes=len(eps), km_p5=kb5, km_p10=kb10, km_median_s=k[2])
                    res[(g, key, E, PHN[ph])] = row
                    lines.append('%-11s %-7s E>=%d %-2s m=%3d exp=%7.0fs plays=%4d rate/s=%s P5(rate)=%.2f P10(rate)=%.2f eps=%4d KM P5=%s P10=%s med=%.1fs' % (
                        g, key, E, PHN[ph], len(pm), row['exp_s'], row['plays'], fmt(r), row['p5_from_rate'][0], row['p10_from_rate'][0], len(eps), fmt(kb5), fmt(kb10), k[2]))
    return res, lines

if __name__ == '__main__':
    groups = {}; whatp = {}
    for g in ('R1e', 'STACK_ALON', 'STACK_ALOFF', 'STACK_RA'):
        L = load(g); groups[g] = [live_samples(m) for m in L]
    groups['STACK_OFF_ALL'] = groups['STACK_ALOFF'] + groups['STACK_RA']
    pros = pickle.load(open('pro_q.pkl', 'rb'))
    groups['PRO'] = [pro_samples(r) for r in pros]
    res, lines = analyse(groups)
    print('\n'.join(lines))
    # what is played on an empty (enemy-empty) board with elixir >= 7, by phase
    print('\nWHAT IS PLAYED (enemy-empty board, elixir>=7, t>=150)')
    for g, S_all in groups.items():
        for ph in (0, 1, 2):
            c = collections.Counter(); forced = 0
            for S in S_all:
                for x in S:
                    if x['play'] and x['e_empty'] and x['el'] >= 7 and x['t'] >= 150 and PH(x['t']) == ph:
                        XY = x.get('XY') or mxy(x['xy'])
                        c[classify(x['name'], XY)] += 1; forced += x.get('forced', False)
            n = sum(c.values())
            print(g, PHN[ph], 'n=%d' % n, 'forced=%d' % forced, ', '.join('%s %.0f%%' % (k, 100 * v / n) for k, v in c.most_common()) if n else '')
    pickle.dump(res, open('q1_res.pkl', 'wb'))
