"""Q4: enemy Goblin Barrel / Miner: where it lands vs where my response goes. Live groups and pros."""
import pickle, numpy as np, collections
from common import *
BARREL = {28000004, 13000081}
MINER = {26000032}
RESP = {'Log', 'Knight', 'Skeletons', 'Tornado', 'IceWizard', 'Tesla'}
PT = [(3.5, 6.5), (14.5, 6.5)]
PRO_N = {'the-log': 'Log', 'knight': 'Knight', 'skeletons': 'Skeletons', 'tornado': 'Tornado', 'ice-wizard': 'IceWizard', 'tesla': 'Tesla'}


def d2(a, b): return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** .5
def near_tower(p, r): return min(d2(p, t) for t in PT) <= r
def log_hits(logxy, tgt): return abs(tgt[0] - logxy[0]) <= 2.5 and -1.0 <= tgt[1] - logxy[1] <= 10.1


def live_threats(m):
    s = m['side']; out = []
    # barrels: enemy projectiles with a barrel id, grouped by target
    for d in m['dec']:
        for q in d['rp']:
            if q[0] == s or q[3] not in BARREL: continue
            vis = q[4] is not None
            tgt = own(s, q[4], q[5]) if vis else None
            if out and out[-1]['kind'] == 'barrel' and d['t'] - out[-1]['t0'] <= 40 and (tgt is None or any(d2(tgt, u) < 1 for u in out[-1]['tgts'])):
                continue
            if out and out[-1]['kind'] == 'barrel' and d['t'] - out[-1]['t0'] <= 4 and tgt is not None:   # evo barrel: real + decoy, one threat
                out[-1]['tgts'].append(tgt); continue
            out.append(dict(kind='barrel', t0=d['t'], tland=d['t'] + 20, tgt=tgt, tgts=[tgt] if tgt else [], target_visible=vis))
    # miners: enemy miner bodies by address; destination = first deploying (kind 14) position, else last of first 3 s
    tr = collections.defaultdict(list)
    for d in m['dec']:
        for b in d['rb']:
            if b[0] != s and b[3] in MINER: tr[b[6]].append((d['t'], own(s, b[1], b[2]), b[5]))
    for a, T in tr.items():
        dep = [x for x in T if x[2] == 14]
        dst = dep[0] if dep else [x for x in T if x[0] <= T[0][0] + 60][-1]
        first = T[0]
        out.append(dict(kind='miner', t0=first[0], tland=dst[0], tgt=dst[1], tgts=[dst[1]], lead_s=(dst[0] - first[0]) / 20,
                        first_dist=d2(first[1], dst[1]), target_visible=None))
    return out


def responses(threats, plays):
    rows = []
    for th in threats:
        if th['tgt'] is None: continue
        T = th.get('tgts') or [th['tgt']]
        if all(u[1] > 16 for u in T): continue
        w = [p for p in plays if th['t0'] <= p[0] <= th['tland'] + 60 and p[1] in RESP]
        if not w: rows.append(dict(kind=th['kind'], resp=None, tgt=th['tgt'])); continue
        p = w[0]; dist = min(d2(p[2], u) for u in T)
        rows.append(dict(kind=th['kind'], resp=p[1], dist=dist, tgt=th['tgt'], at_tower=near_tower(p[2], 2.0), evo_pair=len(T) > 1,
                         tgt_far=all(not near_tower(u, 3.0) for u in T), log_miss=(p[1] == 'Log' and not any(log_hits(p[2], u) for u in T))))
    return rows


def report(name, R):
    for k in ('barrel', 'miner'):
        X = [r for r in R if r['kind'] == k]; Y = [r for r in X if r['resp']]
        if not X: print(name, k, 'n=0'); continue
        ds = np.array([r['dist'] for r in Y]) if Y else np.array([np.nan])
        far = [r for r in Y if r['tgt_far']]; farT = sum(r['at_tower'] for r in far)
        logs = [r for r in Y if r['resp'] == 'Log']; lm = sum(r['log_miss'] for r in logs)
        print('%-11s %-6s threats=%3d responded=%3d | dist resp->landing median %.1f p75 %.1f, >3 tiles %d/%d=%.2f [%.2f,%.2f] | landing >3t from tower: %d, responded AT tower (<=2t) %d/%d=%.2f [%.2f,%.2f] | Log misses landing %d/%d=%.2f [%.2f,%.2f] | resp cards %s' % (
            name, k, len(X), len(Y), np.median(ds), np.percentile(ds, 75), int((ds > 3).sum()), len(Y), *wilson(int((ds > 3).sum()), len(Y)),
            len(far), farT, len(far), *wilson(farT, len(far)), lm, len(logs), *wilson(lm, len(logs)),
            dict(collections.Counter(r['resp'] for r in Y).most_common(4))))


