"""SME-HARDEN census (read-only on sme10): on a10G1's fitted plans, for every torn_step frame, which step_read branches
the frame needs. Dying branch: offset of the recorded row from the removed body's t point, and that body's own last step
(t-1 -> t). Impact branch: the read point against the aim point of every projectile the step removes (same side).
python3 census_step.py MATCH OUT.jsonl"""
import collections, json, os, sys
sys.path.insert(0, os.environ.get('SME_DIR', '/workspace/pilot/sme10'))
import sme_live as L
from sme import run_batch

m, outp = sys.argv[1], sys.argv[2]
res = json.load(open('/workspace/pilot/sme_live/a10G1/%s/result.json' % m))
if not any(c in res.get('counts', {}) for c in ('torn_step',)):
    sys.exit(0)
rec = next(r for r in map(json.loads, open('/workspace/pilot/inputs_v29/inputs_rngfree.jsonl')) if r['match'] == m)
frames = L.load_frames('/workspace/pilot/sme_live/frames2/%s.jsonl' % m)
me, end = rec['my_side'], max(frames)
plan = json.load(open('/workspace/pilot/sme_live/a10G1/%s/plan.json' % m))
o = run_batch([(L.runnable(plan), end + 3, 0)], '/workspace/pilot/harden/work/cs_%s' % m)[0]
by = {x['t']: x for x in o}
an = L.analyse(o, frames, me)
w = open(outp, 'a')
for t, c in sorted(an['cls'].items()):
    if c != 'torn_step':
        continue
    f = frames[t]
    rows = lambda ob: {e[0]: e for e in L.repr_rows(ob)}  # noqa: E731
    a, b, z = rows(by[t]), rows(by[t + 1]), rows(by[t - 1]) if t - 1 in by else {}
    ba = {i: e for i, e in a.items() if e[1] in 'TC'}
    bb = {i: e for i, e in b.items() if e[1] in 'TC'}
    dying, impact, plain = [], [], 0
    for side, x, y, card, hp, kind in f['E']:
        hit1 = any((e[3], e[4], e[5]) == (side, x, y) and hp in (-1, e[6]) or
                   ((e[3], e[4], e[5]) == (side, x, y) and i in ba and hp == ba[i][6]) for i, e in bb.items())
        hit0 = any((e[3], e[4], e[5]) == (side, x, y) and hp in (0, -1, e[6]) for i, e in ba.items() if i not in bb)
        if hit1 or hit0:
            plain += 1
            continue
        if hp in (0, -1):
            for i, e in ba.items():
                if i not in bb and e[3] == side and abs(e[4] - x) + abs(e[5] - y) <= L.STEP_MOVE:
                    last = (e[4] - z[i][4], e[5] - z[i][5]) if i in z else None
                    dying.append({'row': [side, x, y, hp], 'name': e[2], 'body_t': e[4:7], 'off': [x - e[4], y - e[5]],
                                  'last_step': last})
    for cls in 'P':
        pa = {i: e for i, e in a.items() if e[1] == cls}
        pb = {i: e for i, e in b.items() if e[1] == cls}
        pts = {(e[3], e[4], e[5]) for e in list(pa.values()) + list(pb.values())}
        gone = [e for i, e in pa.items() if i not in pb]
        for r in f['P']:
            if (r[0], r[1], r[2]) in pts:
                continue
            impact.append({'read': r[:3], 'gone': [[e[2], e[4], e[5], e[9], e[10]] for e in gone if e[3] == r[0]]})
    w.write(json.dumps({'match': m, 't': t, 'plain_rows': plain, 'dying': dying, 'impact': impact,
                        'el_t1': f['el'] == by[t + 1]['S'][me][0] != by[t]['S'][me][0]}) + '\n')
