"""ENG-FIX5 field gate for SME_SAMETICK_GEN: the rule is extract.match's last step (order_inputs.reorder), and the generation
order of a group does not depend on its incoming order (rows order is idempotent), so reorder(OFF record, gens) equals the ON
extraction. Applies it to every record of the given OFF files and lists the records whose plays change.
    python -I field_gate_gen.py LIVE_DIR OFF.jsonl [...]"""
import json, os, sys
from pathlib import Path
S = Path('C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme')
sys.path[:0] = [str(S), str(S / 'bp9')]
_argv, sys.argv = sys.argv, [sys.argv[0], '', '']
import order_inputs as oi  # noqa: E402
import live_frames  # noqa: E402
sys.argv = _argv
n = ch = 0
for f in sys.argv[2:]:
    for l in open(f):
        rec = json.loads(l)
        path = os.path.join(sys.argv[1], rec['match'] + '.jsonl')
        if not any(len({p['side'] for p in rec['plays'] if p['kind'] == 'play' and p['tick'] == t}) > 1
                   for t in {p['tick'] for p in rec['plays'] if p['kind'] == 'play'}):
            n += 1; continue  # no same-tick cross-side group: reorder cannot change it
        fr = [(x['t'], x) for x in live_frames.convert(path)]
        new = oi.reorder(rec, [], fr=fr, gens=oi.gen_frames(path))
        same = oi.reorder(rec, [], fr=fr)
        n += 1
        if same['plays'] != rec['plays']:
            print('ROWS-NOT-IDEMPOTENT', rec['match'])
        if new['plays'] != rec['plays']:
            ch += 1
            d = [(i, p['side'], p['card'], p['tick'], q['side'], q['card']) for i, (p, q) in enumerate(zip(rec['plays'], new['plays'])) if p != q]
            print('CHANGED', Path(f).name, rec['match'][10:], rec.get('rng_free'), d)
print('records', n, 'changed', ch)
