"""Run the live adapter over recorded live logs (offline PublicObserver replay, as live_gen.observe does).
For each log with hero presses: hazard + decision at every logged 'ability' event and at random non-press frames while the
hero (deployed >= 1 s ago, <= 30 s ago, no press since) is on the board. geometry_ok is not recoverable from the compact frames,
so the table reports the hazard gate alone (p >= P*) and the logged 'why' of the live rule.
"""
import glob, json, random, sys
sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader")
import ability_ice_wizard as A
from live_log_replay import replay

LOGS = sorted(glob.glob("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/live_play_2026100[56]_*.jsonl"))
rng = random.Random(0)
out = {"logs": [], "press_p": [], "other_p": []}
for f in LOGS:
    if len(out["logs"]) >= int(sys.argv[1] if len(sys.argv) > 1 else 3):
        break
    has_frames = has_ab = False
    for l in open(f, encoding="utf-8"):
        has_frames |= '"event": "frame"' in l; has_ab |= '"event": "ability"' in l
        if has_frames and has_ab: break
    if not (has_frames and has_ab):
        continue
    dep = None; last = None; rows = []; spent = True
    for r, pilot in replay(f):
        ev = r.get("event")
        if ev == "confirmed" and r["name"] == "IceWizard":
            dep, spent = int(r["tick"]), False
        if ev == "frame":
            last = r["_frame"]
            if dep is not None and not spent and 20 <= last["game_tick"] - dep <= 600 and rng.random() < 0.02:
                p = A.frosty_fella_press_probability(A.live_features(pilot, last, pilot.public.side, dep))
                ok, why = A.should_press_pro(pilot, last, pilot.public.side, dep, True)
                rows.append(("frame", last["game_tick"], round(p, 4), ok))
                out["other_p"].append(p)
        if ev == "ability" and dep is not None and last is not None:
            fr = dict(last); fr["game_tick"] = int(r["tick"])
            p = A.frosty_fella_press_probability(A.live_features(pilot, fr, pilot.public.side, dep))
            ok, why = A.should_press_pro(pilot, fr, pilot.public.side, dep, True)
            rows.append(("ABILITY", int(r["tick"]), round(p, 4), ok, "age=%.1fs" % ((int(r["tick"]) - dep) * 0.05), r["why"]))
            out["press_p"].append(p); spent = True
    out["logs"].append(f.split("/")[-1])
    print("==", f.split("/")[-1], "P*(V=%g)=%.4f" % (A.V_MIN, A.P_STAR))
    for x in rows[:40]:
        print("  ", *x)
import numpy as np
for k in ("press_p", "other_p"):
    v = np.array(out[k]); print(k, len(v), "mean %.4f median %.4f frac>=P* %.2f" % (v.mean(), np.median(v), (v >= A.P_STAR).mean()))
json.dump(out, open("live_log_check.json", "w"), indent=1)
