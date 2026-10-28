"""SME-F1FIX: two sme_live results.jsonl files, match by match, on counts / first_div / frames / first_detail.
python3 same_res.py A.jsonl B.jsonl"""
import json, sys


def load(p):
    return {r['match']: r for r in map(json.loads, open(p))}


a, b = load(sys.argv[1]), load(sys.argv[2])
keys = ('counts', 'first_div', 'frames', 'first_detail')
diff = [m for m in a if any(a[m].get(k) != b.get(m, {}).get(k) for k in keys)]
print('matches', len(a), len(b), '| differ on counts/first_div/frames/first_detail:', len(diff), diff[:8])
