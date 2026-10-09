"""Owner 2026-10-08 21:4x: an evo Skeleton Barrel took all 3 towers; no Log / IW / evo Tesla. Trace one match: enemy
SkeletonBalloon + its skeletons, my towers, and the bot's decision at each step (hand, top card, gate p vs tau)."""
import json, sys
sys.path.insert(0, '.')
from pipeline.obs_contract import _catalog_names

names = _catalog_names()
f = sys.argv[1]
prev_tw = None
for line in open(f, encoding='utf-8'):
    d = json.loads(line)
    e = d.get('event')
    if e in ('play', 'ability') :
        print('  >>', e, d.get('tick'), d.get('name') or d.get('why'), d.get('xy'), 'elixir', d.get('elixir'))
        continue
    if e != 'decision':
        continue
    pub, dec = d['public'], d['decision']
    side = pub['observer_side']
    foes = [(names.get(int(b['card_id']), b['card_id']), round(b['x'] / 1000, 1), round(b['y'] / 1000, 1), b['hp'])
            for b in pub['raw_bodies'] if b['side'] != side and int(b.get('card_id', -1)) >= 0]
    sk = [x for x in foes if 'Skeleton' in str(x[0])]
    tw = tuple((b['x'] // 1000, b['hp']) for b in pub['raw_bodies'] if b['side'] == side and int(b.get('card_id', -1)) == -1)
    if not sk and tw == prev_tw:
        continue
    hand = [c.get('name') + ('*' if c.get('form') else '') for c in pub.get('own_hand', [])]
    mb = sum(1 for b in pub['model_bodies'] if b['side'] == 1)
    print(d['tick'], 'el', round(float(pub['model_own_elixir'] or 0), 1), 'hand', hand, '| top', dec.get('name'),
          'p', round(dec['p_play'], 2), 'tau', dec.get('gate_tau'), 'PLAY' if dec['play'] else '-',
          '| enemy skel-units', len(sk), sk[:3], '| model enemy bodies', mb, '| my towers', tw if tw != prev_tw else '')
    prev_tw = tw
