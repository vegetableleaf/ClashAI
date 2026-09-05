"""L61: re-drive the 211 replays that converted in HANDOFF 5ay through the real engine WITH per-play recording
(full observation before every driven play of both sides + a compact frame every --record-every ticks), and check
that the final state hash equals the 5ay batch hash for every tag (recording must not perturb the engine).

    research/ext/cr-native-sandbox/.venv/Scripts/python.exe scratchpad/gauntlet/L61/replay_batch_rec.py --port 37031
Output: scratchpad/gauntlet/ext/batch_v2/replay_<tag>.json (NOT committed), summary.jsonl (resumable), aggregate.json.
"""
from __future__ import annotations
import argparse, json, sys, time, traceback
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import replay_drive_rec as replay_drive  # noqa: E402

ROOT = HERE.parents[2]
EXT = ROOT / "scratchpad" / "gauntlet" / "ext"
V1 = EXT / "batch"
OUT = EXT / "batch_v2"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=37031)
    ap.add_argument("--seed", type=int, default=424242)
    ap.add_argument("--level", type=int, default=11)
    ap.add_argument("--record-every", type=int, default=20)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tags", default="")
    ap.add_argument("--redo", action="store_true")
    args = ap.parse_args()

    v1 = {}
    for line in (V1 / "summary.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("ok"):
                v1[row["tag"]] = row
    tags = [t for t in json.loads((EXT / "usable_replays.json").read_text(encoding="utf-8")) if t in v1]
    if args.tags:
        tags = [t for t in args.tags.split(",") if t in v1]
    if args.limit:
        tags = tags[: args.limit]
    OUT.mkdir(parents=True, exist_ok=True)
    summary_path = OUT / "summary.jsonl"
    done: dict[str, dict] = {}
    if summary_path.exists() and not args.redo:
        for line in summary_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line); done[row["tag"]] = row
    print(f"batch_v2: {len(tags)} tags (converted in 5ay), {len(done)} already done, port {args.port}", flush=True)
    t_batch = time.perf_counter()
    with summary_path.open("a", encoding="utf-8") as summary:
        for i, tag in enumerate(tags):
            if tag in done:
                continue
            t0 = time.perf_counter()
            try:
                res = replay_drive.drive(tag, port=args.port, seed=args.seed, level=args.level, elixir_slack=40,
                                         tail_cap=7200, run_label="batch_v2", verbose=False,
                                         record_every=args.record_every, record_full=False, record_plays=True)
                (OUT / f"replay_{tag}.json").write_text(json.dumps(res, default=str), encoding="utf-8")
                g, f = res["grade"], res["final"]
                row = {"tag": tag, "ok": True, "seconds": round(time.perf_counter() - t0, 2),
                       "reset_seconds": res["reset_seconds"], "drive_seconds": res["drive_seconds"],
                       "plays_driven": g["plays_driven"], "accepted": g["accepted"], "rejected_by_reason": g["rejected_by_reason"],
                       "crowns": f["crowns"], "crowns_match": g["crowns_match"], "final_tick": f["tick"],
                       "state_hash": f["state_hash"], "v1_state_hash": v1[tag]["state_hash"],
                       "hash_same_as_v1": f["state_hash"] == v1[tag]["state_hash"],
                       "accepted_same_as_v1": g["accepted"] == v1[tag]["accepted"],
                       "n_play_frames": len(res.get("play_frames", [])), "n_frames": len(res.get("frames", []))}
                msg = (f"acc {row['accepted']}/{row['plays_driven']} crowns {row['crowns']} match={row['crowns_match']} "
                       f"tick {row['final_tick']} hash_same_v1={row['hash_same_as_v1']} frames {row['n_play_frames']}+{row['n_frames']} "
                       f"{row['seconds']}s (v1 {v1[tag]['seconds']}s)")
            except KeyboardInterrupt:
                raise
            except BaseException as exc:
                row = {"tag": tag, "ok": False, "seconds": round(time.perf_counter() - t0, 2),
                       "error_type": type(exc).__name__, "error": str(exc)[:400], "trace": traceback.format_exc()[-1500:]}
                msg = f"FAILED {type(exc).__name__}: {str(exc)[:200]}"
            done[tag] = row
            summary.write(json.dumps(row, default=str) + "\n"); summary.flush()
            print(f"[{i + 1}/{len(tags)}] {tag} {msg}", flush=True)
    rows = [done[t] for t in tags if t in done]
    ok = [r for r in rows if r["ok"]]
    secs = sorted(r["seconds"] for r in ok)
    agg = {"tags": len(rows), "ok": len(ok), "failed": len(rows) - len(ok),
           "failed_by_error": dict(Counter(r["error_type"] for r in rows if not r["ok"])),
           "hash_same_as_v1": sum(r["hash_same_as_v1"] for r in ok), "accepted_same_as_v1": sum(r["accepted_same_as_v1"] for r in ok),
           "hash_differs": [r["tag"] for r in ok if not r["hash_same_as_v1"]],
           "accepted": sum(r["accepted"] for r in ok), "plays_driven": sum(r["plays_driven"] for r in ok),
           "crowns_match": sum(bool(r["crowns_match"]) for r in ok),
           "play_frames": sum(r["n_play_frames"] for r in ok), "drift_frames": sum(r["n_frames"] for r in ok),
           "seconds_per_match": {"median": secs[len(secs) // 2] if secs else None, "min": secs[0] if secs else None,
                                 "max": secs[-1] if secs else None, "mean": round(sum(secs) / len(secs), 2) if secs else None},
           "v1_seconds_per_match_median": sorted(v1[t]["seconds"] for t in tags)[len(tags) // 2] if tags else None,
           "seconds_total": round(sum(r["seconds"] for r in rows), 1),
           "batch_wall_seconds": round(time.perf_counter() - t_batch, 1)}
    (OUT / "aggregate.json").write_text(json.dumps(agg, indent=1), encoding="utf-8")
    print(json.dumps(agg, indent=1), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
