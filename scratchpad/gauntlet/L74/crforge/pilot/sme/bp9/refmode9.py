"""refmode9.py GOAL6_ROWS TRACEDIR -- A2c-9R lead 2: does the game read the reference at its tick-start point when the reference's
own move earlier in the tick was not a route step (a pushback / recoil / knockback flight: aim not a cell centre) or carried a push?
Per clean deciding goal-change event: the mode of the reference's displacement before the unit's replan in the same tick, and
whether the tick-start reference point keeps the held goal (bp5 keep.start). Kept = the five events the game keeps the held route."""
import collections, glob, json, sys
from concurrent.futures import ProcessPoolExecutor
rows_p, td = sys.argv[1], sys.argv[2]
K = {('20261027_000233', 4598, 5000116), ('20261027_000233', 4599, 5000119), ('20261026_180336', 2910, 5000058),
     ('20261026_101112', 5923, 5000156), ('20261026_170912', 745, 5000014)}
rows = collections.defaultdict(list)
for l in open(rows_p):
    x = json.loads(l)
    if x['clean'] and x['pre']:
        x['o'] = 'kept' if (x['m'], x['t'], x['id']) in K else x['out']
        if x['o'] in ('crforge', 'kept'): rows[x['m']].append(x)


def one(m):
    need = {x['t'] for x in rows[m]}
    ev = {}
    for l in open(glob.glob(td + '/live_play_' + m + '.o.jsonl')[0]):
        o = json.loads(l)
        if o['t'] in need: ev[o['t']] = o['ev']
    out = []
    for x in rows[m]:
        e = ev.get(x['t'], [])
        mine = next((k for k, y in enumerate(e) if y[0] == 'replan' and y[1] == x['id']), None)
        if mine is None: continue
        rid = x['ref_id']
        d = next((y for y in e[:mine] if y[0] == 'disp' and y[1] == rid), None)
        p = next((y for y in e[:mine] if y[0] == 'prop' and y[1] == rid), None)
        if d is None: mode = 'ref_not_moved_before'
        elif d[2:4] == d[4:6] or d[6] == 0: mode = 'ref_still'
        elif d[4] % 500 != 250 or d[5] % 500 != 250: mode = 'ref_flight'
        elif p is not None and (p[4] or p[5]): mode = 'ref_route_pushed'
        else: mode = 'ref_route_plain'
        out.append((x['o'], mode, x['keep']['start'], x['m'], x['t'], x['id'], x['name'], x['ref_name']))
    return out


with ProcessPoolExecutor(32) as ex:
    res = [r for o in ex.map(one, sorted(rows)) for r in o]
c = collections.Counter((r[1], r[2], r[0]) for r in res)
for k in sorted({k[:2] for k in c}): print('%-22s start_keeps=%-5s crforge %6d kept %d' % (k + (c[k + ('crforge',)], c[k + ('kept',)])))
for r in res:
    if r[0] == 'kept' or (r[1] == 'ref_flight' and r[2]): print(r)
