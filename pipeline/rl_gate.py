"""E1 RL gate: paired scorer for an INIT checkpoint's e1_eval run vs a CANDIDATE checkpoint's run on the
same held-out ghosts, plus the e1_eval command lines that produce those two runs.

    python -m pipeline.rl_gate --init scratchpad/gauntlet/L67/e1/baseline_k0 --cand scratchpad/gauntlet/L67/e1/cand_k0 ^
        --json scratchpad/gauntlet/L67/e1/gate_report.json

    python -m pipeline.rl_gate --commands --init-ckpt icebow/data/pipeline/s1_icebow_v6lat_s0.pt ^
        --cand-ckpt icebow/data/pipeline/e1_latest.pt --out-root scratchpad/gauntlet/L67/e1/final --engine real

``--commands --config <run dir>/config.yaml`` (L68 T12b): the printed e1_eval lines carry that RL run's CONDITION keys
(noise_off / opp_elixir / action_delay_ticks / extrapolate_ticks -> --noise-off / --opp-elixir / --action-delay /
--extrapolate), so the gate evaluates under the condition the run trained and screened under.

Reads every ``matches.jsonl`` under each ``--init``/``--cand`` dir, recursively (the slot0/slot1 layout of
scratchpad/gauntlet/L68/rank/score.py), keyed by (tag, k) -- FIRST line wins on a repeat key, and the repeat is
counted and warned about (not silently dropped). Pairs the two runs on that key; a (tag, k) present in only one
run is reported as unpaired and excluded from every paired statistic.

Headline delta is the ENTRY-CLUSTERED estimate (per-tag mean over its k seeds, then mean over tags -- the same
statistic the bootstrap CI is built from), not the pooled per-(tag,k) delta; the two differ when tags carry unequal
k counts, and only the entry-clustered one is graded against criterion (i). The pooled delta is still printed, on
its own secondary line, labelled as pooled.

Verdict: scratchpad/gauntlet/L67/e1_engine_rl_design.md section 2.3 "Pre-registered verdict (b)" items (i) paired
delta + CI and (iv) the section 4.2 guards, PLUS the design's held-out-screen rule that the gain must also hold
before the ghost script ended. Item (ii), pro agreement, is NOT computable from matches.jsonl (it needs the clean
VAL split) -- see the printed note; read it from the training log, or ``pipeline.eval_s1`` (S1 checkpoints) /
``pipeline.eval_gen`` (generalist checkpoints, ``"gen": True``) instead.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

import numpy as np

from pipeline.e1_score import cluster_bootstrap, mcnemar_exact          # reuse: entry-clustered bootstrap, exact McNemar p

DRAWS = 10_000
GATE_SEED = 0                              # the ticket pins this gate's bootstrap to seed 0 (e1_score's own default differs)
MIN_TAGS = 20                              # fewer paired tags than this -> INSUFFICIENT, never PASS/FAIL
WIN_VAL = {"win": 1.0, "draw": 0.5, "loss": 0.0}


def val(r: dict) -> float:
    return WIN_VAL[r["outcome"]]


def load_dir(d: Path) -> tuple[dict[tuple[str, int], dict], int]:
    """Every matches.jsonl under ``d``, keyed by (tag, k). FIRST line wins on a repeat key -> (records, n_dup)."""
    out: dict[tuple[str, int], dict] = {}
    dup = 0
    for f in sorted(Path(d).glob("**/matches.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("mode") in ("parity", "liveness"):          # not eval-mode outcome rows
                continue
            key = (str(r["tag"]), int(r.get("k", 0)))
            if key in out:
                dup += 1
                continue
            out[key] = r
    return out, dup


def _mean(xs: list[float]) -> Optional[float]:
    return float(np.mean(xs)) if xs else None


def _win_share(wins: list[dict], key_fn) -> tuple[float, bool]:
    """Mean of key_fn over wins -> (share, defaulted). An empty win list defaults to share 0.0 rather than None,
    so a zero-win side doesn't force every dependent guard to fail for lack of a number."""
    if not wins:
        return 0.0, True
    return float(np.mean([key_fn(r) for r in wins])), False


