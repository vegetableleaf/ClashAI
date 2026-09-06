"""Read-only: why do ~half the crawl2 replays lack x/y markers?  Usage: python xy_why.py icebow|hogeq"""
import csv, json, sys, os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

deck = sys.argv[1]
ROOT = Path("C:/Users/benpe/ClashBot")
D = ROOT / deck / "data/royaleapi/crawl2"
OUT = ROOT / "scratchpad/gauntlet/L64/xy_why"
lines = []
def P(*a):
    s = " ".join(str(x) for x in a); print(s); lines.append(s)

plays = list(csv.DictReader(open(D / "plays_ext.csv", encoding="utf-8")))
bat = list(csv.DictReader(open(D / "battles.csv", encoding="utf-8")))
raw = json.loads((D / "battles_raw.json").read_text(encoding="utf-8"))
done = json.loads((D / "replays_done.json").read_text(encoding="utf-8"))
P(f"== {deck}: plays rows {len(plays)}, battles.csv rows {len(bat)}, battles_raw {len(raw)}, replays_done {len(done)}")
P("plays_ext columns:", list(plays[0].keys()))
P("battles.csv columns:", list(bat[0].keys()))
P("battles_raw keys:", sorted(set(k for r in raw for k in r)))

def hasxy(r):
    v = r.get("tile_x", "")
    return bool(v) and v != "None"
# 1. per-battle x/y flag
by = defaultdict(list)
for r in plays: by[r["replay_tag"]].append(r)
frac = {}
for t, rs in by.items():
    real = [r for r in rs if r.get("attr_ability") != "1" and r.get("attr_card") != "_invalid"]
    n = len(real) or len(rs)
    frac[t] = sum(hasxy(r) for r in real) / n if n else 0.0
P(f"\n== 1. per-battle x/y fraction (ability rows excluded), {len(frac)} replays with plays")
bins = Counter()
for t, f in frac.items():
    b = "0 exactly" if f == 0 else "(0,0.2)" if f < 0.2 else "[0.2,0.8)" if f < 0.8 else "[0.8,1)" if f < 1 else "1 exactly"
    bins[b] += 1
for b in ["0 exactly", "(0,0.2)", "[0.2,0.8)", "[0.8,1)", "1 exactly"]:
    P(f"  {b:>10}: {bins[b]}")
allrows = [r for r in plays]
P(f"  play rows with x/y: {sum(hasxy(r) for r in allrows)}/{len(allrows)}")
cov = {t for t, f in frac.items() if f >= 0.8}
miss_in_cov = Counter()
for t in cov:
    for r in by[t]:
        if not hasxy(r):
            miss_in_cov[(r.get("attr_ability"), r.get("attr_card"))] += 1
P("  in covered battles, rows lacking xy by (ability, card):", miss_in_cov.most_common(8))
P("  rows with x_units == 'None':", sum(1 for r in plays if r.get("x_units") == "None"))
HAS = {t: frac[t] >= 0.5 for t in frac}
def ct(name, keyf, rows, top=12):
    c = defaultdict(lambda: [0, 0])
    for b in rows:
        t = b["replay_tag"]
        if t not in HAS: continue
        k = keyf(b)
        c[k][0] += HAS[t]; c[k][1] += 1
    items = sorted(c.items(), key=lambda kv: -kv[1][1])[:top]
    P(f"\n-- {name}  ({len(c)} levels; showing top {min(top,len(c))} by n)")
    for k, (h, n) in items:
        P(f"  {str(k)[:60]:<60} {h:5d}/{n:<5d} {100*h/n:5.1f}%")
    return c

P(f"\n== 2. cross-tabs (has_xy = frac>=0.5), battles.csv n={len(bat)}")
seen = set(); bat_u = []
for b in bat:
    if b["replay_tag"] in seen: continue
    seen.add(b["replay_tag"]); bat_u.append(b)
P(f"  battles.csv unique replay_tags {len(bat_u)}; with plays {sum(b['replay_tag'] in HAS for b in bat_u)}; has_xy {sum(HAS.get(b['replay_tag'],0) for b in bat_u)}")
ct("battle_type", lambda b: b["battle_type"], bat_u)
ct("result", lambda b: b["result"], bat_u)
ct("player is team[0]", lambda b: b["team_tags"].split(",")[0] == b["player_tag"], bat_u)
ct("n team tags / n opp tags", lambda b: (len(b["team_tags"].split(",")), len(b["opponent_tags"].split(","))), bat_u)
ct("crowns (team,opp)", lambda b: (b["team_crowns"], b["opponent_crowns"]), bat_u)
ct("rank", lambda b: b["rank"], bat_u, top=8)
def rb(v, w):
    try: return f"{int(int(float(v))//w*w)}"
    except Exception: return "?"
