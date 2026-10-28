"""HF IL_Replay re-driven on crforge (P2-RD1's drive(), unchanged) -> R_exchange traces in build.py's npz format.

    run.sh-style env (ROYALE_ENGINE=crforge, CRFORGE_LIB, ...; see redrive/run.sh), then
    python hf_traces.py DATA OUT.npz [--shards N] [--chunk 250] [--workers 40] [--tiers A]
Drives the first N round-robin shards (redrive.jobs order) and keeps tier-A matches (driven to the end, crowns == HF).
Observer = side 0 (team). Both sides' elixir is the engine's exact value (no public-counter estimate), bodies carry the
engine entity_id (exact identity), recorded every 10 ticks (drive()'s record_every). Label y = HF crowns (team > opp);
date = str(int(tag[:8], 16) % 5): HF payloads carry no date, SPLIT_HF.json holds out '4'. Meta also keeps the HF
aggregate_stats (committed elixir and leak per side) to validate the trace's committed / leak streams. Nothing is written into the re-drive's output.
"""
import json
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path[:0] = [str(ROOT), str(HERE), str(ROOT / "scratchpad/gauntlet/L74/plan1026/redrive")]
from pipeline import r_exchange as RX  # noqa: E402
import build  # noqa: E402

SAMPLE = build.SAMPLE


def frames_of(rec):
    out = []
    for f in rec["frames"]:
        E = [[e[0], e[1], e[2], e[7], e[4], e[5], e[6], e[8]] for e in f["entities"] if e[7] != -1]
        T = [[t[0], t[3], t[4], -1, t[5], t[6], -1, f"T{t[0]}_{t[3]}_{t[4]}"] for t in f["towers"]]
        if not T:
            continue
        ents = [(e[0], e[3], e[4], e[5], str(e[7])) for e in E] + [(t[0], -1, t[4], t[5], t[7]) for t in T]
        out.append({"tick": f["tick"], "side": 0, "elixir": f["elixir"][0], "opp_elixir": f["elixir"][1],
                    "ents": ents, "threat": build.threat(E, 0)})
    return out


def shard(job):
    import pyarrow.parquet as pq
    import redrive as RD
    RD.env_and_catalog()
    agg = {r["replay_tag"]: json.loads(r["payload_json"]).get("replay", {}).get("aggregate_stats", {})
           for r in pq.read_table(job["rp"], columns=["replay_tag", "payload_json"])
           .slice(job["lo"], job["hi"] - job["lo"]).to_pylist()}
    res = []
    for src in RD.hf_sources(Path(job["rp"]), Path(job["ap"]), job["lo"], job["hi"], RD.env_and_catalog()[1]):
        try:
            g, rec = RD.drive(src, 0)
        except Exception as e:  # noqa: BLE001 -- one bad replay is reported, not fatal
            res.append({"file": src["tag"], "skip": "drive_error " + type(e).__name__})
            continue
        if g["tier"] not in TIERS or rec is None:
            res.append({"file": src["tag"], "skip": "tier_" + g["tier"]})
            continue
        fr = frames_of(rec)
        if len(fr) < 50:
            res.append({"file": src["tag"], "skip": "few_frames"})
            continue
        cr = src["expected"]["crowns_by_side"]
        y = 1 if cr["0"] > cr["1"] else 0 if cr["0"] < cr["1"] else {"victory": 1, "defeat": 0}.get(str(src["result"]), -1)   # hf200 run used win/loss keys: 149 crown ties dropped
        ticks, L = RX.running_losses(fr, VALUES)
        _, C, LT = RX.public_streams(fr)
        keep = np.r_[np.nonzero(np.diff(ticks // SAMPLE, prepend=-1))[0], len(ticks) - 1]
        res.append({"file": src["tag"], "skip": None, "date": str(int(src["tag"][:8], 16) % 5),
                    "hf_committed": [agg.get(src["tag"], {}).get(k, {}).get("total", [None, None])[1] for k in ("team", "opponent")],
                    "hf_leaked": [agg.get(src["tag"], {}).get(k, {}).get("leaked") for k in ("team", "opponent")], "y": y, "label_src": "hf",
                    "crowns": (cr["0"], cr["1"]), "end_tick": int(ticks[-1]), "trace": "hf", "n_obs": len(fr),
                    "body_known_frac": float(np.mean([e[1] in VALUES for f in fr for e in f["ents"] if e[1] != -1]
                                                     or [1.0])),
                    "ticks": ticks[keep], "L": L[keep].astype(np.float32), "C": C[keep].astype(np.float32),
                    "LT": LT[keep].astype(np.float32)})
    return res


def init(tiers):
    global VALUES, TIERS
    VALUES, TIERS = build.load_values(), tiers


def main():
    a = sys.argv[1:]
    opt = lambda k, d: type(d)(a[a.index(k) + 1]) if k in a else d
    import redrive as RD
    js = RD.jobs(Path(a[0]), Path("/tmp/rx_unused"), opt("--chunk", 250), 0, 0)[:opt("--shards", 40)]
    with mp.Pool(opt("--workers", 40), initializer=init, initargs=(set(opt("--tiers", "A").split(",")),)) as pool:
        res = [r for rs in pool.imap_unordered(shard, js) for r in rs]
    ok = [r for r in res if r["skip"] is None]
    np.savez_compressed(a[1], meta=np.array(json.dumps([{k: v for k, v in r.items() if k not in ("ticks", "L", "C", "LT")}
                                                        for r in ok])),
                        skipped=np.array(json.dumps([r for r in res if r["skip"]])),
                        **{f"t_{i}": r["ticks"] for i, r in enumerate(ok)}, **{f"L_{i}": r["L"] for i, r in enumerate(ok)},
                        **{f"C_{i}": r["C"] for i, r in enumerate(ok)}, **{f"LT_{i}": r["LT"] for i, r in enumerate(ok)})
    from collections import Counter
    print(len(res), "replays;", len(ok), "kept;", Counter(r["skip"] for r in res if r["skip"]),
          Counter(r["y"] for r in ok), "dates", min((r["date"] for r in ok), default=None),
          max((r["date"] for r in ok), default=None))


if __name__ == "__main__":
    main()
