"""Where the census reconstruction (raw frame) and the logged model_bodies (look-ahead frame) disagree, by class.
Look-ahead adds predicted drops / removes bodies that die within H ticks; a class that is ALWAYS missing on one
side would instead be a reconstruction bug.  python sanity_diff.py [n_logs=200 newest]"""
import collections, glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '../../../..')))
from census import identities, LOG
from pipeline import vocab
from pipeline.reader_identity_aliases import dedupe_hero_bodies

n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
only_raw, only_model, both, states = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
for f in sorted(glob.glob(LOG + 'live_play_2026*.jsonl'))[-n - 1:-1]:
    for l in open(f, encoding='utf8', errors='replace'):
        if not (l.startswith('{"event": "decision"') and '"raw_bodies"' in l):
            continue
        p = json.loads(l)['public']
        if 'observer_side' not in p:
            continue
        ents = dedupe_hero_bodies({'entities': p['raw_bodies']})['entities']
        mine = collections.Counter(vocab.UNIT_VOCAB[i.cls] for _, _, i in identities(ents, int(p['observer_side'])) if i.cls is not None)
        got = collections.Counter(vocab.UNIT_VOCAB[m['cls']] for m in p['model_bodies'] if m.get('side') == 1)
        states['equal' if mine == got else 'differ'] += 1
        only_raw.update(mine - got); only_model.update(got - mine); both.update(mine & got)
print(dict(states))
print('class: rows only in the raw reconstruction / only in model_bodies / in both')
for c in sorted(set(only_raw) | set(only_model), key=lambda c: -(only_raw[c] + only_model[c]))[:25]:
    print(f'  {c:18s} {only_raw[c]:6d} {only_model[c]:6d} {both[c]:8d}')
