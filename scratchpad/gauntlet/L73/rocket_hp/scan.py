"""Owner 10-08: OT Rocket hit the 1000+ HP tower, not the <497 one. List every live Rocket at tick >= 3600 with the
enemy tower state the model saw (model_towers) and the raw reader bodies near each enemy princess."""
import glob, json, math, sys

files = sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1 else
                         'scratchpad/gauntlet/L68/live_reader/live_play_2026100[78]_*.jsonl'))
for f in files:
    last, ckpt = None, '?'
    for line in open(f):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        e = d.get('event')
        if e == 'start':
            ckpt = str(d.get('ckpt', '?')).split('\\')[-1]
        elif e == 'decision':
            last = d
        elif e == 'play' and d.get('name') == 'Rocket' and int(d['tick']) >= 3600 and last:
            pub = last['public']
            en = [t for t in pub['model_towers'] if t['side'] == 1]
            towers = [b for b in pub.get('raw_bodies', []) if 'tower' in str(b).lower()]
            x, y = json.loads(d['xy']) if isinstance(d['xy'], str) else d['xy']
            print(f.split('_', 2)[-1], ckpt[:45], 'tick', d['tick'], 'xy', (round(x, 3), round(y, 3)),
                  'p', d.get('p_play'), 'dec_tick', last['tick'])
            print('   model_towers enemy:', [(t['kind'], t['lane'], round(t['hp_frac'], 3) if t['hp_frac'] is not None
                                              else None, t['alive']) for t in en])
            for b in towers:
                print('   raw:', {k: b[k] for k in b if k in ('side', 'card', 'name', 'x', 'y', 'hp', 'max_hp', 'kind', 'card_id')})
