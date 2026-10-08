"""Live elixir forecast check: model_own_elixir - own_elixir_raw (26-tick forecast) by tick range, raw < 8 (no cap).
Expected 26 x regen: 1x .46, 2x/OT .93, last OT minute (>= 4800) 1.39.  python diag_forecast.py"""
import json, glob, collections
import econ2 as E

d = collections.defaultdict(list)
fs = sorted(glob.glob(E.G.LOGDIR + "live_play_20261008_1[3-6]*.jsonl"))       # the towerref_w2 live logs
for f in fs:
    for l in open(f, encoding="utf8", errors="replace"):
        if not l.startswith('{"event": "decision"'): continue
        p = json.loads(l).get("public") or {}
        r, m, t = p.get("own_elixir_raw"), p.get("model_own_elixir"), p.get("raw_tick")
        if r is None or m is None or t is None or r >= 8: continue
        d["1x" if t < 2400 else "2x" if t < 3600 else "OT<4800" if t < 4800 else "OT>=4800"].append(m - r)
print({k: (len(v), round(sorted(v)[len(v) // 2], 3)) for k, v in d.items()})
