import json, sys, glob
from collections import Counter
f = sys.argv[1]
rec = json.load(open(f, encoding='utf-8'))
print('keys', sorted(rec.keys()))
fr = sorted(rec['frames'], key=lambda f: int(f['tick']))
print('n frames', len(fr), 'tick range', fr[0]['tick'], fr[-1]['tick'])
import numpy as np
d = np.diff([int(f['tick']) for f in fr]); print('frame gap', Counter(d.tolist()).most_common(6))
print('frame keys', sorted(fr[0].keys()))
print('towers[0]', fr[0].get('towers'))
print('elixir', fr[0].get('elixir'), fr[100].get('elixir'))
print('entity sample', (fr[100].get('entities') or [None])[:2], fr[100].get('native_card_ids', [])[:2], (fr[100].get('entity_ids') or [])[:2])
print('log sample', rec['log'][:3])
print('log keys', Counter(k for e in rec['log'] for k in e).most_common())
print('abil', [e for e in rec['log'] if e.get('ability')][:3])
print('final_decks', rec.get('final_decks'))
for k in ('record_native','record_full','record_every','tag','source','meta'):
    print(k, str(rec.get(k))[:300])
