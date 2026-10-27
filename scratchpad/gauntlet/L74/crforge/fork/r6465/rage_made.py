"""Rage area made tick from its countdown at first sighting: made = first - (4500 - rem)/50 (the table life of the
Rage area; extract.table_shims.life returns None for Rage, whose area comes from RageBottle's DeathAreaEffect, so
fights.deployments dates it at the first sighting). Out: one json line per Rage area {match, side, x, y, first, rem, made}."""
import json, sys, os
d, names = sys.argv[1], [l.strip() for l in open(sys.argv[2]) if l.strip()]
for m in names:
    seen = set()
    for line in open(os.path.join(d, m + '.jsonl'), 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        f = json.loads(line); t = f['tick']
        if t is None or t < 0:
            continue
        for a in f['fx']:
            if a[3] == 28000002 and a[4] > 1 and a[6] not in seen:
                seen.add(a[6])
                print(json.dumps(dict(match=m, side=a[0], x=a[1], y=a[2], first=t, rem=a[4], made=t - round((4500 - a[4]) / 50))))
