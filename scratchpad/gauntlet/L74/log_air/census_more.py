import json, collections
r = json.load(open('scratchpad/gauntlet/L74/log_air/census_1005_1009.json'))
c = r['cases']
print('only_air Logs', len(c), '(of', r['logs'], 'Logs;', r['empty'], 'empty corridor)')
ans = {'Tesla', 'IceWizard'}
print('air answer already in hand at the Log:', sum(bool(ans & set(x['hand'])) for x in c))
print('retarget kinds', dict(collections.Counter(x['retarget'] for x in c)))
print('retarget ground value: mean', sum(x['value'] for x in c) / len(c))
a = r['after_only_air']; t = sum(a.values())
print('after only_air Log:', a, 'total', t, 'air answers (Tesla+IceWizard):', a.get('Tesla', 0) + a.get('IceWizard', 0))
b = r['after_all']; t2 = sum(b.values())
print('after any Log: air-answer share %.3f; after only_air Log %.3f' % ((b.get('Tesla', 0) + b.get('IceWizard', 0)) / t2, (a.get('Tesla', 0) + a.get('IceWizard', 0)) / t))
spells = {'clone', 'rocket', 'arrows', 'the_log', 'fireball', 'zap'}
types = collections.Counter()
for x in c:
    key = tuple(sorted(set(p for p in x['path'] if not p.endswith('_aoe') and p not in spells)))
    types[key] += 1
print('air types in the path of an only_air Log:')
for k, v in types.most_common():
    print('  ', v, k)
sb = sum(1 for x in c if set(p for p in x['path'] if p not in spells) <= {'skeleton_barrel'})
print('Logs whose only flyer is a Skeleton Barrel:', sb)
print('per-match Log rate: %.2f Logs/game over %d games; only_air %.3f/game' % (r['logs_per_match_mean'], r['files'], len(c) / r['files']))
