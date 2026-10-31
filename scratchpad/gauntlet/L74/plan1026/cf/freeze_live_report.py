"""FREEZE-LIVE steps 1 + 3: the tables of SIMPRICE.md section 9 from the pod outputs.
  python -I freeze_live_report.py DIR [cf]            DIR holds fl_rows.jsonl (freeze_live_collect.py), fl_out_full2.jsonl (freeze_live_cf.py, full mode),
                                                      fl_sens_<variant>.jsonl (base mode, perturbed tables), flh_out.jsonl (freeze_live_held.py)
Tables: exact records with Hero IW presses; exposure classes; engine press - no press OUR princess HP; sensitivity; held moments."""
import collections
import json
import os
import random
import sys

D = sys.argv[1]
B = 2000


def jl(name):
    p = os.path.join(D, name)
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


def iw(r):
    return [p for p in r['presses'] if p['card'] == 'IceWizard' and p['slotflag'] == 2]


def ci(items, seed=1):
    """items [(cluster, value)] -> mean, 90% cluster-bootstrap CI, n"""
    by = collections.defaultdict(list)
    for m, v in items:
        by[m].append(v)
    ms = list(by)
    rnd = random.Random(seed)

    def mean(sel):
        a = [v for m in sel for v in by[m]]
        return sum(a) / len(a)
    bs = sorted(mean([ms[rnd.randrange(len(ms))] for _ in ms]) for _ in range(B))
    return mean(ms), bs[int(.05 * B)], bs[int(.95 * B)], sum(len(v) for v in by.values())


def fmt(items):
    if len(items) < 5:
        return 'n %d' % len(items)
    e, lo, hi, n = ci(items)
    return '%+.0f [%+.0f, %+.0f] n%d' % (e, lo, hi, n)


# ---------------------------------------------------------------- A. the records
rows = jl('fl_rows.jsonl')
key = lambda r: (r['counts'].get('div', 0), sum(1 for p in iw(r) if p['src'] == 'recon_add'), 0 if 'gate' in r['run'] else 1, -r['frames'])  # noqa: E731
by = collections.defaultdict(list)
for r in rows:
    if r['frames']:
        by[r['match']].append(r)
best = {m: min(rs, key=key) for m, rs in by.items()}
ex = [b for b in best.values() if b['counts'].get('div', 0) == 0]
exiw = [b for b in ex if iw(b)]
print('A. RECON records (all runs pooled, best plan per match): %d matches; fully exact (every reader frame; reader-flagged torn frames excluded) %d' % (len(best), len(ex)))
print('   with >= 1 Hero IW press (either side): %d records, %d presses (%s); of them GATE plans (hand rules, no RECON edits) %d records / %d presses' % (
    len(exiw), sum(len(iw(b)) for b in exiw), dict(collections.Counter(p['src'] for b in exiw for p in iw(b))),
    sum(1 for b in exiw if 'gate' in b['run']), sum(len(iw(b)) for b in exiw if 'gate' in b['run'])))
withp = [b for b in best.values() if iw(b)]
nop = [b for b in best.values() if not iw(b)]
print('   exact rate with a press %d / %d, without %d / %d' % (sum(b['counts'].get('div', 0) == 0 for b in withp), len(withp),
                                                           sum(b['counts'].get('div', 0) == 0 for b in nop), len(nop)))
fail = [b for b in best.values() if b['counts'].get('div', 0) > 0 and iw(b)]
near = [b for b in fail if any(0 <= b['first_div'] - p['run'] <= 300 for p in iw(b))]
print('   failing records with a press: %d; first divergence within 300 ticks after a press: %d' % (len(fail), len(near)))

# ---------------------------------------------------------------- B. the engine counterfactual
out = [r for r in (jl('fl_out_full3.jsonl') or jl('fl_out_full2.jsonl')) if 'error' not in r]
clean = {r['match'] for r in out if r['base']['counts'].get('div', 0) == 0}
P = []
for r in out:
    for p in r['presses']:
        p = dict(p, match=r['match'], own=p['side'] == r['me'], clean=r['match'] in clean)
        P.append(p)


