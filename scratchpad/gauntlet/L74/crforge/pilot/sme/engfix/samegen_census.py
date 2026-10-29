"""ENG-FIX5 census: same-tick cross-side play groups, the record's order (bp9 order_inputs = reader ROW order) vs the game's
creation order read from phase2 'generation' (the game's entity id; the address of an ents row maps it).
A play's new bodies are found as order_inputs.first_rows finds them (side, within 1,500 Manhattan of the point, not within 20 of
a same (side, card) row of the frame before the tick; first frame in [tick, tick + 10]).
    python -I gen_census.py LIVE_DIR INPUTS.jsonl [...]      -> one line per group + a summary"""
import json, os, sys

LD = sys.argv[1]


def frames(path):
    out = {}
    for line in open(path, 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        d = json.loads(line)
        t = d['tick']
        if t is None or t < 0 or t in out:
            continue
        g = {u.get('address'): u.get('generation') for u in (d.get('phase2') or {}).get('units') or []}
        out[t] = [(e[0], e[1], e[2], e[3], g.get(e[7]) if len(e) > 7 else None) for e in d['ents']]
    return sorted(out.items())


def reading(ts, p, run):
    before = [f for t, f in ts if t < run]
    old = before[-1] if before else []
    for t, f in ts:
        if t < run or t > run + 10:
            continue
        rows = [k for k, e in enumerate(f) if e[0] == p['side'] and e[3] != -1 and abs(e[1] - p['x']) + abs(e[2] - p['y']) <= 1500
                and not any(o[0] == e[0] and o[3] == e[3] and abs(o[1] - e[1]) <= 20 and abs(o[2] - e[2]) <= 20 for o in old)]
        if rows:
            gens = [f[k][4] for k in rows]
            return (t, min(rows)), (min(gens) if all(x is not None for x in gens) else None), [f[k][3] for k in rows]
    return None, None, None


tot = dict(groups=0, both_read=0, agree=0, differ=0, nogen=0)
for inp in sys.argv[2:]:
    for l in open(inp):
        rec = json.loads(l)
        by = {}
        for i, p in enumerate(rec['plays']):
            if p['kind'] == 'play':
                by.setdefault(p['tick'], []).append(i)
        groups = [(t, ix) for t, ix in sorted(by.items()) if len({rec['plays'][i]['side'] for i in ix}) >= 2]
        if not groups:
            continue
        ts = frames(os.path.join(LD, rec['match'] + '.jsonl'))
        for tick, ix in groups:
            tot['groups'] += 1
            rd = {i: reading(ts, rec['plays'][i], tick) for i in ix}
            known = [i for i in ix if rd[i][0] is not None]
            if len(known) < 2:
                continue
            tot['both_read'] += 1
            if any(rd[i][1] is None for i in known):
                tot['nogen'] += 1
                print(rec['match'][10:], tick, 'NOGEN'); continue
            by_gen = sorted(known, key=lambda i: rd[i][1])
            ok = by_gen == sorted(known)  # the record keeps its slots: current order = index order
            tot['agree' if ok else 'differ'] += 1
            print(rec['match'][10:], tick, 'agree' if ok else 'DIFFER',
                  [(rec['plays'][i]['side'], rec['plays'][i]['card'], rd[i][0], rd[i][1], rd[i][2][:3]) for i in ix])
print('SUMMARY', tot)
