"""budget9.py GOAL6_ROWS TRACEDIR -- A2c-9R: is the game's route search rationed per tick? For each clean deciding goal-change
event: crforge searches ('replan' probe events) earlier in the same tick before the unit's own, and in the whole tick; also
the search route sizes (a node-budget proxy). Kept = the five events the game keeps the held route on."""
import collections, glob, json, sys
from concurrent.futures import ProcessPoolExecutor
rows_p, td = sys.argv[1], sys.argv[2]
K = {('20261027_000233', 4598), ('20261027_000233', 4599), ('20261026_180336', 2910), ('20261026_101112', 5923), ('20261026_170912', 745)}
rows = collections.defaultdict(list)
for l in open(rows_p):
    x = json.loads(l)
    if x['clean'] and x['pre'] and x['out'] in ('crforge', 'alt0', 'neither'):
        x['o'] = 'kept' if (x['m'], x['t']) in K else x['out']
        if x['o'] != 'neither': rows[x['m']].append(x)


def one(m):
    need = {x['t'] for x in rows[m]}
    ev = {}
    for l in open(glob.glob(td + '/live_play_' + m + '.o.jsonl')[0]):
        o = json.loads(l)
        if o['t'] in need: ev[o['t']] = o['ev']
    out = []
    for x in rows[m]:
        e = ev.get(x['t'], [])
        rp = [k for k, y in enumerate(e) if y[0] == 'replan']
        mine = next((k for k in rp if e[k][1] == x['id']), None)
        if mine is None: continue
        before = sum(1 for k in rp if k < mine)
        nodes_before = sum(e[k][4] for k in rp if k < mine)
        out.append((x['o'], before, len(rp), nodes_before, x['m'], x['t']))
    return out


with ProcessPoolExecutor(32) as ex:
    res = [r for o in ex.map(one, sorted(rows)) for r in o]
for f, name in ((1, 'searches before'), (2, 'searches in tick'), (3, 'route nodes before')):
    c = collections.Counter()
    for r in res: c[(r[0], min(r[f], 40 if f == 3 else 12))] += 1
    print(name)
    for v in sorted({k[1] for k in c}): print('   %3d  crforge %6d  kept %d' % (v, c[('crforge', v)], c[('kept', v)]))
for r in res:
    if r[0] == 'kept': print('KEPT', r)
