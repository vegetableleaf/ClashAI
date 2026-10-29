"""Lock of on-time unit answers stratified by a siege_t field, side by side.  python -I strat_t.py FIELD NAME [NAME ...]"""
import json, sys
f = sys.argv[1]
for n in sys.argv[2:]:
    rs = [r for r in json.load(open(f'out/siege_t_{n}.json'))['xbows'] if r.get('xb_uid') is not None
          and r['cls'] == 'answer_ontime' and r['kind'] != 'spell' and r.get(f) is not None]
    out = []
    for k in (0, 1, 2, 3):
        s = [r['locked'] for r in rs if min(int(r[f]), 3) == k]
        out.append(f"{k}{'+' if k == 3 else ''}: {len(s) / len(rs):.2f} ({sum(s) / max(1, len(s)):.2f})")
    print(f"{n:6s} {f} share (lock): " + ' | '.join(out))
