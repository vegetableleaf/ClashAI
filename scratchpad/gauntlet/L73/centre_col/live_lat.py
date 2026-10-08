"""decide_ms of the newest live_play jsonl: first-50 vs last-50 median and share > 300 ms."""
import glob, os, re, statistics
L = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/"
f = max(glob.glob(L + "live_play_*.jsonl"), key=os.path.getmtime)
ms = [int(m) for m in re.findall(r'"decide_ms": *(\d+)', open(f, encoding="utf-8").read())]
if ms:
    print(os.path.basename(f), "n", len(ms), "first50 med", statistics.median(ms[:50]), "last50 med",
          statistics.median(ms[-50:]), ">300ms last50", sum(x > 300 for x in ms[-50:]), "all", sum(x > 300 for x in ms))
