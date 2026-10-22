import json, sys
from collections import Counter
rows = json.load(open(sys.argv[1] + '/cls_flat.json'))
for card in sys.argv[2].split(','):
    rs = [r for r in rows if r['lab'] in (card, card + ' evo')]
    print(f"{card}: {len(rs)} failing | disagreement {dict(Counter(r['bad'][0]['kind'] if r['bad'] else 'none' for r in rs).most_common(4))}")
    print('   first divergence:', '; '.join(f"{k[0]} {k[1]} x{v}" for k, v in Counter((r['cause'][1], r['cause'][2]) for r in rs).most_common(6)))
