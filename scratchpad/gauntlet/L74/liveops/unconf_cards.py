"""Unconfirmed plays by card: post-decoy vs the matches before it (inputs = grep dumps of `"event": "unconfirmed"` lines)."""
import collections, json, sys
for tag, p, n in (("pre ", sys.argv[1], int(sys.argv[3])), ("post", sys.argv[2], int(sys.argv[4]))):
    ev = [json.loads(l) for l in open(p)]
    c = collections.Counter(e["name"] for e in ev)
    print(tag, n, "matches,", len(ev), "unconfirmed events (%.2f per match):" % (len(ev) / n), dict(c.most_common()))