def gate(init_dir: Path, cand_dir: Path, draws: int = DRAWS, seed: int = GATE_SEED) -> dict:
    I, dup_init = load_dir(init_dir)
    C, dup_cand = load_dir(cand_dir)
    keys = sorted(set(I) & set(C))
    unpaired = {"init_only": sorted(f"{t}:{k}" for t, k in set(I) - set(C)),
                "cand_only": sorted(f"{t}:{k}" for t, k in set(C) - set(I))}
    tags = sorted({t for t, _ in keys})

    by_entry_delta: dict[str, list[float]] = defaultdict(list)
    better = worse = 0
    for t, k in keys:
        a, b = val(I[(t, k)]), val(C[(t, k)])
        by_entry_delta[t].append(b - a)
        better += int(b > a)
        worse += int(b < a)

    k_counts = sorted({len(v) for v in by_entry_delta.values()})
    unequal_k = len(k_counts) > 1

    winrate_init = _mean([val(I[key]) for key in keys])
    winrate_cand = _mean([val(C[key]) for key in keys])
    pooled_delta_pp = (winrate_cand - winrate_init) * 100 if keys else None
    ci = cluster_bootstrap(by_entry_delta, draws, seed) if keys else {"point": None, "lo": None, "hi": None}
    delta_pp = ci["point"] * 100 if ci["point"] is not None else None          # headline: entry-clustered, matches the CI

    # before-script subset: a record missing `after_script` is EXCLUDED (not counted as before-script), and its
    # absence on either side makes the before-script criterion ungradable (UNKNOWN), not silently "True == before".
    missing_after_script = [f"init:{t}:{k}" for t, k in keys if "after_script" not in I[(t, k)]]
    missing_after_script += [f"cand:{t}:{k}" for t, k in keys if "after_script" not in C[(t, k)]]
    init_before = [I[key] for key in keys if I[key].get("after_script") is False]
    cand_before = [C[key] for key in keys if C[key].get("after_script") is False]
    wr_before_init = _mean([val(r) for r in init_before])
    wr_before_cand = _mean([val(r) for r in cand_before])
    before_delta_pp = (wr_before_cand - wr_before_init) * 100 if None not in (wr_before_init, wr_before_cand) else None

    ppm_init = [I[key]["plays_per_min"] for key in keys if I[key].get("plays_per_min") is not None]
    ppm_cand = [C[key]["plays_per_min"] for key in keys if C[key].get("plays_per_min") is not None]
    m_init, m_cand = _mean(ppm_init), _mean(ppm_cand)
    ppm_ratio = (m_cand / m_init) if m_init else None

    init_wins = [I[key] for key in keys if I[key]["outcome"] == "win"]
    cand_wins = [C[key] for key in keys if C[key]["outcome"] == "win"]
    outlived_init, outlived_init_defaulted = _win_share(init_wins, lambda r: float(bool(r.get("won_after_script"))))
    outlived_cand, outlived_cand_defaulted = _win_share(cand_wins, lambda r: float(bool(r.get("won_after_script"))))
    outlived_rise_pp = (outlived_cand - outlived_init) * 100

    le10_init, le10_init_defaulted = _win_share(init_wins, lambda r: float(int(r.get("ghost_delivered", 0)) <= 10))
    le10_cand, le10_cand_defaulted = _win_share(cand_wins, lambda r: float(int(r.get("ghost_delivered", 0)) <= 10))
    le10_rise_pp = (le10_cand - le10_init) * 100

    refusal_init = _mean([int(I[key].get("ghost_refused", 0)) + int(I[key].get("ghost_undelivered", 0)) for key in keys])
    refusal_cand = _mean([int(C[key].get("ghost_refused", 0)) + int(C[key].get("ghost_undelivered", 0)) for key in keys])
    # a zero-refusal init can't be "doubled"; give it +1.0/match of slack instead of demanding cand stay at 0.
    refusal_bound = max(2 * refusal_init, refusal_init + 1.0) if refusal_init is not None else None

    n_tags = len(tags)
    before_script_unknown = len(missing_after_script) > 0
    insufficient = n_tags < MIN_TAGS or before_script_unknown
    c1 = delta_pp is not None and delta_pp >= 5.0
    c2 = ci["lo"] is not None and ci["lo"] * 100 > 0
    c3: Optional[bool] = None if before_script_unknown else (before_delta_pp is not None and before_delta_pp > 0)
    c4 = ppm_ratio is not None and 0.8 <= ppm_ratio <= 1.2
    c5 = outlived_rise_pp <= 15.0
    c6 = le10_rise_pp <= 10.0
    c7 = refusal_bound is not None and refusal_cand is not None and refusal_cand <= refusal_bound
    criteria = {"delta_ge_5pp": c1, "ci_lower_gt_0": c2, "before_script_delta_gt_0": c3,
                "plays_per_min_ratio_in_0.8_1.2": c4, "outlived_script_rise_le_15pp": c5,
                "le10_delivered_win_share_rise_le_10pp": c6, "ghost_refusal_rate_le_2x_init": c7}
    graded = {k: v for k, v in criteria.items() if v is not None}
    verdict = "INSUFFICIENT" if insufficient else ("PASS" if all(graded.values()) else "FAIL")

    return {
        "n_pairs": len(keys), "n_entries": n_tags, "unpaired": unpaired,
        "duplicates": {"init": dup_init, "cand": dup_cand},
        "k_counts_equal": not unequal_k, "k_count_range": [k_counts[0], k_counts[-1]] if k_counts else None,
        "winrate_init": winrate_init, "winrate_cand": winrate_cand,
        "delta_pp": delta_pp, "pooled_delta_pp": pooled_delta_pp,
        "delta_ci95_pp": {"lo": ci["lo"] * 100 if ci["lo"] is not None else None,
                          "hi": ci["hi"] * 100 if ci["hi"] is not None else None, "draws": draws, "seed": seed},
        "mcnemar": {"cand_better": better, "cand_worse": worse, "exact_p": mcnemar_exact(better, worse)},
        "before_script_missing_field": missing_after_script, "before_script_unknown": before_script_unknown,
        "winrate_before_script_init": wr_before_init, "winrate_before_script_cand": wr_before_cand,
        "before_script_delta_pp": before_delta_pp,
        "plays_per_min_init": round(m_init, 3) if m_init is not None else None,
        "plays_per_min_cand": round(m_cand, 3) if m_cand is not None else None,
        "plays_per_min_ratio": round(ppm_ratio, 3) if ppm_ratio is not None else None,
        "outlived_script_win_share_init": outlived_init, "outlived_script_win_share_cand": outlived_cand,
        "outlived_script_rise_pp": outlived_rise_pp,
        "outlived_share_defaulted": {"init": outlived_init_defaulted, "cand": outlived_cand_defaulted},
        "le10_delivered_win_share_init": le10_init, "le10_delivered_win_share_cand": le10_cand,
        "le10_delivered_win_share_rise_pp": le10_rise_pp,
        "le10_share_defaulted": {"init": le10_init_defaulted, "cand": le10_cand_defaulted},
        "ghost_refusal_rate_init": round(refusal_init, 3) if refusal_init is not None else None,
        "ghost_refusal_rate_cand": round(refusal_cand, 3) if refusal_cand is not None else None,
        "ghost_refusal_rate_bound": round(refusal_bound, 3) if refusal_bound is not None else None,
        "criteria": criteria, "verdict": verdict,
    }


