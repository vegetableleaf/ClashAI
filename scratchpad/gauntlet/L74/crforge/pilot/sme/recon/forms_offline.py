"""RECON-6 offline: which records get form_repairs variants (laptop, no engine; E0 = 5.99, the measured start elixir).
  python -I forms_offline.py SET.jsonl ...   -> per record with variants: match, side, descriptions"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recon, forms  # noqa: E402

tab = recon.Tab()
ru = forms.rules(tab)
n = nv = 0
for fn in sys.argv[1:]:
    for l in open(fn):
        rec = json.loads(l)
        n += 1
        try:
            plan = recon.base_plan(rec, {})
        except TypeError:
            continue                                  # no own deal in the record: unplannable for every pipeline
        recon.with_elixir_base(plan, tab, 5.99)
        for sd in (0, 1):
            if sd == rec['my_side']:
                continue
            vs = forms.form_repairs(rec, plan, sd, tab, 5.99, ru)
            if vs:
                nv += 1
                print(rec['match'][-13:], 'side', sd, 'cycle_base', plan['_cycle_base'][sd], len(vs), 'variants:', [v[0] for v in vs][:6])
print('records', n, 'with variants', nv)
