"""Raw native body census per family: (name, card_id, max_hp, kind, hp<=0) incl. card_id -1 non-tower and unreadable
bodies. Distinct bodies by (side, entity_id). Usage: python native_census.py [per_family=20]"""
import json, random, collections, sys
from concurrent.futures import ProcessPoolExecutor
NAMES = {'SkeletonKing', 'WitchMother', 'GoblinDrill', 'Phoenix', 'GoblinCage', 'GoblinGiant', 'SkeletonBalloon', 'Witch',
         'Tombstone', 'FirespiritHut', 'DarkWitch', 'GoblinHut', 'BarbarianHut', 'Graveyard'}

def one(p):
    r = json.load(open(p, encoding='utf-8'))
    bodies = {}; coexist = collections.Counter()
    for f in r['frames']:
        drill = collections.defaultdict(set)
        for e in f['entities']:
            name, cid, eid = str(e[3]), int(e[-2]), int(e[-1])
            tower = cid < 0 and (int(e[5]) in (3052, 4824) or int(e[6]) in (12, 13) and int(e[5]) > 1400)
            if tower: continue
            if name in NAMES or cid < 0:
                k = (int(e[0]), eid if eid >= 0 else (name, int(e[1]) // 500, int(e[2]) // 500))
                bodies.setdefault(k, (name, cid, int(e[5]), int(e[6]), int(e[4]) <= 0))
                if name == 'GoblinDrill' and e[4] > 0: drill[int(e[0])].add(int(e[5]))
        for s, v in drill.items():
            if {1313, 2560} <= v: coexist['drill_1313_and_2560_same_frame'] += 1
            if v: coexist['drill_frames'] += 1
    return [list(v) for v in bodies.values()], dict(coexist)

if __name__ == '__main__':
    per = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    pre = json.load(open('../spawners/prefilter.json')); pre.update(json.load(open('prefilter_extra.json')))
    rnd = random.Random(20261006); pick = set()
    byfam = collections.defaultdict(list)
    for p, fams in pre.items():
        for f in fams: byfam[f.split('@')[0] + ('@' + f.split('@')[1] if '@' in f else '')].append(p)
    for f, ps in sorted(byfam.items()):
        pick.update(rnd.sample(sorted(ps), min(per, len(ps))))
    census = collections.Counter(); co = collections.Counter()
    with ProcessPoolExecutor(6) as ex:
        for b, c in ex.map(one, sorted(pick), chunksize=2):
            for row in b: census[tuple(row)] += 1
            co.update(c)
    rows = sorted(census.items())
    for k, n in rows: print(k, n)
    print(dict(co), len(pick))
    json.dump(dict(replays=len(pick), coexist=dict(co), census=[list(k) + [n] for k, n in rows]), open('native_census.json', 'w'), indent=0)
