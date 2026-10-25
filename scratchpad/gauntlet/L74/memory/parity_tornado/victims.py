"""List the enemy victim labels of our Tornado fights (label check for q23_replay's class filters). Read-only.
  python victims.py MATCHES_DIR"""
import glob
import json
import sys
from collections import Counter

c = Counter()
for f in glob.glob(sys.argv[1] + '/*.json'):
    for fi in json.load(open(f)).get('fights') or []:
        if fi.get('own') and fi['anchor']['name'] == 'Tornado':
            c.update({v['victim'] for v in (fi.get('jm') or {}).get('j2') or [] if v['victim'].startswith('opp ')})
print(c.most_common(40))
