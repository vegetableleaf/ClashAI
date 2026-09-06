"""L63e smoke: (1) icebow tag 000YLY0JCPGL with record_plays -> final state_hash must equal batch_v2's;
(2) first hogeq tag with --crawl hogeq on port 37032 -> loads, drives, grades."""
import json, sys, time
from pathlib import Path
ROOT = Path(r"C:/Users/benpe/ClashBot")
sys.path.insert(0, str(ROOT / "research/sandbox_tools"))
import replay_drive as rd
out = {}
t0 = time.perf_counter()
r = rd.drive("000YLY0JCPGL", port=37031, seed=424242, level=11, elixir_slack=40, tail_cap=7200, run_label="smoke", verbose=False,
             record_every=20, record_plays=True)
ref = json.loads((ROOT / "scratchpad/gauntlet/ext/batch_v2/replay_000YLY0JCPGL.json").read_text(encoding="utf-8"))
out["icebow"] = {"hash": r["final"]["state_hash"], "ref_hash": ref["final"]["state_hash"],
                 "same": r["final"]["state_hash"] == ref["final"]["state_hash"],
                 "play_frames": len(r.get("play_frames", [])), "ref_play_frames": len(ref.get("play_frames", [])),
                 "frames": len(r.get("frames", [])), "seconds": round(time.perf_counter() - t0, 2)}
rd.set_crawl("hogeq")
tags = json.loads((ROOT / "scratchpad/gauntlet/ext/corpus_v3/tags_hogeq.json").read_text())
t0 = time.perf_counter()
try:
    r = rd.drive(tags[0], port=37032, seed=424242, level=11, elixir_slack=40, tail_cap=7200, run_label="smoke", verbose=False,
                 record_every=20, record_plays=True)
    out["hogeq"] = {"tag": tags[0], "grade": r.get("grade"), "final": r.get("final"), "play_frames": len(r.get("play_frames", [])),
                    "seconds": round(time.perf_counter() - t0, 2)}
except BaseException as e:
    out["hogeq"] = {"tag": tags[0], "error": type(e).__name__, "msg": str(e)[:300]}
Path(ROOT / "scratchpad/gauntlet/L63/s0/smoke_v3.out").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
print(json.dumps(out, default=str)[:1500])
