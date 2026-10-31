"""RECON-5 own-tap census (laptop, no engine):  python -I recon/r5_taps.py INPUTS.jsonl [INPUTS2.jsonl ...]
Per record: our own taps no extracted own play explains (recon.unmatched_taps), whether our known cycle fails (recon.cycle_ok), and whether
restoring the taps makes it fit. Tests the claim 'a missed own play is an unmatched tap of ours'."""
import json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recon  # noqa: E402


def main():
    c = collections.Counter()
    for f in sys.argv[1:]:
        for line in open(f):
            r = json.loads(line)
            me = r['my_side']
            plan = recon.base_plan(r, None)
            un = recon.unmatched_taps(r, plan, me)
            fail = not plan['_cycle_base'][me]
            k = 'own_fail' if fail else 'own_ok'
            c[k] += 1
            c[k, 'unmatched>0'] += bool(un)
            c[k, 'unmatched==1'] += len(un) == 1
            if un:
                rt = recon.restore_taps(r, plan, me)
                c[k, 'fits_after_restore'] += bool(rt and rt[1]['_cycle_base'][me])
    for k in sorted(c, key=str):
        print(k, c[k])


if __name__ == '__main__':
    main()
