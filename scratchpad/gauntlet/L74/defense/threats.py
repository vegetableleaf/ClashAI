"""Threatened-state index for the VM model passes (F2/F3), from defense.py's normalised data (laptop, one core):
  out/threat_index.json.gz = {"pros": {"<id12>|<side>": [[tick, elixir, lane, lane value, lead card], ...]},
                              "live": {"<log file>": [[decision tick, raw elixir, lane, lane value, lead card], ...]}}
A state is threatened when one lane holds >= 3 elixir of enemy value on my half (own y <= 16; defense.py values); the
heavier lane is recorded. Live: towerref_w2 logs only."""
import os, sys, gzip, json, collections
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
sys.path.insert(0, HERE)
import defense as D


def index(m):
    out = []
    for s in m["S"]:
        vL, vR = D.lane_val(s[3], "L"), D.lane_val(s[3], "R")
        lane, v = ("L", vL) if vL >= vR else ("R", vR)
        if v < 3: continue
        c = collections.Counter()
        for b in s[3]:
            if b[2] <= D.HALF_Y and D.lane_of(b[1]) == lane: c[b[0]] += b[3]
        out.append([s[0], None if s[1] is None else round(s[1], 2), lane, round(v, 2), c.most_common(1)[0][0]])
    return out


if __name__ == "__main__":
    R = {"pros": {}, "live": {}}
    for m in D.load("pros"):
        sid = m["file"].rsplit("_s", 1)
        R["pros"][f"{sid[0][:12]}|{sid[1]}"] = index(m)
    for m in D.load("live"):
        if m["fam"].startswith("towerref"): R["live"][m["file"]] = index(m)
    with gzip.open(HERE + "out/threat_index.json.gz", "wt") as fh: json.dump(R, fh)
    print({k: (len(v), sum(map(len, v.values()))) for k, v in R.items()})
