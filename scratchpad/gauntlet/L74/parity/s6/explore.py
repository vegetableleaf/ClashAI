"""Quick confusion tables over the collector output: python explore.py FILE.jsonl.gz [more]"""
import collections
import gzip
import json
import sys


def load(paths):
    rows = []
    for p in paths:
        for l in gzip.open(p, 'rt'):
            r = json.loads(l)
            r['log'] = p
            rows.append(r)
    return rows


def conf(title, pairs, top=14):
    c = collections.Counter(pairs)
    n = sum(c.values())
    print(f'-- {title} (n={n})')
    for k, v in c.most_common(top):
        print(f'   {v:7d} {v / n:6.3f}  {k}')


if __name__ == '__main__':
    rows = load(sys.argv[1:])
    b = [r for r in rows if r['k'] == 'b']
    al = [r for r in b if r['dist'] <= 250]
    print('bodies', len(b), 'aligned<=0.25 tile', len(al), 'cue rows', sum(r['lv']['cue'] for r in b))
    conf('state live->sim (aligned, non-tower)', [(r['lv']['st'], r['sm']['st']) for r in al if not r['tw']])
    conf('state live->sim towers', [(r['lv']['st'], r['sm']['st']) for r in al if r['tw']])
    cue = [r for r in al if r['lv']['cue']]
    conf('target none/set: live,sim by tower', [(r['tw'], r['lv']['tg'] is None, r['sm']['tg'] is None, r['lv']['ph']) for r in cue], 24)
    conf('phase live->sim', [(r['lv']['ph'], r['sm']['ph']) for r in cue])
