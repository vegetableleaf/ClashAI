"""SME-F1FIX: crown towers (reader card -1) that leave the list while the match goes on, with the hp last read, and what
was visible in the last frame with them: enemy projectiles aimed within 3,000 of the tower and enemy bodies within 8,000.
The 000420@3519 shape is 'no projectile, no body'. Visible board only. python -I tower_vanish.py INPUTS.jsonl ..."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'extract'))
import extract  # noqa: E402

n = quiet = 0
for f in sys.argv[1:]:
    for l in open(f):
        m = json.loads(l)['match']
        prev, seen, last_t = None, set(), None
        rows = []
        for line in open(extract.LIVE / (m + '.jsonl'), 'rb'):
            if b'"frame"' not in line[:40]:
                continue
            d = json.loads(line); t = d['tick']
            if t is None or t < 0 or t in seen:
                continue
            seen.add(t)
            if prev:
                now = {(e[0], e[1], e[2]) for e in d['ents'] if e[3] == -1}
                for e in prev['ents']:
                    if e[3] == -1 and (e[0], e[1], e[2]) not in now:
                        pr = [p[:6] for p in prev.get('proj') or () if p[0] != e[0] and p[4] is not None
                              and abs(p[4] - e[1]) + abs(p[5] - e[2]) < 3000]
                        bo = [b[3] for b in prev['ents'] if b[0] != e[0] and b[1] is not None and b[3] != -1
                              and abs(b[1] - e[1]) + abs(b[2] - e[2]) < 8000]
                        rows.append((t, e[:5], len(pr), bo[:6]))
            prev = d
        for t, e, npr, bo in rows:
            n += 1; quiet += npr == 0 and not bo
            print(m[10:], 'gone at', t, 'tower', e, 'enemy proj aimed near', npr, 'enemy bodies near', bo,
                  '<- nothing visible' if npr == 0 and not bo else '')
print('tower removals', n, '| with nothing visible', quiet)
