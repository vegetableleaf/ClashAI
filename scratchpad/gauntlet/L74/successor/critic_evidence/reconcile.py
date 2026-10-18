# Per match log since the 12530 anchor: attach the next ladder result (before the next match log); infer missing ones from anchors.
import re, json, math
P = r"C:/Users/benpe/ClashBot/scratchpad/gauntlet/L70/live/overnight.out"
L = open(P, encoding="utf-8", errors="replace").read().splitlines()
ev = []
for i, s in enumerate(L[46888:], 46889):
    m = re.search(r"\[ladder\] trophies: (\d+) total", s)
    if m: ev.append(("A", i, int(m.group(1)))); continue
    m = re.search(r"\[ladder\] result: (WIN|LOSS|DRAW).*?trophies ([+-]?\d+|n/a)", s)
    if m: ev.append(("R", i, m.group(1), None if m.group(2)=="n/a" else int(m.group(2)))); continue
    if s.startswith('{"played"'):
        try: ev.append(("M", i, json.loads(s)["log"].split("live_play_")[-1][:15]))
        except Exception: pass
# matches: M followed by R before the next M
matches = []
for k, e in enumerate(ev):
    if e[0] != "M": continue
    res = None
    for f in ev[k+1:]:
        if f[0] == "M": break
        if f[0] == "R": res = f; break
    matches.append({"log": e[2], "line": e[1], "res": res[2] if res else None, "d": res[3] if res else None})
# anchors -> segments
anchors = [e for e in ev if e[0]=="A"]
out = []
for a, b in zip(anchors, anchors[1:]):
    seg = [m for m in matches if a[1] < m["line"] < b[1]]
    logged = sum(m["d"] for m in seg if m["d"] is not None)
    miss = [m for m in seg if m["res"] is None or m["d"] is None]
    gap = b[2] - a[2] - logged
    out.append((a[2], b[2], len(seg), logged, gap, [(m["log"], m["res"], m["d"]) for m in miss]))
for o in out:
    if o[4] != 0 or o[5]: print(o)
print("match logs:", len(matches), "with ladder delta:", sum(m["d"] is not None for m in matches))
