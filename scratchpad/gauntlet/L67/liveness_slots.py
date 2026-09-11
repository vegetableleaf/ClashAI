"""L67m liveness, reference-free: the L63 script compared against ext/batch/replay_000YLY0JCPGL.json, which no longer
exists. Here one known-drivable hogeq replay (first non-evo-E-barb tag of the new HF hogeq crawl, 122 plays) is driven through EACH slot with the same
seed; both must finish and agree on the final state hash, crowns and accepted plays. Output: liveness_slots.out"""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research" / "sandbox_tools"))
import replay_drive
replay_drive.set_crawl(str(ROOT / "scratchpad/gauntlet/ext/crawl_hf_hogeq"))
tag = "edf93c4519044b89944be9341d9f45ce"
def sig(r):
    f, g = r["final"], r["grade"]
    return {"terminal_tick": f["terminal_tick"], "outcome": f["outcome"], "crowns": f["crowns"], "state_hash": f["state_hash"],
            "plays_driven": g["plays_driven"], "accepted": g["accepted"], "invalid_placement": g["invalid_placement"]}
out = {"tag": tag}
for port in (37031, 37032):
    t0 = time.time()
    try:
        r = replay_drive.drive(tag, port=port, seed=424242, level=11, elixir_slack=40, tail_cap=7200, run_label="l67live", verbose=False)
        out[port] = sig(r); out[port]["seconds"] = round(time.time() - t0, 2)
    except Exception as e:
        out[port] = {"error": repr(e)[:300], "seconds": round(time.time() - t0, 2)}
a, b = out[37031], out[37032]
out["slots_agree"] = ("error" not in a and "error" not in b and a | {"seconds": 0} == b | {"seconds": 0})
(Path(__file__).parent / "liveness_slots.out").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
print(json.dumps({"slots_agree": out["slots_agree"], "a": (a.get("accepted"), a.get("seconds"), a.get("error")),
                  "b": (b.get("accepted"), b.get("seconds"), b.get("error"))}))
