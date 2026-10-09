import json, collections
r = json.load(open('scratchpad/gauntlet/L74/log_air/census_1005_1009.json'))
c = r['cases']
print('only_air Logs', len(c))
ans = {'Tesla', 'IceWizard'}
print('air answer already in hand at the Log:', sum(bool(ans & set(x['hand'])) for x in c))
print('retarget kinds', collections.Counter(x['retarget'] for x in c))
print('retarget ground value: mean', sum(x['value'] for x in c) / len(c))
a = r['after_only_air']; t = sum(a.values())
print('after only_air Log:', a, 'total', t, 'air answers (Tesla+IceWizard):', a.get('Tesla', 0) + a.get('IceWizard', 0))
b = r['after_all']; t2 = sum(b.values())
print('after any Log: air answers share', (b.get('Tesla', 0) + b.get('IceWizard', 0)) / t2, 'only_air share', (a.get('Tesla', 0) + a.get('IceWizard', 0)) / t)
