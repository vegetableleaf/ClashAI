"""RECON-3 diagnostic: flags-off record of each Tombstone-hero match with unit_index 2 added to its extracted Tombstone
ability plays (dates unchanged, source cast_seen). If RECON v2's repress then fixes them, the missing unit_index is the
reason repress was inert. Usage: python3 mk_unit_test.py IN.jsonl OUT.jsonl match1,match2,..."""
import json, sys
src, dst, ms = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
n = 0
with open(dst, 'w') as w:
    for l in open(src):
        r = json.loads(l)
        if any(r['match'].endswith(m) for m in ms):
            for p in r['plays']:
                if p['kind'] == 'ability' and p['card'] == 'Tombstone' and p.get('source') == 'cast_seen':
                    p['unit_index'] = 2
                    n += 1
            w.write(json.dumps(r) + '\n')
print('patched abilities', n)
