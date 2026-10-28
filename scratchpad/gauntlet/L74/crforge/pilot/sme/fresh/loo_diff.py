"""SME-FRESH: per-flag activation of the extractor rules. For each off_<FLAG>.jsonl (loo_ext.sh) against the full-flag
records: records whose JSON differs, play rows added / removed / changed, and how many of those records are RNG-free.
    python -I loo_diff.py FULL.jsonl LOODIR"""
import glob, json, os, sys
full = {r['match']: r for r in map(json.loads, open(sys.argv[1]))}


def key(p):
    return (p['side'], p['kind'], p.get('name'), p.get('deck_index'), p.get('source'))


print('flag\trecords_changed\trngfree_changed\trows_only_on\trows_only_off\trows_changed\tmatches')
for f in sorted(glob.glob(os.path.join(sys.argv[2], 'off_*.jsonl'))):
    off = {r['match']: r for r in map(json.loads, open(f))}
    n = nf = on_only = off_only = chg = 0
    ms = []
    for m, r in full.items():
        o = off.get(m)
        if o is None or json.dumps(o, sort_keys=True) == json.dumps(r, sort_keys=True):
            continue
        n += 1; nf += r['rng_free']; ms.append(m[10:])
        a = [json.dumps(p, sort_keys=True) for p in r['plays']]
        b = [json.dumps(p, sort_keys=True) for p in o['plays']]
        sa, sb = set(a), set(b)
        ka = {key(json.loads(x)) for x in sa - sb}; kb = {key(json.loads(x)) for x in sb - sa}
        chg += len(ka & kb); on_only += len(sa - sb) - len(ka & kb); off_only += len(sb - sa) - len(ka & kb)
    print('%s\t%d\t%d\t%d\t%d\t%d\t%s' % (os.path.basename(f)[4:-6], n, nf, on_only, off_only, chg, ','.join(ms)))
