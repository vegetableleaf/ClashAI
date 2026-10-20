import json, sys
from collections import Counter
det = json.load(open(sys.argv[1] + '/j7div_detail.json'))
for whose in ('own', 'opp'):
    g = [x for x in det if x[3] == whose]
    print(whose, len(g), 'd values', Counter(x[6] for x in g).most_common(25))
    print('   own cards before', Counter(c for x in g for c in set(x[7]) if c.startswith('own')).most_common(12))
    print('   opp cards before', Counter(c for x in g for c in set(x[7]) if c.startswith('opp')).most_common(12))
    print('   live hp at div', Counter(x[4] for x in g).most_common(8), 'sim hp', Counter(x[5] for x in g).most_common(8))
