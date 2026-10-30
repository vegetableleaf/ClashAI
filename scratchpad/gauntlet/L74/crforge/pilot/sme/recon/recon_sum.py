"""recon_sum.py RESULTS.jsonl... -- one line per RECON search result: counts, first div, kept edits, rounds, window runs
(= sum of legal hypotheses = crforge runs over [d-125, d+400]) and full runs (1 base + 1 per kept beam child), vs the
hand-rule target (RECON.md section 7 item 1)."""
import json, sys

TARGET = {'021310': 1765, '151109': 3031, '031310': 2142, '235834': 2271, '220244': 3025, '222707': 1766}
for path in sys.argv[1:]:
    for line in open(path):
        r = json.loads(line)
        m = r['match'][-6:]
        if 'error' in r:
            print(m, 'ERROR', r['error'][:200]); continue
        log = [x for x in r['log'] if 'round' in x]
        win = sum(x['legal'] for x in log)
        full = 1 + sum(min(x['better'], 4) for x in log)   # upper bound: base + kept children per member-round
        ex = r['counts'].get('exact', 0)
        t = TARGET.get(m)
        verdict = '' if t is None else ('PASS' if ex == t == r['frames'] else 'FAIL target %d' % t)
        print(m, r['counts'], 'first', r['first_div'], 'frames', r['frames'], verdict,
              '| edits', r['edits'], 'cost', r['edit_cost'], 'given_up', r['given_up'],
              '| member-rounds', len(log), 'window runs', win, 'full runs <=', full,
              '| plants missed', (r.get('plants') or {}).get('missed'))