def _pct(x: Optional[float]) -> str:
    return f"{100 * x:.1f}%" if x is not None else "n/a"


def _pp(x: Optional[float]) -> str:
    return f"{x:+.1f} pp" if x is not None else "n/a"


def print_report(r: dict) -> None:
    print(f"paired: {r['n_pairs']} (tag, k) pairs over {r['n_entries']} distinct entries (tags)")
    u = r["unpaired"]
    print(f"unpaired: {len(u['init_only'])} init-only, {len(u['cand_only'])} cand-only (excluded from paired stats)")
    d = r["duplicates"]
    if d["init"] or d["cand"]:
        print(f"WARNING: duplicate (tag,k) rows dropped (first line kept): {d['init']} in init, {d['cand']} in cand")
    if not r["k_counts_equal"]:
        lo, hi = r["k_count_range"]
        print(f"WARNING: tags have unequal k counts ({lo}-{hi} seeds/tag) -- the entry-clustered stats still weight "
              f"every tag equally regardless of how many seeds it carries")
    print(f"winrate  init {_pct(r['winrate_init'])}  cand {_pct(r['winrate_cand'])}")
    print(f"HEADLINE entry-clustered delta (per-tag mean over k, then mean over tags): {_pp(r['delta_pp'])}")
    print(f"  pooled (tag,k) delta, for reference only: {_pp(r['pooled_delta_pp'])}")
    ci = r["delta_ci95_pp"]
    print(f"  entry-clustered bootstrap 95% CI of delta: [{ci['lo']:+.1f}, {ci['hi']:+.1f}] pp "
          f"({ci['draws']} draws, seed {ci['seed']})" if ci["lo"] is not None else "  CI: n/a")
    m = r["mcnemar"]
    print(f"  McNemar (tag,k)-level: cand-better {m['cand_better']}, cand-worse {m['cand_worse']} (exact p={m['exact_p']:.4f})")
    if r["before_script_unknown"]:
        print(f"before-script winrate: UNKNOWN -- after_script missing on {len(r['before_script_missing_field'])} records")
    else:
        print(f"before-script winrate  init {_pct(r['winrate_before_script_init'])}  cand {_pct(r['winrate_before_script_cand'])}  "
              f"delta {_pp(r['before_script_delta_pp'])}")
    print(f"plays/min  init {r['plays_per_min_init']}  cand {r['plays_per_min_cand']}  "
          f"ratio cand/init {r['plays_per_min_ratio']}" if r["plays_per_min_ratio"] is not None else "plays/min: n/a")
    od = r["outlived_share_defaulted"]
    if od["init"] or od["cand"]:
        print("note: zero-win side(s) treated as 0.0 outlived-script / <=10-delivered share "
              f"(init defaulted={od['init']}, cand defaulted={od['cand']})")
    print(f"outlived-the-script win share  init {_pct(r['outlived_script_win_share_init'])}  "
          f"cand {_pct(r['outlived_script_win_share_cand'])}  rise {_pp(r['outlived_script_rise_pp'])}")
    print(f"<=10-delivered win share  init {_pct(r['le10_delivered_win_share_init'])}  "
          f"cand {_pct(r['le10_delivered_win_share_cand'])}  rise {_pp(r['le10_delivered_win_share_rise_pp'])}")
    print(f"ghost refusal rate/match  init {r['ghost_refusal_rate_init']}  cand {r['ghost_refusal_rate_cand']}  "
          f"(pass bound: cand <= {r['ghost_refusal_rate_bound']})")
    print()
    print("item (ii) pro agreement is NOT checked here -- read it from the training log, or pipeline.eval_s1 (S1) / "
          "pipeline.eval_gen (generalist checkpoint) on the clean VAL split (not in matches.jsonl).")
    print()
    labels = {"delta_ge_5pp": "(i)  paired entry-clustered delta >= +5 pp", "ci_lower_gt_0": "(i)  CI lower bound > 0",
              "before_script_delta_gt_0": "     before-script delta > 0",
              "plays_per_min_ratio_in_0.8_1.2": "(iii) plays/min ratio in [0.8, 1.2]",
              "outlived_script_rise_le_15pp": "(iv) outlived-script share rise <= 15 pp",
              "le10_delivered_win_share_rise_le_10pp": "(iv) <=10-delivered win-share rise <= 10 pp",
              "ghost_refusal_rate_le_2x_init": "(iv) ghost refusal rate <= 2x init (or init + 1.0/match)"}
    if r["verdict"] == "INSUFFICIENT":
        print("(not graded: insufficient)")
    for key, label in labels.items():
        v = r["criteria"][key]
        status = "UNKNOWN" if v is None else ("PASS" if v else "FAIL")
        print(f"  {status}  {label}")
    if r["n_entries"] < MIN_TAGS:
        print(f"\nVERDICT: INSUFFICIENT ({r['n_entries']} paired tags < {MIN_TAGS})")
    elif r["before_script_unknown"]:
        print(f"\nVERDICT: INSUFFICIENT (after_script missing on {len(r['before_script_missing_field'])} records)")
    else:
        print(f"\nVERDICT: {r['verdict']}")


