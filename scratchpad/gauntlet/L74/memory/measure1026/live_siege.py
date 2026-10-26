"""measure1026 Q2 live: every ENEMY Mortar (and, for comparison, enemy X-Bow) body in our Ranked live matches, from the raw frame
track in live_cache.pkl (live_pass.py), per model (CLX / CLXIII / CLXIV) + the live win rate vs Mortar decks.

    icebow/.venv/Scripts/python.exe -B -X utf8 scratchpad/gauntlet/L74/memory/measure1026/live_siege.py > live_siege.out

Per body (reader address; card = catalog display name of the reader card id):
  presence    first -> last frame seen (s; includes the 3.5 s deploy, so an expired 30 s building shows ~33.5 s);
              'killed' = gone before 31 s and not at the match end (censored when last seen <= 1 s before the last frame)
  shells      unique projectile addresses whose SOURCE address is the body; 'tower' = aimed within 1.2 tiles of an own tower
  per-shell   the aimed tower's HP drop from the last frame <= landing (= the shell's last frame) to the first frame >= landing + 8
              ticks (other attackers can add to a drop: the median is the clean read)
  threatened  the own princess its first tower shell aimed at; else the one on its side of the centre line
  in reach    <= 13.5 tiles (centre to centre) from the threatened princess (habit_terms.XB_REACH)
  response    own plays in (first seen, +8 s] by position: ON it (<= 3.5 tiles from it) / IN FRONT (<= 6 tiles of the threatened
              princess, not on it) / ELSEWHERE; plus own X-Bow, Rocket, Log
  pummelled   in reach, >= 3 shells on a tower, and no own play ON it within 8 s
The same placements through siege_lib.report (the rule the pro numbers use) are printed at the end. CIs: Wilson 95 % on body
shares, match-cluster bootstrap where stated."""
import math
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import siege_lib as S  # noqa: E402

TICK = .05
W8 = 160


def own_xy(x, y, side):
    return (x / 18000, 1 - y / 32000) if side == 0 else (1 - x / 18000, y / 32000)


def bodies_of(m):
    side, t = m['side'], m['track']
    last_frame = t['towers'][-1][0] if t['towers'] else m['last']
    own_tw = {}
    series = defaultdict(list)                                   # (side, x, y) -> [(tick, hp)]
    for tk, tw in t['towers']:
        for s_, x, y, hp, mx in tw:
            series[(s_, x, y)].append((tk, hp))
            if s_ == side:
                own_tw[(x, y)] = 0 if abs(x - 9000) < 1000 else (1 if own_xy(x, y, side)[0] < .5 else 2)
    by = defaultdict(list)
    for b in t['bodies']:
        if b[1] != side and b[6] >= 1000:     # max HP: an evolved Mortar's Goblins share its reader card id (323 HP)
            by[b[2]].append(b)
    shells = defaultdict(dict)
    for p in t['proj']:
        tk, s_, pa, src, x, y, tx, ty, cid = p
        d = shells[src].setdefault(pa, dict(first=tk, last=tk, tx=tx, ty=ty))
        d['last'] = tk
    own = [e for e in m['events'] if e['type'] == 'play' and e['mine'] and e.get('xy') is not None]
    out = []
    for addr, bs in by.items():
        f0, f1 = bs[0][0], bs[-1][0]
        xy = own_xy(bs[0][3], bs[0][4], side)
        tower_shells, troop_shells, drops, tgt = 0, 0, [], None
        for d in sorted(shells.get(addr, {}).values(), key=lambda d: d['first']):
            hit = next(((x, y) for (x, y) in own_tw if abs(d['tx'] - x) <= 1200 and abs(d['ty'] - y) <= 1200), None)
            if hit is None:
                troop_shells += 1
                continue
            tower_shells += 1
            tgt = tgt if tgt is not None else own_tw[hit]
            ser = series[(side, hit[0], hit[1])]
            ts = [a for a, _ in ser]
            i0 = max(0, np.searchsorted(ts, d['last'], 'right') - 1)
            i1 = np.searchsorted(ts, d['last'] + 8, 'left')
            if i1 < len(ser):
                drops.append(ser[i0][1] - ser[i1][1])
        lane = tgt if tgt in (1, 2) else (1 if xy[0] < .5 else 2)
        reach = S.tiles(xy, S.TOWER_XY[lane])
        resp = [(q['card'], (q['tick'] - f0) * TICK, S.tiles(q['xy'], xy), S.tiles(q['xy'], S.TOWER_XY[lane]))
                for q in own if f0 < q['tick'] <= f0 + W8]
        cen = f1 >= last_frame - 20
        pres = (f1 - f0) * TICK
        out.append(dict(card='mortar' if bs[0][7] == 'Mortar' else 'x-bow', addr=addr, pres=pres, censored=cen,
                        killed=(not cen) and pres < 31, hp_last=bs[-1][5] / max(bs[0][6], 1), reach=reach, in_reach=reach <= S.REACH,
                        tower_shells=tower_shells, troop_shells=troop_shells, drops=drops, resp=resp,
                        on=[r for r in resp if r[2] <= S.ON_R], front=[r for r in resp if r[2] > S.ON_R and r[3] <= 6],
                        elsewhere=[r for r in resp if r[2] > S.ON_R and r[3] > 6]))
    return out


def wl(k, n):
    lo, hi = S.wilson(k, n)
    return f'{k / n:.3f} [{lo:.3f}, {hi:.3f}] ({k}/{n})' if n else 'n/a'


