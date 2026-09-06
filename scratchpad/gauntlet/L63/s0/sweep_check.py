"""Independent re-run: from_engine over every frame + play_frame of all batch_v2 recordings (side 0 and side 1)."""
import json, glob, sys, time
sys.path.insert(0, r"C:\Users\benpe\ClashBot")
from pipeline import obs_contract as oc
deck = oc.load_deck("icebow")
files = sorted(glob.glob(r"C:\Users\benpe\ClashBot\scratchpad\gauntlet\ext\batch_v2\replay_*.json"))
n = bad = 0; unm = set(); units_tot = 0; t0 = time.time(); errs = 0
for fp in files:
    r = json.load(open(fp, encoding="utf-8"))
    for fr in (r.get("frames") or []) + (r.get("play_frames") or []):
        for side in (0, 1):
            try:
                bs = oc.from_engine(fr, side, deck, unmapped=unm)
            except Exception as e:
                errs += 1; 
                if errs <= 3: print("ERR", fp[-20:], repr(e)[:160])
                continue
            n += 1; units_tot += len(bs.units)
            for u in bs.units + bs.spells:
                if not (0 <= u.x <= 1 and 0 <= u.y <= 1): bad += 1
print(json.dumps({"files": len(files), "frames_x_sides": n, "errors": errs, "unmapped": sorted(unm), "out_of_range": bad,
                  "units_per_frame": round(units_tot / max(n, 1), 2), "seconds": round(time.time() - t0, 1)}))
