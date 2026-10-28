"""a10G1 -> h11: torn frames that became div, and the rule mix of h11's torn frames (provenance)."""
import collections, json
flags = {json.loads(l)['match']: json.loads(l)['flags'] for l in open('/workspace/pilot/inputs/inputs_rngfree.jsonl')}
old = {r['match']: r for r in map(json.loads, open('/workspace/pilot/sme_live/a10G1/results.jsonl'))}
new = {r['match']: r for r in map(json.loads, open('/workspace/pilot/sme_live/h11b/results.jsonl'))}
lost, rules, play, snapP = [], collections.Counter(), collections.Counter(), collections.Counter()
for m, r in new.items():
    o = old[m]
    gone = sorted(set(o.get('torn_ticks', [])) - set(r.get('torn_ticks', [])))
    if gone:
        lost.append((m, bool(flags.get(m)), gone, o.get('first_div'), r.get('first_div')))
    for t, p in (r.get('torn_prov') or {}).items():
        rules[p['rule']] += 1
        if p['rule'] in ('mixed', 'cross', 'step'):
            play[(p['rule'], 'player ' + p['player'])] += 1
            for l in p['objects'].values():
                play[(p['rule'], l.split('/')[0].replace('dead_in_step', 'dead_in_step#')[:16])] += 1
        if p['rule'] == 'snap':
            snapP["snap whole-state"] += 1
        if p['rule'] == 'hidden':
            snapP['hidden point_checked %d/%d' % (p['point_checked'], p['bodies'])] += 1
print('old torn frames not torn now:', len(lost))
for x in lost:
    print('  ', x[0], 'flagged' if x[1] else 'UNFLAGGED', x[2], 'first div', x[3], '->', x[4])
print('rules', dict(rules))
for k, v in sorted(play.items()):
    print('  ', k, v)
print(dict(snapP))
