"""L74 factorial analysis (2^(5-1), E = ABCD, 16 runs + references u250 / Mark CXXXVIII on the same 960 paired games).

    python analyze.py [ROOT]      ROOT default C:/Users/benpe/pod_backup_weekend/pod1017_factorial (pull.sh's copies)
    python analyze.py --selftest  synthetic data with planted effects (recovered exactly / within noise), Lenth by hand

Reads ROOT/<run>/eval/<run>_{741200,742000}/D3/matches.jsonl (live_eval_pod.sh layout). Prints:
  1. per run: signs, seed, wins / 960, win % +- its binomial SE, the habit metrics, and paired deltas vs u250 and vs
     Mark CXXXVIII (heroiw/validate.paired_drift: pairs by (census, seed), checks opponent deck / side / policy match);
  2. for win % and each habit metric, every MAIN effect (mean of its 8 '+' runs minus its 8 '-' runs) and all 10 TWO-WAY
     interactions (same contrast on the product column; aliased with the complementary three-way, I = ABCDE), each with
     two 95% CIs: (a) the per-run eval SE propagated through the contrast, SE = sqrt(sum var_i) / 8 -- eval-game noise
     only, runs taken as independent (the shared paired games make it conservative for eval noise), training-seed noise
     NOT included; (b) Lenth's pseudo standard error over the 15 contrasts, +- t(.975, 5) PSE -- includes run-to-run
     (seed) noise, assumes most of the 15 effects are null. The wider one is named per metric.
Habit metrics (search_s0 --habit-log, the levels worker's definitions): early offensive X-Bow = offensive X-Bow among the
first two plays when X-Bow is in the opening hand (%); unforced princess Rockets / match = rocket_princess - rocket_lethal
(a finisher Rocket on the king tower makes this a slight under-count); late (tick >= 2400) offensive X-Bows and Rockets /
match."""
import itertools
import json
import math
import random
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "heroiw"))
from validate import paired_drift  # noqa: E402

ROOT = Path("C:/Users/benpe/pod_backup_weekend/pod1017_factorial")
NAMES = "ABCDE"
LABEL = {"A": "cue layer", "B": "exploiter league", "C": "opp tower troops", "D": "live levels", "E": "tower shaping"}
SEEDS = (741200, 742000)
T975_5 = 2.5706                       # Student t, 0.975 quantile, 5 df (Lenth: m / 3 = 15 / 3)
REFS = {"ref_u250": "u250 (Mark CXXIV)", "ref_cxxxviii": "Mark CXXXVIII"}
HABITS = ("early_xbow_pct", "unforced_princess_rockets", "late_xbow_off", "late_rockets")


def design():
    """[(run, seed, {A..E: +-1})] in standard order (A fastest), E = ABCD; checked against design.txt when present."""
    out = []
    for i, bits in enumerate(itertools.product((-1, 1), repeat=4)):
        a, b, c, d = bits[::-1]
        out.append((f"fact{i + 1:02d}", 301 + i, {"A": a, "B": b, "C": c, "D": d, "E": a * b * c * d}))
    txt = HERE / "design.txt"
    if txt.is_file():
        for line in txt.read_text().splitlines():
            if line and not line.startswith("#"):
                run, signs, seed = line.split()[:3]
                r = next(x for x in out if x[0] == run)
                assert int(seed) == r[1] and signs == "".join(f"{k}{'+' if r[2][k] > 0 else '-'}" for k in NAMES), line
    return out


def columns(runs):
    """effect name -> (sign column over the runs, alias)."""
    cols = {k: ([s[k] for _, _, s in runs], "".join(sorted(set(NAMES) - {k}))) for k in NAMES}
    for p, q in itertools.combinations(NAMES, 2):
        cols[p + q] = ([s[p] * s[q] for _, _, s in runs], "".join(sorted(set(NAMES) - {p, q})))
    return cols


