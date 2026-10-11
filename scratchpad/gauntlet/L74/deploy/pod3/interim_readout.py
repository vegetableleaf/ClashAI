"""READ-ONLY interim D1/D4 fixed-fork readout on pod 1, using the stage's own code (variant_search.estimate / label).
python interim_readout.py   (run with PYTHONDONTWRITEBYTECODE=1; reads /workspace/results/wk/S9XL2b/fixed, writes nothing there)"""
import json, sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, "/workspace/wk_xl2/scratchpad/gauntlet/L74/weekend")
import variant_search as V

R = Path("/workspace/results/wk/S9XL2b/fixed")


def load(dest, bounds):
    """-> (rows, complete?, reached, expected, note)"""
    mom = json.loads((dest / "moments.json").read_text())
    seeds = V.moment_seeds(mom, bounds)
    expected = sum(len(v) for v in mom.values())
    p = dest / "forks" / "matches.jsonl"
    if not p.exists():
        return [], False, 0, expected, "no matches.jsonl"
    try:
        rows = V.read_matches(dest / "forks", bounds, seeds=seeds)
        reached = sum(r.get("mech", {}).get("moments", [0, 0])[1] for r in rows)
        return rows, reached == expected, reached, expected, "validated by read_matches (seed set, fork-to-end, A replay)"
    except Exception as e:  # in progress: take the raw rows
        rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
        reached = sum(r.get("mech", {}).get("moments", [0, 0])[1] for r in rows)
        return rows, False, reached, expected, f"read_matches refused: {str(e)[:90]}"


def f(e):
    if e["mean"] is None:
        return "n/a"
    return f"{100 * e['mean']:+.2f} pp [{100 * (e['mean'] - e['half_width']):+.2f}, {100 * (e['mean'] + e['half_width']):+.2f}]"


out = ["INTERIM D1/D4 fixed-fork readout (pod 1, S9XL2b/fixed, read-only; stage code: variant_search.estimate/label, CR1 CIs clustered by match).",
       "stage label rule (variant_search.label, on the DO - own estimate): 'do' if mean - half_width > 0; 'alt' if mean + half_width < 0; else 'none' (also 'none' if any skipped match or A-replay mismatch).",
       "DO = D1 best defender now / D4 air-capable card; HOLD = D1 wait / D4 ground-only card; own = the model's own decision (arm A). Win = win 1 / else 0 at match end."]
for dr in ("D1", "D4"):
    allrows, parts = [], []
    for census in ("evo", "lad"):
        dest = R / census / dr / "fixed"
        if not dest.exists():
            parts.append(f"{census}: no directory"); continue
        rows, ok, reached, expected, note = load(dest, V.SEEDS["fixed"][census])
        allrows += rows
        e = V.estimate(rows, dr, None, "own") if rows else None
        parts.append(f"{census}: {len(rows)} matches, moments reached/expected {reached}/{expected}, complete={ok} ({note})")
        if e:
            out.append(f"{dr} {census}: n {e['n']} moments in {e['matches']} matches | DO - own {f(e)}")
    complete = all("complete=True" in p for p in parts) and len(parts) == 2
    own, hold = V.estimate(allrows, dr, None, "own"), V.estimate(allrows, dr, None, "hold")
    tag = "COMPLETE" if complete else "PARTIAL"
    out.append(f"{dr} {tag} pooled evo+lad | " + " ; ".join(parts))
    out.append(f"{dr} {tag} pooled | n {own['n']} moments in {own['matches']} matches | win DO - HOLD {f(hold)} | win DO - own {f(own)} | skipped_matches {own['skipped_matches']} no_arm {own['no_arm']} A-replay checks {own['replay_checks']} bad {own['bad_replay']}")
    out.append(f"{dr} {tag} label (stage rule, DO - own): {V.label(own)} ; DO - HOLD CI {'excludes' if (hold['mean'] is not None and (hold['mean'] - hold['half_width'] > 0 or hold['mean'] + hold['half_width'] < 0)) else 'includes'} 0")
print("\n".join(out))
