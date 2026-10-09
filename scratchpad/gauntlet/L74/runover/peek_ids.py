"""Raw (name, max_hp, form) of enemy bodies vs the vocab class the model received, one log."""
import json, sys, collections
sys.path.insert(0, '.')
from pipeline.obs_contract import _catalog_names, catalog_card_form
from pipeline import vocab
names = _catalog_names()
raw_c, mod_c = collections.Counter(), collections.Counter()
for l in open(sys.argv[1], encoding='utf-8'):
    if not l.startswith('{"event": "decision"'): continue
    p = json.loads(l)['public']; s = p['observer_side']
    for b in p['raw_bodies']:
        if b['side'] != s and int(b['card_id']) >= 0:
            raw_c[(names.get(int(b['card_id'])), b['max_hp'], catalog_card_form(int(b['card_id']))[1])] += 1
    for b in p['model_bodies']:
        if b['side'] == 1: mod_c[(vocab.UNIT_VOCAB[b['cls']], b.get('form'))] += 1
print('RAW enemy (name,max_hp,form):'); [print(' ', k, v) for k, v in raw_c.most_common()]
print('MODEL enemy (cls,form):'); [print(' ', k, v) for k, v in mod_c.most_common()]