def condition_flags(cfg: Optional[dict]) -> str:
    """An rl_royale config's condition keys -> the e1_eval flags that reproduce them ('' for the defaults / no config).
    ``noise_off``: list, comma string or ``all`` (e1_eval's alias for every component)."""
    if not cfg:
        return ""
    spec = cfg.get("noise_off") or []
    names = [x.strip() for x in spec.split(",") if x.strip()] if isinstance(spec, str) else [str(x) for x in spec]
    out = []
    if names:
        out.append(f"--noise-off {','.join(names)}")
    if cfg.get("opp_elixir"):
        out.append(f"--opp-elixir {cfg['opp_elixir']}")
    if int(cfg.get("action_delay_ticks") or 0):
        out.append(f"--action-delay {int(cfg['action_delay_ticks'])}")
    if int(cfg.get("extrapolate_ticks") or 0):
        out.append(f"--extrapolate {int(cfg['extrapolate_ticks'])}")
    return "".join(" " + f for f in out)


def print_commands(init_ckpt: str, cand_ckpt: str, out_root: str, engine: str, cfg: Optional[dict] = None) -> None:
    cond = condition_flags(cfg)
    if cfg is not None:
        print(f"# condition from the run config:{cond or ' none (the defaults)'}")
    if engine == "royale":
        for label, ckpt in (("init", init_ckpt), ("cand", cand_ckpt)):
            print(f"research/ext/Royale/.venv/Scripts/python.exe -m pipeline.e1_eval --engine royale --port 0 "
                  f"--ckpt {ckpt} --split heldout --entries all --seeds 0,1,2 --device cuda --batch 29{cond} "
                  f"--out {out_root}/{label}")
        print("\nnote: e1_eval --engine royale skips entries RoyaleSim cannot load; unpaired-count them, don't stop the gate.")
    else:
        ports = {"slot0": (38031, "0/2"), "slot1": (38032, "1/2")}
        for label, ckpt in (("init", init_ckpt), ("cand", cand_ckpt)):
            for slot, (port, shard) in ports.items():
                print(f"icebow/.venv/Scripts/python.exe -m pipeline.e1_eval --port {port} --ckpt {ckpt} "
                      f"--split heldout --entries all --seeds 0,1,2 --shard {shard}{cond} --out {out_root}/{label}/{slot}")
        print("\nnote: boot the real engine first (see HANDOFF / e1/_boot.ps1) before running these.")


