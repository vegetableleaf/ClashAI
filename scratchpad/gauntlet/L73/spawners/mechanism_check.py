"""Mechanism checks on the native audit (read-only):
1. Which bodies carry hp<=0 / max_hp<=0 (parent or child, which form), per family.
2. For every phantom/missed play of a spawner card: was a same-side parent present but unreadable (hp<=0) at that tick
   (=> dropped by public_frame/from_engine), and for missed plays: did a same-card body of LOWER max_hp vanish within
   1.5 tiles in the previous 60 ticks (death-spawn rule) or a HIGHER max_hp body sit on the board (parent rule)?
Writes mechanism_check.json."""
import os, sys, json, collections
ROOT = r'C:\Users\benpe\ClashBot'
sys.path.insert(0, ROOT)
HERE = os.path.dirname(os.path.abspath(__file__))
from pipeline.native_recording import tag_native_recording
from pipeline import vocab

res = [r for r in json.load(open(os.path.join(HERE, 'native_audit_raw.json'))) if 'error' not in r]
NAME = {'witch': 'Witch', 'night_witch': 'DarkWitch', 'furnace': 'FirespiritHut', 'tombstone': 'Tombstone', 'goblin_hut': 'GoblinHut',
        'goblin_cage': 'GoblinCage', 'phoenix': 'Phoenix', 'barbarian_hut': 'BarbarianHut', 'goblin_drill': 'GoblinDrill'}
neg = collections.Counter(); cases = []
todo = [(r, s) for r in res for s in r['sides'] if any(k in NAME for _, k in s['phantom'] + s['missed'])]
negscan = [r for r in res if r['neg_hp_frames']][:120]
for r in negscan:
    rec = tag_native_recording(json.load(open(r['path'], encoding='utf-8')), {})
    last = {}
    for f in rec['frames']:
        for e, eid, form in zip(f['entities'], f['entity_ids'], f['unit_forms']):
            if e[3] in NAME.values() and e[4] <= 0:
                neg[(e[3], 'max_hp_unreadable' if e[5] <= 0 else f'hp<=0 max{e[5]}', form, 'first_max_hp=%s' % last.get(eid))] += 1
            if e[5] > 0:
                last[eid] = e[5]
cache = {}
for r, s in todo:
    if r['path'] not in cache:
        cache = {r['path']: tag_native_recording(json.load(open(r['path'], encoding='utf-8')), {})}
    rec = cache[r['path']]; opp = 1 - s['observer']
    frames = {int(f['tick']): f for f in rec['frames']}
    ticks = sorted(frames)
    for kind, lst in (('phantom', s['phantom']), ('missed', s['missed'])):
        for t, k in lst:
            if k not in NAME:
                continue
            name = NAME[k]
            t = int(t)
            # nearest recorded frame at/after the event
            ft = next((x for x in ticks if x >= t), ticks[-1])
            f = frames[ft]
            same = [e for e in f['entities'] if e[0] == opp and e[3] == name]
            unreadable_parent = any(e[4] <= 0 or e[5] <= 0 for e in same)
            prev = [frames[x] for x in ticks if ft - 60 <= x < ft]
            ids_now = {eid for e, eid in zip(f['entities'], f['entity_ids']) if e[0] == opp and e[3] == name}
            gone = {}
            for pf in prev:
                for e, eid in zip(pf['entities'], pf['entity_ids']):
                    if e[0] == opp and e[3] == name and e[5] > 0 and eid not in ids_now:
                        gone[eid] = (e[1], e[2], e[5])
            cases.append(dict(kind=kind, card=k, tick=t, path=os.path.basename(r['path']), unreadable_parent_present=unreadable_parent,
                              same_card_bodies=[(e[4], e[5]) for e in same][:8],
                              vanished_same_card_last60=[v[2] for v in gone.values()][:8]))
summ = collections.Counter((c['kind'], c['card'], 'unreadable_parent' if c['unreadable_parent_present'] else
                            ('vanished_same_card_body' if c['vanished_same_card_last60'] else
                             ('higher_hp_same_card_on_board' if c['same_card_bodies'] else 'other'))) for c in cases)
out = dict(neg_hp_bodies=[list(k) + [v] for k, v in neg.most_common()], cases=cases,
           summary=[list(k) + [v] for k, v in sorted(summ.items())])
json.dump(out, open(os.path.join(HERE, 'mechanism_check.json'), 'w'), indent=1)
print('NEG-HP bodies (first 25):')
for row in out['neg_hp_bodies'][:25]: print(' ', row)
print('PHANTOM/MISSED mechanism:')
for row in out['summary']: print(' ', row)