if __name__ == '__main__':
    G = {'R1e': load('R1e'), 'STACK_since04': load('STACK_ALON') + load('STACK_ALOFF') + load('STACK_RA'), 'STACK_RA': load('STACK_RA')}
    for g, L in G.items():
        R = []; vis = []; miners = []
        for m in L:
            th = live_threats(m)
            vis += [t['target_visible'] for t in th if t['kind'] == 'barrel']
            miners += [t for t in th if t['kind'] == 'miner']
            R += responses(th, [(p['t'], p['name'], mxy(p['xy'])) for p in m['play']])
        report(g, R)
        if vis: print('   barrel target present in raw projectile at first sighting: %d/%d' % (sum(vis), len(vis)))
        if miners:
            lead = np.array([t['lead_s'] for t in miners]); fd = np.array([t['first_dist'] for t in miners])
            print('   miner visible before surfacing: lead median %.1fs (>=0.5 s: %d/%d), first-seen distance to destination median %.1f tiles' % (
                np.median(lead), int((lead >= 0.5).sum()), len(lead), np.median(fd)))
    pros = pickle.load(open('pro_q.pkl', 'rb'))
    R = []
    for r in pros:
        mp = [(p['t'], PRO_N.get(p['card'], p['card']), (p['X'], p['Y'])) for p in r['plays'] if p['me'] and not p['ability']]
        th = [dict(kind='barrel' if p['card'].startswith('goblin-barrel') else 'miner', t0=p['t'], tland=p['t'] + (20 if p['card'].startswith('goblin-barrel') else 30), tgt=(p['X'], p['Y']), tgts=[(p['X'], p['Y'])])
              for p in r['plays'] if not p['me'] and p['X'] is not None and (p['card'].startswith('goblin-barrel') or p['card'] == 'miner')]
        R += responses(th, mp)
    report('PRO', R)


def far_vs_near():
    """response distance when the landing is far (>3 t) from my princess towers vs at a tower"""
    G = {'R1e': load('R1e'), 'STACK_since04': load('STACK_ALON') + load('STACK_ALOFF') + load('STACK_RA')}
    pros = pickle.load(open('pro_q.pkl', 'rb'))
    PR = []
    for r in pros:
        mp = [(p['t'], PRO_N.get(p['card'], p['card']), (p['X'], p['Y'])) for p in r['plays'] if p['me'] and not p['ability']]
        th = [dict(kind='barrel' if p['card'].startswith('goblin-barrel') else 'miner', t0=p['t'], tland=p['t'] + (20 if p['card'].startswith('goblin-barrel') else 30), tgt=(p['X'], p['Y']), tgts=[(p['X'], p['Y'])])
              for p in r['plays'] if not p['me'] and p['X'] is not None and (p['card'].startswith('goblin-barrel') or p['card'] == 'miner')]
        PR += responses(th, mp)
    sets = {g: [r for m in L for r in responses(live_threats(m), [(p['t'], p['name'], mxy(p['xy'])) for p in m['play']])] for g, L in G.items()}
    sets['PRO'] = PR
    for g, R in sets.items():
        for far in (False, True):
            X = [r['dist'] for r in R if r['resp'] and r['tgt_far'] == far]
            k = sum(x > 3 for x in X)
            print('%-13s landing %-14s n=%4d response >3 tiles from landing %d/%d=%.2f [%.2f,%.2f], median %.1f' % (
                g, 'FAR from tower' if far else 'at tower', len(X), k, len(X), *wilson(k, len(X)), np.median(X) if X else float('nan')))


if __name__ == '__main__':
    far_vs_near()
