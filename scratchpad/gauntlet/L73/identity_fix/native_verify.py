"""Native verification (a): fv4 vs fv5 board classes through obs_contract.from_engine on re-drive recordings.
Truth = the level-11 HP census (native_census.out) written out by hand below, NOT body_identity's own tables.
Usage: python native_verify.py [n_replays=300] [frame_stride=3]"""
import sys, json, random, collections
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, r'C:\Users\benpe\ClashBot')
from pipeline import vocab
from pipeline.obs_contract import from_engine, load_deck
from pipeline.native_recording import tag_native_recording

C, P, N = 'child', 'parent', 'child_no_class'
# (engine name, level-11 max_hp) -> (role, expected class). Evidence: native_census.out (+ ../spawners native_summary).
EXPECT = {('Witch', 81): (C, 'skeletons'), ('Witch', 839): (P, 'witch'), ('Witch', -1): ('unreadable', 'witch'),
          ('DarkWitch', 81): (C, 'bats'), ('DarkWitch', 906): (P, 'night_witch'),
          ('FirespiritHut', 217): (C, 'fire_spirit'), ('FirespiritHut', 238): (C, 'fire_spirit'),
          ('FirespiritHut', 727): (P, 'furnace'), ('FirespiritHut', 798): (P, 'furnace'),
          ('Tombstone', 81): (C, 'skeletons'), ('Tombstone', 529): (P, 'tombstone'), ('Tombstone', -1): ('unreadable', 'tombstone'),
          ('GoblinHut', 133): (C, 'spear_goblins'), ('GoblinHut', 1180): (P, 'goblin_hut'),
          ('BarbarianHut', 716): (C, 'barbarians'), ('BarbarianHut', 1164): (P, 'barbarian_hut'),
          ('Graveyard', 81): (C, 'skeletons'),
          ('GoblinDrill', 202): (C, 'goblins'), ('GoblinDrill', 1313): (P, 'goblin_drill'), ('GoblinDrill', 2560): (P, 'goblin_drill'),
          ('SkeletonBalloon', 81): (C, 'skeletons'), ('SkeletonBalloon', 532): (P, 'skeleton_barrel'), ('SkeletonBalloon', 665): (P, 'skeleton_barrel'),
          ('GoblinGiant', 133): (C, 'spear_goblins'), ('GoblinGiant', 202): (C, 'goblins'), ('GoblinGiant', 3110): (P, 'goblin_giant'),
          ('GoblinCage', 780): (P, 'goblin_cage'), ('GoblinCage', 1080): (N, 'goblin_cage'),
          ('Phoenix', 1052): (P, 'phoenix'), ('Phoenix', 317): (N, 'phoenix'),
          ('SkeletonKing', 1): (C, 'skeletons'), ('SkeletonKing', 2298): (P, 'skeleton_king'),
          ('WitchMother', 529): (P, 'mother_witch'), ('-1', 629): (C, 'mother_witch_hog'), ('-1', 202): (C, 'goblins')}
NAMES = {k[0] for k in EXPECT}
DECK = None


def one(path):
    global DECK
    DECK = DECK or load_deck('icebow')
    stride = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    rec = tag_native_recording(json.load(open(path, encoding='utf-8')), {})
    res = collections.Counter(); unm = {4: set(), 5: set()}; other = collections.Counter()
    for fr in rec['frames'][::stride]:
        obs = dict(fr, players=[])
        want = collections.defaultdict(list)
        for e, form in zip(fr['entities'], fr['unit_forms']):
            name, mhp = str(e[3]), int(e[5])
            if name in NAMES and (name, mhp) in EXPECT and (e[4] > 0 or mhp <= 0):
                want[(int(e[0]), round(e[1] / 18000, 6), round(1 - e[2] / 32000, 6))].append((name, mhp, form))
            elif name in NAMES and name != '-1' and e[4] > 0:
                other[(name, mhp)] += 1
        for fv in (4, 5):
            bs = from_engine(obs, 0, DECK, unmapped=unm[fv], feature_version=fv)
            pool = {k: list(v) for k, v in want.items()}
            got = collections.Counter()
            for u in bs.units:
                k = (u.side, round(u.x, 6), round(u.y, 6))
                if pool.get(k):
                    name, mhp, form = pool[k].pop()
                    role, cls = EXPECT[(name, mhp)]
                    ok_cls = vocab.UNIT_VOCAB[u.cls] == cls
                    ok_form = u.form == (form if role in (P, 'unreadable') else 0)
                    res[(fv, name, mhp, role, 'seen')] += 1
                    res[(fv, name, mhp, role, 'cls_ok')] += ok_cls
                    res[(fv, name, mhp, role, 'cls_form_ok')] += ok_cls and ok_form
                    res[(fv, name, mhp, role, 'hp_unknown')] += u.hp_frac is None
            for k, v in pool.items():
                for name, mhp, form in v:
                    res[(fv, name, mhp, EXPECT[(name, mhp)][0], 'dropped')] += 1
    return [list(k) + [v] for k, v in res.items()], {k: sorted(v) for k, v in unm.items()}, [list(k) + [v] for k, v in other.items()]


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    pre = json.load(open('../spawners/prefilter.json'))
    pre.update({p: v for p, v in json.load(open('prefilter_extra.json')).items() if 'SkeletonKing' in v})
    byf = collections.defaultdict(list)
    for p, fams in sorted(pre.items()):
        for f in fams:
            byf[f].append(p)
    rnd = random.Random(20261006); pick = []
    while len(pick) < n:   # round-robin over families so rare ones are present
        for f in sorted(byf):
            c = [p for p in byf[f] if p not in pick]
            if c and len(pick) < n:
                pick.append(rnd.choice(c))
    tot = collections.Counter(); unm = {4: set(), 5: set()}; other = collections.Counter()
    with ProcessPoolExecutor(6) as ex:
        for res, u, o in ex.map(one, pick, chunksize=2):
            for *k, v in res: tot[tuple(k)] += v
            for fv in (4, 5): unm[fv] |= set(u[fv] if fv in u else u[str(fv)])
            for *k, v in o: other[tuple(k)] += v
    json.dump(dict(replays=len(pick), stride=int(sys.argv[2]) if len(sys.argv) > 2 else 3,
                   rows=[list(k) + [v] for k, v in sorted(tot.items())], unmapped={k: sorted(v) for k, v in unm.items()},
                   unexpected_hp=[list(k) + [v] for k, v in other.most_common()]),
              open('native_verify.json', 'w'), indent=0)
    keys = sorted({k[1:4] for k in tot})
    print(f'{"name":15s} {"hp":>5} {"role":14s} | fv4 seen cls_ok form_ok drop | fv5 seen cls_ok form_ok hp_unk drop')
    for name, mhp, role in keys:
        r = lambda fv, m: tot[(fv, name, mhp, role, m)]
        print(f'{name:15s} {mhp:>5} {role:14s} | {r(4,"seen"):7d} {r(4,"cls_ok"):6d} {r(4,"cls_form_ok"):7d} {r(4,"dropped"):5d} |'
              f' {r(5,"seen"):7d} {r(5,"cls_ok"):6d} {r(5,"cls_form_ok"):7d} {r(5,"hp_unknown"):6d} {r(5,"dropped"):5d}')
    print('unmapped', {k: sorted(v) for k, v in unm.items()})
    print('family bodies with an HP outside EXPECT (top 15):', other.most_common(15))
