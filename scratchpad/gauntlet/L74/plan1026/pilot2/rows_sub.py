"""rows_sub.py A.jsonl B.jsonl -- rows_eq.py's fields for every game of A (a GAP_CHUNKS block) against the SAME game in B (a full
480-row block): games matched on (seed, tag, learner_side, opp_deck); prints identical / matched / unmatched."""
import json
import sys

ID = ("seed", "tag", "learner_side", "opp_deck")
K = ("outcome", "end_tick", "tower_hp_diff", "crowns_for", "crowns_against")
rows = [[json.loads(x) for x in open(f) if x.strip()] for f in sys.argv[1:3]]
key = lambda r: json.dumps([r.get(k) for k in ID])                  # noqa: E731
b = {}
for r in rows[1]:
    b.setdefault(key(r), []).append([r.get(k) for k in K])
same = matched = 0
for r in rows[0]:
    got = b.get(key(r))
    if got:
        matched += 1
        same += [r.get(k) for k in K] in got
print(f"{same}/{len(rows[0])} identical, {matched} matched in B ({len(rows[1])} rows)")
