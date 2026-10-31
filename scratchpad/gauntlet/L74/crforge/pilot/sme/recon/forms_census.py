"""RECON-6 field census of forms.align on the frozen extractor inputs (laptop, no engine):
  python -I forms_census.py SET1.jsonl SET2.jsonl ...  -> per (side, card) sequences: cost 0 share, the cost > 0 list, own-tap check."""
import collections, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recon, forms  # noqa: E402

tab = recon.Tab()
ru = forms.rules(tab)
n_seq = n_ok = n_play = n_bad_play = 0
bad = []
tapcheck = collections.Counter()
for fn in sys.argv[1:]:
    for l in open(fn):
        rec = json.loads(l)
        me = rec['my_side']
        plan = None
        for side in (0, 1):
            res = forms.analyse(rec, side, tab, ru)
            for card, (cost, alts, n, ranks) in res.items():
                n_seq += 1
                n_play += n
                if cost == 0:
                    n_ok += 1
                    continue
                bad.append((rec['match'][-13:], 'own' if side == me else 'opp', card, cost, n, alts[:3]))
                if side == me:
                    # the unmatched own tap (RECON-5) must sit in the gap the alignment names (an 'ins' before observed play i)
                    plan = plan or recon.base_plan(rec, {}) if False else plan
                    taps = [t for t in rec.get('own_taps') or [] if t['name'] == card]
                    tapcheck[('own_resid', len(alts), bool(taps))] += 1
print('sequences with a form rule: %d, cost 0: %d (%.2f%%); plays in them %d' % (n_seq, n_ok, 100 * n_ok / max(1, n_seq), n_play))
for b in bad:
    print(b)
print(dict(tapcheck))
