"""Verifier planted-divergence harness. python3 plant.py MATCH OUTJSONL [NEXACT]
Runs the fitted a10G1 plan once, re-runs the full comparator pipeline (analyse + bp_snap + mech_torn + late_reclass)
on frames with ONE planted change at a frame t, and records the class of t. Read-only on the SME code."""
import json, os, sys, copy, random
sys.path.insert(0, '/workspace/pilot/sme11')
import sme_live as L
import bp_snap, mech_torn
from sme import run_batch

m, outp = sys.argv[1], sys.argv[2]
nex = int(sys.argv[3]) if len(sys.argv) > 3 else 6
rec = next(r for r in map(json.loads, open('/workspace/pilot/inputs_v29/inputs_rngfree.jsonl')) if r['match'] == m)
base_frames = L.load_frames('/workspace/pilot/sme_live/frames2/%s.jsonl' % m)
for h in rec.get('reader_hidden') or ():
    for t in base_frames:
        if h['last'] < t <= h['end']:
            base_frames[t].setdefault('H', []).append([h['side'], h['name'], (h['track'] or {}).get(str(t))])
me, end = rec['my_side'], max(base_frames)
plan = json.load(open('/workspace/pilot/sme_live/a10G1/%s/plan.json' % m))
work = '/workspace/pilot/harden/work/vp_%s' % m
o = run_batch([(L.runnable(plan), end + 3, 0)], work)[0]


def pipeline(frames):  # SME-HARDEN: the hardened comparator (analyse + reclassify), else the verifier's harness as is
    return L.reclassify(plan, frames, me, L.analyse(o, frames, me), o, work)


base = pipeline(base_frames)
res0 = json.load(open('/workspace/pilot/sme_live/a10G1/%s/result.json' % m))
same = base['counts'] == res0['counts']
w = open(outp, 'a')
w.write(json.dumps({'match': m, 'sanity_counts_match': same, 'counts': base['counts']}) + '\n')
import collections as _c
cap = int(sys.argv[4]) if len(sys.argv) > 4 else 99
_k = _c.Counter(); torn = []
for t in sorted(base['cls']):
    c = base['cls'][t]
    if c.startswith('torn') and _k[c] < cap:
        _k[c] += 1; torn.append(t)
ts = sorted(base['cls'])
iso_exact = [t for k, t in enumerate(ts) if base['cls'][t] == 'exact' and 0 < k < len(ts) - 1
             and base['cls'][ts[k - 1]] == 'exact' and base['cls'][ts[k + 1]] == 'exact'
             and any(e[3] != -1 for e in base_frames[t]['E'])]
random.seed(7)
targets = torn + random.sample(iso_exact, min(nex, len(iso_exact)))


def plants(f):
    out = []
    us = [i for i, e in enumerate(f['E']) if e[3] != -1 or e[5] not in (12, 13)]
    ts_ = [i for i, e in enumerate(f['E']) if i not in us]
    if us:
        i = us[0]
        g = copy.deepcopy(f); g['E'][i][1] += 1; out.append(('move_unit_x+1', g))
        g = copy.deepcopy(f); g['E'][i][2] -= 1; out.append(('move_unit_y-1', g))
        hp_i = next((j for j in us if f['E'][j][4] not in (-1, 0)), None)
        if hp_i is not None:
            g = copy.deepcopy(f); g['E'][hp_i][4] -= 1; out.append(('unit_hp-1', g))
        g = copy.deepcopy(f); g['E'].pop(i); out.append(('remove_unit', g))
        g = copy.deepcopy(f); g['E'].append(list(f['E'][i])); out.append(('dup_unit', g))
        g = copy.deepcopy(f); e = list(f['E'][i]); e[1] += 3000; out.append(('add_unit_far', g)); g['E'].append(e)
    if ts_:
        g = copy.deepcopy(f); g['E'][ts_[0]][4] -= 1; out.append(('tower_hp-1', g))
        g = copy.deepcopy(f); g['E'].pop(ts_[-1]); out.append(('remove_tower', g))
    if f['P']:
        g = copy.deepcopy(f); g['P'].pop(0); out.append(('remove_proj', g))
        g = copy.deepcopy(f); g['P'][0][1] += 1; out.append(('move_proj', g))
    if f['A']:
        g = copy.deepcopy(f); g['A'].pop(0); out.append(('remove_area', g))
    g = copy.deepcopy(f); g['el'] += 1; out.append(('elixir+1raw', g))
    g = copy.deepcopy(f); g['el'] -= 1; out.append(('elixir-1raw', g))
    g = copy.deepcopy(f); g['el'] += 10000; out.append(('elixir+1whole', g))
    g = copy.deepcopy(f); g['el'] -= 10000; out.append(('elixir-1whole', g))
    if f.get('hand'):
        g = copy.deepcopy(f); g['hand'] = list(reversed(f['hand'])); out.append(('hand_swap', g))
    return out


for t in targets:
    for name, g in plants(base_frames[t]):
        fr = dict(base_frames); fr[t] = g
        an = pipeline(fr)
        changed = {u: (base['cls'][u], an['cls'][u]) for u in an['cls'] if an['cls'][u] != base['cls'].get(u) and u != t}
        w.write(json.dumps({'match': m, 't': t, 'base': base['cls'][t], 'plant': name, 'now': an['cls'][t],
                            'others_changed': changed}) + '\n')
        w.flush()
