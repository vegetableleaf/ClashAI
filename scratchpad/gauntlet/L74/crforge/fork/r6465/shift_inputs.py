"""Copy an inputs jsonl, moving each Rage 'bottle_made' play to made(countdown) - 10 (rage_made.jsonl). Measurement only."""
import json, sys
src, made_path, out = sys.argv[1:4]
made = [json.loads(l) for l in open(made_path)]
n = moved = 0
with open(out, 'w') as w:
    for l in open(src):
        r = json.loads(l)
        for p in r['plays']:
            if p.get('dated') == 'bottle_made' and p['card'] == 'Rage':
                n += 1
                hit = [a for a in made if a['match'] == r['match'] and a['side'] == p['side'] and (a['x'], a['y']) == (p['x'], p['y'])
                       and a['first'] == p['tick'] + 10]
                assert len(hit) == 1, (r['match'], p)
                t = hit[0]['made'] - 10
                if t != p['tick']:
                    moved += 1
                    print(r['match'], p['tick'], '->', t)
                p['tick'] = t; p['run_ticks'] = [t, t]
        w.write(json.dumps(r) + '\n')
print('rage bottle plays', n, 'moved', moved)
