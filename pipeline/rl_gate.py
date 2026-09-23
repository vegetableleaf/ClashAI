"""E1 RL gate: paired scorer for an INIT checkpoint's e1_eval run vs a CANDIDATE checkpoint's run on the
same held-out ghosts, plus the e1_eval command lines that produce those two runs.


    python -m pipeline.rl_gate --commands --init-ckpt icebow/data/pipeline/s1_icebow_v6lat_s0.pt ^

Reads every ``matches.jsonl`` under each ``--init``/``--cand`` dir, recursively (the slot0/slot1 layout of
key; a (tag, k) present in only one run is reported as unpaired and excluded from every paired statistic.

delta + CI and (iv) the section 4.2 guards, PLUS the design's held-out-screen rule that the gain must also hold
before the ghost script ended. Item (ii), pro agreement, is NOT computable from matches.jsonl (it needs the clean
VAL split) -- see the printed note; read it from the training log / ``pipeline.eval_s1`` instead.
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


def load_dir(d: Path) -> dict[tuple[str, int], dict]:
    """Every matches.jsonl under ``d``, keyed by (tag, k); last line wins on a repeat key."""
    out: dict[tuple[str, int], dict] = {}
    for f in sorted(Path(d).glob("**/matches.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("mode") in ("parity", "liveness"):          # not eval-mode outcome rows
                continue
            out[(str(r["tag"]), int(r.get("k", 0)))] = r
    return out


def _mean(xs: list[float]) -> Optional[float]:
    return float(np.mean(xs)) if xs else None


def gate(init_dir: Path, cand_dir: Path, draws: int = DRAWS, seed: int = GATE_SEED) -> dict:
    I, C = load_dir(init_dir), load_dir(cand_dir)
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

    winrate_init = _mean([val(I[key]) for key in keys])
    winrate_cand = _mean([val(C[key]) for key in keys])
    delta_pp = (winrate_cand - winrate_init) * 100 if keys else None
    ci = cluster_bootstrap(by_entry_delta, draws, seed) if keys else {"point": None, "lo": None, "hi": None}

    init_before = [I[key] for key in keys if not I[key].get("after_script")]
    cand_before = [C[key] for key in keys if not C[key].get("after_script")]
    wr_before_init = _mean([val(r) for r in init_before])
    wr_before_cand = _mean([val(r) for r in cand_before])
    before_delta_pp = (wr_before_cand - wr_before_init) * 100 if None not in (wr_before_init, wr_before_cand) else None

    ppm_init = [I[key]["plays_per_min"] for key in keys if I[key].get("plays_per_min") is not None]
    ppm_cand = [C[key]["plays_per_min"] for key in keys if C[key].get("plays_per_min") is not None]
    m_init, m_cand = _mean(ppm_init), _mean(ppm_cand)
    ppm_ratio = (m_cand / m_init) if m_init else None

    init_wins = [I[key] for key in keys if I[key]["outcome"] == "win"]
    cand_wins = [C[key] for key in keys if C[key]["outcome"] == "win"]
    outlived_init = _mean([float(bool(r.get("won_after_script"))) for r in init_wins])
    outlived_cand = _mean([float(bool(r.get("won_after_script"))) for r in cand_wins])
    outlived_rise_pp = (outlived_cand - outlived_init) * 100 if None not in (outlived_init, outlived_cand) else None

    le10_init = _mean([float(int(r.get("ghost_delivered", 0)) <= 10) for r in init_wins])
    le10_cand = _mean([float(int(r.get("ghost_delivered", 0)) <= 10) for r in cand_wins])
    le10_rise_pp = (le10_cand - le10_init) * 100 if None not in (le10_init, le10_cand) else None

    refusal_init = _mean([int(I[key].get("ghost_refused", 0)) + int(I[key].get("ghost_undelivered", 0)) for key in keys])
    refusal_cand = _mean([int(C[key].get("ghost_refused", 0)) + int(C[key].get("ghost_undelivered", 0)) for key in keys])

    n_tags = len(tags)
    insufficient = n_tags < MIN_TAGS
    c1 = delta_pp is not None and delta_pp >= 5.0
    c2 = ci["lo"] is not None and ci["lo"] * 100 > 0
    c3 = before_delta_pp is not None and before_delta_pp > 0
    c4 = ppm_ratio is not None and 0.8 <= ppm_ratio <= 1.2
    c5 = outlived_rise_pp is not None and outlived_rise_pp <= 15.0
    c6 = le10_rise_pp is not None and le10_rise_pp <= 10.0
    c7 = refusal_init is not None and refusal_cand is not None and (
        refusal_cand == 0 if refusal_init == 0 else refusal_cand <= 2 * refusal_init)
    criteria = {"delta_ge_5pp": c1, "ci_lower_gt_0": c2, "before_script_delta_gt_0": c3,
                "plays_per_min_ratio_in_0.8_1.2": c4, "outlived_script_rise_le_15pp": c5,
                "le10_delivered_win_share_rise_le_10pp": c6, "ghost_refusal_rate_le_2x_init": c7}
    verdict = "INSUFFICIENT" if insufficient else ("PASS" if all(criteria.values()) else "FAIL")

    return {
        "n_pairs": len(keys), "n_entries": n_tags, "unpaired": unpaired,
        "winrate_init": winrate_init, "winrate_cand": winrate_cand, "delta_pp": delta_pp,
        "delta_ci95_pp": {"lo": ci["lo"] * 100 if ci["lo"] is not None else None,
                          "hi": ci["hi"] * 100 if ci["hi"] is not None else None, "draws": draws, "seed": seed},
        "mcnemar": {"cand_better": better, "cand_worse": worse, "exact_p": mcnemar_exact(better, worse)},
        "winrate_before_script_init": wr_before_init, "winrate_before_script_cand": wr_before_cand,
        "before_script_delta_pp": before_delta_pp,
        "plays_per_min_init": m_init, "plays_per_min_cand": m_cand, "plays_per_min_ratio": ppm_ratio,
        "outlived_script_win_share_init": outlived_init, "outlived_script_win_share_cand": outlived_cand,
        "outlived_script_rise_pp": outlived_rise_pp,
        "le10_delivered_win_share_init": le10_init, "le10_delivered_win_share_cand": le10_cand,
        "le10_delivered_win_share_rise_pp": le10_rise_pp,
        "ghost_refusal_rate_init": refusal_init, "ghost_refusal_rate_cand": refusal_cand,
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
    print(f"winrate  init {_pct(r['winrate_init'])}  cand {_pct(r['winrate_cand'])}  "
          f"paired delta {_pp(r['delta_pp'])}")
    ci = r["delta_ci95_pp"]
    print(f"  entry-clustered bootstrap 95% CI of delta: [{ci['lo']:+.1f}, {ci['hi']:+.1f}] pp "
          f"({ci['draws']} draws, seed {ci['seed']})" if ci["lo"] is not None else "  CI: n/a")
    m = r["mcnemar"]
    print(f"  McNemar (tag,k)-level: cand-better {m['cand_better']}, cand-worse {m['cand_worse']} (exact p={m['exact_p']:.4f})")
    print(f"before-script winrate  init {_pct(r['winrate_before_script_init'])}  cand {_pct(r['winrate_before_script_cand'])}  "
          f"delta {_pp(r['before_script_delta_pp'])}")
    print(f"plays/min  init {r['plays_per_min_init']}  cand {r['plays_per_min_cand']}  "
          f"ratio cand/init {r['plays_per_min_ratio']:.3f}" if r["plays_per_min_ratio"] is not None else "plays/min: n/a")
    print(f"outlived-the-script win share  init {_pct(r['outlived_script_win_share_init'])}  "
          f"cand {_pct(r['outlived_script_win_share_cand'])}  rise {_pp(r['outlived_script_rise_pp'])}")
    print(f"<=10-delivered win share  init {_pct(r['le10_delivered_win_share_init'])}  "
          f"cand {_pct(r['le10_delivered_win_share_cand'])}  rise {_pp(r['le10_delivered_win_share_rise_pp'])}")
    print(f"ghost refusal rate/match  init {r['ghost_refusal_rate_init']}  cand {r['ghost_refusal_rate_cand']}")
    print()
    print("item (ii) pro agreement is NOT checked here -- read it from the training log / pipeline.eval_s1 "
          "(clean VAL split, not in matches.jsonl).")
    print()
    labels = {"delta_ge_5pp": "(i)  paired delta >= +5 pp", "ci_lower_gt_0": "(i)  CI lower bound > 0",
              "before_script_delta_gt_0": "     before-script delta > 0",
              "plays_per_min_ratio_in_0.8_1.2": "(iii) plays/min ratio in [0.8, 1.2]",
              "outlived_script_rise_le_15pp": "(iv) outlived-script share rise <= 15 pp",
              "le10_delivered_win_share_rise_le_10pp": "(iv) <=10-delivered win-share rise <= 10 pp",
              "ghost_refusal_rate_le_2x_init": "(iv) ghost refusal rate <= 2x init"}
    for key, label in labels.items():
        print(f"  {'PASS' if r['criteria'][key] else 'FAIL'}  {label}")
    if r["n_entries"] < MIN_TAGS:
        print(f"\nVERDICT: INSUFFICIENT ({r['n_entries']} paired tags < {MIN_TAGS})")
    else:
        print(f"\nVERDICT: {r['verdict']}")


def print_commands(init_ckpt: str, cand_ckpt: str, out_root: str, engine: str) -> None:
    if engine == "royale":
        for label, ckpt in (("init", init_ckpt), ("cand", cand_ckpt)):
            print(f"research/ext/Royale/.venv/Scripts/python.exe -m pipeline.e1_eval --engine royale --port 0 "
                  f"--ckpt {ckpt} --split heldout --entries all --seeds 0,1,2 --device cuda --batch 29 "
                  f"--out {out_root}/{label}")
        print("\nnote: e1_eval --engine royale skips entries RoyaleSim cannot load; unpaired-count them, don't stop the gate.")
    else:
        ports = {"slot0": (38031, "0/2"), "slot1": (38032, "1/2")}
        for label, ckpt in (("init", init_ckpt), ("cand", cand_ckpt)):
            for slot, (port, shard) in ports.items():
                print(f"icebow/.venv/Scripts/python.exe -m pipeline.e1_eval --port {port} --ckpt {ckpt} "
                      f"--split heldout --entries all --seeds 0,1,2 --shard {shard} --out {out_root}/{label}/{slot}")
        print()


def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--init", type=Path, help="INIT checkpoint's e1_eval output dir")
    ap.add_argument("--cand", type=Path, help="CANDIDATE checkpoint's e1_eval output dir")
    ap.add_argument("--json", type=Path, default=None, help="also write the report dict as JSON here")
    ap.add_argument("--commands", action="store_true", help="print (don't run) the e1_eval command lines instead of scoring")
    ap.add_argument("--init-ckpt", help="--commands only")
    ap.add_argument("--cand-ckpt", help="--commands only")
    ap.add_argument("--out-root", help="--commands only: --out root (forward slashes), <root>/init and <root>/cand")
    ap.add_argument("--engine", choices=("royale",), default="royale", help="--commands only")
    return ap


def main(argv=None) -> None:
    ap = build_argparser()
    args = ap.parse_args(argv)
    if args.commands:
        if not (args.init_ckpt and args.cand_ckpt and args.out_root):
            ap.error("--commands needs --init-ckpt, --cand-ckpt and --out-root")
        print_commands(args.init_ckpt, args.cand_ckpt, args.out_root, args.engine)
        return
    if not (args.init and args.cand):
        ap.error("need --init and --cand (or --commands)")
    report = gate(args.init, args.cand)
    print_report(report)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
