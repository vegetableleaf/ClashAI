"""L74/habits follow-ups on the live cache + pro sides (same definitions as hablib):
  1 match-level early bridge X-Bow (first 2 plays) vs not, by the counter band / punish window at that X-Bow
  2 opponent CYCLE at bridge X-Bows: every heavy card the opponent has shown was among its last 4 plays (= not in hand)
  3 X-Bow life distribution (natural lifetime vs destroyed early) and 'crushed' (life < 12 s) by heavy-at-it
  4 heavy-push responses when the Rocket was in hand AND affordable (own elixir >= 6)
  5 Rockets per minute and per-match differences between Marks (match bootstrap)
    python extra.py"""
import json
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hablib as H  # noqa: E402
import live_tables as LT  # noqa: E402
import pro_tables as PT  # noqa: E402

pct = LT.pct


def diff_ci(a, b, f, B=2000, seed=1):
    rng = random.Random(seed)
    d = []
    for _ in range(B):
        x = [rng.choice(a) for _ in a]
        y = [rng.choice(b) for _ in b]
        try:
            d.append(f(x) - f(y))
        except ZeroDivisionError:
            pass
    d.sort()
    return round(f(a) - f(b), 3), (round(d[int(.025 * len(d))], 3), round(d[int(.975 * len(d)) - 1], 3))


def heavy_out(m, t):
    """None = the opponent has shown no heavy card yet; True = every heavy shown is among its last 4 plays (not in hand)."""
    prior = [p for p in sorted(m['opp'], key=lambda p: p['tick']) if p['tick'] < t]
    heavy = {p['card'] for p in prior if (H.kind(p['card']) == 'troop' and H.cost(p['card']) >= H.HEAVY_COST)
             or p['card'] in H.BIG_SPELLS}
    if not heavy:
        return None
    last4 = {p['card'] for p in prior[-4:]}
    return heavy <= last4


