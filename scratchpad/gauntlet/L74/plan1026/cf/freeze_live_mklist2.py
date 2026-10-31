"""FREEZE-LIVE step 3 list builder.
  laptop:  python -I freeze_live_mklist2.py held LIVE_MOMENTS.jsonl HELD.json     (held ability moments with a >= 6-elixir freeze target, per match)
  pod:     python3 freeze_live_mklist2.py join LIST.jsonl HELD.json LIST2.jsonl [MAXPER]   (LIST = freeze_live_list.py output: the exact records)"""
import json
import sys

if sys.argv[1] == 'held':
    held = {}
    for l in open(sys.argv[2]):
        m = json.loads(l)
        f = m.get('feat')
        if m['kind'] != 'held' or not f or len(f) != 55 or f[46] * 10 + 1e-6 < 6.0:
            continue
        held.setdefault(m['match'], []).append([m['tick'], round(f[46] * 10, 2), m['elixir']])
    json.dump(held, open(sys.argv[3], 'w'))
    print('matches', len(held), 'moments', sum(len(v) for v in held.values()))
else:
    held = json.load(open(sys.argv[3]))
    cap = int(sys.argv[5]) if len(sys.argv) > 5 else 10 ** 9
    n = k = 0
    with open(sys.argv[4], 'w') as w:
        for l in open(sys.argv[2]):
            r = json.loads(l)
            h = held.get(r['match'])
            if not h:
                continue
            r['held'] = h[:cap]
            w.write(json.dumps(r) + '\n'); n += 1; k += len(r['held'])
    print('records', n, 'moments', k)
