"""Behaviour of the hero ability bodies in native re-drive recordings (the real engine, level 11): lifetime, distance
moved, speed, and the nearest enemy BUILDING / crown tower at the body's last frame (building-targeters end there).
  python native_motion.py [replays per card=6] -> native_motion.out"""
import glob, json, math, random, re, sys, collections
try:
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass
MAIN = 'C:/Users/benpe/ClashBot/'
META = json.load(open(MAIN + 'icebow/data/pipeline/gen_dataset_v32_fv5.json'))
WANT = {'DarkPrince@hero': ('DarkPrince', 1356), 'Musketeer@hero': ('Musketeer', 1536), 'Balloon@hero': ('Balloon', 473),
        'Tombstone@hero': ('Tombstone', 4224), 'Goblins@hero': ('Goblins', 2560), 'EliteArcher@hero': ('EliteArcher', 271)}
K = int(sys.argv[1]) if len(sys.argv) > 1 else 6
by = collections.defaultdict(list)
for c in META['corpora']:
    for p in sorted(glob.glob(MAIN + c.replace('\\', '/') + '/j*/replay_*.json')):
        head = open(p, encoding='utf-8').read(8000)
        m = re.search(r'"final_decks":\s*(\{"0":\s*\[[^\]]*\],\s*"1":\s*\[[^\]]*\]\})', head)
        if m:
            for s, d in json.loads(m.group(1)).items():
                for n in d:
                    if n in WANT:
                        by[n].append(p)
rnd = random.Random(7)
for t, (name, hp) in WANT.items():
    out = []
    for p in rnd.sample(sorted(set(by[t])), min(K * 3, len(set(by[t])))):
        r = json.load(open(p, encoding='utf-8'))
        tr = collections.defaultdict(list)
        for fr in r['frames']:
            for e in fr['entities']:
                if str(e[3]) == name and int(e[5]) == hp and e[4] > 0:
                    tr[(e[0], e[-1])].append((fr['tick'], e[1], e[2], e[0], fr))
        for (side, eid), pts in tr.items():
            (t0, x0, y0, _, _), (t1, x1, y1, _, fr) = pts[0], pts[-1]
            d = math.hypot(x1 - x0, y1 - y0) / 1000
            bld = [math.hypot(e[1] - x1, e[2] - y1) / 1000 for e in fr['entities']
                   if e[0] != side and (int(e[6]) in (12, 13) or str(e[3]) in ('Tesla', 'Cannon', 'InfernoTower', 'BombTower', 'Xbow', 'Mortar', 'GoblinCage', 'Tombstone', 'GoblinHut', 'BarbarianHut', 'FirespiritHut', 'ElixirCollector'))]
            out.append((t1 - t0, d, d / max((t1 - t0) / 20, .05), min(bld) if bld else None))
        if len(out) >= K:
            break
    print(f'{t} {name} {hp}: n {len(out)}')
    for life, d, v, nb in out[:K]:
        print(f'   life {life / 20:5.1f} s  moved {d:5.1f} tiles  {v:4.2f} tiles/s  nearest enemy building at end {nb if nb is None else round(nb, 1)}')
