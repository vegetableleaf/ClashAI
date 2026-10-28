"""Census of every hero Mini PEKKA (card 203000018) body in the live logs of an inputs file (A2c round 8, item 2).
    python -I mp_census.py INPUTS.jsonl LIVE_DIR [CARD]
Per body (address): first/last tick in ents, kind sequence changes, the cast (kind 15 -> 14 after being active or
p2 cast_timer > 0), the last tick in ents, and how many frames after its last ents row a projectile still targets the
address (the body still exists as a target) plus the last such tick."""
import json, sys, os, collections
inputs, live = sys.argv[1], sys.argv[2]
card = int(sys.argv[3]) if len(sys.argv) > 3 else 203000018
for m in [json.loads(l)['match'] for l in open(inputs)]:
    p = os.path.join(live, m + '.jsonl')
    rows = collections.defaultdict(list)    # addr -> [(t, kind, hp, x, y)]
    tgt = collections.defaultdict(list)     # addr -> ticks a projectile targets it
    timer = collections.defaultdict(list)   # addr -> ticks with p2 cast_timer > 0
    seen = set()
    for line in open(p, 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        d = json.loads(line)
        t = d['tick']
        if t is None or t < 0 or t in seen:
            continue
        seen.add(t)
        for e in d['ents']:
            if e[3] == card:
                rows[e[7]].append((t, e[6], e[4], e[1], e[2]))
        for pr in d['proj']:
            if len(pr) > 9 and pr[9]:
                tgt[pr[9]].append(t)
        for u in (d.get('phase2') or {}).get('units', []):
            a = u.get('ability') or {}
            if a.get('cast_timer_ms_raw'):
                timer[u.get('address')].append((t, a['cast_timer_ms_raw']))
    for a, r in rows.items():
        ks = [(t, k) for i, (t, k, *_ ) in enumerate(r) if i == 0 or r[i - 1][1] != k]
        last = r[-1]
        after = [t for t in tgt.get(a, []) if t > last[0]]
        print(m, a, 'first', r[0][0], 'last', last[0], 'hp_last', last[2], 'kinds', ks, 'timer', timer.get(a, [])[:3],
              'tgt_after', len(after), (after[0], after[-1]) if after else None)
