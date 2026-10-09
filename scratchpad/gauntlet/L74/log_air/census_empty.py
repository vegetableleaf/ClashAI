import json, collections
r = json.load(open('scratchpad/gauntlet/L74/log_air/census_1005_1009.json'))
print('Logs', r['logs'], 'only_air', r['only_air'], 'of which an enemy projectile lands in the corridor (Goblin Barrel exemption, approx.)',
      r['barrel'], 'empty', r['empty'], 'hits', r['hits'])
c = r['empty_cases']
n = len(c)
pc = collections.Counter(x['cls'] for x in c)
print({k: '%d (%.0f%%)' % (v, 100 * v / n) for k, v in pc.items()})
for k in pc:
    xs = [x for x in c if x['cls'] == k]
    e = [x['elixir'] for x in xs if x['elixir'] is not None]
    d = [x['dist'] for x in xs if x['dist'] is not None]
    ys = collections.Counter(x['xy'][1] for x in xs).most_common(3)
    print(k, 'n', len(xs), 'elixir mean %.1f' % (sum(e) / len(e)), 'nearest-foe dist median', sorted(d)[len(d) // 2] if d else None,
          'cast y top', ys, 'median n_foes', sorted(x['n_foes'] for x in xs)[len(xs) // 2])
