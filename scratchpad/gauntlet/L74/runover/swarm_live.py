"""L74 runover: the bot's answer to skeleton swarms / Skeleton Barrels on its half (live, cache.pkl).

Episode = enemy Skeleton Barrel (parent body, any form) or >= 4 enemy skeleton bodies (any source, by resolved class
'skeletons'/'skeleton_army') on my half (own y < 16); new episode after 5 s without. Response window = first 6 s.
Reports: elixir at start, plays in the window (cards), share with a swarm answer (Log, Tesla, IceWizard, Tornado, Knight
... listed separately), share where such a card was affordable at some state but not played, gate p vs tau there, and the
tower HP lost in the 12 s after the start. Matches with non-icebow plays excluded.
"""
import os, sys, json, pickle, collections, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__))
TPS = 20.0
ICEBOW = {'Xbow', 'Tesla', 'IceWizard', 'Knight', 'Log', 'Tornado', 'Rocket', 'Skeletons'}
SPLASH = {'Log', 'Tesla', 'IceWizard', 'Tornado'}
cache = pickle.load(open(os.path.join(HERE, 'cache.pkl'), 'rb'))
M = {json.loads(l)['file']: json.loads(l) for l in open(os.path.join(HERE, 'matches.jsonl'))}
out = []
def P(*a): out.append(' '.join(str(x) for x in a))


def episodes(S, kind):
    ev, last = [], -1e9
    for i, s in enumerate(S):
        if kind == 'barrel':
            on = any(e[2] == 'SkeletonBalloon' and e[8] is True and e[1] < 16 for e in s[6])
        else:
            on = sum(1 for e in s[6] if e[6] in ('skeletons', 'skeleton_army') and e[1] < 16) >= 4
        if on:
            if s[0] - last > 5 * TPS: ev.append(i)
            last = s[0]
    return ev


for kind in ('barrel', 'swarm'):
    rows = []
    for b, m in M.items():
        r = cache[b]
        if any(p[1] not in ICEBOW for p in r['plays']): continue
        S = r['S']
        for i in episodes(S, kind):
            t = S[i][0]
            win = [s for s in S[i:] if s[0] <= t + 6 * TPS]
            plays = [p[1] for p in r['plays'] if p[0] is not None and t - 1 * TPS <= p[0] <= t + 6 * TPS]
            aff_held, ps, taus = set(), [], []
            for s in win:
                el = s[1] or 0
                aff = {h[0] for h in s[2] if h[0] in SPLASH and (h[1] or 99) <= el + 0.05}
                if aff and not s[3][0]:
                    aff_held |= aff; ps.append(s[3][1]); taus.append(s[3][2])
            def hp(s): return sum(s[4].values())
            later = [s for s in S[i:] if s[0] <= t + 12 * TPS]
            lost = hp(S[i]) - hp(later[-1]) if later else 0
            rows.append(dict(file=b, fam=m['fam'], result=m['result'], el=S[i][1] or 0, plays=plays,
                             splash=any(p in SPLASH for p in plays), aff_held=sorted(aff_held - set(plays)),
                             p=st.median([x for x in ps if x is not None]) if ps and any(x is not None for x in ps) else None,
                             tau=st.median([x for x in taus if x is not None]) if taus and any(x is not None for x in taus) else None,
                             lost=lost))
    for lab, sel in (('all families', lambda r: True), ('towerref_w2 (current)', lambda r: r['fam'] == 'towerref_w2'),
                     ('fv6 (stack2k + towerref)', lambda r: r['fam'] in ('towerref_w2', 'stack2k_cellref'))):
        R = [r for r in rows if sel(r)]
        if not R: continue
        n = len(R)
        P(f'\n=== {kind} episodes on my half, {lab}: n={n} in {len({r["file"] for r in R})} matches')
        P(f'  elixir at start: median {st.median([r["el"] for r in R]):.1f}; < 2: {sum(r["el"] < 2 for r in R)}; < 3: {sum(r["el"] < 3 for r in R)}')
        P(f'  any play within -1..+6 s: {sum(bool(r["plays"]) for r in R)}/{n}; a splash answer (Log/Tesla/IW/Tornado): {sum(r["splash"] for r in R)}/{n}')
        c = collections.Counter(p for r in R for p in r['plays']); P('  cards played:', dict(c.most_common()))
        first = collections.Counter(r['plays'][0] if r['plays'] else '(none)' for r in R); P('  first card:', dict(first.most_common()))
        nh = [r for r in R if not r['splash'] and r['aff_held']]
        P(f'  NO splash answer although one was affordable and the gate held: {len(nh)}/{n}; held: '
          f'{dict(collections.Counter(x for r in nh for x in r["aff_held"]).most_common())}; p median '
          f'{st.median([r["p"] for r in nh if r["p"] is not None]) if nh else None} vs tau {st.median([r["tau"] for r in nh if r["tau"] is not None]) if nh else None}')
        nb = [r for r in R if not r['splash'] and not r['aff_held']]
        P(f'  NO splash answer and none affordable (broke / not in hand): {len(nb)}/{n}')
        for lab2, rr in (('splash answer', [r for r in R if r['splash']]), ('no splash answer', [r for r in R if not r['splash']])):
            if rr: P(f'  tower HP lost in 12 s after start, {lab2}: median {st.median([r["lost"] for r in rr]):.0f} mean {sum(r["lost"] for r in rr) / len(rr):.0f} (n {len(rr)})')
open(os.path.join(HERE, 'swarm_live.txt'), 'w').write('\n'.join(out) + '\n')
print('\n'.join(out))
