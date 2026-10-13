"""Offline suite runner. Native mode only contacts an already-running loopback sandbox."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

from .adapters import ROOT
from .analysis import attribute, metrics, save_history
from .core import json_dump
from .generators import catalog, chosen_cards, digest, random_scenario, unit_suites
from .pool import atomic_json, read_json, run_cases
from .resources import check_workers, cpu_lock

HERE = Path(__file__).resolve().parent


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--oracle", choices=["wheel", "native", "fake", "fake-bug"], default="wheel")
    p.add_argument("--candidate", choices=["fork", "wheel", "fake", "fake-bug"], default="fork")
    p.add_argument("--candidate-python", default=sys.executable)
    p.add_argument("--oracle-python", default=sys.executable)
    p.add_argument("--candidate-runtime")
    p.add_argument("--oracle-runtime")
    p.add_argument("--native-manifest")
    p.add_argument("--native-template")
    p.add_argument("--native-port", type=int, default=37031)
    p.add_argument("--seed", type=int, default=74)
    p.add_argument("--cards", help="comma-separated explicit card set; otherwise icebow + census top 60")
    p.add_argument("--census", type=Path, default=ROOT / "scratchpad/gauntlet/L74/livecal/census_lad.json")
    p.add_argument("--apk-snapshot", type=Path)
    p.add_argument("--units", choices=["all", "none"], default="all")
    p.add_argument("--unit-limit", type=int, help="explicit debug subset, recorded in recipe")
    p.add_argument("--skirmishes", type=int, default=100)
    p.add_argument("--full-matches", type=int, default=1000)
    p.add_argument("--repro", type=Path, help="replay a frozen scenario JSON instead of generating suites")
    p.add_argument("--tolerances", type=Path, help="JSON path-glob -> absolute tolerance; exact metrics stay exact")
    p.add_argument("--out", type=Path, default=HERE / "out" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ"))
    p.add_argument("--history", type=Path, default=HERE / "history")
    p.add_argument("--minimize-limit", type=int, help="optional first N divergences; default minimizes all failures")
    p.add_argument("--timeout", type=int, default=600, help="seconds per scenario per owned worker")
    p.add_argument("--workers", type=int, default=1, help="isolated engine pairs (2 processes each); capped at (CPU quota-2)/2")
    p.add_argument("--resume", action="store_true", help="skip completed cases in the matching output directory")
    return p


def main(argv=None):
    a = parser().parse_args(argv)
    if (min(a.skirmishes, a.full_matches) < 0 or a.timeout <= 0
            or (a.minimize_limit is not None and a.minimize_limit < 0)
            or (a.unit_limit is not None and a.unit_limit < 0)):
        raise ValueError("counts must be nonnegative and timeout positive")
    a.out = a.out.resolve()
    tolerances = json.loads(a.tolerances.read_text()) if a.tolerances else {}
    if any(type(v) not in (int, float) or not 0 <= v < float("inf") for v in tolerances.values()):
        raise ValueError("invalid tolerances")
    cards, sources = catalog(a.apk_snapshot)
    if a.repro:
        scenarios = [json.loads(a.repro.read_text(encoding="utf-8"))]
        sources[str(a.repro)] = digest(a.repro)
        names = []
    else:
        names = chosen_cards(cards, names=a.cards.split(",") if a.cards else None, census=a.census)
        if not a.cards:
            sources[str(a.census)] = digest(a.census)
        scenarios = []
        if a.units == "all":
            for i, s in enumerate(unit_suites(a.seed, names, cards)):
                if a.unit_limit is not None and i >= a.unit_limit:
                    break
                scenarios.append(s)
        scenarios.extend(random_scenario(a.seed + 100000 + i, cards, names) for i in range(a.skirmishes))
        scenarios.extend(random_scenario(a.seed + 200000 + i, cards, names, full=True) for i in range(a.full_matches))
    if not scenarios:
        raise ValueError("empty requested cohort")
    profile = "common" if a.oracle == "native" else "public"
    cohort_hash = hashlib.sha256(json.dumps(scenarios, sort_keys=True).encode()).hexdigest()
    provenance = dict(oracle=a.oracle, candidate=a.candidate, profile=profile, tolerances=tolerances,
                      seed=a.seed, cards=names, sources=sources, cohort_sha256=cohort_hash,
                      requested_full_matches=a.full_matches, unit_limit=a.unit_limit,
                      minimization_limit=a.minimize_limit,
                      comparison_scope=("synthetic FakeEngine state only" if "fake" in a.oracle or "fake" in a.candidate else
                                        "narrow common public fields; VM UNTESTED" if profile == "common"
                                        else "all exposed fork public state; quantized timers/elixir"))
    check_workers(a.workers)
    if a.oracle == "native" and a.native_port + a.workers - 1 > 65535:
        raise ValueError("native worker ports exceed 65535")
    # Scheduling is deliberately absent from the measurement recipe/history.
    # Bind engine selection separately so a resumed directory cannot mix runtimes.
    execution = {name: getattr(a, name) for name in (
        "candidate_python", "oracle_python", "candidate_runtime", "oracle_runtime",
        "native_manifest", "native_template", "native_port")}
    execution["runtime_environment"] = os.environ.get("ROYALE_RUNTIME")
    execution["native_inputs"] = {name: digest(getattr(a, name)) for name in
                                  ("native_manifest", "native_template") if getattr(a, name)}
    with cpu_lock():
        exists = a.out.exists()
        if exists and not a.resume:
            raise FileExistsError(a.out)
        if exists and a.resume:
            if read_json(a.out / "recipe.json") != provenance:
                raise ValueError("resume recipe differs from requested cohort/options")
            if (a.out / ".execution.json").exists() and read_json(a.out / ".execution.json") != execution:
                raise ValueError("resume engine configuration differs")
        a.out.mkdir(parents=True, exist_ok=True)
        atomic_json(a.out / "recipe.json", provenance)
        atomic_json(a.out / ".execution.json", execution)
        rows, repros = run_cases(a, scenarios, profile, tolerances)
        return write_report(a, rows, repros, provenance)


def write_report(a, rows, repros, provenance):
    report = metrics(rows, provenance)
    report["minimized_repros"] = len(repros)
    report["unminimized_divergences"] = sum(bool(r.get("divergence")) for r in rows) - len(repros)
    json_dump(a.out / "attribution.json", attribute(repros))
    # Persist the reporting clock before appending history. If killed just after
    # that append, resume finds its exact content hash rather than duplicating it.
    finalizing = a.out / ".finalizing.json"
    old_path = finalizing if finalizing.exists() else a.out / "report.json"
    if a.resume and old_path.exists():
        old_report = read_json(old_path)
        old_body = {k: v for k, v in old_report.items() if k != "created_utc"}
        if old_body == {k: v for k, v in report.items() if k != "created_utc"}:
            report = old_report
    atomic_json(finalizing, report)
    previous = a.out / ".history.json"
    history_path = None
    if a.resume and previous.exists():
        receipt = read_json(previous)
        if Path(receipt["path"]).is_file() and read_json(Path(receipt["path"])) == report:
            history_path = Path(receipt["path"])
    if a.resume and history_path is None:
        digest = hashlib.sha256(json.dumps(report, sort_keys=True, allow_nan=False).encode()).hexdigest()[:12]
        history_path = next((p for p in sorted(a.history.glob(f"*-{digest}.json"))
                             if read_json(p) == report), None)
    if history_path is None:
        history_path = save_history(a.history, report)
    atomic_json(a.out / "report.json", report)
    atomic_json(previous, {"path": str(history_path)})
    lines = [f"DIFFSIM {report['measurement']}", f"Requested={len(rows)} errors={report['errors']}",
             f"Profile: {provenance['comparison_scope']}", ""]
    for name, v in {**report["suites"], "short_horizon_exact": report["short_horizon_exact"],
                    "full_match_trace_exact": report["full_match_trace_exact"],
                    "full_match_result_match": report["full_match_result_match"]}.items():
        lines.append(f"{name}: {v['successes']}/{v['total']} = {v['percent']}%; Wilson 95% CI {v['ci95_percent']}")
    lines.extend(["", "Owner real-game goal proven: NO", f"Dated history: {history_path}"])
    (a.out / "SUMMARY.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    finalizing.unlink()
    print("\n".join(lines))
    return 0 if report["all_sanity_exact"] else 1


if __name__ == "__main__":
    sys.exit(main())
