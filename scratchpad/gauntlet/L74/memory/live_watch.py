"""Live watch (owner 10-26: "keep watch of its habits, its rocket use, and changes in strategy mid-match") -- per model key
(a substring of the live log's start record, e.g. CLXIV_MEMORY), from the live reader logs:
  habits    win rate, seconds at >= 9.9 elixir per match, first own play (s), plays / min
  rockets   Rockets / match, tower Rockets / match (aim at a princess / king slot), Rocket + own Tornado combos / match
  xbow      reach X-Bows / match, lock rate (match_memory: princess -5% in 600 ticks)
  ADAPT     mid-match: share of reach X-Bows followed by ANOTHER reach X-Bow within 30 s, after a FAILED vs a LOCKED one;
            X-Bow attempts / min before vs after the match's first failed X-Bow (memory should cut repeats after failures)
Match-cluster bootstrap 95% CIs on the rates. Usage: python live_watch.py KEY [KEY ...] [--since YYYYMMDD_HHMMSS]"""
import argparse
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[3])]
LOGS = HERE.parents[1] / 'L68' / 'live_reader'
TICK0 = 78                     # live game_tick runs 78 ahead of the match clock (gate_metrics)
FULL = 9.9


def matches(key, since):
    import live_dump as LD
    from pipeline import match_memory as M
    for f in sorted(LOGS.glob('live_play_*.jsonl')):
        if since and f.stem.replace('live_play_', '') < since:
            continue
        with open(f, 'rb') as fh:
            ok = False
            for _, raw in zip(range(400), fh):
                if b'"event": "start"' in raw[:60]:
                    ok = key.encode() in raw
                    break
        if not ok:
            continue
        try:
            m = LD.read(f)
        except Exception as exc:                                  # a truncated / odd log: skip, count it
            print(f'skip {f.name}: {exc!r}'[:140], file=sys.stderr)
            continue
        if not m['samples'] or not m['end']:
            continue
        ev = M.build(m['side'], m['samples'], m['plays']).events(m['last'] + 1)
        yield f.name, m, ev


def one(m, ev):
    s = m['samples']
    leak = sum((b['tick'] - a['tick']) * 0.05 for a, b in zip(s, s[1:])
               if (a['elixir'] or 0) >= FULL and (b['elixir'] or 0) >= FULL)
    own = [e for e in ev if e['type'] == 'play' and e['mine']]
    dur = max((m['last'] - TICK0) * 0.05, 1.0)
    first = (min(e['tick'] for e in own) - TICK0) * 0.05 if own else None
    rk = [e for e in own if e['card'] == 'rocket']
    xb = [e for e in own if e['card'] == 'x-bow' and e.get('reach') and e.get('xb')]
    won = bool(((m['end'] or {}).get('towers') or {}).get('won'))
    nxt = {'failed': [0, 0], 'locked': [0, 0]}
    for i, e in enumerate(xb):
        k = 'locked' if e['xb']['locked'] else 'failed'
        nxt[k][1] += 1
        nxt[k][0] += int(i + 1 < len(xb) and xb[i + 1]['tick'] - e['tick'] <= 600)
    f1 = next((e['tick'] for e in xb if not e['xb']['locked']), None)
    pre = post = None
    if f1 is not None:
        pre_min, post_min = max((f1 - TICK0) * 0.05 / 60, 0.25), max((m['last'] - f1) * 0.05 / 60, 0.25)
        pre = sum(e['tick'] <= f1 for e in xb) / pre_min
        post = sum(e['tick'] > f1 for e in xb) / post_min
    return dict(won=won, leak=leak, first=first, ppm=len(own) / (dur / 60), rk=len(rk),
                rk_tower=sum(bool(e.get('aim') is not None) for e in rk), combo=sum(bool((e.get('rk') or {}).get('combo')) for e in rk),
                xb=len(xb), lock=sum(bool(e['xb']['locked']) for e in xb), nxt=nxt, pre=pre, post=post)


def ci(vals, rng, n=1000):
    if not vals:
        return float('nan'), float('nan'), float('nan')
    m = sum(vals) / len(vals)
    bs = sorted(sum(rng.choice(vals) for _ in vals) / len(vals) for _ in range(n))
    return m, bs[int(.025 * n)], bs[int(.975 * n)]


def report(key, rows):
    rng = random.Random(0)
    n = len(rows)
    print(f'## {key}: {n} matches')
    if not n:
        return
    f = lambda k: ci([r[k] for r in rows if r[k] is not None], rng)
    for name, k in (('win rate', 'won'), ('seconds at full / match', 'leak'), ('first play s', 'first'), ('plays / min', 'ppm'),
                    ('Rockets / match', 'rk'), ('tower Rockets / match', 'rk_tower'), ('combos / match', 'combo'),
                    ('reach X-Bows / match', 'xb')):
        m, lo, hi = f(k)
        print(f'  {name:26s} {m:7.3f} [{lo:.3f}, {hi:.3f}]')
    xb, lk = sum(r['xb'] for r in rows), sum(r['lock'] for r in rows)
    print(f'  X-Bow lock rate            {lk / max(xb, 1):7.3f} ({lk}/{xb})')
    for k in ('failed', 'locked'):
        a, b = sum(r['nxt'][k][0] for r in rows), sum(r['nxt'][k][1] for r in rows)
        print(f'  ADAPT next X-Bow <= 30 s after a {k:6s} one: {a / max(b, 1):.3f} ({a}/{b})')
    pp = [(r['pre'], r['post']) for r in rows if r['pre'] is not None]
    if pp:
        print(f'  ADAPT X-Bows / min before vs after the first failure: {sum(p for p, _ in pp) / len(pp):.2f} -> '
              f'{sum(q for _, q in pp) / len(pp):.2f} (n {len(pp)} matches)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('keys', nargs='+')
    ap.add_argument('--since', default='')
    a = ap.parse_args()
    for key in a.keys:
        report(key, [one(m, ev) for _, m, ev in matches(key, a.since)])


if __name__ == '__main__':
    main()
