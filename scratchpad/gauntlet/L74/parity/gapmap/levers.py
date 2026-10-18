"""Lever sizing on FIN12_stamped: failing fights (joined.tsv) -> mechanism levers; recoverable = sum(ceil - aK) (the fight
scores its noise ceiling once its cause is fixed: an UPPER bound). Unlabeled fights are spread over the levers by this
gapmap's sample (mine.tsv), weighted per stratum. Then the cumulative scenario (biggest lever first, full recovery) on the
two trigger halves at the +DAYS projection (trigger.json: per-card p_need, f).
usage: python levers.py joined.tsv trigger.json sample.txt [DAYS=3] > LEVERS.txt"""
import json, sys
from collections import defaultdict
from trigger import p_need, GOAL_ALL, GOAL_CARD, GOAL_N, TIER_SHARE
from buckets import R7


def lever(src, fam, cls):
    f = fam.lower()
    if cls == 'N':
        return 'N noise (ceiling <= 0.75)'
    if 'stale' in f:
        return '? unlabeled'
    if src == 'mine':
        return fam.split(':', 1)[1]
    if 'setup-steer' in f:
        return 'U/H set-up walker movement state'
    if any(k in f for k in ('r7a:pos', 'r7c:swarm', 'r7dauto:p', 'movement', 'swarm / walker', 'r5d:p ', 'p-other')):
        return 'S swarm / walker movement (new bodies)'
    if 'r7a:unp' in f:
        return 'S/H unpaired body first (spawn point / pairing)'
    if 'h-order' in f:
        return 'H H-ORDER tie flips (broke FIN11-agreeing fights)'
    if 'mega knight' in f or 'mk stand' in f or 'uppercut' in f:
        return 'S Mega Knight jump / landing / stand'
    if 'tesla' in f:
        return 'S Tesla hide / under-damage'
    if any(k in f for k in ('hittick', 'ekret', 'ekint', 'pulse')):
        return 'S Evo Knight reduction / hit tick'
    if 'iwcube' in f or 'iw-press-date' in f:
        return 'H Hero IW cube / press date'
    if any(k in f for k in ('target pick', 'r7dauto:t', 'r7a:tgt', 's target', 'tower acquisition')):
        return 'S target pick (acquisition / retarget)'
    if any(k in f for k in ('hit / death', 'r7c:b', 'r7dauto:d', 'r7dauto:k', 'r5d:x', 'r7a:hp', 's(b)', 'first divergence',
                            'no paired', 'r6c:s (b)', 'own skeletons', 'iw splash', 'opp iw', 'opp gg', 'kill timing')):
        return 'S unresolved hit / death timing'
    if cls.startswith('U'):
        return 'U other reader gaps (hp -1 overheal, unseen hit)'
    if cls.startswith('H'):
        return 'H other harness'
    if cls.startswith('S'):
        return 'S other laws'
    return '? unlabeled'


