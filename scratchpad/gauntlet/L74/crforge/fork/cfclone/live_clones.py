# usage: live_clones.py LIVE_LOG [WINDOW] -- CF-CLONE-3: in one live_play log (memory-reader frames), every new entity
# with max hit points 1 (a clone), and the entities of its side near it in the ticks around its birth
# (ents rows: side, x, y, ?, hp, max hp, kind, address).
import json, sys
path = sys.argv[1]
win = int(sys.argv[2]) if len(sys.argv) > 2 else 20
frames = []
for line in open(path):
    try:
        d = json.loads(line)
    except ValueError:
        continue
    if d.get("event") == "frame" and d.get("ents"):
        frames.append((d["tick"], d["ents"]))
seen = set()
births = []
for tick, ents in frames:
    for e in ents:
        if e[5] == 1 and e[7] not in seen:
            seen.add(e[7])
            births.append((tick, e))
print(path, "frames", len(frames), "clone births", len(births))
for tick, c in births:
    print("clone born", tick, c)
    for t, ents in frames:
        if tick - win <= t <= tick + win:
            near = [e for e in ents if e[0] == c[0] and e[5] > 1 and abs(e[1] - c[1]) + abs(e[2] - c[2]) < 4000]
            print("  ", t, near)
