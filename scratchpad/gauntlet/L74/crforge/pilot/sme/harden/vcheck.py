"""SME-HARDEN: every non-div outcome of the verifier's own plant harness (vplant11.py = smever/plant.py on the hardened
comparator) re-checked with plant_suite's independent witness. python3 vcheck.py vplants.jsonl"""
import collections, json, sys
sys.path.insert(0, '/workspace/pilot/sme11')
import sme_live as L
import plant_suite as PS
from sme import run_batch, diff

rows = [r for r in map(json.loads, open(sys.argv[1])) if 'plant' in r and r['now'] != 'div']
KIND = {'remove_unit': 'remove', 'remove_tower': 'remove', 'remove_proj': 'remove', 'remove_area': 'remove',
        'dup_unit': 'dup', 'move_unit_x+1': 'move', 'move_unit_y-1': 'move', 'move_proj': 'move', 'unit_hp-1': 'hp',
        'tower_hp-1': 'hp'}
out = collections.Counter()
for m in sorted({r['match'] for r in rows}):
    rec = next(x for x in map(json.loads, open('/workspace/pilot/inputs_v29/inputs_rngfree.jsonl')) if x['match'] == m)
    frames = L.load_frames('/workspace/pilot/sme_live/frames2/%s.jsonl' % m)
    for h in rec.get('reader_hidden') or ():
        for t in frames:
            if h['last'] < t <= h['end']:
                frames[t].setdefault('H', []).append([h['side'], h['name'], (h['track'] or {}).get(str(t))])
    me, end = rec['my_side'], max(frames)
    plan = json.load(open('/workspace/pilot/sme_live/a10G1/%s/plan.json' % m))
    work = '/dev/shm/vc/%s' % m
    o = run_batch([(L.runnable(plan), end + 3, 0)], work)[0]
    by = {x['t']: x for x in o}
    an = L.reclassify(plan, frames, me, L.analyse(o, frames, me), o, work)
    ts = sorted(an['cls'])
    for r in (x for x in rows if x['match'] == m):
        t, f = r['t'], frames[r['t']]
        g = json.loads(json.dumps(f))
        us = [i for i, e in enumerate(f['E']) if e[3] != -1 or e[5] not in (12, 13)]
        tw = [i for i, e in enumerate(f['E']) if i not in us]
        p, obj = r['plant'], None
        if p == 'remove_unit':
            obj = PS._obj(g['E'].pop(us[0]))
        elif p == 'remove_tower':
            obj = PS._obj(g['E'].pop(tw[-1]))
        elif p == 'dup_unit':
            g['E'].append(list(f['E'][us[0]]))
            obj = PS._obj(f['E'][us[0]])
        elif p == 'remove_proj':
            obj = ('P', tuple(g['P'].pop(0)[:3]))
        elif p == 'remove_area':
            obj = ('A', tuple(g['A'].pop(0)[:3]))
        elif p == 'elixir+1whole':
            g['el'] += 10000
        else:
            out[('not rebuilt', p)] += 1
            continue
        fr = dict(frames)
        fr[t] = g
        k = ts.index(t)
        a = L.reclassify(plan, fr, me, L.analyse(o, fr, me, ts[max(0, k - 6)], ts[min(len(ts) - 1, k + 6)]), o, work)
        now, nprov = a['cls'][t], a['prov'].get(t)
        rc = L.canon_live(g, me)
        why = None
        for lab, ob in (('legal_t', by.get(t)), ('legal_t1', by.get(t + 1))):
            s = L.sim_canon(ob, me)
            if why is None and not diff(L.fill_placeholder(rc, s), s):
                why = lab
        why = why or PS.witness(KIND.get(p, 'other'), obj, an['cls'][t], now, an['prov'].get(t), nprov, by[t], by.get(t + 1))
        out[(r['base'], p, now, why or 'MISSED')] += 1
        print(m, t, r['base'], p, r['now'], '->', now, why or 'MISSED')
for k, v in sorted(out.items()):
    print(v, k)
