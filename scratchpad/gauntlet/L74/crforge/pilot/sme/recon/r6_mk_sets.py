"""RECON-6 (pod): build the held-out run subsets of one set from its flags-off / flags-on extractor inputs (RECON-5's mk_sets.py + the forms set).
  python3 recon/r6_mk_sets.py DATAROOT NAME      # DATAROOT/NAME/off.jsonl (flags off, v3 / RECON inputs), on.jsonl (flags on, the gate's inputs)
writes next to them: off_u / on_u (unique matches), off_aff (RECON_CYC can change: opponent plays fit no deal, or an unmatched own tap),
off_form (forms.form_repairs may yield a variant: the opponent has a form residual explained by deletions), off_cycform = aff or form
(the RECON_CYC=1 RECON_FORM=1 run set), off_hidden_u / on_hidden_u / off_cycform_hidden (reader-hidden records, the ASSIGN off guard)."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault('SME_TABLES', '/workspace/crforge_cache/tables/16.635.3')
import recon, forms  # noqa: E402

root, name = sys.argv[1], sys.argv[2]
D = os.path.join(root, name)
tab = recon.Tab()
ru = forms.rules(tab)
seen, offr, aff, frm = set(), [], set(), set()
for l in open(os.path.join(D, 'off.jsonl')):
    r = json.loads(l)
    if r['match'] in seen:
        continue
    seen.add(r['match'])
    offr.append((l, r))
    try:
        plan = recon.base_plan(r, None)
    except Exception as e:               # e.g. no own deal in the record: every pipeline errors on it alike
        print('  unplannable', r['match'], repr(e)[:80])
        continue
    me = r['my_side']
    if not plan['_cycle_base'][1 - me] or recon.unmatched_taps(r, plan, me):
        aff.add(r['match'])
    # forms: any opponent card whose observed forms need deleted plays (superset of the records form_repairs can change)
    res = forms.analyse(r, 1 - me, tab, ru)
    if any(c for c, *_ in res.values()):
        frm.add(r['match'])
cf = aff | frm
hid = {r['match'] for l, r in offr if r.get('reader_hidden')}


def w(fn, rows):
    open(os.path.join(D, fn), 'w').writelines(rows)


w('off_u.jsonl', [l for l, r in offr])
w('off_aff.jsonl', [l for l, r in offr if r['match'] in aff])
w('off_form.jsonl', [l for l, r in offr if r['match'] in frm])
w('off_cycform.jsonl', [l for l, r in offr if r['match'] in cf])
w('off_hidden_u.jsonl', [l for l, r in offr if r['match'] in hid])
w('off_cycform_hidden.jsonl', [l for l, r in offr if r['match'] in hid and r['match'] in cf])
onr = {}
for l in open(os.path.join(D, 'on.jsonl')):
    r = json.loads(l)
    onr.setdefault(r['match'], l)
w('on_u.jsonl', [onr[m] for m in sorted(onr)])
w('on_hidden_u.jsonl', [onr[m] for m in sorted(onr) if m in hid])
print(name, 'unique', len(offr), 'affected', len(aff), 'form-residual', len(frm), 'union', len(cf), 'hidden', len(hid), 'union+hidden', len(hid & cf))
print('affected', sorted(a[-6:] for a in aff))
print('form-residual', sorted(a[-6:] for a in frm))
