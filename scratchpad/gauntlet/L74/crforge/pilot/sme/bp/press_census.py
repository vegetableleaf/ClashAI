"""Census of our own ability presses against our elixir drops (A2c-BP2), all matches of an inputs file. Our side only.
    python3 press_census.py INPUTS.jsonl FRAMES_DIR > out.txt
A drop is a frame pair (a, b) with our elixir down >= 1.5 elixir. It is explained by one of our card plays run in
[a-1, b] or one of our ability commands run in [a-1, b]. Prints each own ability with no drop at its tick, the nearest
unexplained drop before / after it, and every unexplained drop."""
import collections, json, os, sys
inp, fdir = sys.argv[1], sys.argv[2]
cnt = collections.Counter()
for l in open(inp):
    r = json.loads(l)
    m, my = r['match'], r['my_side']
    fp = os.path.join(fdir, m + '.jsonl')
    if not os.path.exists(fp):
        continue
    fr = {f['t']: f['el'] for f in map(json.loads, open(fp))}
    ts = sorted(fr)
    drops = [(a, b, fr[a] - fr[b]) for a, b in zip(ts, ts[1:]) if fr[a] - fr[b] >= 15000]
    own = [p for p in r['plays'] if p['side'] == my]
    pl = [p for p in own if p['kind'] == 'play']
    ab = [p for p in own if p['kind'] == 'ability']
    un = []
    for a, b, d in drops:
        if any(a - 1 <= t <= b for p in pl for t in range(p['run_ticks'][0], p['run_ticks'][1] + 1)):
            cnt['drop_play'] += 1
        elif any(a - 1 <= p['tick'] <= b for p in ab):
            cnt['drop_ability'] += 1
        else:
            un.append((a, b, d))
    cnt['drop_unexplained'] += len(un)
    for p in ab:
        cnt['ability'] += 1
        if any(a - 1 <= p['tick'] <= b for a, b, _ in drops):
            cnt['ability_on_drop'] += 1
            continue
        cnt['ability_no_drop'] += 1
        before = max((x for x in un if x[1] <= p['tick']), default=None, key=lambda x: x[1])
        after = min((x for x in un if x[0] >= p['tick']), default=None, key=lambda x: x[0])
        print('ABIL', m, p['card'], p['tick'], p.get('source'), p.get('dated'), 'before', before,
              'gap', p['tick'] - before[1] if before else None, 'after', after)
    for x in un:
        print('UNEXPL', m, x, 'abilities', [(p['card'], p['tick']) for p in ab if abs(p['tick'] - x[0]) <= 400])
print('COUNTS', dict(cnt))