def body_report(title, B):
    print(f'\n### {title}: {len(B)} bodies')
    if not B:
        return
    R = [b for b in B if b['in_reach']]
    for lab, X in (('all', B), ('in reach', R)):
        if not X:
            continue
        ts = [b['tower_shells'] for b in X]
        dr = [d for b in X for d in b['drops']]
        print(f'  [{lab}] n {len(X)}: hit our tower (>= 1 shell) {wl(sum(t > 0 for t in ts), len(X))}; tower shells / body mean '
              f'{np.mean(ts):.2f} (max {max(ts)}); troop shells / body {np.mean([b["troop_shells"] for b in X]):.2f}; '
              f'per-shell tower HP drop median {np.median(dr) if dr else float("nan"):.0f} (n {len(dr)}); '
              f'tower HP lost to shells / body (sum of drops) mean {np.mean([sum(b["drops"]) for b in X]):.0f}')
        pr = [b['pres'] for b in X if not b['censored']]
        print(f'      presence s (uncensored n {len(pr)}): median {np.median(pr) if pr else float("nan"):.1f}, '
              f'p25 {np.percentile(pr, 25) if pr else float("nan"):.1f}, p75 {np.percentile(pr, 75) if pr else float("nan"):.1f}; '
              f'killed before 31 s {wl(sum(b["killed"] for b in X), sum(not b["censored"] for b in X))}')
        print(f'      within 8 s: any own play {wl(sum(bool(b["resp"]) for b in X), len(X))}; ON it {wl(sum(bool(b["on"]) for b in X), len(X))}; '
              f'IN FRONT of the threatened princess {wl(sum(bool(b["front"]) for b in X), len(X))}; ONLY elsewhere '
              f'{wl(sum(bool(b["elsewhere"]) and not b["on"] and not b["front"] for b in X), len(X))}; nothing '
              f'{wl(sum(not b["resp"] for b in X), len(X))}')
        print(f'      own X-Bow in 8 s {wl(sum(any(r[0] == "x-bow" for r in b["resp"]) for b in X), len(X))}; Rocket ON it '
              f'{wl(sum(any(r[0] == "rocket" for r in b["on"]) for b in X), len(X))}; Log ON it '
              f'{wl(sum(any(r[0] == "the-log" for r in b["on"]) for b in X), len(X))}; PUMMELLED (>= 3 tower shells, nothing ON it '
              f'in 8 s) {wl(sum(b["tower_shells"] >= 3 and not b["on"] for b in X), len(X))}')
        print(f'      plays by place: ON {Counter(r[0] for b in X for r in b["on"]).most_common(6)} | FRONT '
              f'{Counter(r[0] for b in X for r in b["front"]).most_common(6)} | ELSEWHERE '
              f'{Counter(r[0] for b in X for r in b["elsewhere"]).most_common(6)}')
        fr = [b['resp'][0] for b in X if b['resp']]
        if fr:
            print(f'      first own play: delay median {np.median([r[1] for r in fr]):.1f} s, {np.median([r[2] for r in fr]):.1f} tiles from it, '
                  f'{np.median([r[3] for r in fr]):.1f} tiles from the threatened princess; cards {Counter(r[0] for r in fr).most_common(6)}')


def main():
    cache = pickle.load(open(HERE / 'live_cache.pkl', 'rb'))
    M = [m for m in cache.values() if m['pmax'] == S.PRINCESS_HP and ((m['end'] or {}).get('towers') or {}).get('crowns_me') is not None]
    print(f'{len(M)} main-account Ranked matches')
    print('\n## live win rate vs decks with a Mortar (the opponent played one) vs other decks')
    for g in ('CLX', 'CLXIII', 'CLXIV', None):
        X = [m for m in M if g is None or m['model'] == g]
        won = lambda m: bool(m['end']['towers'].get('won'))
        a = [m for m in X if 'mortar' in m['opp_cards']]
        o = [m for m in X if 'mortar' not in m['opp_cards']]
        k1, n1, k2, n2 = sum(map(won, a)), len(a), sum(map(won, o)), len(o)
        l1, u1 = S.wilson(k1, n1)
        l2, u2 = S.wilson(k2, n2)
        d = k1 / n1 - k2 / n2 if n1 and n2 else float('nan')
        lo = d - math.sqrt((k1 / n1 - l1) ** 2 + (u2 - k2 / n2) ** 2) if n1 else float('nan')
        hi = d + math.sqrt((u1 - k1 / n1) ** 2 + (k2 / n2 - l2) ** 2) if n1 else float('nan')
        print(f'  {g or "pooled":7s} Mortar decks {wl(k1, n1)} ({n1 / len(X):.3f} of matches) | others {wl(k2, n2)} | '
              f'diff {d * 100:+.1f} pp [{lo * 100:+.1f}, {hi * 100:+.1f}]')
    allb = defaultdict(list)
    plc = defaultdict(list)
    for m in M:
        if 'track' not in m:
            continue
        for b in bodies_of(m):
            allb[(m['model'], b['card'])].append(b)
            allb[('pooled', b['card'])].append(b)
        p = S.placements(m['events'])
        for g in (m['model'], 'pooled'):
            for k in ('mortar', 'x-bow'):
                q = [x for x in p if x['card'] == k]
                if q:
                    plc[(g, k)].append(q)
    print('\n## per enemy body (raw frame track)')
    for g in ('CLX', 'CLXIII', 'CLXIV', 'pooled'):
        for k in ('mortar', 'x-bow'):
            body_report(f'{g} enemy {k}', allb.get((g, k), []))
    print('\n## same placements through siege_lib.report (the pro rule; memory events)')
    for g in ('CLX', 'CLXIII', 'pooled'):
        for k in ('mortar', 'x-bow'):
            if plc.get((g, k)):
                S.report(f'LIVE {g} vs opponent {k}', plc[(g, k)])


if __name__ == '__main__':
    main()
