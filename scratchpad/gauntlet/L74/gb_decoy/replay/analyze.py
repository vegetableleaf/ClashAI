"""GB-DECOY model replay summary: per cast window (windows.json) the first answer on my half (Log / Knight / IceWizard /
Skeletons / Tornado / Tesla, decided between the throw - 2 and landing + 40) in the logged live run, the replay with
--barrel-decoy off and with it on; real-lane counts per variant. Plain casts: every decision off vs on (must be equal);
all decisions: replay off vs the logged live decision (replay fidelity).

    python analyze.py OUT_DIR windows.json"""
import collections
import glob
import json
import os
import sys

ANSWERS = {'Log', 'Knight', 'IceWizard', 'Skeletons', 'Tornado', 'Tesla'}
K = ('play', 'name', 'xy')


def lane(xy):
    return 'L' if xy[0] < 0.5 else 'R'


def first(rows, t0, tl, v):
    for r in rows:
        d = r[v]
        if d and t0 - 2 <= r['tick'] <= tl + 40 and d['play'] and d['name'] in ANSWERS and d['xy'] and d['xy'][1] > 0.5:
            return d['name'], lane(d['xy']), r['tick'] - t0
    return None


def main(out_dir, windows):
    win = json.load(open(windows))
    c = collections.Counter()
    evo_rows = []
    for path in sorted(glob.glob(os.path.join(out_dir, '*.jsonl'))):
        f = os.path.basename(path)
        rows = [json.loads(l) for l in open(path)]
        for r in rows:
            if r['off'] is None:
                continue
            c['all'] += 1
            c['fidelity_off_eq_logged'] += all(r['off'][k] == r['logged'][k] for k in K)
            c['all_off_eq_on'] += r['off'] == r['on']
        evo_file = any(w['kind'] == 'evo' for w in win.get(f, []))
        for w in win.get(f, []):
            t0, tl = w['t0'], w['tland']
            inw = [r for r in rows if t0 - 2 <= r['tick'] <= tl + 40 and r['off'] is not None]
            if w['kind'] == 'plain':
                c['plain_casts'] += 1
                c['plain_casts_in_evo_matches'] += evo_file
                c['plain_casts_identical_in_no_evo_matches'] += (not evo_file) and all(r['off'] == r['on'] for r in inw)
                c['plain_decisions'] += len(inw)
                c['plain_off_eq_on'] += sum(r['off'] == r['on'] for r in inw)
                c['plain_casts_identical'] += all(r['off'] == r['on'] for r in inw)
                fo, fn = first(inw, t0, tl, 'off'), first(inw, t0, tl, 'on')
                c['plain_first_real_off'] += bool(fo) and fo[1] == w['real']
                c['plain_first_real_on'] += bool(fn) and fn[1] == w['real']
                continue
            c['evo_casts'] += 1
            res = {v: first(inw, t0, tl, v) for v in ('logged', 'off', 'on')}
            for v, a in res.items():
                c[f'evo_answered_{v}'] += a is not None
                c[f'evo_real_{v}'] += a is not None and a[1] == w['real']
            evo_rows.append(dict(file=f, t0=t0, real=w['real'], **res))
    for k in sorted(c):
        print(k, c[k])
    print()
    for e in evo_rows:
        print(e['file'], e['t0'], 'real', e['real'], 'logged', e['logged'], 'off', e['off'], 'on', e['on'])


if __name__ == '__main__':
    main(*sys.argv[1:3])
