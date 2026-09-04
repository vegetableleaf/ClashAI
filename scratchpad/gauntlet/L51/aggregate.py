"""L51 aggregate: our sim's replay-drive grade vs RoyaleAPI and vs the real engine's per-tag results."""
import json, statistics as st
from pathlib import Path
L = Path("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L51/simbatch"); E = Path("C:/Users/benpe/ClashBot/scratchpad/gauntlet/ext/batch")
rows = []
for p in sorted(L.glob("replay_*.json")):
    s = json.loads(p.read_text()); e = json.loads((E / p.name).read_text())
    if "grade" not in s: print("ERR", s); continue
    eg = e["grade"]; ef = e["final"]
    e_rej = sum(eg["rejected_by_reason"].values()) if isinstance(eg["rejected_by_reason"], dict) else 0
    e_clean = (ef["crowns"] == [e["expected"]["crowns_by_side"]["0"], e["expected"]["crowns_by_side"]["1"]]) and e_rej == 0 and eg.get("invalid_placement", 0) == 0
    exp = s["expected"]["crowns_by_side"]; ew = 0 if ef["crowns"][0] > ef["crowns"][1] else (1 if ef["crowns"][1] > ef["crowns"][0] else None)
    rows.append(dict(tag=s["tag"], sim=s["final"]["crowns"], eng=ef["crowns"], real=exp,
                     sim_cm=s["grade"]["crowns_match"], sim_wm=s["grade"]["winner_match"],
                     eng_cm=ef["crowns"] == exp, eng_wm=ew == s["expected"]["winner"],
                     sim_eng_cm=s["final"]["crowns"] == ef["crowns"], sim_w=s["final"]["winner"], eng_w=ew, real_w=s["expected"]["winner"],
                     e_clean=e_clean, acc=s["grade"]["accepted"], rej=s["grade"]["rejected"], driven=s["grade"]["plays_driven"],
                     delays=s["grade"]["elixir_delays"]["n"], maxdelay=s["grade"]["elixir_delays"]["max_ticks"],
                     t=s["final"]["t"], term=s["final"]["terminated"], tm=s["grade"]["terminal_minus_last_play_s"],
                     early=s["grade"]["ended_before_last_play"], abil=s["grade"]["skipped_ability"],
                     e_tick=ef["terminal_tick"], e_reason=ef["termination_reason"], sim_secs=s["drive_seconds"],
                     reasons=[l.get("reason") for l in s["log"] if l.get("reason")]))
n = len(rows); pct = lambda k: "%d/%d = %.1f%%" % (sum(1 for r in rows if r[k]), n, 100 * sum(1 for r in rows if r[k]) / n)
print("n =", n)
print("SIM  crowns match RoyaleAPI:", pct("sim_cm"), "| winner:", pct("sim_wm"))
print("ENG  crowns match RoyaleAPI:", pct("eng_cm"), "| winner:", pct("eng_wm"), "(recomputed from the engine batch files)")
print("SIM crowns == ENGINE crowns:", pct("sim_eng_cm"))
both = sum(1 for r in rows if r["sim_cm"] and r["eng_cm"]); onlye = sum(1 for r in rows if r["eng_cm"] and not r["sim_cm"]); onlys = sum(1 for r in rows if r["sim_cm"] and not r["eng_cm"]); neither = n - both - onlye - onlys
print("crowns-match 2x2: both %d, engine-only %d, sim-only %d, neither %d" % (both, onlye, onlys, neither))
cl = [r for r in rows if r["e_clean"]]
print("ENGINE-CLEAN subset n=%d: sim crowns match RoyaleAPI %d (%.1f%%), winner %d (%.1f%%)" % (len(cl), sum(r["sim_cm"] for r in cl), 100*sum(r["sim_cm"] for r in cl)/len(cl), sum(r["sim_wm"] for r in cl), 100*sum(r["sim_wm"] for r in cl)/len(cl)))
# mismatch direction (sim vs real)
d = {"sim s0 win / real s1": 0, "sim s1 win / real s0": 0, "same winner diff crowns": 0, "sim draw": 0, "real draw": 0}
for r in rows:
    if r["sim_cm"]: continue
    if r["sim_w"] is None: d["sim draw"] += 1
    elif r["real_w"] is None: d["real draw"] += 1
    elif r["sim_w"] == r["real_w"]: d["same winner diff crowns"] += 1
    elif r["sim_w"] == 0: d["sim s0 win / real s1"] += 1
    else: d["sim s1 win / real s0"] += 1
print("SIM mismatch direction:", d)
print("SIM total crowns per match: sim %.2f, engine %.2f, real %.2f" % (st.mean(sum(r["sim"]) for r in rows), st.mean(sum(r["eng"]) for r in rows), st.mean(sum(r["real"]) for r in rows)))
print("SIM crowns by side mean: s0 %.2f s1 %.2f | real s0 %.2f s1 %.2f | engine s0 %.2f s1 %.2f" % (st.mean(r["sim"][0] for r in rows), st.mean(r["sim"][1] for r in rows), st.mean(r["real"][0] for r in rows), st.mean(r["real"][1] for r in rows), st.mean(r["eng"][0] for r in rows), st.mean(r["eng"][1] for r in rows)))
print("3-crown matches: sim %d, engine %d, real %d" % (sum(3 in r["sim"] for r in rows), sum(3 in r["eng"] for r in rows), sum(3 in r["real"] for r in rows)))
acc = sum(r["acc"] for r in rows); drv = sum(r["driven"] for r in rows); rej = sum(r["rej"] for r in rows)
print("plays driven %d, accepted %d (%.1f%%), rejected %d; matches with any rejection %d; ability plays skipped %d" % (drv, acc, 100*acc/drv, rej, sum(r["rej"]>0 for r in rows), sum(r["abil"] for r in rows)))
import collections
print("rejection reasons:", collections.Counter(x for r in rows for x in r["reasons"]))
print("elixir delays: matches with any %d, total %d, max ticks %d" % (sum(r["delays"]>0 for r in rows), sum(r["delays"] for r in rows), max(r["maxdelay"] for r in rows)))
print("terminated %d/%d; sim terminal t median %.1f s (engine %.1f s); ended before last real play: sim %d, engine %d; terminal-minus-last-play median sim %+.1f s" % (sum(r["term"] for r in rows), n, st.median(r["t"] for r in rows), st.median(r["e_tick"]/20 for r in rows), sum(r["early"] for r in rows), sum(1 for r in rows if r["e_tick"] < 0 or False), st.median(r["tm"] for r in rows)))
print("sim terminal t buckets: <180 %d, 180-180.9 %d, 181-300 %d, >=300 %d" % (sum(r["t"]<180 for r in rows), sum(180<=r["t"]<181 for r in rows), sum(181<=r["t"]<300 for r in rows), sum(r["t"]>=300 for r in rows)))
print("wall: total %.1f s, median %.2f s per match" % (sum(r["sim_secs"] for r in rows), st.median(r["sim_secs"] for r in rows)))
# plays accepted before the sim ended, share of the real timeline
print("share of real (non-ability) plays the sim was still running for: %.1f%%" % (100 * acc / drv))
Path("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L51/aggregate.json").write_text(json.dumps(rows, indent=0))
