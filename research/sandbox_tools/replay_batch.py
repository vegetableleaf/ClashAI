"""Batch-convert every usable RoyaleAPI replay through the real libg engine and grade the results.

Usage (sandbox venv, service already attested on --port):
    python research/sandbox_tools/replay_batch.py [--tags usable_replays.json] [--limit N] [--port 37031]
        [--determinism-every K]  (re-run every K-th tag once more and compare final state hashes)

Per tag: replay_drive.drive(...) in-process (one python, one TCP session per tag), result JSON to
scratchpad/gauntlet/ext/batch/replay_<tag>.json, one summary line appended to batch/summary.jsonl
(re-runnable: tags with an existing summary line are skipped unless --redo).  Ends with batch/aggregate.json.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import replay_drive  # noqa: E402

ROOT = HERE.parents[1]
EXT = ROOT / "scratchpad" / "gauntlet" / "ext"
OUT = EXT / "batch"


def summarize(tag: str, res: dict, seconds: float) -> dict:
    g, f = res["grade"], res["final"]
    return {"tag": tag, "ok": True, "seconds": round(seconds, 2),
            "plays_total": g["plays_total"], "plays_driven": g["plays_driven"], "accepted": g["accepted"],
            "rejected_by_reason": g["rejected_by_reason"], "invalid_placement": g["invalid_placement"],
            "elixir_delays_n": g["elixir_delays"]["n"], "elixir_delays_max": g["elixir_delays"]["max_ticks"],
            "skipped": len(g["skipped"]), "skipped_ability": sum("ability" in e["skipped"] for e in g["skipped"]),
            "deal_consistent": res["deal_inference"], "position_based": res["deal_probe"]["position_based"],
            "terminated": f["terminated"], "termination_reason": f["termination_reason"], "outcome": f["outcome"],
            "crowns": f["crowns"], "expected_crowns": [res["expected"]["crowns_by_side"][0], res["expected"]["crowns_by_side"][1]],
            "crowns_match": g["crowns_match"], "final_tick": f["tick"], "last_play_tick": res["expected"]["last_play_tick"],
            "terminal_vs_last_play": g["terminal_vs_last_play_ticks"], "state_hash": f["state_hash"],
            "reset_seconds": res["reset_seconds"], "drive_seconds": res["drive_seconds"]}


def median(values: list) -> float | None:
    values = sorted(v for v in values if v is not None)
    return values[len(values) // 2] if values else None


def aggregate(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["ok"]]
    bad = [r for r in rows if not r["ok"]]
    acc = sum(r["accepted"] for r in ok); driven = sum(r["plays_driven"] for r in ok)
    rej: Counter = Counter()
    for r in ok:
        rej.update(r["rejected_by_reason"])
    det = [r for r in ok if r.get("determinism") is not None]
    return {"tags": len(rows), "converted": len(ok), "failed": len(bad),
            "failed_by_error": dict(Counter(r["error_type"] for r in bad)),
            "plays_driven": driven, "accepted": acc, "accept_rate": round(acc / driven, 4) if driven else None,
            "rejected_by_reason": dict(rej), "invalid_placement": sum(r["invalid_placement"] for r in ok),
            "matches_with_rejections": sum(1 for r in ok if r["rejected_by_reason"]),
            "elixir_delays_plays": sum(r["elixir_delays_n"] for r in ok),
            "elixir_delays_max_ticks": max([r["elixir_delays_max"] for r in ok] or [0]),
            "ability_plays_skipped": sum(r["skipped_ability"] for r in ok),
            "position_based_all": all(r["position_based"] for r in ok) if ok else None,
            "terminated": sum(r["terminated"] for r in ok),
            "termination_reasons": dict(Counter(str(r["termination_reason"]) for r in ok)),
            "crowns_match": sum(bool(r["crowns_match"]) for r in ok),
            "crowns_match_rate": round(sum(bool(r["crowns_match"]) for r in ok) / len(ok), 4) if ok else None,
            "outcomes": dict(Counter(str(r["outcome"]) for r in ok)),
            "clean": sum(1 for r in ok if r["crowns_match"] and not r["rejected_by_reason"] and r["invalid_placement"] == 0),
            "terminal_vs_last_play": {"median": median([r["terminal_vs_last_play"] for r in ok]),
                                      "negative": sum(1 for r in ok if r["terminal_vs_last_play"] is not None and r["terminal_vs_last_play"] < 0)},
            "determinism": {"checked": len(det), "same": sum(r["determinism"] == "SAME" for r in det)},
            "seconds_total": round(sum(r["seconds"] for r in rows), 1),
            "seconds_per_match_median": median([r["seconds"] for r in ok])}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tags", default=str(EXT / "usable_replays.json"))
    ap.add_argument("--port", type=int, default=37031)
    ap.add_argument("--seed", type=int, default=424242)
    ap.add_argument("--level", type=int, default=11)
    ap.add_argument("--elixir-slack", type=int, default=40)
    ap.add_argument("--tail-cap", type=int, default=7200)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--determinism-every", type=int, default=10, help="re-run every K-th tag and compare hashes (0=off)")
    ap.add_argument("--redo", action="store_true")
    args = ap.parse_args()

    tags = json.loads(Path(args.tags).read_text(encoding="utf-8"))
    if args.limit:
        tags = tags[: args.limit]
    OUT.mkdir(parents=True, exist_ok=True)
    summary_path = OUT / "summary.jsonl"
    done: dict[str, dict] = {}
    if summary_path.exists() and not args.redo:
        for line in summary_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line); done[row["tag"]] = row
    print(f"batch: {len(tags)} tags, {len(done)} already done, port {args.port}", flush=True)

    t_batch = time.perf_counter()
    with summary_path.open("a", encoding="utf-8") as summary:
        for i, tag in enumerate(tags):
            if tag in done:
                continue
            t0 = time.perf_counter()
            try:
                res = replay_drive.drive(tag, port=args.port, seed=args.seed, level=args.level, elixir_slack=args.elixir_slack,
                                         tail_cap=args.tail_cap, run_label="batch", verbose=False)
                (OUT / f"replay_{tag}.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
                row = summarize(tag, res, time.perf_counter() - t0)
                if args.determinism_every and i % args.determinism_every == 0:
                    res2 = replay_drive.drive(tag, port=args.port, seed=args.seed, level=args.level, elixir_slack=args.elixir_slack,
                                              tail_cap=args.tail_cap, run_label="batch-rerun", verbose=False)
                    row["determinism"] = "SAME" if res2["final"]["state_hash"] == res["final"]["state_hash"] else "DIFFERENT"
                    row["rerun_state_hash"] = res2["final"]["state_hash"]
                msg = (f"acc {row['accepted']}/{row['plays_driven']} rej {row['rejected_by_reason']} crowns {row['crowns']} "
                       f"exp {row['expected_crowns']} match={row['crowns_match']} term={row['termination_reason']} "
                       f"tick {row['final_tick']} (last play {row['last_play_tick']}) {row['seconds']}s"
                       + (f" det={row['determinism']}" if "determinism" in row else ""))
            except KeyboardInterrupt:
                raise
            except BaseException as exc:  # SystemExit from drive() on inference failures, socket errors, KeyError on slugs
                row = {"tag": tag, "ok": False, "seconds": round(time.perf_counter() - t0, 2),
                       "error_type": type(exc).__name__, "error": str(exc)[:400], "trace": traceback.format_exc()[-1500:]}
                msg = f"FAILED {type(exc).__name__}: {str(exc)[:200]}"
            done[tag] = row
            summary.write(json.dumps(row, default=str) + "\n"); summary.flush()
            print(f"[{i + 1}/{len(tags)}] {tag} {msg}", flush=True)

    rows = [done[t] for t in tags if t in done]
    agg = aggregate(rows)
    agg["batch_wall_seconds"] = round(time.perf_counter() - t_batch, 1)
    (OUT / "aggregate.json").write_text(json.dumps(agg, indent=1), encoding="utf-8")
    print(json.dumps(agg, indent=1), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
