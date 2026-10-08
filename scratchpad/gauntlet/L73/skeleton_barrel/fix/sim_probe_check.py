"""Check a SIM probe log (blind verifier's probe.py: one JSON line per decision with the observed Skeleton Barrel bodies, the
tracker's pending drops and the number of predicted bodies in the look-ahead) for the two defects of the first candidate:
  * "double": a pending drop still shown (predicted skeletons in the look-ahead) while the real children of that drop are
    on the observed board at the same decision (real 7 + predicted 7 = 14);
  * "phantom after death": a drop still pending at a decision AFTER real children were seen near it.
Also: drops that never got children (false positives), predicted-body decisions, 14-skeleton boards (enemy class count).
Usage: sim_probe_check.py <probe.jsonl> [out.json]
"""
import json, math, sys
from collections import Counter

rows = [json.loads(l) for l in open(sys.argv[1])]
matches, cur, prev = [], [], -1
for r in rows:
    if r['tick'] < prev:
        matches.append(cur); cur = []
    cur.append(r); prev = r['tick']
matches.append(cur)

S = Counter()
drops = []
for mi, m in enumerate(matches):
    first_seen = {}                       # body id -> first decision tick it was on the board
    for r in m:
        for e in r['sb']:
            first_seen.setdefault(e['id'], r['tick'])
    keys = {}
    for r in m:
        for t0, x, y, mh in r['pending']:
            keys.setdefault((t0, x, y), []).append(r)
    for (t0, x, y), rs in keys.items():
        def kids(r):               # this drop's real children: barrel skeletons FIRST seen at/after t0 (older barrels' do not count)
            return [e for e in r['sb'] if e['mh'] < 300 and e['s'] != r['my'] and first_seen[e['id']] >= t0
                    and math.hypot(e['x'] - x, e['y'] - y) <= 4500]
        seen_real = False
        double = phantom = 0
        for r in m:
            if r['tick'] < t0:
                continue
            real = len(kids(r))
            pend = any(tuple(p[:3]) == (t0, x, y) for p in r['pending'])
            if pend and real:
                double += 1
            if pend and seen_real:
                phantom += 1
            seen_real = seen_real or real > 0
        drops.append(dict(match=mi, t0=t0, x=x, y=y, decisions_pending=len(rs), last_pending_tick=rs[-1]['tick'], double=double,
                          phantom_after_children=phantom, ever_real_children=seen_real))
S['matches'] = len(matches)
S['decisions'] = len(rows)
S['drops_registered'] = len(drops)
S['drops_with_double_board'] = sum(d['double'] > 0 for d in drops)
S['drops_with_phantom_after_children'] = sum(d['phantom_after_children'] > 0 for d in drops)
S['drops_never_got_children (false positives)'] = sum(not d['ever_real_children'] for d in drops)
S['decisions_with_predicted_bodies'] = sum(r['pred'] > 0 for r in rows)
S['decisions_with_predicted_and_real_children_in_view'] = sum(
    r['pred'] > 0 and any(e['mh'] < 300 and e['s'] != r['my'] and e['n'] == 'SkeletonBalloon' for e in r['sb']) for r in rows)
big = [r for r in rows if sum(v for k, v in r['enemy'].items() if 'barrel' in k.lower() or 'balloon' in k.lower()) >= 14]
S['boards_with_>=14 barrel-class enemy tokens (the "14 skeletons" board)'] = len(big)
S['  ... of which with a pending drop at that decision (real + predicted)'] = sum(bool(r['pending']) for r in big)
out = dict(summary=dict(S), drops=drops)
print(json.dumps(out['summary'], indent=1))
if len(sys.argv) > 2:
    json.dump(out, open(sys.argv[2], 'w'), indent=1)