def lenth_pse(effects):
    a = sorted(abs(e) for e in effects)
    med = lambda v: (v[(len(v) - 1) // 2] + v[len(v) // 2]) / 2      # noqa: E731
    s0 = 1.5 * med(a)
    return 1.5 * med([x for x in a if x < 2.5 * s0])


def contrast(y, var, col):
    """(estimate, eval SE): mean of '+' minus mean of '-' over 16 runs = sum(c y) / 8."""
    return sum(c * v for c, v in zip(col, y)) / 8, math.sqrt(sum(var)) / 8


def load_rows(root, run):
    rows = []
    for s in SEEDS:
        p = Path(root) / run / "eval" / f"{run}_{s}" / "D3" / "matches.jsonl"
        if not p.is_file():
            return None
        rows += [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    return rows if len(rows) == 960 else None


def metrics(rows):
    """{metric: (value, variance of the value)} for one run."""
    n = len(rows)
    p = sum(r["outcome"] == "win" for r in rows) / n
    out = {"win_pct": (100 * p, 1e4 * p * (1 - p) / n)}
    hs = [r["habits"] for r in rows if "habits" in r]
    if len(hs) != n:
        return out
    def mean_var(xs, scale=1.0):
        m = sum(xs) / len(xs)
        v = sum((x - m) ** 2 for x in xs) / max(1, len(xs) - 1) / len(xs)
        return scale * m, scale * scale * v
    hand = [h["xbow_off_first2"] for h in hs if h["xbow_open_hand"]]
    out["early_xbow_pct"] = mean_var([float(x) for x in hand], 100.0) if hand else (float("nan"), float("nan"))
    out["unforced_princess_rockets"] = mean_var([h["rocket_princess"] - h["rocket_lethal"] for h in hs])
    out["late_xbow_off"] = mean_var([h["late"]["xbow_off"] for h in hs])
    out["late_rockets"] = mean_var([h["late"]["rocket"] for h in hs])
    return out


def vs(base, rows):
    if base is None:
        return "-"
    try:
        d = paired_drift(base, rows, expected=960)
    except ValueError as exc:
        return f"unpaired ({exc})"
    return f"{d['delta_pp']:+.2f} [{d['ci95_pp'][0]:+.2f}, {d['ci95_pp'][1]:+.2f}]"


def effect_table(name, unit, runs, m):
    cols = columns(runs)
    y = [m[r][name][0] for r, _, _ in runs]
    var = [m[r][name][1] for r, _, _ in runs]
    if any(math.isnan(v) for v in y + var):
        print(f"\n{name}: missing values, skipped")
        return {}
    est = {k: contrast(y, var, c) for k, (c, _) in cols.items()}
    pse = lenth_pse([e for e, _ in est.values()])
    me_l = T975_5 * pse
    print(f"\n{name} ({unit}): Lenth PSE {pse:.3f} -> +-{me_l:.3f};  eval-SE CI half-width "
          f"{1.96 * min(s for _, s in est.values()):.3f}..{1.96 * max(s for _, s in est.values()):.3f}")
    print(f"  {'effect':6} {'alias':6} {'estimate':>9}   {'95% CI (eval SE)':22} {'95% CI (Lenth)':22} wider")
    for k, (e, s) in est.items():
        lab = LABEL.get(k, " x ".join(LABEL[c].split()[0] for c in k))
        print(f"  {k:6} {cols[k][1]:6} {e:+9.3f}   [{e - 1.96 * s:+8.3f}, {e + 1.96 * s:+8.3f}]   "
              f"[{e - me_l:+8.3f}, {e + me_l:+8.3f}]   {'Lenth' if me_l > 1.96 * s else 'eval'}   {lab}")
    wider = "Lenth" if me_l > 1.96 * max(s for _, s in est.values()) else (
        "eval SE" if me_l < 1.96 * min(s for _, s in est.values()) else "mixed")
    print(f"  -> wider CI for {name}: {wider}")
    return {k: (e, s, me_l) for k, (e, s) in est.items()}


def analyze(root):
    runs = design()
    data = {r: load_rows(root, r) for r, _, _ in runs}
    refs = {k: load_rows(root, k) for k in REFS}
    m = {r: metrics(rows) for r, rows in data.items() if rows is not None}
    print(f"factorial root {root}: {len(m)}/16 runs complete; refs: "
          + ", ".join(f"{REFS[k]} {'ok' if v is not None else 'missing'}" for k, v in refs.items()))
    for k, rows in refs.items():
        if rows is not None:
            mm = metrics(rows)
            print(f"  {REFS[k]:18} win {mm['win_pct'][0]:.2f}% +- {math.sqrt(mm['win_pct'][1]):.2f}"
                  + "".join(f"  {h} {mm[h][0]:.3f}" for h in HABITS if h in mm))
    if all(v is not None for v in refs.values()):
        print(f"  Mark CXXXVIII vs u250 (paired): {vs(refs['ref_u250'], refs['ref_cxxxviii'])}")
    print(f"\n{'run':7} {'signs':11} seed  {'wins':>8} {'win %':>13}  {'early X%':>8} {'unf.R':>6} {'lateX':>6} {'lateR':>6}"
          f"  {'vs u250 [95% CI]':24} vs Mark CXXXVIII [95% CI]")
    for r, seed, s in runs:
        if r not in m:
            print(f"{r:7} {''.join(f'{k}{chr(43) if s[k] > 0 else chr(45)}' for k in NAMES):11} {seed}  (not complete)")
            continue
        w = sum(x["outcome"] == "win" for x in data[r])
        hab = "".join(f" {m[r][h][0]:6.2f}" if h in m[r] else "      -" for h in HABITS)
        print(f"{r:7} {''.join(f'{k}{chr(43) if s[k] > 0 else chr(45)}' for k in NAMES):11} {seed}  {w:4d}/960 "
              f"{m[r]['win_pct'][0]:6.2f} +-{math.sqrt(m[r]['win_pct'][1]):4.2f}  {hab}  "
              f"{vs(refs['ref_u250'], data[r]):24} {vs(refs['ref_cxxxviii'], data[r])}")
    if len(m) < 16:
        print(f"\neffects need all 16 runs ({len(m)}/16 complete): with runs missing the contrasts are not orthogonal")
        return None
    out = {"win_pct": effect_table("win_pct", "pp of win rate", runs, m)}
    if all(all(h in m[r] for h in HABITS) for r in m):
        for h, unit in zip(HABITS, ("pp", "per match", "per match", "per match")):
            out[h] = effect_table(h, unit, runs, m)
    print("\nNotes: two-way interactions are aliased with the complementary three-way (column 'alias'); the 4 pods are"
          " the (sign AC, sign AB) blocks, so AC, AB and BC also carry any pod difference. Eval-SE CIs ignore"
          " training-seed noise; Lenth's include it.")
    return out


def selftest():
    # Lenth by hand: |c| median 1.5 -> s0 2.25, trim at 5.625 drops 9 and 12, median of the other 13 = 1 -> PSE 1.5
    c = [12, -9, 1, -1, 2, -2, 0.5, -0.5, 1.5, -1.5, 3, -3, 0.2, -0.2, 0.8]
    assert abs(lenth_pse(c) - 1.5) < 1e-12, lenth_pse(c)
    runs = design()
    cols = columns(runs)
    assert all(sum(a * b for a, b in zip(cols[x][0], cols[y][0])) == 0 for x, y in itertools.combinations(cols, 2))
    planted = {"A": 6.0, "C": -4.0, "E": 2.0, "AB": 3.0, "DE": -2.5}
    # exact recovery (no noise): y = 50 + sum effect / 2 x column
    y = [50 + sum(v / 2 * cols[k][0][i] for k, v in planted.items()) for i in range(16)]
    for k in cols:
        e, _ = contrast(y, [1.0] * 16, cols[k][0])
        assert abs(e - planted.get(k, 0.0)) < 1e-9, (k, e)
    # noisy end-to-end: 960 paired games per run written in live_eval_pod.sh's layout, then analyze()
    rng = random.Random(20261017)
    keys = [(f"live_{i % 3}", s + i) for s in SEEDS for i in range(480)]
    deck = {k: [f"card{rng.randrange(40)}"] for k in keys}
    side = {k: rng.randrange(2) for k in keys}
    def write(root, run, p):
        for s in SEEDS:
            d = Path(root) / run / "eval" / f"{run}_{s}" / "D3"
            d.mkdir(parents=True)
            with (d / "matches.jsonl").open("w") as f:
                for k in [k for k in keys if s <= k[1] < s + 480]:
                    hand = rng.random() < 0.5
                    h = {"xbow_open_hand": hand, "xbow_off_first2": hand and rng.random() < 0.57, "rocket_princess":
                         rng.randrange(3), "rocket_lethal": 0, "late": {"xbow_off": rng.randrange(5), "rocket": rng.randrange(2)}}
                    f.write(json.dumps({"census": k[0], "seed": k[1], "outcome": "win" if rng.random() < p else "loss",
                                        "opp_deck": deck[k], "learner_side": side[k], "opp_gen_sha256": "x", "searched": 0,
                                        "habits": h}) + "\n")
    with tempfile.TemporaryDirectory() as t:
        for (r, _, _), yi in zip(runs, y):
            write(t, r, yi / 100)
        write(t, "ref_u250", 0.50)
        write(t, "ref_cxxxviii", 0.55)
        out = analyze(t)
    assert out is not None
    for k in cols:
        e, s, me_l = out["win_pct"][k]
        assert abs(e - planted.get(k, 0.0)) < 4 * s, (k, e, s)      # within 4 eval SEs (fixed RNG seed)
    assert out["win_pct"]["A"][0] - 1.96 * out["win_pct"]["A"][1] > 0            # the big planted effect is detected
    assert abs(out["early_xbow_pct"]["A"][0]) < 4 * out["early_xbow_pct"]["A"][1]   # habits: no planted effect
    print("\nSELFTEST PASS (Lenth by hand; orthogonal columns; exact recovery; noisy recovery within 4 SE)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        analyze(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT)
