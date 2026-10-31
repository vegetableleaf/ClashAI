import json, sys, collections
rows = [json.loads(l) for l in open(sys.argv[1])]
rs = collections.Counter(); att = acc = 0; mins = 0
byreason = collections.defaultdict(list)
for r in rows:
    att += r['plays_attempted']; acc += r['plays_accepted']; mins += r['end_tick'] / 1200
    for k, v in r['refuse_reasons'].items(): rs[k] += v
    for q in r['own_reasons']:
        if not q[3]: byreason[q[4]].append(q)
print('n', len(rows), 'attempted', att, 'accepted', acc, 'ratio', round(acc / att, 3), 'attempted/min', round(att / mins, 2), 'accepted/min', round(acc / mins, 2))
print('refuse reasons', dict(rs))
# elixir margin of the refused-by-elixir
import statistics
sys.path.insert(0, 'C:/Users/benpe/ClashBot')
from pipeline.opp_elixir_count import card_cost
for k, v in byreason.items():
    m = []
    for q in v:
        c = card_cost(q[2].replace('_evo', '').replace('_hero', '')) or 0
        if q[5] is not None: m.append(q[5] - c)
    print(k, len(v), 'elixir-cost median %.2f' % statistics.median(m) if m else '')
