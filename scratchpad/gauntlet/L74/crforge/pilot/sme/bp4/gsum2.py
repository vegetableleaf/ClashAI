"""Cross-tab of goal_census rows: events whose goal change came from the reference's own move earlier in the tick
(tick-start variant keeps the held goal), by (unit side, reference side, reference id < unit id), clean, outcome."""
import collections, json, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
dec = [x for x in rows if x['pre'] and x['out'] in ('crforge', 'alt0') and x['clean']]
c = collections.Counter((x['side'], x['ref_side'], x['ref_id'] < x['id'], x['out']) for x in dec if x['keep']['start'])
for k, v in sorted(c.items(), key=str):
    print(k, v)