def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--init", type=Path, help="INIT checkpoint's e1_eval output dir")
    ap.add_argument("--cand", type=Path, help="CANDIDATE checkpoint's e1_eval output dir")
    ap.add_argument("--json", type=Path, default=None, help="also write the report dict as JSON here")
    ap.add_argument("--commands", action="store_true", help="print (don't run) the e1_eval command lines instead of scoring")
    ap.add_argument("--init-ckpt", help="--commands only")
    ap.add_argument("--cand-ckpt", help="--commands only")
    ap.add_argument("--out-root", help="--commands only: --out root (forward slashes), <root>/init and <root>/cand")
    ap.add_argument("--engine", choices=("real", "royale"), default="real", help="--commands only")
    ap.add_argument("--config", type=Path, default=None, help="--commands only: the RL run's config.yaml; its "
                    "condition keys become e1_eval flags (--noise-off / --opp-elixir / --action-delay / --extrapolate)")
    return ap


def main(argv=None) -> None:
    ap = build_argparser()
    args = ap.parse_args(argv)
    if args.commands:
        if not (args.init_ckpt and args.cand_ckpt and args.out_root):
            ap.error("--commands needs --init-ckpt, --cand-ckpt and --out-root")
        cfg = None
        if args.config:
            import yaml
            cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
        print_commands(args.init_ckpt, args.cand_ckpt, args.out_root, args.engine, cfg)
        return
    if not (args.init and args.cand):
        ap.error("need --init and --cand (or --commands)")
    report = gate(args.init, args.cand)
    print_report(report)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
