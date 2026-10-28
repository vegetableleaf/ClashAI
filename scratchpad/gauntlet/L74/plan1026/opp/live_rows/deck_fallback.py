"""Planted test of a fallback 8th-card completion for 7-seen matches that complete_hf abstains on (no library deck holds all 7):
candidate c scored by the sides of library decks that hold c and >= 6 of the 7 seen cards.
    python -I deck_fallback.py REC/train/index.jsonl [...]   -> accuracy / coverage per share threshold (stdout)"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_records as L  # noqa: E402


def fallback(seen):
    w = Counter()
    for ks, n in L.hf_library().items():
        if len(ks & seen) >= 6:
            for c in ks - seen:
                w[c] += n
    if not w:
        return None, 0.0
    k, v = w.most_common(1)[0]
    return k, v / sum(w.values())


res = []
for p in sys.argv[1:]:
    for line in open(p):
        j = json.loads(line)
        lv = j.get('live')
        if not lv or len(lv['seen']) != 8:
            continue
        seen = set(lv['seen'])
        for h in sorted(seen):
            s7 = seen - {h}
            if L.complete_hf(s7)[0] is not None:
                continue                          # complete_hf answers: not a fallback case
            k, share = fallback(s7)
            res.append((share, k == h))
print('fallback cases', len(res))
for th in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5):
    a = [ok for s, ok in res if s >= th]
    print(f'share >= {th}: answered {100 * len(a) / max(1, len(res)):.1f}%  accuracy {100 * sum(a) / max(1, len(a)):.1f}%')
