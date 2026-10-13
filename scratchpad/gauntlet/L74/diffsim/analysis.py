"""Delta debugging, mechanic grouping, binomial intervals and progress history."""
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import re

from .core import json_dump


def signature(divergence):
    d = divergence.json() if hasattr(divergence, "json") else divergence
    field = re.sub(r"(?:units|towers)\.[^.]+\.", "entity.", d["field"])
    field = re.sub(r"\[\d+\]", "[]", field)
    return tuple(sorted(d["cards"])), field, d["event_type"]


def minimize(scenario, predicate):
    """Return a 1-minimal repro, not a claim of global combinatorial optimality.

    Predicate must retain the original mechanic signature and reject invalid
    candidates. Tests use fresh engines every call. Frozen plays only: a policy
    must first be materialized so deletions never regenerate different actions.
    """
    s = deepcopy(scenario)
    if s.get("policy"):
        raise ValueError("materialize policy before minimizing")
    if not predicate(s):
        raise ValueError("input does not reproduce divergence")
    calls = 1

    def accepts(candidate):
        nonlocal calls
        calls += 1
        return predicate(candidate)

    changed = True
    while changed:
        changed = False
        for field in ("plays", "units"):
            n = 2
            while s.get(field):
                items = s[field]
                width = math.ceil(len(items) / n)
                reduced = False
                for start in range(0, len(items), width):
                    candidate = deepcopy(s)
                    candidate[field] = items[:start] + items[start + width:]
                    if accepts(candidate):
                        s, reduced, changed = candidate, True, True
                        n = max(2, n - 1)
                        break
                if not reduced:
                    if n >= len(items):
                        break
                    n = min(len(items), n * 2)
        # Prefix divergence is monotone for frozen actions; binary-search horizon.
        lo, hi = 0, s["duration_ticks"]
        while lo < hi:
            mid = (lo + hi) // 2
            candidate = deepcopy(s)
            candidate["duration_ticks"] = mid
            candidate["plays"] = [p for p in s["plays"] if p["tick"] <= mid]
            if accepts(candidate):
                hi = mid
            else:
                lo = mid + 1
        if lo < s["duration_ticks"]:
            s["duration_ticks"] = lo
            s["plays"] = [p for p in s["plays"] if p["tick"] <= lo]
            changed = True
    # Recheck the final artifact, not just a candidate preceding its last edit.
    if not accepts(s):
        raise RuntimeError("nondeterministic minimization predicate")
    return s, {"predicate_calls": calls, "minimality": "1-minimal plays/initial units; shortest prefix"}


def attribute(repros):
    groups = defaultdict(list)
    for repro in repros:
        groups[signature(repro["divergence"])].append(repro["id"])
    return [dict(cards=list(k[0]), field=k[1], event_type=k[2], frequency=len(ids), repros=sorted(ids))
            for k, ids in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))]


def proportion(successes, total):
    if not 0 <= successes <= total:
        raise ValueError("invalid binomial counts")
    if not total:
        return dict(successes=0, total=0, percent=None, ci95_percent=None)
    z = 1.959963984540054
    p = successes / total
    denom = 1 + z*z/total
    center = (p + z*z/(2*total)) / denom
    half = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / denom
    return dict(successes=successes, total=total, percent=100*p,
                ci95_percent=[100*max(0, center-half), 100*min(1, center+half)])


def metrics(rows, provenance):
    suites = {}
    for suite in sorted({r["suite"] for r in rows}):
        subset = [r for r in rows if r["suite"] == suite]
        suites[suite] = proportion(sum(r.get("exact") is True for r in subset), len(subset))
    short = [r for r in rows if r["suite"] == "skirmish"]
    full = [r for r in rows if r["suite"] == "full"]
    native = provenance.get("oracle") == "native"
    full_exact = sum(r.get("exact") is True and r.get("completed") is True for r in full)
    results = sum(r.get("result_match") is True and r.get("completed") is True for r in full)
    errors = sum(r.get("status") == "error" for r in rows)
    fake = any(str(provenance.get(k, "")).startswith("fake") for k in ("oracle", "candidate"))
    return dict(schema_version=1, created_utc=datetime.now(timezone.utc).isoformat(),
                provenance=provenance, measurement="synthetic_fake" if fake else "native_unqualified" if native else "stand_in_only",
                ci_method="Wilson 95%; per-scenario Bernoulli, descriptive for correlated unit suites",
                requested=len(rows), errors=errors, suites=suites,
                short_horizon_exact=proportion(sum(r.get("exact") is True for r in short), len(short)),
                full_match_trace_exact=proportion(full_exact, len(full)),
                full_match_result_match=proportion(results, len(full)),
                # Never promote an unvalidated native adapter to the owner's proof.
                owner_goal_proven=False,
                observed_threshold_met=(native and len(full) >= 1000 and full_exact/len(full) >= .99
                                        and results == len(full) and errors == 0),
                all_sanity_exact=(bool(rows) and not errors and all(r.get("exact") is True for r in rows)
                                  and all(r.get("completed") and r.get("result_match") for r in full)))


def save_history(directory, report):
    directory.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, sort_keys=True, allow_nan=False).encode()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S.%fZ")
    path = directory / f"{stamp}-{hashlib.sha256(payload).hexdigest()[:12]}.json"
    # Unique immutable dated report; never overwrite an earlier run.
    with path.open("x", encoding="utf-8") as f:
        f.write(payload.decode() + "\n")
    return path
