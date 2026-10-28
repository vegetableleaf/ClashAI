"""Census (A2c round 8, item 2): reader bodies that leave the ents list while a reader projectile still targets their
address (the game object still exists). python -I hidden_census.py INPUTS.jsonl LIVE_DIR
Per such body: match, card, side, last ents tick + row, first/last later tick a projectile targets it, frames between,
the target points those projectiles carry."""
import json, sys, os
inputs, live = sys.argv[1], sys.argv[2]
for m in [json.loads(l)['match'] for l in open(inputs)]:
    last, tgt, seen = {}, {}, set()
    for line in open(os.path.join(live, m + '.jsonl'), 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        d = json.loads(line)
        t = d['tick']
        if t is None or t < 0 or t in seen:
            continue
        seen.add(t)
        here = set()
        for e in d['ents']:
            last[e[7]] = (t, e[:7])
            here.add(e[7])
        for pr in d['proj']:
            a = pr[9] if len(pr) > 9 else None
            if a and a in last and a not in here:
                tgt.setdefault(a, []).append((t, pr[4], pr[5]))
    for a, v in tgt.items():
        lt, row = last[a]
        v = [x for x in v if x[0] > lt]
        if v:
            print(m, row[3], 'side', row[0], 'kind', row[6], 'last', lt, row[1:3], 'hp', row[4], 'tgt', v[0][0], '-', v[-1][0],
                  'n', len(v), 'pts', sorted({(x[1], x[2]) for x in v})[:3])
