"""S0 liveness: drive one real replay through EACH slot via the caller's own path (replay_drive.drive),
compare crowns_match/accept_rate/hash to the L61 batch result for the same tag. Output: liveness.out"""
import json, sys, time
from pathlib import Path
ROOT = Path(r"C:\Users\benpe\ClashBot"); sys.path.insert(0, str(ROOT / "research" / "sandbox_tools"))
import replay_drive
tag = "000YLY0JCPGL"
ref = json.loads((ROOT / "scratchpad/gauntlet/ext/batch" / f"replay_{tag}.json").read_text(encoding="utf-8"))
def sig(r):
    f, g = r["final"], r["grade"]
    return {"terminal_tick": f["terminal_tick"], "outcome": f["outcome"], "crowns": f["crowns"], "state_hash": f["state_hash"],
            "opening_state_hash": r["opening_state_hash"], "plays_driven": g["plays_driven"], "accepted": g["accepted"],
            "invalid_placement": g["invalid_placement"]}
out = {"tag": tag, "ref": sig(ref)}
for port in (37031, 37032):
    t0 = time.time()
    try:
        r = replay_drive.drive(tag, port=port, seed=424242, level=11, elixir_slack=40, tail_cap=7200, run_label="s0live", verbose=False)
        out[port] = sig(r); out[port]["seconds"] = round(time.time() - t0, 2)
        out[port]["same_as_ref"] = (sig(r) == out["ref"])
    except Exception as e:
        out[port] = {"error": repr(e)[:300], "seconds": round(time.time() - t0, 2)}
(ROOT / "scratchpad/gauntlet/L63/s0/liveness.out").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
print(json.dumps({p: (v.get("same_as_ref"), v.get("seconds"), v.get("error")) for p, v in out.items() if p != "tag" and p != "ref"}))
