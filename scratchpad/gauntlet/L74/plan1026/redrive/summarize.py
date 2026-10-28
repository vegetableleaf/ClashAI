"""summarize.py OUT [OUT ...] -- tiers, reasons, refusal details and accepted-play fractions from OUT/grades/*.jsonl."""
import collections, json, sys
from pathlib import Path

for out in sys.argv[1:]:
    gs = [json.loads(l) for p in sorted(Path(out, "grades").glob("*.jsonl")) for l in open(p)]
    driven = [g for g in gs if "accepted_plays" in g]
    tiers = collections.Counter(g["tier"] for g in gs)
    reasons = collections.Counter(f"{g['tier']}:{g.get('reason', '')}" for g in gs)
    acc = sum(g["accepted_plays"] for g in driven)
    tot = sum(g["plays"] for g in driven)
    nih = collections.Counter(min(g["cut_prev_gap"], 99) // 10 * 10 for g in gs
                              if g.get("reason") == "refused:not_in_hand" and g.get("cut_prev_gap") is not None)
    ab = collections.Counter(g.get("reason") for g in gs if g.get("cut_ability"))
    a_crowns = sum(g.get("crowns_match", False) for g in driven)
    print(json.dumps(dict(out=out, replays=len(gs), tiers=dict(tiers), driven=len(driven),
                          accepted_play_share=round(acc / max(tot, 1), 4), crowns_match_driven=a_crowns,
                          reasons=dict(reasons.most_common(25)), not_in_hand_prev_gap_10s=dict(sorted(nih.items())),
                          cut_on_ability=dict(ab)), indent=1))
