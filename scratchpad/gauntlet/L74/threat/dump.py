import json, sys
for l in open(sys.argv[1]):
    d = json.loads(l)
    if d.get('event') == 'decision':
        pub, dec = d['public'], d['decision']
        hp = [round(t['hp_frac'], 3) for t in pub['model_towers'][:3]]
        print(d['tick'], pub['model_tick'], hp, round(dec['p_play'], 2), dec.get('gate_tau'), dec['play'],
              dec.get('no_affordable'), dec.get('name'), pub['model_own_elixir'],
              len([b for b in pub['model_bodies'] if b.get('side') != 0]), dec.get('hazard_step_s'))
    elif d.get('event') in ('play', 'end'):
        print('  ', d.get('event'), {k: d[k] for k in list(d)[:7]})
