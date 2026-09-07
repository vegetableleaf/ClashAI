"""Run the S3 gate on the states BOTH sides actually produced, and say how many that is.

The teacher cannot return a target for every benchmark state: some rows are ability plays, some tags fail
deal inference, and some episodes are already terminal at the branch tick. `s3_bench.score` refuses to
score a bench row with no prediction (correctly -- silently dropping states would let a teacher improve
its number by declining the hard ones), so the paired comparison has to be run on an explicit subset with
the student measured on exactly those same states.

This writes that subset as a bench file and reports its size, so the gate's denominator is visible rather
than implied. Dropped states are listed by reason where known.

usage: gate.py <bench.json> <teacher.jsonl> <student.jsonl> [--out-bench <path>]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bench", type=Path)
    ap.add_argument("teacher", type=Path)
    ap.add_argument("student", type=Path)
    ap.add_argument("--out-bench", type=Path, default=Path("scratchpad/gauntlet/L66/bench_covered.json"))
    a = ap.parse_args()

    bench = json.loads(a.bench.read_text(encoding="utf-8"))
    tea = [json.loads(l) for l in a.teacher.read_text(encoding="utf-8").splitlines() if l.strip()]
    stu = [json.loads(l) for l in a.student.read_text(encoding="utf-8").splitlines() if l.strip()]
    tk = {(r["tag"], r["tick"]) for r in tea}
    sk = {(r["tag"], r["tick"]) for r in stu}
    keep = [r for r in bench["rows"] if (r["tag"], r["tick"]) in tk and (r["tag"], r["tick"]) in sk]

    meta = dict(bench["meta"])
    meta.update({"n": len(keep), "covered_of": len(bench["rows"]),
                 "replays": len({r["tag"] for r in keep}),
                 "teacher_rows": len(tea), "student_rows": len(stu)})
    a.out_bench.parent.mkdir(parents=True, exist_ok=True)
    a.out_bench.write_text(json.dumps({"meta": meta, "rows": keep}), encoding="utf-8")
    print(json.dumps({"covered": len(keep), "of": len(bench["rows"]),
                      "coverage_pct": round(100 * len(keep) / max(1, len(bench["rows"])), 1),
                      "replays": meta["replays"], "out": str(a.out_bench)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
