"""RECON-7 (pod): the records RECON-7 can change = the RECON-5 + forms set (off_cycform) + a BarbLog card in either deck + a v3 search that reached round 39.
  python3 recon/r7_pick.py DATADIR V3_RESULTS.jsonl   -> DATADIR/off_r7.jsonl + off_r7_hidden.jsonl (every other record keeps its v3 / RECON-5 row; RECON.md 14.4)"""
import json, os, sys
D, v3 = sys.argv[1], sys.argv[2]
capped = set()
for l in open(v3):
    r = json.loads(l)
    if max([L.get('round', -1) for L in r.get('log') or []] + [-1]) >= 39:
        capped.add(r['match'])
base = {json.loads(l)['match'] for l in open(os.path.join(D, 'off_cycform.jsonl'))}
out, why = [], {'cycform': 0, 'barblog': 0, 'capped': 0}
for l in open(os.path.join(D, 'off_u.jsonl')):
    r = json.loads(l)
    decks = [(s.get('deck') or []) for s in (r.get('sides') or {}).values()] if isinstance(r.get('sides'), dict) else []
    bl = any('BarbLog' in d for d in decks)
    m = r['match']
    if m in base or bl or m in capped:
        out.append(l)
        why['cycform'] += m in base; why['barblog'] += bl and m not in base; why['capped'] += m in capped and m not in base and not bl
open(os.path.join(D, 'off_r7.jsonl'), 'w').writelines(out)
open(os.path.join(D, 'off_r7_hidden.jsonl'), 'w').writelines([l for l in out if json.loads(l).get('reader_hidden')])   # the ASSIGN-off guard set
print('off_r7', len(out), why, 'capped', sorted(c[-6:] for c in capped))
