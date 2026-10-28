"""For each h11 torn_snap frame: is there a state whose board AND whole player state both match (strict same-state)?
python3 snap_strict.py MATCH OUT.jsonl"""
import json, os, sys
sys.path.insert(0, '/workspace/pilot/sme11')
import sme_live as L
import bp_snap
from sme import run_batch, diff

m, outp = sys.argv[1], sys.argv[2]
res = json.load(open('/workspace/pilot/sme_live/h11/%s/result.json' % m))
ts = [int(t) for t, p in (res.get('torn_prov') or {}).items() if p['rule'] == 'snap']
if not ts:
    sys.exit(0)
rec = next(r for r in map(json.loads, open('/workspace/pilot/inputs_v29/inputs_rngfree.jsonl')) if r['match'] == m)
frames = L.load_frames('/workspace/pilot/sme_live/frames2/%s.jsonl' % m)
me, end = rec['my_side'], max(frames)
plan = json.load(open('/workspace/pilot/sme_live/h11/%s/plan.json' % m))
work = '/dev/shm/snapstrict/%s' % m
o = {x['t']: x for x in run_batch([(L.runnable(plan), end + 3, 0)], work)[0]}
snaps = bp_snap.snapshots(L.runnable(plan), [t + 1 for t in ts], max(ts) + 3, work)
w = open(outp, 'a')
for t in ts:
    states = [o[t]] + snaps.get(t + 1, []) + [o[t + 1]]
    f = frames[t]
    rc0 = L.canon_live(f, me)
    board = []
    for k, s in enumerate(states):
        sc = L.sim_canon(s, me)
        if not [x for x in diff(L.fill_placeholder(rc0, sc), sc) if not x[0].startswith('S')]:
            board.append(k)
    strict = [k for k in board if L.player_from(f, [(k, states[k])], me) is not None]
    el_only = [k for k in board if f['el'] == states[k]['S'][me][0]]
    w.write(json.dumps({'match': m, 't': t, 'board_states': board, 'strict': strict, 'el_same_state': el_only,
                        'prov': res['torn_prov'][str(t)]}) + '\n')
