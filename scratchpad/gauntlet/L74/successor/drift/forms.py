import json, collections
d = json.load(open('drift.json'))
rows = [r for r in d['live'] if r['mark'] == 'CXXXVIII']
c = collections.Counter(k for r in rows for k in r['opp'])
for card in ('megaknight', 'witch', 'firecracker', 'hogrider', 'valkyrie', 'electrogiant', 'elixirgolem', 'goldenknight', 'ronin', 'bats', 'skeletons', 'xbow'):
    tr = {k: round(100*v, 2) for k, v in d['pools']['train']['form'].items() if k.split('@')[0] == card}
    d3 = {k: round(100*v, 2) for k, v in d['pools']['d3']['form'].items() if k.split('@')[0] == card}
    print(card, {k: v for k, v in c.items() if k.split('@')[0] == card}, '| train', tr, '| d3', d3)
