"""ENG-FIX5: every raw frame sample in [T0, T1] of a live log: tick, t_dev, elixir, opp_elixir_est, backlog and our new
bodies (side my_side, card, x, y). python raw_el.py LOG T0 T1"""
import json, sys
t0, t1 = int(sys.argv[2]), int(sys.argv[3])
for line in open(sys.argv[1], 'rb'):
    head = line[:40]
    if b'"frame"' in head:
        d = json.loads(line)
        t = d['tick']
        if t is None or not t0 <= t <= t1:
            continue
        me = d.get('my_side')
        own = [(e[3], e[1], e[2]) for e in d['ents'] if e[0] == me and e[3] != -1]
        print('t=%s t_dev=%.4f el=%s opp=%s backlog=%s own=%s' % (t, d['t_dev'], d['elixir'], d.get('opp_elixir_est'),
                                                                   d.get('backlog'), own[:6]))
    elif b'"decision"' in head or b'"action"' in head or b'"tap"' in head:
        d = json.loads(line)
        rt = (d.get('public') or {}).get('raw_tick') or d.get('tick')
        if rt is not None and t0 <= rt <= t1:
            print('   ', d.get('event'), json.dumps({k: d[k] for k in list(d)[:8] if k != 'public'})[:300])
