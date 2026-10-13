"""Offline suite runner. Native mode only contacts an already-running loopback sandbox."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from .adapters import ROOT
from .analysis import attribute, metrics, minimize, save_history, signature
from .core import json_dump
from .generators import catalog, chosen_cards, digest, random_scenario, unit_suites
from .runner import Worker, paired

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
    return p


def main(argv=None):
    a = parser().parse_args(argv)
    if (min(a.skirmishes, a.full_matches) < 0 or a.timeout <= 0
            or (a.minimize_limit is not None and a.minimize_limit < 0)
            or (a.unit_limit is not None and a.unit_limit < 0)):
        raise ValueError("counts must be nonnegative and timeout positive")
    a.out = a.out.resolve()
    a.out.mkdir(parents=True, exist_ok=False)
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
    json_dump(a.out / "recipe.json", provenance)
    rows, repros = [], []
    candidate = oracle = None
    try:
        candidate = Worker(a.candidate_python, a.candidate, a.out / "candidate", runtime=a.candidate_runtime, timeout=a.timeout)
        oracle = Worker(a.oracle_python, a.oracle, a.out / "oracle", runtime=a.oracle_runtime,
                        native_manifest=a.native_manifest, native_template=a.native_template,
                        native_port=a.native_port, timeout=a.timeout,
                        expected_version="0.1.33" if a.oracle == "wheel" else None)
        for i, s in enumerate(scenarios):
            key = f"{i:06d}"
            json_dump(a.out / "scenarios" / f"{key}-requested.json", s)
            row = None
            try:
                row, frozen = paired(candidate, oracle, s, profile, tolerances)
                json_dump(a.out / "scenarios" / f"{key}.json", frozen)
                if row["divergence"] and (a.minimize_limit is None or len(repros) < a.minimize_limit):
                    wanted = signature(row["divergence"])
                    def predicate(trial):
                        try:
                            result, _ = paired(candidate, oracle, trial, profile)
                            # Trials are disposable owned files; retained full traces are untouched.
                            for path in result["traces"].values():
                                Path(path).unlink()
                            for path in result["full_diagnostic_traces"].values():
                                if path:
                                    Path(path).unlink()
                            return result["divergence"] is not None and signature(result["divergence"]) == wanted
                        except (ValueError, RuntimeError):
                            return False
                    minimal, info = minimize(frozen, predicate)
                    verified, _ = paired(candidate, oracle, minimal, profile)
                    if not verified["divergence"] or signature(verified["divergence"]) != wanted:
                        raise RuntimeError("final minimized repro failed independent replay")
                    repro = dict(id=key, divergence=verified["divergence"], minimization=info,
                                 original_id=s["id"], traces=verified["traces"])
                    json_dump(a.out / "repros" / f"{key}.json", minimal)
                    json_dump(a.out / "repros" / f"{key}.evidence.json", repro)
                    repros.append(repro)
            except Exception as exc:
                if row is not None:
                    row["minimization_error"] = f"{type(exc).__name__}: {exc}"
                else:
                    row = dict(id=s["id"], suite=s["suite"], status="error", exact=False, completed=False,
                               result_match=False, error=f"{type(exc).__name__}: {exc}")
            rows.append(row)
            json_dump(a.out / "cases" / f"{key}.json", row)
            print(f"{i+1}/{len(scenarios)} {s['suite']} {row['status']} exact={row['exact']}", flush=True)
    finally:
        for worker in (candidate, oracle):
            if worker:
                worker.close()
    report = metrics(rows, provenance)
    report["minimized_repros"] = len(repros)
    report["unminimized_divergences"] = sum(bool(r.get("divergence")) for r in rows) - len(repros)
    json_dump(a.out / "attribution.json", attribute(repros))
    json_dump(a.out / "report.json", report)
    history_path = save_history(a.history, report)
    lines = [f"DIFFSIM {report['measurement']}", f"Requested={len(rows)} errors={report['errors']}",
             f"Profile: {provenance['comparison_scope']}", ""]
    for name, v in {**report["suites"], "short_horizon_exact": report["short_horizon_exact"],
                    "full_match_trace_exact": report["full_match_trace_exact"],
                    "full_match_result_match": report["full_match_result_match"]}.items():
        lines.append(f"{name}: {v['successes']}/{v['total']} = {v['percent']}%; Wilson 95% CI {v['ci95_percent']}")
    lines.extend(["", "Owner real-game goal proven: NO", f"Dated history: {history_path}"])
    (a.out / "SUMMARY.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if report["all_sanity_exact"] else 1


if __name__ == "__main__":
    sys.exit(main())
