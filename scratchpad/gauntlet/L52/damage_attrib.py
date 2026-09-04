"""L52: per-match tower damage side-by-side (engine final HP vs sim final HP, both 211 replays), and which
OPPONENT (side 0) cards are associated with the sim's EXCESS damage on the icebow (side 1) towers.
Engine batch = scratchpad/gauntlet/ext/batch (no per-tick record; final tower HP only); sim = a simbatch dir."""
import json, sys, csv, statistics as st, collections
from pathlib import Path
ROOT = Path("C:/Users/benpe/ClashBot")
simdir = ROOT / "scratchpad/gauntlet" / (sys.argv[1] if len(sys.argv) > 1 else "L51/simbatch")
battles = {r["replay_tag"]: r for r in csv.DictReader(open(ROOT / "icebow/data/royaleapi/crawl2/battles.csv", encoding="utf-8"))}
rows = []
for p in sorted((ROOT / "scratchpad/gauntlet/ext/batch").glob("replay_*.json")):
    tag = p.stem.replace("replay_", "")
    e = json.loads(p.read_text()); s = json.loads((simdir / f"replay_{tag}.json").read_text())
    if "final" not in e or "final" not in s: continue
    def dmg(fin, side):
        tw = [t for t in fin["towers"] if t["side"] == side]
        mx = {"king": 4824, "princess": 3052}
        return sum(mx[t["type"]] - t["hp"] for t in tw)
    et = e["final"]["terminal_tick"] / 20.0; stt = s["final"]["t"]
    rows.append({"tag": tag, "e_dmg1": dmg(e["final"], 1), "s_dmg1": dmg(s["final"], 1), "e_dmg0": dmg(e["final"], 0), "s_dmg0": dmg(s["final"], 0),
                 "e_t": et, "s_t": stt, "opp": battles[tag]["opponent_deck"].split(","), "team": battles[tag]["team_deck"].split(",")})
n = len(rows)
print(f"n={n} matches. Tower damage TAKEN, total over the match (HP):")
for side, lab in ((1, "icebow side 1"), (0, "opponent side 0")):
    e = [r[f"e_dmg{side}"] for r in rows]; s = [r[f"s_dmg{side}"] for r in rows]
    print(f"  {lab}: engine median {st.median(e):.0f} mean {st.mean(e):.0f} | sim median {st.median(s):.0f} mean {st.mean(s):.0f}")
print(f"  match length: engine median {st.median(r['e_t'] for r in rows):.0f} s, sim {st.median(r['s_t'] for r in rows):.0f} s")
# damage RATE (HP per second of match) to remove the length effect
for side, lab in ((1, "icebow side 1"), (0, "opponent side 0")):
    e = [r[f"e_dmg{side}"] / r["e_t"] for r in rows]; s = [r[f"s_dmg{side}"] / r["s_t"] for r in rows]
    print(f"  {lab} damage RATE HP/s: engine median {st.median(e):.1f} | sim median {st.median(s):.1f}")
# by opponent card: mean sim-minus-engine excess damage on side-1 towers, matches containing the card
exc = collections.defaultdict(list)
for r in rows:
    for c in set(r["opp"]):
        exc[c].append(r["s_dmg1"] - r["e_dmg1"])
base = st.mean(r["s_dmg1"] - r["e_dmg1"] for r in rows)
print(f"\nExcess damage on icebow towers, sim minus engine: mean {base:.0f} HP/match. By opponent card (n>=8):")
for c, v in sorted(exc.items(), key=lambda kv: -st.mean(kv[1])):
    if len(v) >= 8: print(f"   {c:22s} n={len(v):3d}  mean excess {st.mean(v):6.0f}  median {st.median(v):6.0f}")