def main(jpath, tpath, spath, days):
    T = json.load(open(tpath))
    M, per_day, S = T['M'], T['per_day'], T['stats']
    cards = {c['card']: c for c in T['cards']}
    J = [l.rstrip('\n').split('\t') for l in open(jpath, encoding='utf-8')]
    # stratum weights for the sample: own all, big opp <= 5 of the card's unlabeled, rest random 30 of the remainder
    samp = {l.split('\t')[0] for l in open(spath)}
    unl = [j for j in J if j[6] == '?' or j[8] == 'mine']        # the population the sample was drawn from
    by_card = defaultdict(list)
    for j in unl:
        by_card[j[2]].append(j)
    big = {c for c, xs in by_card.items() if not c.startswith('own ') and sum(1-float(x[3]) for x in xs) >= 5}
    rest_all = [j for j in unl if not j[2].startswith('own ') and j[2] not in big]
    rest_s = [j for j in rest_all if f"{j[0]}@{j[1]}" in samp]
    w_rest = len(rest_all)/max(1, len(rest_s))
    mine = {}
    for j in J:
        if j[8] == 'mine':
            mine[j[0], j[1], j[2]] = lever('mine', j[7], j[6])
    rows = []                                    # (card, lever, mass, rec, weight)
    unl_sample = []
    for j in J:
        stem, t0, card, aK, ceil, cls, fam, src = j[0], j[1], j[2], float(j[3]), j[4], j[6], j[7], j[8]
        c = float(ceil) if ceil not in ('', 'None') else 1.
        L = lever(src, fam, cls)
        rows.append((card, L, 1-aK, max(0., c-aK), 1.))
        if src == 'mine':
            if card.startswith('own '):
                w = 1.
            elif card in big:
                w = len(by_card[card])/sum(1 for x in by_card[card] if f"{x[0]}@{x[1]}" in samp)
            else:
                w = w_rest
            unl_sample.append((card, L, 1-aK, max(0., c-aK), w))
    # extrapolate: unlabeled fights NOT in the sample get the sample's lever mix of their stratum
    labeled_or_sampled = [r for r in rows if r[1] != '? unlabeled']
    left = [(j[2], 1-float(j[3]), max(0., (float(j[4]) if j[4] not in ('', 'None') else 1.)-float(j[3]))) for j in J
            if j[6] == '?' and j[8] != 'mine']
    def mix(pred):
        xs = [s for s in unl_sample if pred(s[0])]
        tot = sum(s[3]*s[4] for s in xs)
        m = defaultdict(float)
        for s in xs:
            m[s[1]] += s[3]*s[4]/tot if tot else 0
        return m
    mix_big = {c: mix(lambda x, c=c: x == c) for c in big}
    mix_rest = mix(lambda x: not x.startswith('own ') and x not in big)
    extra = []
    for card, mass, rec in left:
        m = mix_big.get(card) or mix_rest
        for L, share in m.items():
            extra.append((card, L, mass*share, rec*share, share))
    allr = labeled_or_sampled + extra
    lev = defaultdict(lambda: dict(mass=0., rec=0., n=0., cards=defaultdict(float)))
    for card, L, mass, rec, w in allr:
        lev[L]['mass'] += mass; lev[L]['rec'] += rec; lev[L]['n'] += w; lev[L]['cards'][card] += rec
    N = S['OVERALL']['n']
    # cumulative scenario at +days
    def state(fixed, frac=1.):
        rec_c = defaultdict(float)
        for card, L, mass, rec, w in allr:
            if L in fixed:
                rec_c[card] += rec*frac
        sumaK = {c: S[c]['p']*S[c]['n'] for c in S}
        o_p = (sumaK['OVERALL'] + sum(rec_c.values()))/N
        sB, meet, flips = T['tierB_share'], 0., []
        for c, r in cards.items():
            if 'n' not in r:
                continue
            p = (sumaK[c] + rec_c.get(c, 0))/S[c]['n']
            if rec_c.get(c) and r['ceil'] is not None:
                p = min(p, max(r['ceil'], r['p']))          # a perfect SIM scores the noise ceiling on average
            n2 = r['n'] + days*per_day*r['rate']
            need = p_need(n2, r['f'], GOAL_CARD)
            ok = n2 >= GOAL_N and (p >= 1 or (need is not None and p >= need))
            if ok:
                meet += r['share']
                if not r['meets']:
                    flips.append(c)
        n2o = N*(M + days*per_day)/M
        return o_p, p_need(n2o, T['f_overall'], GOAL_ALL), meet/sB, flips
    out = [f"failing fights {len(J)}; labeled by rounds 4-7 {sum(1 for j in J if j[6] != '?')}, this gapmap's sample "
           f"{len(unl_sample)}, extrapolated {len(left)} (stratum mix of the sample)", '',
           'lever | fights | miss mass | recoverable (UB) | overall +p (UB) | in r7 buckets (a/b/c/d) | tier-B coverage alone '
           f'(+{days:g} d; data-only base) | top cards by recoverable']
    base_cov = None
    for L, v in sorted(lev.items(), key=lambda kv: -kv[1]['rec']):
        top = sorted(v['cards'].items(), key=lambda kv: -kv[1])[:6]
        inb = '/'.join(f"{sum(x for c, x in v['cards'].items() if c in R7[b]):.0f}" for b in ('r7a', 'r7b', 'r7c', 'r7d'))
        alone = state({L})[2]
        base_cov = state(set())[2]
        out.append(f"{L} | {v['n']:.0f} | {v['mass']:.1f} | {v['rec']:.1f} | +{v['rec']/N:.4f} | {inb} | {alone:.3f} "
                   f"({alone-base_cov:+.3f}) | " + ', '.join(f"{c} {x:.1f}" for c, x in top))
    order = [L for L, _ in sorted(lev.items(), key=lambda kv: -kv[1]['rec']) if not L.startswith(('N ', '?'))]
    out += ['', f"CUMULATIVE (full recovery, biggest first) at +{days} d of live data (per-card p_need from trigger.json; a card "
            f"counts when its new p >= its p_need at its +{days} d n):",
            'after lever | overall p (need) | tier-B coverage (need 0.90) | cards meeting at +d that do not meet today']
    o, need, cov, fl = state(set())
    out.append(f"(none: data only) | {o:.4f} ({need:.4f}) | {cov:.3f} | {', '.join(fl)}")
    done = set()
    for L in order:
        done.add(L)
        o, need, cov, fl = state(done)
        out.append(f"+ {L} | {o:.4f} ({need:.4f}) | {cov:.3f} | {len(fl)} cards")
    out.append('  final flips: ' + ', '.join(fl))
    # card-first view: what each tier-B card that does not meet needs, and where its recoverable mass sits
    out += ['', f"PER CARD (tier B, not meeting): fights to recover for p >= p_need(+{days:g} d) vs recoverable, and its levers",
            'card | share | n | p | p_need | deficit (fights) | recoverable | needed share of recoverable | levers (recoverable)']
    for c, r in sorted(cards.items(), key=lambda kv: -kv[1]['share']):
        if 'n' not in r or r['meets']:
            continue
        n2 = r['n'] + days*per_day*r['rate']
        need = p_need(n2, r['f'], GOAL_CARD)
        rc = defaultdict(float)
        for card, L, mass, rec, w in allr:
            if card == c and not L.startswith('N '):
                rc[L] += rec
        tot = sum(rc.values())
        dfc = None if need is None else max(0., (need - r['p'])*r['n'])
        lim = 'n < 30 at +d' if n2 < GOAL_N else ('cannot (p_need > ceiling ' + f"{r['ceil']:.3f})" if need is None or
              (r['ceil'] is not None and need > r['ceil']) else '')
        out.append(f"{c} | {r['share']:.4f} | {r['n']} | {r['p']:.3f} | {'-' if need is None else f'{need:.3f}'} | "
                   f"{'-' if dfc is None else f'{dfc:.1f}'} | {tot:.1f} | "
                   f"{'-' if dfc is None or not tot else f'{dfc/tot:.0%}'} {lim} | " +
                   ', '.join(f"{L.split(' ', 1)[1][:28]} {x:.1f}" for L, x in sorted(rc.items(), key=lambda kv: -kv[1])[:4]))
    allL = set(order)
    out += ['', f"LEAVE-ONE-OUT at +{days:g} d (every other lever fully recovered): what is lost without this lever",
            'lever missing | overall p (need) | tier-B coverage | cards that then miss']
    o_all, need_all, cov_all, fl_all = state(allL)
    for L in order:
        o, need, cov, fl = state(allL - {L})
        lost = [c for c in fl_all if c not in fl]
        out.append(f"- {L} | {o:.4f} ({need:.4f}) | {cov:.3f}{' GATES' if cov < TIER_SHARE <= cov_all else ''} | {', '.join(lost)}")
    out += ['', 'HALF recovery (each lever recovers 50% of its recoverable mass), same order:']
    done = set()
    for L in order:
        done.add(L)
        o, need, cov, fl = state(done, .5)
        out.append(f"+ {L} | {o:.4f} ({need:.4f}) | {cov:.3f} | {len(fl)} cards")
    print('\n'.join(out))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else 3.)
