"""V1-LIVEROWS label quality: opponent deck completion (live_records.complete_hf) and the seen-card set, against truth.

    python -I deck_check.py REC/train/index.jsonl REC/calibration/index.jsonl   -> JSON on stdout

(1) planted: every match whose opponent showed 8 cards -> hide each card in turn, complete the other 7 -> correct / wrong /
    abstain (no library deck holds the 7, or the top 8th card < 60% / < 3 sides). Optimistic: the hidden card WAS played, a real
    7-seen match's 8th card never was (often a situational card).
(2) battle log (Ranked, 10-26 08:09 on; calibration block): the poller's deck of the mapped battle vs (a) the 8 seen cards,
    (b) the completion a 7-seen match would have got (unbiased for (1)'s selection), (c) the seen set being a subset."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_records as L  # noqa: E402


def main(paths):
    c = Counter()
    for p in paths:
        for line in open(p):
            j = json.loads(line)
            lv = j.get('live')
            if not lv:
                continue
            seen, bl = set(lv['seen']), set(lv['bl_deck'] or [])
            c[f'seen:{min(len(seen), 9)}'] += 1
            if len(seen) == 8:
                for h in sorted(seen):
                    k8, how, n, pr = L.complete_hf(seen - {h})
                    c['planted_n'] += 1
                    c['planted_' + ('correct' if k8 == h else 'wrong' if k8 else 'abstain:' + how)] += 1
            if bl:
                c['bl_n'] += 1
                c['bl_seen_subset'] += seen <= bl
                if len(seen) == 8:
                    c['bl_seen8_n'] += 1
                    c['bl_seen8_equal'] += seen == bl
                if len(seen) == 7 and seen <= bl:
                    k8, how, n, pr = L.complete_hf(seen)
                    c['bl_seen7_n'] += 1
                    c['bl_seen7_' + ('correct' if k8 is not None and seen | {k8} == bl else 'wrong' if k8 else 'abstain:' + how)] += 1
    pct = lambda a, b: round(100 * c[a] / max(1, c[b]), 1)  # noqa: E731
    ans = c['planted_correct'] + c['planted_wrong']
    ans7 = c['bl_seen7_correct'] + c['bl_seen7_wrong']
    out = dict(planted=dict(n=c['planted_n'], answered_pct=round(100 * ans / max(1, c['planted_n']), 1),
                            accuracy_when_answered_pct=round(100 * c['planted_correct'] / max(1, ans), 1)),
               battlelog=dict(matches=c['bl_n'], seen_subset_pct=pct('bl_seen_subset', 'bl_n'),
                              seen8_equal_pct=pct('bl_seen8_equal', 'bl_seen8_n'), seen8_n=c['bl_seen8_n'],
                              seen7_n=c['bl_seen7_n'], seen7_answered_pct=round(100 * ans7 / max(1, c['bl_seen7_n']), 1),
                              seen7_accuracy_when_answered_pct=round(100 * c['bl_seen7_correct'] / max(1, ans7), 1)),
               raw=dict(sorted(c.items())))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main(sys.argv[1:])
