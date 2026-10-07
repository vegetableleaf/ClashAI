"""Tally checkpoint / feature version / audit flags across the Oct 4-6 live logs."""
import json, glob, collections, os
c = collections.Counter()
for f in sorted(glob.glob('scratchpad/gauntlet/L68/live_reader/live_play_2026100[456]_*.jsonl')):
    with open(f) as fh:
        s = json.loads(fh.readline())
    if s.get('event') != 'start':
        c['nostart'] += 1
        continue
    c[(os.path.basename(s.get('ckpt', '').replace(os.sep, '/').replace(chr(92), '/')), s.get('feature_version'),
       s.get('public_audit'), s.get('extrapolate'))] += 1
for k, v in c.items():
    print(v, k)
