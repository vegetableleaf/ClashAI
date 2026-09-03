"""Pro spell NICHES from the crawl (GAUNTLET L16 / HANDOFF §5bq). For every spell the icebow side casts
(log / tornado / rocket), what the OPPONENT played in the previous `W` seconds, and where the spell
landed. Run from icebow/: python ../scratchpad/gauntlet/L16/pro_spell_niche.py"""
import csv, collections, sys
W = 6.0
rows = list(csv.DictReader(open("data/royaleapi/crawl2/plays_ext.csv", encoding="utf-8")))
by = collections.defaultdict(list)
for r in rows: by[r["replay_tag"]].append(r)
# icebow side = the side that plays x-bow in that replay
out = {"the-log": collections.Counter(), "tornado": collections.Counter(), "rocket": collections.Counter()}
n_cast = collections.Counter(); n_side = 0; pos = {k: collections.Counter() for k in out}
gap = {k: [] for k in out}
for tag, ps in by.items():
    ps.sort(key=lambda r: float(r["seconds"]))
    sides = {r["attr_s"] for r in ps if r["attr_card"] == "x-bow"}
    for side in sides:
        n_side += 1
        opp = [r for r in ps if r["attr_s"] != side]
        for r in ps:
            if r["attr_s"] != side or r["attr_card"] not in out: continue
            sp = r["attr_card"]; t = float(r["seconds"]); n_cast[sp] += 1
            prev = [o for o in opp if 0.0 <= t - float(o["seconds"]) <= W]
            if prev:
                last = max(prev, key=lambda o: float(o["seconds"]))
                out[sp][last["attr_card"]] += 1; gap[sp].append(t - float(last["seconds"]))
            else:
                out[sp]["(no opp play in %.0fs)" % W] += 1
            if r["tile_y"]:
                y = float(r["tile_y"]); x = float(r["tile_x"])
                # blue is the high-y half (16..31); normalise both sides to "own half = high"
                if side == "red": y = 31.0 - y
                zone = ("ENEMY princess-tower zone" if y <= 8 else "enemy half" if y < 16
                        else "own half, bridge side" if y < 24 else "own back / king zone")
                pos[sp][zone] += 1
print(f"icebow sides: {n_side}; casts: {dict(n_cast)}")
for sp in out:
    tot = n_cast[sp]; print(f"\n== {sp}: {tot} casts; opponent's LAST play within {W:.0f}s before it (share of casts)")
    for k, v in out[sp].most_common(14): print(f"   {k:28s} {v:5d}  {100*v/tot:5.1f}%")
    g = sorted(gap[sp]); print(f"   gap to that play: p50 {g[len(g)//2]:.1f}s  n={len(g)}")
    tt = sum(pos[sp].values()); print(f"   landing zone (n={tt}):", {k: f"{100*v/tt:.0f}%" for k, v in pos[sp].most_common()})

# ---- by CLASS of what the opponent put down in the window (any play, not only the last) ----
SWARM = {"skeletons","goblins","spear-goblins","goblin-gang","bats","minions","minion-horde","skeleton-army","guards",
         "goblin-barrel","princess","dart-goblin","skeleton-barrel","barbarian-barrel","fire-spirit","electro-spirit",
         "ice-spirit","heal-spirit","rascals","archers","firecracker","wall-breakers","goblin-drill","royal-recruits","zappies","three-musketeers"}
MEDIUM = {"knight","valkyrie","musketeer","wizard","electro-wizard","ice-wizard","mini-pekka","bomber","witch","mother-witch",
          "baby-dragon","hunter","magic-archer","dark-prince","prince","lumberjack","bandit","ghost","royal-ghost","fisherman",
          "night-witch","executioner","flying-machine","mega-minion","inferno-dragon","cannon-cart","electro-dragon","phoenix",
          "little-prince","goblin-machine","monk","archer-queen","golden-knight","skeleton-king","mighty-miner","suspicious-bush","goblinstein","berserker","goblin-demolisher"}
TANK = {"hog-rider","battle-ram","ram-rider","giant","royal-giant","golem","elite-barbarians","royal-hogs","balloon","lava-hound",
        "pekka","mega-knight","electro-giant","goblin-giant","giant-skeleton","sparky","barbarians","elixir-golem","miner","wall-breakers","graveyard","boss-bandit","rune-giant"}
BUILD = {"tesla","cannon","x-bow","mortar","elixir-collector","inferno-tower","bomb-tower","goblin-cage","furnace","tombstone","goblin-hut","barbarian-hut","goblin-drill"}
SPELL = {"fireball","zap","the-log","tornado","rocket","lightning","poison","arrows","freeze","rage","earthquake","snowball","giant-snowball","clone","mirror","void","royal-delivery","barbarian-barrel"}
def cls(c):
    if c in BUILD: return "building"
    if c in TANK: return "tank/wincon"
    if c in SWARM: return "swarm/cheap"
    if c in MEDIUM: return "medium"
    if c in SPELL: return "spell"
    return "other"
byc = {k: collections.Counter() for k in out}; anyc = {k: collections.Counter() for k in out}
for tag, ps in by.items():
    sides = {r["attr_s"] for r in ps if r["attr_card"] == "x-bow"}
    for side in sides:
        opp = [r for r in ps if r["attr_s"] != side and r["attr_card"] != "_invalid"]
        for r in ps:
            if r["attr_s"] != side or r["attr_card"] not in out: continue
            t = float(r["seconds"]); sp = r["attr_card"]
            prev = [o for o in opp if 0.0 <= t - float(o["seconds"]) <= W]
            classes = {cls(o["attr_card"]) for o in prev}
            if not prev: byc[sp]["(nothing)"] += 1
            else:
                for c in classes: anyc[sp][c] += 1
                last = max(prev, key=lambda o: float(o["seconds"])); byc[sp][cls(last["attr_card"])] += 1
print("\n== by CLASS of the opponent's play in the previous 6 s (last play | any play in window), share of casts")
for sp in out:
    tot = n_cast[sp]
    print(f"  {sp:9s}", "  ".join(f"{c}: {100*byc[sp][c]/tot:4.1f}% | {100*anyc[sp][c]/tot:4.1f}%" for c in ("swarm/cheap","medium","tank/wincon","building","spell","(nothing)")))
