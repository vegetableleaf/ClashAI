"""Owner 10-08 13:4x: enemy Inferno Dragon behind the king, the bot leaked ~4 elixir, then lost a tower. Trace one match:
per decision tick, own elixir, gate p vs tau, enemy bodies (model frame), plays, and tower HP changes."""
import json, sys

f = sys.argv[1]
t_lo, t_hi = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (0, 10 ** 9)
prev_tw = None
for line in open(f):
    try:
        d = json.loads(line)
    except ValueError:
        continue
    e = d.get('event')
    if e == 'start':
        print('ckpt', str(d.get('ckpt')).split('\\')[-1], 'tau', d.get('tau'), d.get('decision_options', {}).get('tau_phase'))
    elif e == 'decision' and t_lo <= int(d['tick']) <= t_hi:
        pub, dec = d['public'], d['decision']
        en = [(b['cls'], round(b['x'], 2), round(b['y'], 3)) for b in pub['model_bodies'] if b['side'] == 1]
        tw = tuple((t['side'], t['lane'], round(t['hp_frac'], 3)) for t in pub['model_towers'] if t['alive'])
        print(d['tick'], 'elix', round(float(pub['model_own_elixir'] or 0), 2), 'p', round(dec['p_play'], 3),
              'tau', dec.get('gate_tau'), 'play' if dec['play'] else '-', dec.get('name'), 'enemy', en[:5])
        if tw != prev_tw:
            print('   towers', tw)
            prev_tw = tw
    elif e in ('play', 'end') and (e == 'end' or t_lo <= int(d['tick']) <= t_hi):
        print('  >>', e, d.get('tick'), d.get('name'), d.get('xy'), d.get('elixir'))
