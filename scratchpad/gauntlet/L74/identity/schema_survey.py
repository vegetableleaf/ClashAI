"""Which live logs carry decision.public.raw_bodies vs only frame 'ents' (first 3000 lines per file)."""
import glob, collections, os
LOG = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/'
c = collections.Counter(); first = {}
for f in sorted(glob.glob(LOG + 'live_play_2026*.jsonl')):
    kinds = set()
    with open(f, encoding='utf8', errors='replace') as fh:
        for i, l in enumerate(fh):
            if i > 3000: break
            if l.startswith('{"event": "frame"'): kinds.add('frame_ents' if '"ents"' in l else 'frame_other')
            elif l.startswith('{"event": "decision"'): kinds.add('dec_raw' if '"raw_bodies"' in l else 'dec_noraw')
    k = tuple(sorted(kinds)); c[k] += 1; first.setdefault(k, os.path.basename(f))
for k, v in c.most_common(): print(v, k, first[k])
