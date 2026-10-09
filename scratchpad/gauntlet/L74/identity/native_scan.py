"""Training side of the identity census: how the live model's TRAINING corpora (gen_dataset_v32_fv5 'corpora', native
re-drive recordings, level 11) carry the same bodies. For each target card (native final_decks token), up to K replays
(seeded sample) are parsed; every body whose card_id belongs to a target card is keyed (name, card_id, form, max_hp)
with its fv5 identity (body_identity.resolve_board, tower factor 1.0 = level 11, as the dataset builder).
Counts: distinct bodies (side, entity id) and recorded frames (record_every 10 ticks). Single process, below normal.
  python native_scan.py [K=25]   -> native_scan.json
"""
import collections, glob, json, os, random, re, sys, time
try:
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '../../../..')))
from pipeline.obs_contract import catalog_card_form
from pipeline import vocab, body_identity as BI

MAIN = 'C:/Users/benpe/ClashBot/'
META = json.load(open(MAIN + 'icebow/data/pipeline/gen_dataset_v32_fv5.json'))
TARGETS = ['Balloon@hero', 'Goblins@hero', 'Musketeer@hero', 'DarkPrince@hero', 'Tombstone@hero', 'IceGolemite@hero',
           'EliteArcher@hero', 'LittlePrince', 'Goblinstein', 'BattleRam', 'BattleRam@evolution', 'GoblinGang',
           'SkeletonArmy@evolution', 'Mortar@evolution', 'Ghost@evolution', 'Ghost', 'RageBarbarian@evolution',
           'Wallbreakers@evolution', 'GoblinCage', 'GoblinCage@evolution', 'Phoenix', 'IceSpirits@evolution',
           'AngryBarbarians@evolution', 'ElixirGolem', 'SuspiciousBush', 'RamRider', 'Rascals', 'ThreeMusketeers',
           'LavaHound', 'Golem', 'ElectroSpirit', 'Wizard@hero', 'Bowler@hero', 'BarbLog@hero']


def main():
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    files = []
    for c in META['corpora']:
        files += sorted(glob.glob(MAIN + c.replace('\\', '/') + '/j*/replay_*.json'))
    by = collections.defaultdict(list)
    t0 = time.time()
    for p in files:
        with open(p, encoding='utf-8') as f:
            head = f.read(8000)
        m = re.search(r'"final_decks":\s*(\{"0":\s*\[[^\]]*\],\s*"1":\s*\[[^\]]*\]\})', head)
        if not m:
            continue
        decks = json.loads(m.group(1))
        for s, d in decks.items():
            for n in d:
                if n in TARGETS:
                    by[n].append((p, int(s)))
    print('replays', len(files), 'head scan', f'{time.time() - t0:.0f}s', {t: len(by[t]) for t in TARGETS}, flush=True)
    rnd = random.Random(20261008)
    pick = collections.defaultdict(set)          # path -> {(side, target)}
    for t in TARGETS:
        for p, s in rnd.sample(by[t], min(K, len(by[t]))):
            pick[p].add((s, t))
    agg = {}
    for i, (p, st) in enumerate(sorted(pick.items())):
        r = json.load(open(p, encoding='utf-8'))
        want = {}                                 # (side, base name) -> target
        for s, t in st:
            want[(s, t.split('@')[0])] = t
        for fr in r['frames']:
            ents = fr['entities']
            board = []
            for e in ents:
                s, name, hp, mhp, cid, eid = int(e[0]), str(e[3]), e[4], e[5], int(e[-2]), int(e[-1])
                if name == '-1' or (hp <= 0 and mhp > 0):
                    continue
                board.append((s, name, float(mhp), catalog_card_form(cid)[1], False, cid, eid))
            ids = BI.resolve_board([b[:5] for b in board], {0: 1.0, 1: 1.0}) if board else []
            for b, ident in zip(board, ids):
                t = want.get((b[0], b[1]))
                if t is None:
                    continue
                k = (t, b[1], b[5], b[3], int(b[2]), None if ident.cls is None else vocab.UNIT_VOCAB[ident.cls], ident.form, ident.reason)
                a = agg.setdefault(k, dict(frames=0, bodies=set(), replays=set()))
                a['frames'] += 1; a['bodies'].add((p, b[0], b[6])); a['replays'].add(p)
        if i % 25 == 0:
            print(f'[{i}/{len(pick)}] {time.time() - t0:.0f}s', flush=True)
    rows = [dict(target=k[0], name=k[1], card_id=k[2], form=k[3], max_hp=k[4], cls=k[5], cls_form=k[6], reason=k[7],
                 frames=a['frames'], bodies=len(a['bodies']), replays=len(a['replays'])) for k, a in agg.items()]
    rows.sort(key=lambda r: (r['target'], -r['bodies']))
    json.dump(dict(K=K, n_replays={t: len(by[t]) for t in TARGETS}, sampled=len(pick), rows=rows),
              open(os.path.join(HERE, 'native_scan.json'), 'w'), indent=0)
    for r in rows:
        print(r)
    print(f'done {time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
