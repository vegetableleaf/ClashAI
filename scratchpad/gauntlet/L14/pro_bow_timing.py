"""Pro X-Bow depth vs match time (GAUNTLET L14 / HANDOFF §5bn). Reproduces the table used to rule on the
time-gated defensive snap. Blue side = tile_y <= 15 half; front (offensive) bow = tile_y 18.5/19.5 (bridge
band, reaches a princess); back (defensive) = tile_y 21.5-25.5. Run from icebow/: python ../scratchpad/gauntlet/L14/pro_bow_timing.py"""
import csv, collections
P = "data/royaleapi/crawl2/plays_ext.csv"
B = "data/royaleapi/crawl2/battles.csv"
rows = [r for r in csv.DictReader(open(P, encoding="utf-8")) if r["attr_card"] == "x-bow" and r["tile_y"]]
print("x-bow plays with tiles:", len(rows))
blue = [r for r in rows if float(r["tile_y"]) >= 16]          # deployer's own half is the high-y half for blue
print("blue-side (tile_y>=16):", len(blue))
def depth(r):
    y = float(r["tile_y"])
    return "front" if y < 20 else ("back" if y > 21 else "mid")   # tiles are half-integers: 18.5/19.5 front, 21.5+ back, 20.5 mid
def bucket(s):
    s = float(s)
    if s < 30: return "0-30s"
    if s < 120: return "30-120s"
    if s < 180: return "2x(120-180)"
    if s < 240: return "OT(180-240)"
    return "3xOT(240+)"
tab = collections.defaultdict(collections.Counter)
for r in blue: tab[bucket(r["seconds"])][depth(r)] += 1
print("\ntime bucket        n   front  back  mid  front%")
for b in ["0-30s","30-120s","2x(120-180)","OT(180-240)","3xOT(240+)"]:
    c = tab[b]; n = sum(c.values())
    print(f"{b:16s} {n:4d}  {c['front']:5d} {c['back']:5d} {c['mid']:4d}  {100*c['front']/max(n,1):5.1f}")
# tower proxy: replays where the crawled player took >=1 crown (final only -- no event times)
crowns = {r["replay_tag"]: int(r["team_crowns"] or 0) for r in csv.DictReader(open(B, encoding="utf-8"))}
for lbl, sel in [("took >=1 crown (final)", lambda t: crowns.get(t, 0) >= 1), ("took 0", lambda t: crowns.get(t, 0) == 0)]:
    sub = [r for r in blue if sel(r["replay_tag"])]
    f = sum(depth(r) == "front" for r in sub)
    print(f"{lbl:24s} n={len(sub):4d} front {100*f/max(len(sub),1):5.1f}%")
# per-replay switch front->back
by = collections.defaultdict(list)
for r in blue: by[r["replay_tag"]].append((float(r["seconds"]), depth(r)))
sw = 0; sw_t = collections.Counter()
for t, ps in by.items():
    ps.sort(); seen_front = False
    for s, d in ps:
        if d == "front": seen_front = True
        elif d == "back" and seen_front:
            sw += 1; sw_t[bucket(s)] += 1; break
print(f"\nreplays with blue bows: {len(by)}; switched front->back: {sw}; first switch by bucket: {dict(sw_t)}")
# same proxy restricted to LATE bows (>=120 s), the only ones the phase flip could act on
for lbl, sel in [("late, took >=1 crown", lambda t: crowns.get(t, 0) >= 1), ("late, took 0", lambda t: crowns.get(t, 0) == 0)]:
    sub = [r for r in blue if sel(r["replay_tag"]) and float(r["seconds"]) >= 120]
    f = sum(depth(r) == "front" for r in sub)
    print(f"{lbl:24s} n={len(sub):4d} front {100*f/max(len(sub),1):5.1f}%")