ct("rating bucket (100)", lambda b: rb(b["rating"], 100), bat_u, top=15)
ct("wins_7d bucket (20)", lambda b: rb(b["wins_7d"], 20), bat_u, top=12)
ct("clan_tag", lambda b: b["clan_tag"], bat_u, top=10)
ct("player_tag", lambda b: b["player_tag"] + " " + b["player_name"][:12], bat_u, top=60)
ct("deck", lambda b: b["deck"], bat_u, top=8)
ct("replay_tag len", lambda b: len(b["replay_tag"]), bat_u)
ct("replay_tag prefix2", lambda b: b["replay_tag"][:2], bat_u, top=12)
ct("replay_tag char0", lambda b: b["replay_tag"][0], bat_u, top=12)
ct("replay_tag char1", lambda b: b["replay_tag"][1], bat_u, top=12)
ct("replay_tag char2", lambda b: b["replay_tag"][2], bat_u, top=12)
ct("replay_tag char3", lambda b: b["replay_tag"][3], bat_u, top=12)
ct("replay_tag chars 4-5", lambda b: b["replay_tag"][4:6], bat_u, top=12)
def day(b):
    try: return datetime.fromtimestamp(int(b["battle_timestamp"]), tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception: return "?"
def hour(b):
    try: return datetime.fromtimestamp(int(b["battle_timestamp"]), tz=timezone.utc).strftime("%H")
    except Exception: return "?"
cday = ct("battle day (UTC)", day, bat_u, top=60)
ct("battle hour (UTC)", hour, bat_u, top=24)
ct("plays count bucket (20)", lambda b: rb(b["plays"], 20), bat_u, top=12)
ct("team_elixir_leaked bucket (2)", lambda b: rb(b["team_elixir_leaked"] or 0, 2), bat_u, top=8)
ct("team_elixir_total==0/empty", lambda b: b["team_elixir_total"] in ("", "0"), bat_u)
P("\n-- battle day chronological")
for k in sorted(cday):
    h, n = cday[k]; P(f"  {k} {h:4d}/{n:<4d} {100*h/n:5.1f}%")
P("\n-- file mtimes:", {f: datetime.fromtimestamp(os.path.getmtime(D / f), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC") for f in ["battles.csv", "plays_ext.csv", "battles_raw.json", "players_done.json", "replays_done.json", "roster.json"]})
extra = sorted(set(k for r in raw for k in r) - set(bat[0].keys()))
P("  battles_raw keys not in battles.csv:", extra)
rawmap = {r["replay_tag"]: r for r in raw}
for k in extra:
    ct("raw:" + k, lambda b, k=k: rawmap.get(b["replay_tag"], {}).get(k, "<absent>"), bat_u, top=10)
P("\n-- battles.csv row-order (fetch order) bucket of 100")
for i in range(0, len(bat_u), 100):
    chunk = bat_u[i:i+100]
    h = sum(HAS.get(b["replay_tag"], 0) for b in chunk if b["replay_tag"] in HAS)
    n = sum(b["replay_tag"] in HAS for b in chunk)
    days = sorted(set(day(b) for b in chunk))
    P(f"  rows {i:5d}-{i+len(chunk)-1:5d}: {h:4d}/{n:<4d} {100*h/max(n,1):5.1f}%  battle days {days[0]}..{days[-1]}")
inraw = {r["replay_tag"] for r in raw}
P(f"\n-- raw battles {len(inraw)}, in battles.csv {len(inraw & seen)}, in replays_done {len(inraw & set(done))}, done but not in csv {len(set(done) - seen)}, csv not in done {len(seen - set(done))}")
P("\n-- per player: covered vs uncovered battle-timestamp (players with >=5 battles in both halves)")
pp = defaultdict(lambda: {True: [], False: []})
for b in bat_u:
    t = b["replay_tag"]
    if t in HAS:
        try: pp[b["player_tag"]][HAS[t]].append(int(b["battle_timestamp"]))
        except Exception: pass
nboth = 0; newer_cov = 0
for p, d in pp.items():
    if len(d[True]) >= 5 and len(d[False]) >= 5:
        nboth += 1
        mc = sorted(d[True])[len(d[True])//2]; mu = sorted(d[False])[len(d[False])//2]
        newer_cov += mc > mu
P(f"  players with >=5 in both halves: {nboth}; covered-half median newer than uncovered in {newer_cov}")
clean = 0; tot = 0
for p, d in pp.items():
    if d[True] and d[False]:
        tot += 1
        if max(d[False]) < min(d[True]): clean += 1
P(f"  clean time split within player (max uncovered ts < min covered ts): {clean}/{tot}")
P("\n-- all battles sorted by battle_timestamp, buckets of 100")
srt = sorted([b for b in bat_u if b["replay_tag"] in HAS], key=lambda b: int(b["battle_timestamp"] or 0))
for i in range(0, len(srt), 100):
    chunk = srt[i:i+100]
    h = sum(HAS[b["replay_tag"]] for b in chunk)
    P(f"  {day(chunk[0])} .. {day(chunk[-1])}: {h:4d}/{len(chunk):<4d} {100*h/len(chunk):5.1f}%")
(OUT / f"{deck}_xy_why.txt").write_text("\n".join(lines), encoding="utf-8")
json.dump({t: f for t, f in frac.items()}, open(OUT / f"{deck}_frac.json", "w"))
