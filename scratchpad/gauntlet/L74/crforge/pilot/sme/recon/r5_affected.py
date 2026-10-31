"""RECON-5: which records RECON_CYC=1 can change (laptop, no engine):  python -I recon/r5_affected.py INPUTS.jsonl [...] --out LIST.txt
affected = the opponent's extracted plays fit no deal (best-prefix deal + repairs start) OR one of our own taps is unmatched (restore_taps).
Every other record takes none of the RECON_CYC code paths, so its RECON_CYC=1 result is its RECON_CYC=0 result by construction."""
import json, os, sys, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recon  # noqa: E402


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('inputs', nargs='+'); ap.add_argument('--out')
    a = ap.parse_args()
    aff, n = [], 0
    for f in a.inputs:
        for line in open(f):
            r = json.loads(line); n += 1
            me = r['my_side']
            plan = recon.base_plan(r, None)
            if not plan['_cycle_base'][1 - me] or recon.unmatched_taps(r, plan, me):
                aff.append(r['match'])
    print('records', n, 'affected', len(aff))
    if a.out:
        open(a.out, 'w').write('\n'.join(aff) + '\n')


if __name__ == '__main__':
    main()