def main():
    live = LT.load()
    pros = PT.load()
    LG = ['CXXIV', 'CXXXVIII', 'CLIII']
    PG = ['pro icebow crawl2', 'pro icebow8 HF', 'pro other X-Bow HF']
    print('## 1. Match level: the FIRST bridge X-Bow among the first 2 plays (early) vs later / none')
    for g in LG + PG:
        M = [m for m in live + pros if m['group'] == g]
        rows = []
        for m in M:
            x = H.xbow_events(m)
            f = x[0] if x else None
            rows.append(dict(key=m['key'], win=m['win'], early=bool(f and f['early']), band=f and f['band'],
                             punish=f and f['punish'], heavy=f and f['heavy']))
        E = [r for r in rows if r['early']]
        N = [r for r in rows if not r['early']]
        d, ci = diff_ci(E, N, H.wr) if E and N else (float('nan'), ('', ''))
        line = f"  {g:20s} matches {len(rows):5d}  early {pct(len(E) / len(rows))}  win early {pct(H.wr(E))} vs not {pct(H.wr(N))}  diff {d:+.3f} {ci}"
        sub = []
        for lab, f in (('est>=7', lambda r: r['band'] == '>=7'), ('est<7', lambda r: r['band'] in ('<=3', '4-6')),
                       ('no punish', lambda r: r['punish'] is False), ('punish', lambda r: r['punish'] is True),
                       ('heavy came', lambda r: r['heavy'] is True), ('no heavy', lambda r: r['heavy'] is False)):
            S = [r for r in E if f(r)]
            if S:
                sub.append(f"{lab} {len(S)}: {pct(H.wr(S))}")
        print(line + '\n      early & ' + '; '.join(sub))
    print('\n## 2. Opponent cycle at bridge X-Bows: P(heavy card / big spell at the X-Bow within 8 s) by heavy-out-of-hand')
    for g in LG + PG:
        M = [m for m in live + pros if m['group'] == g]
        rows = []
        for m in M:
            for r in H.xbow_events(m):
                r['out'] = heavy_out(m, r['tick'])
                rows.append(r)
        parts = []
        for lab, v in (('none shown yet', None), ('heavy in hand possible', False), ('every heavy out of hand', True)):
            S = [r for r in rows if r['out'] is v]
            if S:
                parts.append(f"{lab}: n {len(S)} heavy-next {pct(H.mean([r['heavy'] for r in S]))} win {pct(H.wr(S))}")
        print(f'  {g:20s} ' + ' | '.join(parts))
        for b in ('<=3', '4-6', '>=7'):
            parts = []
            for lab, v in (('possible', False), ('out', True)):
                S = [r for r in rows if r['out'] is v and r['band'] == b]
                if S:
                    parts.append(f"{lab} n {len(S)} heavy {pct(H.mean([r['heavy'] for r in S]))}")
            print(f'      est {b:4s} ' + ' | '.join(parts))
    print('\n## 3. Live X-Bow life (bridge X-Bows; censored at match end excluded)')
    for g in LG:
        M = [m for m in live if m['group'] == g]
        rows = [r for m in M for r in H.xbow_events(m) if 'life_s' in r and r['end_tick'] < m['frames'][-1][0] - 20]
        L = sorted(r['life_s'] for r in rows)
        q = lambda p: L[int(p * (len(L) - 1))]
        print(f"  {g:9s} n {len(L)} life p10/25/50/75/90/max {q(.1)}/{q(.25)}/{q(.5)}/{q(.75)}/{q(.9)}/{L[-1]}  "
              f"share >= 25 s {pct(sum(x >= 25 for x in L) / len(L))}")
        for lab, f in (('heavy came', lambda r: r['heavy']), ('no heavy', lambda r: not r['heavy'])):
            S = [r for r in rows if f(r)]
            print(f"      {lab:10s} n {len(S)} crushed(<12 s) {pct(H.mean([r['life_s'] < 12 for r in S]))} "
                  f"median life {statistics.median(r['life_s'] for r in S)} dmg {H.mean([r['dmg'] for r in S]):.0f} win {pct(H.wr(S))}")
        for b in ('<=3', '4-6', '>=7'):
            S = [r for r in rows if r['band'] == b]
            print(f"      est {b:4s} n {len(S)} crushed {pct(H.mean([r['life_s'] < 12 for r in S]))} dmg {H.mean([r['dmg'] for r in S]):.0f}"
                  f" heavy {pct(H.mean([r['heavy'] for r in S]))} win {pct(H.wr(S))}")
    print('\n## 4. Live heavy pushes (body-based) when the Rocket was in hand AND own elixir >= 6 at the event')
    for g in LG:
        R = [r for m in live if m['group'] == g for r in LT.body_pushes(m)]
        S = [r for r in R if r['rocket_in_hand'] and (r['own_el'] or 0) >= 6]
        if not S:
            continue
        c = Counter(r['resp'] for r in S)
        print(f"  {g:9s} {len(S)} of {len(R)} pushes: " + ', '.join(f"{k} {pct(v / len(S))}" for k, v in c.most_common()) +
              f"  | tower HP taken: cheap_only {H.mean([r['taken'] for r in S if r['resp'] == 'cheap_only']):.0f}, "
              f"rocket(any) {H.mean([r['taken'] for r in S if r['resp'].startswith('rocket')]):.0f}, "
              f"other {H.mean([r['taken'] for r in S if r['resp'] == 'other']):.0f}")
    print('\n## 5. Rockets per match / per minute (match bootstrap), and differences')
    per = {}
    for g in LG + PG:
        M = [m for m in live + pros if m['group'] == g and m.get('rocket_deck', True)]
        rows = []
        for m in M:
            mins = (m['meta']['end'] or {}).get('seconds', 0) / 60 if 'meta' in m else max(q['tick'] for q in m['own'] + m['opp']) * H.TICK_S / 60
            k = sum(q['card'] == 'rocket' for q in m['own'])
            rows.append(dict(key=m['key'], n=k, mins=max(mins, .5)))
        per[g] = rows
        f = lambda s: sum(r['n'] for r in s) / len(s)
        fm = lambda s: sum(r['n'] for r in s) / sum(r['mins'] for r in s)
        print(f"  {g:20s} matches {len(rows):5d}  Rockets/match {f(rows):.2f} {H.boot_ci(rows, f)}  per minute {fm(rows):.3f} {H.boot_ci(rows, fm)}"
              f"  mean match {H.mean([r['mins'] for r in rows]):.2f} min")
    f = lambda s: sum(r['n'] for r in s) / len(s)
    fm = lambda s: sum(r['n'] for r in s) / sum(r['mins'] for r in s)
    for a, b in (('CLIII', 'CXXXVIII'), ('CXXXVIII', 'CXXIV'), ('CLIII', 'CXXIV')):
        print(f"  {a} - {b}: per match {diff_ci(per[a], per[b], f)}  per minute {diff_ci(per[a], per[b], fm)}")


if __name__ == '__main__':
    main()
