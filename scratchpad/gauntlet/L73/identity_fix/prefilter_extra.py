"""Head-only scan: native recordings whose final decks hold Skeleton King or Goblinstein (not in the L73 prefilter)."""
import glob, re, json
ROOT = r'C:\Users\benpe\ClashBot'
WANT = {'SkeletonKing', 'Goblinstein'}
out = {}
for p in glob.glob(ROOT + r'\scratchpad\gauntlet\ext\corpus_*\*_public_v1\j*\replay_*.json'):
    with open(p, encoding='utf-8') as f: head = f.read(6000)
    m = re.search(r'"final_decks":\s*(\{"0":\s*\[[^\]]*\],\s*"1":\s*\[[^\]]*\]\})', head)
    if m:
        fam = sorted({n.split('@')[0] for s in json.loads(m.group(1)).values() for n in s} & WANT)
        if fam: out[p] = fam
print(len(out), sum('SkeletonKing' in v for v in out.values()))
json.dump(out, open('prefilter_extra.json', 'w'))
