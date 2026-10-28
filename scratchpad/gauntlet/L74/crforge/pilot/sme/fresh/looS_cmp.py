"""SME-FRESH: per-flag SME activation table. python3 looS_cmp.py INPUTS_RNGFREE.jsonl RUNS_DIR
Each L_<FLAG> (flag off) against L_base: matches whose result differs (counts, first div or repair log), unflagged exact
apart from torn, exact frames, and the frame-class counts that moved."""
import collections, glob, json, os, sys
flags = {json.loads(l)['match']: json.loads(l)['flags'] for l in open(sys.argv[1])}


def load(d):
    return {r['match']: r for r in map(json.loads, open(os.path.join(d, 'results.jsonl')))}


def ok(r):
    return 'error' not in r and r['counts'].get('div', 0) == 0 and r['missing_in_sim'] == 0


base = load(os.path.join(sys.argv[2], 'L_base'))
print('flag_off\tmatches_changed\tunflagged_pass\texact_frames\tclass_delta\tchanged')
for d in sorted(glob.glob(os.path.join(sys.argv[2], 'L_*'))):
    if not os.path.isdir(d):
        continue
    r = load(d)
    ch = [m for m in base if json.dumps({k: v for k, v in base[m].items()}, sort_keys=True) !=
          json.dumps({k: v for k, v in r.get(m, {}).items()}, sort_keys=True)]
    cd = collections.Counter()
    for m in base:
        for k, v in base[m].get('counts', {}).items():
            cd[k] -= v
        for k, v in r.get(m, {}).get('counts', {}).items():
            cd[k] += v
    print('%s\t%d\t%d\t%d\t%s\t%s' % (os.path.basename(d)[2:], len(ch), sum(ok(r[m]) for m in r if not flags[m]),
          sum(x['counts'].get('exact', 0) for x in r.values() if 'error' not in x), {k: v for k, v in cd.items() if v},
          ','.join(m[10:] for m in ch)))
