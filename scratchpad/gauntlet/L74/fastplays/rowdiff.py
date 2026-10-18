"""Which keys differ between two rows files for the same seeds (census evo rows only; a row without census = evo, the plan's job 0).
    python rowdiff.py A.jsonl B.jsonl [ignore,keys]"""
import json
import sys

a = {r['seed']: r for r in map(json.loads, open(sys.argv[1]).read().splitlines()) if r.get('census', 'evo') == 'evo'}
b = {r['seed']: r for r in map(json.loads, open(sys.argv[2]).read().splitlines()) if r.get('census', 'evo') == 'evo'}
ign = set(sys.argv[3].split(',')) if len(sys.argv) > 3 else set()
diff, same = {}, 0
for s in sorted(set(a) & set(b)):
    ka = {k: v for k, v in a[s].items() if k not in ign}
    kb = {k: v for k, v in b[s].items() if k not in ign}
    keys = [k for k in set(ka) | set(kb) if ka.get(k) != kb.get(k)]
    same += not keys
    for k in keys:
        diff.setdefault(k, []).append((s, str(ka.get(k))[:60], str(kb.get(k))[:60]))
print('common seeds', len(set(a) & set(b)), 'identical', same)
for k, v in sorted(diff.items()):
    print(k, len(v), v[:2])
