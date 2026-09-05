"""Ghost-rejection vs match time + outcome sanity, over one or more bench_*.json runs."""
import json, statistics, sys
from collections import Counter, defaultdict
from pathlib import Path

rows = []
for p in sys.argv[1:]:
    rows += json.loads(Path(p).read_text(encoding="utf-8"))["rows"]
by_tag = {}
for r in rows:                                   # de-duplicate tags across runs
    by_tag.setdefault(r["tag"], r)
rows = list(by_tag.values())

BUCKETS = [(0, 60), (60, 120), (120, 180), (180, 240), (240, 10 ** 9)]
att = Counter(); rej = Counter()
first_rej = []
for r in rows:
    for tick, ok, reason in r["ghost_events"]:
        s = tick * 0.05
        for lo, hi in BUCKETS:
            if lo <= s < hi:
                att[(lo, hi)] += 1
                rej[(lo, hi)] += (0 if ok else 1)
    bad = [t for t, ok, _ in r["ghost_events"] if not ok]
    if bad:
        first_rej.append(min(bad) * 0.05)

per = [r["ghost_rejected"] / max(1, r["ghost_ok"] + r["ghost_rejected"]) for r in rows]
undel = [r["ghost_undelivered"] / max(1, r["ghost_total"]) for r in rows]
out = {
    "matches": len(rows),
    "ghost_rejections_per_match": {
        "mean": round(statistics.mean(r["ghost_rejected"] for r in rows), 3),
        "median": statistics.median(r["ghost_rejected"] for r in rows),
        "max": max(r["ghost_rejected"] for r in rows),
        "matches_with_zero": sum(1 for r in rows if r["ghost_rejected"] == 0),
        "histogram": dict(sorted(Counter(r["ghost_rejected"] for r in rows).items()))},
    "ghost_reject_rate_per_match": {"mean": round(statistics.mean(per), 4),
                                    "median": round(statistics.median(per), 4),
                                    "max": round(max(per), 4)},
    "ghost_reject_rate_by_match_time": {
        f"{lo}-{hi if hi < 10**9 else 'end'}s": {
            "attempts": att[(lo, hi)], "rejected": rej[(lo, hi)],
            "rate": round(rej[(lo, hi)] / att[(lo, hi)], 4) if att[(lo, hi)] else None}
        for lo, hi in BUCKETS},
    "first_rejection_seconds": {"n_matches": len(first_rej),
                                "median": round(statistics.median(first_rej), 1) if first_rej else None,
                                "min": round(min(first_rej), 1) if first_rej else None,
                                "max": round(max(first_rej), 1) if first_rej else None},
    "ghost_undelivered": {
        "note": "commands never ATTEMPTED because the match ended first -- the dominant way a ghost "
                "stops mattering, far larger than outright rejection",
        "total": sum(r["ghost_undelivered"] for r in rows),
        "of_total_commands": sum(r["ghost_total"] for r in rows),
        "frac_mean": round(statistics.mean(undel), 4), "frac_median": round(statistics.median(undel), 4)},
    "sanity": {
        "terminated": sum(r["terminated"] for r in rows), "of": len(rows),
        "outcomes": dict(Counter(r["outcome"] for r in rows)),
        "mean_crowns_for": round(statistics.mean(r["crowns"][0] for r in rows), 3),
        "mean_crowns_against": round(statistics.mean(r["crowns"][1] for r in rows), 3),
        "mean_match_seconds": round(statistics.mean(r["seconds"] for r in rows), 1),
        "median_match_seconds": statistics.median(r["seconds"] for r in rows),
        "match_seconds_min_max": [min(r["seconds"] for r in rows), max(r["seconds"] for r in rows)],
        "mean_reward": round(statistics.mean(r["reward"] for r in rows), 3),
        "our_plays_per_match": round(statistics.mean(r["our_plays"] for r in rows), 2),
        "our_reject_rate": round(sum(r["our_rejected"] for r in rows)
                                 / max(1, sum(r["our_plays"] + r["our_rejected"] for r in rows)), 4),
        "termination_reasons": dict(Counter(r.get("termination_reason") for r in rows)),
        "expected_vs_actual": {
            "human_icebow_result": dict(Counter(r["expected_result"] for r in rows)),
            "our_policy_result": dict(Counter(r["outcome"] for r in rows))},
        "deal_cache_hit": sum(1 for r in rows if r.get("deal_cache_hit")),
        "deal_seconds_median": statistics.median(r.get("deal_s", 0.0) for r in rows),
        "unmapped_entities": sum(r["unmapped_entities"] for r in rows)},
}
print(json.dumps(out, indent=1))
Path(sys.argv[1]).with_name("analysis_bench.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
