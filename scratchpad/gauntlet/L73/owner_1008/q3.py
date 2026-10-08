"""Q3: consecutive plays (pairs within 3/5 s), overspend vs threat, conflict patterns; forecast error after my own knockback/pull."""
import collections, numpy as np, pickle, csv
from common import *
from cards import COST, uval
from q2 import enemy_plays
BC = {'Knight': 3, 'Skeletons': 1, 'Log': 2, 'Tornado': 3, 'Tesla': 4, 'Xbow': 6, 'Rocket': 6, 'IceWizard': 3}
SPELL = {'Log', 'Tornado', 'Rocket'}
PN = {'the-log': 'Log', 'tornado': 'Tornado', 'rocket': 'Rocket', 'knight': 'Knight', 'skeletons': 'Skeletons', 'tesla': 'Tesla', 'x-bow': 'Xbow', 'ice-wizard': 'IceWizard'}


def pairs(plays, opp, W):
    """plays: [(t, name, X, Y, cost)] mine; opp: [(t, X, Y, cost)] enemy plays. Defensive pairs within W ticks."""
    out = []
    for a, b in zip(plays, plays[1:]):
        if b[0] - a[0] > W: continue
        if a[1] == 'Xbow' or b[1] == 'Xbow': continue           # X-Bow placement is offence, not a response
        if a[3] > 16 or b[3] > 16: continue                       # both aimed at my half = responses
        thr = [o for o in opp if a[0] - 160 <= o[0] <= a[0] and o[2] < 20]
        out.append(dict(a=a[1], b=b[1], spent=a[4] + b[4], threat=sum(o[3] for o in thr), gap=(b[0] - a[0]) / 20))
    return out


def live_plays(m):
    P = [(p['t'], p['name']) + mxy(p['xy']) + (BC.get(p['name'], 3),) for p in m['play']]
    O = [(o['t'], o['X'], o['Y'], o['cost']) for o in enemy_plays(m)]
    return P, O


def pro_plays(r):
    P = [(p['t'], PN.get(p['card'], p['card']), p['X'], p['Y'], p['cost']) for p in r['plays'] if p['me'] and not p['ability']]
    O = [(p['t'], p['X'], p['Y'], p['cost']) for p in r['plays'] if not p['me'] and not p['ability'] and p['X'] is not None]
    return P, O


def summarise(name, PO):
    for W, lab in ((60, '3s'), (100, '5s')):
        allp = [x for P, O in PO for x in pairs(P, O, W)]
        nplays = sum(len(P) for P, O in PO); n = len(allp)
        over = [x for x in allp if x['spent'] > x['threat'] + 1]
        lt = sum(1 for x in allp if x['a'] == 'Log' and x['b'] == 'Tornado')
        ds = sum(1 for x in allp if x['a'] in SPELL and x['b'] in SPELL and x['threat'] <= 3)
        print('%-10s %s: defensive pairs %d (%.1f per 100 plays) | spent>threat+1: %d/%d=%.2f [%.2f,%.2f] | median spent %.0f vs threat %.0f | Log->Tornado %d (%.1f/100 plays) | 2 spells on threat<=3: %d' % (
            name, lab, n, 100 * n / max(nplays, 1), len(over), n, *wilson(len(over), n),
            np.median([x['spent'] for x in allp]) if n else 0, np.median([x['threat'] for x in allp]) if n else 0,
            lt, 100 * lt / max(nplays, 1), ds))


def ability_after_spell(L):
    k = n = 0
    for m in L:
        for a in m['ab']:
            n += 1
            k += any(p['name'] in ('Log', 'Tornado') and 0 <= a['t'] - p['t'] <= 60 for p in m['play'])
    return k, n


def pro_ability_after_spell():
    base = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L70/abilities/ice_wizard_hero/crawl/'
    hs = {b['replay_tag']: b['hero_side'] for b in csv.DictReader(open(base + 'battles.csv'))}
    rows = collections.defaultdict(list)
    for r in csv.DictReader(open(base + 'plays.csv')): rows[r['replay_tag']].append(r)
    k = n = 0
    spells = {'the-log', 'tornado', 'fireball', 'zap', 'barbarian-barrel', 'arrows', 'poison', 'giant-snowball', 'rocket', 'earthquake'}
    for tag, R in rows.items():
        side = hs.get(tag)
        for r in R:
            if r['attr_ability'] == '1' and r['attr_s'] == side:
                n += 1; t = float(r['seconds'])
                k += any(q['attr_s'] == side and q['attr_ability'] == '0' and q['attr_card'].replace('-ev1', '') in spells
                         and 0 <= t - float(q['seconds']) <= 3 for q in R)
    return k, n


# ---------- forecast check (recorded-frame matches only)
EFFECT = {'Log', 'Tornado'}


