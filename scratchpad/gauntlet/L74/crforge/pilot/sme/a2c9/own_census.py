"""A2c-9T item 1: every own troop / building play (source own_tap), three dating signals, game vs crforge.
    python3 own_census.py INPUTS.jsonl RUN DEPLOY.jsonl OUT.jsonl
R = the plan's run tick (the phase-3 birth stamp for 4,840 of 4,841 plays; 171753's Knight is own_play_elixir-dated).
crforge puts a play's effects (cost taken, body) on frame R+1.
- tap: R - (the play's own tap tick), the input lag.
- drop: the frame pair (a, b) where our elixir falls by the card's cost (>= cost - 0.11, as own_play_elixir); 'in' when
  a <= R < b (R+1 in (a, b]), 'R_before' when R < a (frame a, after R, still shows the cost untaken), 'R_after' when R >= b.
- move: bp5/deploy_census.py rows of our side born at R+1 (crforge's first move cm vs the game's (m_lo, m_hi]); a play
  agrees when every row agrees; clean = cm <= the run's first divergence for every row."""
import collections, json, os, sys
inp, run, dep, outp = sys.argv[1:5]
T = '/workspace/crforge_cache/tables/16.402.22/'
cost = {}
for f in ('spells_characters', 'spells_buildings', 'spells_other'):
    for n, r in json.load(open(T + f + '.json'))['rows'].items():
        if r['columns'].get('ManaCost') is not None:
            cost.setdefault(n, r['columns']['ManaCost'])
rows = collections.defaultdict(list)
for l in open(dep):
    x = json.loads(l)
    rows[(x['m'], x['side'], x['tb'])].append(x)
res = {}
for l in open(os.path.join(run, 'results.jsonl')):
    x = json.loads(l)
    res[x['match']] = x
cls = lambda lo, hi, R: 'in' if lo < R + 1 <= hi else 'R_before' if R + 1 <= lo else 'R_after'  # noqa: E731
out, tab = [], collections.Counter()
for l in open(inp):
    r = json.loads(l)
    me, m = r['my_side'], r['match']
    fr = {f['t']: f for f in map(json.loads, open('/workspace/pilot/sme_live/frames2/%s.jsonl' % m))}
    ts = sorted(fr)
    for p in r['plays']:
        if p['side'] != me or p['kind'] != 'play' or p.get('source') != 'own_tap':
            continue
        R, k = p['tick'], cost.get(p['card'])
        tap = max((t['tick'] for t in r['own_taps'] if t['name'] == p['name'] and 0 <= R - t['tick'] <= 80), default=None)
        o = dict(m=m[10:], card=p['card'], R=R, dated=p.get('dated'), lag=None if tap is None else R - tap)
        if k is not None:
            dr = [(a, b) for a, b in zip(ts, ts[1:]) if R - 15 <= a <= R + 15 and fr[a]['el'] - fr[b]['el'] >= 10000 * k - 1100]
            if dr:
                a, b = min(dr, key=lambda ab: min(abs(ab[0] - R), abs(ab[1] - R - 1)))
                o.update(drop=cls(a, b, R), drop_pair=[a, b])
            else:
                o['drop'] = 'none'
        mv = rows.get((m[10:], me, R + 1), [])
        if mv and all('mv' in x for x in mv):
            o['move'] = 'agree' if all(x['mv'] == 'agree' for x in mv) else '/'.join(sorted({x['mv'] for x in mv if x['mv'] != 'agree'}))
            o['move_clean'] = all(x.get('mv_clean') for x in mv)
            o['move_pairs'] = [[x['cm'], x['m_lo'], x['m_hi']] for x in mv]
        else:
            o['move'] = 'no_row' if not mv else 'no_move'
        out.append(o)
        tab[(o.get('drop'), o['move'], o.get('move_clean'))] += 1
with open(outp, 'w') as w:
    for o in out:
        w.write(json.dumps(o) + '\n')
print('own_tap plays', len(out))
for k, v in sorted(tab.items(), key=lambda z: -z[1]):
    print(' drop=%s move=%s clean=%s' % k, v)
print('lag', sorted(collections.Counter(o['lag'] for o in out).items()))
for o in out:
    if o.get('drop') not in ('in', None, 'none') or o['move'] not in ('agree', 'no_row', 'no_move'):
        print(o)
