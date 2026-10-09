import sys, collections, os
sys.path.insert(0, "C:/Users/benpe/ClashBot/.claude/worktrees/agent-a062325a516da5d40/scratchpad/gauntlet/L74/mistakes")
import mistakes as K
ms = K.load_live()
print(len(ms))
c = collections.Counter()
for m in ms:
    f = os.path.basename(m["file"])
    c[f[10:18]] += 1
print(sorted(c.items()))
print(collections.Counter(m["fam"] for m in ms))
m = ms[-1]
print(m["file"], m["fam"], m["res"], len(m["S"]), m["S"][100][:3], m["S"][100][5], m["S"][100][3][:2], m["S"][100][4])
nd = sum(1 for x in m["S"] if x[5] is not None)
print("decisions", nd)
ts = [x[0] for x in m["S"]]
import numpy as np
print(np.median(np.diff(ts)), ts[:5])
print(collections.Counter(x[5][2] for mm in ms[-30:] for x in mm["S"] if x[5] is not None).most_common(12))
