"""A2c-BP6: does the game update entities in a swap-remove order (a dead entity's slot gets the last entity) rather than
crforge's creation order? Tests it on the bp5 goal6 census rows (goal changes with a held route) where the two orders
put the unit and its reference the other way round.
    python3 swap_test.py GOAL6.jsonl.gz TRACEDIR     (TRACEDIR: AimRun5 o.jsonl per match, C and PA rows every tick)
Models: A = one list of characters + projectiles + areas; B = characters only. Additions append in id order at the end of
the tick they first appear; removals (ids gone) swap-remove in ascending slot order. The order of tick t is the list after
tick t-1. Prediction where crforge visits the reference first and the model visits the unit first: the goal with the
reference at its end-of-t-1 point (goal6 x.e1) -> keep (alt0) iff it equals the held goal."""
import collections, gzip, json, os, sys
rows = [json.loads(l) for l in gzip.open(sys.argv[1], 'rt')]
TD = sys.argv[2]
by_m = collections.defaultdict(list)
for r in rows:
    if r['clean'] and r['pre'] and r['out'] in ('crforge', 'alt0') and r.get('x'):
        by_m[r['m']].append(r)
res = {'A': collections.Counter(), 'B': collections.Counter()}
hits = collections.defaultdict(list)
for m, rs in sorted(by_m.items()):
    f = os.path.join(TD, 'live_play_' + m + '.o.jsonl')
    if not os.path.exists(f):
        continue
    need = collections.defaultdict(list)
    for r in rs:
        need[r['t']].append(r)
    L = {'A': [], 'B': []}
    for line in open(f):
        o = json.loads(line)
        t = o['t']
        cids = [c[0] for c in o['C']]
        if t in need:  # order of tick t = lists after tick t-1 (before this tick's update below)
            cpos = {i: k for k, i in enumerate(cids)}
            for r in need[t]:
                u, ref = r['id'], r['ref_id']
                if u not in cpos or ref not in cpos:
                    continue
                cr_ref_first = cpos[ref] < cpos[u]
                for mdl in ('A', 'B'):
                    pos = {i: k for k, i in enumerate(L[mdl])}
                    if u not in pos or ref not in pos:
                        res[mdl]['missing'] += 1
                        continue
                    sw_ref_first = pos[ref] < pos[u]
                    if sw_ref_first == cr_ref_first:
                        res[mdl][('same', r['out'])] += 1
                        continue
                    if cr_ref_first:
                        keep = r['x']['e1'] == r['held']
                        ok = (r['out'] == 'alt0') == keep
                        res[mdl][('flip_unit_first', 'pred_keep' if keep else 'pred_change', r['out'])] += 1
                        if r['out'] == 'alt0' or keep:
                            hits[mdl].append((m, t, u, ref, r['out'], 'pred_keep' if keep else 'pred_change'))
                    else:
                        res[mdl][('flip_ref_first', r['out'])] += 1
                        if r['out'] == 'alt0':
                            hits[mdl].append((m, t, u, ref, r['out'], 'ref_first'))
        ids = {'A': cids + [p[0] for p in o.get('PA', [])], 'B': cids}
        for mdl in ('A', 'B'):
            cur = set(ids[mdl])
            lst = L[mdl]
            gone = sorted((k for k, i in enumerate(lst) if i not in cur), reverse=False)
            for i in [lst[k] for k in gone]:
                k = lst.index(i)
                lst[k] = lst[-1]
                lst.pop()
            have = set(lst)
            lst += sorted(i for i in cur if i not in have)
for mdl in ('A', 'B'):
    print(mdl, sorted(res[mdl].items(), key=str))
    for h in hits[mdl][:40]:
        print('  ', mdl, h)