def cls(p):
    e = p.get('exposure')
    return 'none' if not e or e['n'] == 0 else '>=6' if e['el'] >= 6 else '3-6' if e['el'] >= 3 else '<3'


print('\nB. engine press - no press from the exact state (%d records, %d presses: own %d, opponent %d; %d records re-run plain-exact)' % (
    len(out), len(P), sum(p['own'] for p in P), sum(not p['own'] for p in P), len(clean)))
print('   cube lifetime in the exact records (ticks): median %d, max %d; exposure class (enemy bodies in 2.5 t of the cube): %s' % (
    sorted(p['cube_ticks'] for p in P)[len(P) // 2], max(p['cube_ticks'] for p in P), dict(collections.Counter(cls(p) for p in P))))


def pr_hp(p, key, d):
    v = (p.get('eff') or {}).get(str(d))
    if not v:
        return None
    t = [(a, b) for (x, y, a, b) in v[key] if x != 9000]
    return (sum(a or 0 for a, b in t), sum(b or 0 for a, b in t)) if t else None


print('   OUR princess HP, press - no press (HP; own presses + = saves; opponent presses - = their freeze costs us), 90% match-cluster CI:')
for who, key, lab in ((True, 'presser_towers', 'OWN'), (False, 'victim_towers', 'OPP')):
    for c in ('all', '>=6', '3-6', '<3', 'none'):
        sel = [p for p in P if p['own'] == who and (c == 'all' or cls(p) == c)]
        line = []
        for d in (150, 300, 450, 900):
            items = [(p['match'], x[0] - x[1]) for p in sel for x in [pr_hp(p, key, d)] if x]
            line.append('+%d: %s' % (d, fmt(items)))
        print('     %s %-5s | %s' % (lab, c, ' | '.join(line)))
        if who and c == '>=6':
            for d in (300,):
                v = sorted(x[0] - x[1] for p in sel for x in [pr_hp(p, key, d)] if x)
                if v:
                    print('        distribution at +300 (n %d): mean %.0f, median %.0f, quartiles %s, 90th %s, share 0: %.2f, share > 300: %.2f' % (
                        len(v), sum(v) / len(v), v[len(v) // 2], [v[int(q * (len(v) - 1))] for q in (.25, .75)], v[int(.9 * (len(v) - 1))],
                        sum(x == 0 for x in v) / len(v), sum(x > 300 for x in v) / len(v)))
sel = [p for p in P if p['own'] and cls(p) == '>=6']
rg = [p for p in sel if p.get('ref_gain')]
if any('ref_gain' in p for p in P):
    print('   own >= 6 presses where the no-press branch accepts a recorded own play the live history refused (the press cost 2 elixir; favours the no-press branch): %d / %d' % (len(rg), len(sel)))
    for d in (150, 300, 900):
        items = [(p['match'], x[0] - x[1]) for p in sel if not p.get('ref_gain') for x in [pr_hp(p, 'presser_towers', d)] if x]
        print('     without those presses, +%d: %s' % (d, fmt(items)))
act = sum(1 for p in sel if any(v['ndiff_enemy_units'] > 0 for k, v in (p.get('eff') or {}).items() if int(k) >= 25))
print('   own >=6 presses whose no-press branch differs in some enemy body (x, y, hp) at >= 25 ticks: %d / %d' % (act, len(sel)))

# ---------------------------------------------------------------- C. sensitivity
base = {r['match']: r for r in out}
cl = {}
for m, r in base.items():
    best_c = 'none'
    order = {'none': 0, '<3': 1, '3-6': 2, '>=6': 3}
    for p in r['presses']:
        c = cls(p)
        if order[c] > order[best_c]:
            best_c = c
    cl[m] = best_c
print('\nC. sensitivity: the same %d plain-exact records re-run with perturbed freeze tables (engine code untouched):' % len(clean))
for v in ('noop', 'freeze90', 'radius2000', 'radius3000', 'cube4000b', 'cube4000', 'slow15', 'slow0'):
    s = jl('fl_sens_%s.jsonl' % v)
    if not s:
        continue
    n = broke = b6 = n6 = 0
    ticks = []
    for r in s:
        if 'error' in r or r['match'] not in clean:
            continue
        n += 1
        n6 += cl[r['match']] == '>=6'
        if r['base']['counts'].get('div', 0) > 0:
            broke += 1
            b6 += cl[r['match']] == '>=6'
            pr = [p['run'] for p in base[r['match']]['presses'] if p['run'] <= r['base']['first']]
            if pr:
                ticks.append(r['base']['first'] - max(pr))
    ticks.sort()
    print('   %-11s no longer exact %3d / %d (%2.0f%%); of the >= 6 class %3d / %d; first diverging frame after the last press: median %s ticks' % (
        v, broke, n, 100.0 * broke / max(n, 1), b6, n6, ticks[len(ticks) // 2] if ticks else '-'))

# ---------------------------------------------------------------- D. held moments
h = jl('flh_out.jsonl')
if h:
    own_press = {r['match']: [p['run'] for p in r['presses'] if p['side'] == r['me']] for r in out}
    allp = {d: [] for d in (100, 150, 300, 450)}
    cleanp = {d: [] for d in (100, 150, 300, 450)}
    tot = acc = near = 0
    for r in h:
        for m in r.get('moments', []):
            tot += 1
            if m.get('refused') or m['cube_ticks'] == 0:
                continue
            acc += 1
            if any(abs(run - m['run']) <= 600 for run in own_press.get(r['match'], [])):
                near += 1
                continue
            for d in allp:
                v = m['hp'].get(str(d))
                if v:
                    allp[d].append((r['match'], v[0] - v[1]))
                    # clean: the press branch refuses none of my recorded plays that the live history accepted, up to run + d
                    if not any(t <= m['run'] + d for t in m.get('ref_extra', [])):
                        cleanp[d].append((r['match'], v[0] - v[1]))
    print('\nD. engine press ADDED at held moments (>= 6-elixir freeze target by the head feature) vs the live no-press history: %d moments, %d accepted (cube stands), %d dropped (a real own press within 600 ticks)' % (tot, acc, near))
    print('   OUR princess HP, press - live (+ = the added press saves), all accepted: ' + ' | '.join('+%d: %s' % (d, fmt(v)) for d, v in allp.items()))
    print('   same, only moments where the press branch refuses none of my recorded plays (the press costs 2 elixir; the plays do not adapt): ' + ' | '.join('+%d: %s' % (d, fmt(v)) for d, v in cleanp.items()))
    refx = sum(1 for r in h for m in r.get('moments', []) if m.get('ref_extra'))
    print('   moments with >= 1 extra refused own play inside +450: %d / %d accepted' % (refx, acc))
    # placebo: the added press split by what the engine says the cube catches (exposure none = the freeze acts on nothing, so any
    # "effect" there is replay mismatch / the cast itself, not the freeze)
    def xcls(e):
        return 'none' if not e or e['n'] == 0 else '>=6' if e['el'] >= 6 else '3-6' if e['el'] >= 3 else '<3'
    byc = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in h:
        for m in r.get('moments', []):
            if m.get('refused') or m['cube_ticks'] == 0 or any(abs(run - m['run']) <= 600 for run in own_press.get(r['match'], [])):
                continue
            for d in (100, 150, 300, 450):
                v = m['hp'].get(str(d))
                if v and not any(t <= m['run'] + d for t in m.get('ref_extra', [])):
                    byc[xcls(m.get('exposure'))][d].append((r['match'], v[0] - v[1]))
    for c in ('>=6', '3-6', '<3', 'none'):
        print('   held-add by engine exposure %-4s | ' % c + ' | '.join('+%d: %s' % (d, fmt(byc[c][d])) for d in (100, 150, 300, 450)))
