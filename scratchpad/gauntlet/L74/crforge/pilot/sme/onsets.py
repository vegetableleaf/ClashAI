"""Exact/diverged segments of a score_frames.jsonl, with the first diff of each diverged segment (onset)."""
import json, sys
fr = [json.loads(l) for l in open(sys.argv[1])]
seg = None
for f in fr + [{'t': 10 ** 9, 'n': 0, 'shift': None, 'd': []}]:
    bad = f['n'] > 0 and f['shift'] is None
    if seg is None or bad != seg[0]:
        if seg:
            print('%-8s %5d-%5d frames %4d' % ('DIVERGED' if seg[0] else 'exact', seg[1], seg[2], seg[3]),
                  json.dumps(seg[4])[:400] if seg[0] else '')
        seg = [bad, f['t'], f['t'], 0, f['d'][:3]]
    seg[2] = f['t']; seg[3] += 1
