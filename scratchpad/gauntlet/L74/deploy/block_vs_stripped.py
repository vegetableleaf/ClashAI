"""CLXV 150-match block verdict vs stripped CLXIII (owner 10-31: compare, do not revert on the old 32.7% bar).

Waits until the battle log holds 150 Ranked battles since the block start, then posts the comparison to Discord and
exits. Report only: it never touches live. Keep CLXV unless it is significantly below stripped CLXIII (one-sided p < .05).
Run detached (WMI) from the repo root: python -I scratchpad/gauntlet/L74/deploy/block_vs_stripped.py
"""
import json, math, os, subprocess, sys, time

LOG = "scratchpad/gauntlet/L74/crapi/data/own_battlelog.jsonl"
POST = "scratchpad/gauntlet/L69/discord/post.py"
MSG = "scratchpad/gauntlet/L74/deploy/block_vs_stripped.msg"
BLOCK_FROM = "20261031T100400"                       # UTC; CLXV redeployed 06:04 EDT
STRIPPED = [("20261031T013800", "20261031T062400"), ("20261031T084000", "20261031T100100")]   # CLXIII stripped, UTC
N = 150


def ranked():
    seen = {}
    for line in open(LOG, encoding="utf-8"):
        b = json.loads(line)["battle"]
        if b.get("type") == "pathOfLegend":
            seen[b["battleTime"][:15]] = b["team"][0]["crowns"] > b["opponent"][0]["crowns"]
    return sorted(seen.items())


def verdict(rows):
    blk = [w for t, w in rows if t >= BLOCK_FROM][:N]
    ref = [w for t, w in rows if any(a <= t < b for a, b in STRIPPED)]
    w1, n1, w2, n2 = sum(blk), len(blk), sum(ref), len(ref)
    p1, p2 = w1 / n1, w2 / n2
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    pool = (w1 + w2) / (n1 + n2)
    z = (p1 - p2) / math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2))
    p_worse = 0.5 * math.erfc(-z / math.sqrt(2))     # one-sided P(CLXV worse)
    keep = p_worse >= 0.05
    return (f"CLXV 150-block verdict vs stripped CLXIII: CLXV {w1}/{n1} ({p1:.1%}) vs CLXIII stripped {w2}/{n2} ({p2:.1%}); "
            f"diff {p1 - p2:+.1%} [{p1 - p2 - 1.96 * se:+.1%}, {p1 - p2 + 1.96 * se:+.1%}], one-sided p(worse) {p_worse:.3f} -> "
            + ("KEEP CLXV (not significantly worse)." if keep else "CLXV significantly WORSE: lead to revert to stripped CLXIII."))


if __name__ == "__main__":
    if "--test" in sys.argv:
        demo = [("20261031T020000", True)] * 25 + [("20261031T030000", False)] * 65 + \
               [("20261031T110000", True)] * 56 + [("20261031T120000", False)] * 94
        print(verdict(sorted(demo)))
        assert "KEEP" in verdict(sorted(demo))
        bad = [("20261031T020000", True)] * 25 + [("20261031T030000", False)] * 65 + \
              [("20261031T110000", True)] * 20 + [("20261031T120000", False)] * 130
        assert "WORSE" in verdict(sorted(bad))
        sys.exit(0)
    while sum(t >= BLOCK_FROM for t, _ in ranked()) < N:
        time.sleep(600)
    text = verdict(ranked())
    open(MSG, "w", encoding="utf-8").write(text + "\n")
    subprocess.run([sys.executable, POST, MSG])
    print(time.strftime("%FT%T"), text, flush=True)
