"""Ablation verdicts -> the CONFIRMED list (owner rule: a flagged-but-exact record counts when the missed play its edits restore is ablation-needed).
  python3 recon/r5_confirm.py ablate_edits.jsonl [...]   -> prints per record and, last, the comma list of confirmed matches
confirmed = at least one structural edit (add / drop / replace / point / repress) and EVERY structural edit 'needed' (0 unneeded, harmful, error).
deal_only = no structural edit at all (the exact result needs only the deal / the +-1 tick shifts): not a restored play, listed apart, not confirmed."""
import json, sys

STRUCT = ('add', 'drop', 'replace', 'point', 'repress')
conf, dealonly, bad = [], [], []
for f in sys.argv[1:]:
    for l in open(f):
        r = json.loads(l)
        st = [e for e in r['edits'] if e['kind'] in STRUCT]
        verd = [e['verdict'] for e in st]
        noop = sum(e['kind'] == 'noop' for e in r['edits'])
        if not st:
            dealonly.append(r['match']); tag = 'deal_only'
        elif all(v == 'needed' for v in verd):
            conf.append(r['match']); tag = 'CONFIRMED'
        else:
            bad.append(r['match']); tag = 'NOT confirmed'
        print(r['match'][-13:], tag, [(e['kind'], e['desc'][:50], e['verdict']) for e in st], 'noop', noop)
print('confirmed %d, deal_only %d, not confirmed %d' % (len(conf), len(dealonly), len(bad)))
print('CONFIRMED=' + ','.join(conf))
print('DEAL_ONLY=' + ','.join(dealonly))
