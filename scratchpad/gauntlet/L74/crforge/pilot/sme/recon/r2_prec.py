"""RECON-2 item 3 precision table (section 9.2): RECON search (flags off) on the not-strictly-exact strict-fresh records vs
a reference (the strict fresh results, or the flags-on gate), with every kept structural edit and its ablation verdict.
    python3 recon/r2_prec.py RECON/recon_results.jsonl ABL/ablate.jsonl REF1.jsonl[,REF2...]
made exact = RECON strictly exact; improved = more exact frames, or the same and a later first div; worse = fewer exact frames."""
import json, sys


def load(paths):
    out = {}
    for p in paths.split(','):
        for line in open(p):
            r = json.loads(line)
            out[r['match']] = r
    return out


def main():
    rc, abl, ref = load(sys.argv[1]), load(sys.argv[2]), load(sys.argv[3])
    tally = {'made exact': 0, 'improved': 0, 'same': 0, 'worse': 0, 'error': 0}
    adds = {'needed': 0, 'unneeded': 0, 'harmful': 0, 'error': 0}
    for m in sorted(rc):
        r, f = rc[m], ref.get(m, {})
        if 'error' in r:
            tally['error'] += 1
            print(m, 'ERROR', r['error'][:120]); continue
        ex, fex = r['counts'].get('exact', 0), (f.get('counts') or {}).get('exact', 0)
        fd = lambda x: x.get('first_div') if x.get('first_div') is not None else 10 ** 9
        if ex == r['frames']:
            v = 'made exact'
        elif ex > fex or (ex == fex and fd(r) > fd(f)):
            v = 'improved'
        elif ex == fex and fd(r) == fd(f):
            v = 'same'
        else:
            v = 'worse' if ex < fex else 'same'
        tally[v] += 1
        st = [e for e in r['edits'] if not e.startswith('shift')]
        ab = [(a.get('card'), a.get('run'), a.get('verdict')) for a in (abl.get(m) or {}).get('adds', [])]
        for a in (abl.get(m) or {}).get('adds', []):
            adds[a.get('verdict', 'error')] = adds.get(a.get('verdict', 'error'), 0) + 1
        print(m[-15:], '%-10s' % v, 'recon', r['counts'], r['first_div'], '| ref', f.get('counts'), f.get('first_div'),
              '| kept', st, '| ablate', ab, '| flags', r.get('flags') or '')
    print('records', len(rc), tally)
    print('kept adds (ablation):', adds)


if __name__ == '__main__':
    main()