def forecast_rows(m, H=26):
    s = m['side']; F = m['frames']
    if not F: return []
    idx = {t: i for i, (t, el, en) in enumerate(F)}
    ticks = np.array([f[0] for f in F])
    conf = [(c['t'], c['name'], mxy(c['xy'])) for c in m['conf']]
    abil = [a['t'] for a in m['abc']]
    rows = []
    for d in m['dec']:
        t = d['t']
        if t not in idx or idx[t] == 0: continue
        i = idx[t]; k = i - 1
        while k > 0 and F[k][0] >= t: k -= 1
        if F[k][0] >= t: continue
        tp, _, ep = F[k]; _, _, en = F[i]
        j = int(np.argmin(abs(ticks - (t + H))))
        if abs(ticks[j] - (t + H)) > 2: continue
        fut = {e[6]: e for e in F[j][2] if e[0] != s}
        prev = {e[6]: e for e in ep if e[0] != s}
        hero = [e for e in en if e[0] == s and e[3] in (26000023, 203000023)]
        recent = [c for c in conf if 0 <= t - c[0] <= 40]
        rec_eff = [c for c in recent if c[1] in EFFECT]
        rec_ab = [a for a in abil if 0 <= t - a <= 40]
        is_second = bool(d['play']) and any(0 <= t - c[0] <= 4 for c in conf)
        for e in en:
            if e[0] == s or e[6] not in prev or e[6] not in fut: continue
            p = prev[e[6]]
            if p[3] != e[3]: continue
            g = t - tp
            fx = min(max(e[1] + (e[1] - p[1]) / g * H, 0), 18000); fy = min(max(e[2] + (e[2] - p[2]) / g * H, 0), 32000)
            r = fut[e[6]]; err = ((fx - r[1]) ** 2 + (fy - r[2]) ** 2) ** .5 / 1000
            X, Y = own(s, e[1], e[2])
            hit = False
            for c in rec_eff:
                cx, cy = c[2]
                if c[1] == 'Tornado' and ((X - cx) ** 2 + (Y - cy) ** 2) ** .5 <= 5.5: hit = True
                if c[1] == 'Log' and abs(X - cx) <= 2.5 and cy - 1 <= Y <= cy + 11: hit = True
            if rec_ab and hero:
                hx, hy = own(s, hero[0][1], hero[0][2])
                if ((X - hx) ** 2 + (Y - hy) ** 2) ** .5 <= 6: hit = True
            cat = 'my_effect_hit' if hit else ('my_effect_elsewhere' if (rec_eff or rec_ab) else ('my_other_play' if recent else 'no_recent_play'))
            rows.append(dict(cat=cat, err=err, second=is_second, moving=(e[1], e[2]) != (p[1], p[2])))
    return rows


def share15(U):
    v = [r['err'] >= 1.5 for R in U for r in R]
    return float(np.mean(v)) if v else float('nan')


if __name__ == '__main__':
    groups = {'R1e': load('R1e'), 'STACK_ALON': load('STACK_ALON'), 'STACK_OFF': load('STACK_ALOFF') + load('STACK_RA')}
    pros = pickle.load(open('pro_q.pkl', 'rb'))
    print('== consecutive defensive pairs (both plays aimed at my half, no X-Bow); threat = enemy play cost landing at Y<20 in the 8 s before')
    for g, L in groups.items(): summarise(g, [live_plays(m) for m in L])
    summarise('PRO', [pro_plays(r) for r in pros])
    print('\n== live cadence: tap->confirm, confirm->next tap')
    for g, L in groups.items():
        lat, nxt = [], []
        for m in L:
            for c in m['conf']:
                pl = [p for p in m['play'] if p['t'] < c['t']]
                if pl: lat.append((c['t'] - pl[-1]['t']) / 20)
                nx = [p for p in m['play'] if p['t'] > c['t']]
                if nx: nxt.append((nx[0]['t'] - c['t']) / 20)
        print(g, 'tap->confirm median %.2fs p90 %.2fs | next tap within 0.2 s of a confirm: %.2f of confirms | median confirm->next tap %.1fs' % (
            np.median(lat), np.percentile(lat, 90), np.mean(np.array(nxt) <= 0.2), np.median(nxt)))
    print('\n== IW ability pressed within 3 s after my Log/Tornado')
    for g, L in groups.items():
        k, n = ability_after_spell(L); print(g, '%d/%d=%.2f [%.2f,%.2f]' % (k, n, *wilson(k, n)))
    k, n = pro_ability_after_spell(); print('PRO hero crawl (any own spell)', '%d/%d=%.2f [%.2f,%.2f]' % (k, n, *wilson(k, n)))
    print('\n== forecast error: 26-tick dead reckoning vs real position, enemy units that moved, recorded-frame matches')
    rec = [m for g in ('R1e', 'R1e_late', 'STACK_ALON', 'STACK_ALOFF', 'STACK_RA') for m in load(g) if m['frames']]
    per = [forecast_rows(m) for m in rec]
    print('matches with frames', len(rec))
    for cat in ('no_recent_play', 'my_other_play', 'my_effect_elsewhere', 'my_effect_hit'):
        u = [[r for r in R if r['cat'] == cat and r['moving']] for R in per]
        n = sum(len(R) for R in u)
        print('%-20s n=%6d  err>=1.5 tiles: %s  median err %.2f' % (cat, n, fmt(boot(u, share15, B=300)),
                                                                  np.median([r['err'] for R in u for r in R]) if n else float('nan')))
    for cat in ('my_effect_hit', 'my_other_play', 'no_recent_play'):
        v = [[r for r in R if r['cat'] == cat and r['second'] and r['moving']] for R in per]
        print('  at SECOND-play decisions (<=0.2 s after a confirm) %-16s n=%d err>=1.5: %s' % (cat, sum(len(R) for R in v), fmt(boot(v, share15, B=300))))
    pickle.dump(per, open('q3_forecast_rows.pkl', 'wb'))
