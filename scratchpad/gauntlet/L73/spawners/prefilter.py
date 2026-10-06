"""List native re-drive recordings whose final decks hold a spawner-family card (reads only the file head)."""
import glob, re, json, collections
ROOT = r'C:\Users\benpe\ClashBot'
FAM = ['Witch', 'DarkWitch', 'FirespiritHut', 'WitchMother', 'Tombstone', 'GoblinHut', 'BarbarianHut', 'Graveyard', 'GoblinDrill',
       'SkeletonBalloon', 'GoblinGiant', 'GoblinCage', 'Phoenix', 'ElixirGolem']
out = {}; cnt = collections.Counter(); tot = 0
for corp in glob.glob(ROOT + r'\scratchpad\gauntlet\ext\corpus_*\*_public_v1'):
    for p in glob.glob(corp + r'\j*\replay_*.json'):
        tot += 1
        with open(p, encoding='utf-8') as f: head = f.read(6000)
        m = re.search(r'"final_decks":\s*(\{"0":\s*\[[^\]]*\],\s*"1":\s*\[[^\]]*\]\})', head)
        if not m: cnt['no_head'] += 1; continue
        d = json.loads(m.group(1))
        fam = sorted({n.split('@')[0] + ('@' + n.split('@')[1] if '@' in n else '') for s in d.values() for n in s if n.split('@')[0] in FAM})
        if fam:
            out[p] = fam
            for f in fam: cnt[f] += 1
print(tot, len(out)); print(cnt)
json.dump(out, open('prefilter.json', 'w'))
