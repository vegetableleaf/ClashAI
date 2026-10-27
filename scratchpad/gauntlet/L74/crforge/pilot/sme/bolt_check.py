"""Lightning bolt timing, sim vs live: for every LighningSpell projectile line in the sim (one point, one tick b), is the
recorded frame at b+k (k = -1..+3) showing a Lightning projectile at that point? Also: is the struck target's hp at
b+k already reduced in the recorded frame?
    python3 bolt_check.py RUNDIR [FRAMES_DIR]   (matches whose plan has a Lightning play)"""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import run_batch  # noqa: E402
from sme_live import load_frames, runnable  # noqa: E402

run = sys.argv[1]
fdir = sys.argv[2] if len(sys.argv) > 2 else '/workspace/pilot/sme_live/frames'
seen, absent, hpdone, hpnot = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
bolts = 0
for l in open(os.path.join(run, 'results.jsonl')):
    m = json.loads(l)['match']
    p = os.path.join(run, m, 'plan.json')
    if not os.path.exists(p):
        continue
    plan = json.load(open(p))
    if not any(c.get('card') == 'Lightning' for c in plan['cmds']):
        continue
    frames = load_frames(os.path.join(fdir, m + '.jsonl'))
    o = run_batch([(runnable(plan), max(frames) + 3, 0)], os.path.join(run, m, 'bolt'))[0]
    if o is None:
        continue
    by = {x['t']: x for x in o}
    for x in o:
        for e in x['E']:
            if e[1] != 'P' or e[2] != 'LighningSpell':
                continue
            b, side, px, py = x['t'], e[3], e[4], e[5]
            # the target: the sim body at the point whose hp drops at b+1
            nxt = by.get(b + 1)
            tgt = None
            if nxt:
                for f in x['E']:
                    if f[1] in 'TC' and f[4] == px and f[5] == py and f[6] > 0:
                        after = [g for g in nxt['E'] if g[0] == f[0]]
                        if after and after[0][6] < f[6]:
                            tgt = (f[3], f[4], f[5], f[6])
            bolts += 1
            for k in range(-1, 4):
                fr = frames.get(b + k)
                if fr is None:
                    continue
                has = any(q[0] == side and q[1] == px and q[2] == py and q[3] == 28000007 for q in fr['P'])
                (seen if has else absent)[k] += 1
                if tgt:
                    rows = [q for q in fr['E'] if q[0] == tgt[0] and q[1] == tgt[1] and q[2] == tgt[2]]
                    if rows:
                        (hpdone if rows[0][4] < tgt[3] else hpnot)[k] += 1
print('sim bolts', bolts)
print('recorded frame at sim bolt tick + k shows the bolt:', {k: (seen[k], seen[k] + absent[k]) for k in sorted(set(seen) | set(absent))})
print('recorded target hp already reduced at + k:', {k: (hpdone[k], hpdone[k] + hpnot[k]) for k in sorted(set(hpdone) | set(hpnot))})
