r"""3-SEED CONFIRMATION of the reward A/B's dose pair (HANDOFF 5x).

    python tools/ab3_confirm.py --write                       # generate the 9 cell configs
    python tools/ab3_confirm.py --launch --workers 0 --wave 9  # 9 cells at once, proven path
    python tools/ab3_confirm.py --launch --workers 12 --wave 1 # one cell at a time, 5u path

WHY THIS EXISTS. The 4-arm screen produced 5q's designed signature -- the bank dose pair went
monotone at m=1000 (control 6.3 -> bank2 7.5 -> bank6 12.0) and both bank arms ROSE while control
and restraint fell. It also produced the reason that signature cannot be believed yet: **the arm
ordering completely INVERTED between m=500 and m=1000 on the same seed** (bank2 went from worst
treatment arm to above control). That is the n=1 noise floor, measured. Three seeds is what 5q
required before acting on any winner, and it tests the dose-response directly.

RESTRAINT IS DROPPED. It read BELOW control at both m=500 (3.2 vs 13.0) and m=1000 (2.0 vs 6.3),
with the lowest x-bow share of the four. Carrying a fourth arm would cost a third of the compute to
re-measure a loser; the term stays in env.py at its shipped 0.0 default.

/!\ --workers AND --wave ARE NOT FREE PARAMETERS. See 5u/5x:
  * Worker-side search lets ONE run reach ~13 cores instead of 3.25. It does NOT add cores. Nine
    concurrent cells already saturate 16, so `--workers 12 --wave 9` is 108 worker processes on 16
    cores -- oversubscription, not speedup.
  * Which arrangement is fastest is UNMEASURED. Run the queued benchmark first and set these from
    its numbers.
  * Worker-side search shipped TODAY and its LEARNING PARITY is unverified (5u). A confirmation run
    is the wrong place to debut an unproven path: a subtle bug there produces a clean-looking and
    invalid result. Gate on the benchmark's parity check before choosing --workers 12.
"""
import argparse
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from ab_reward_arms import ARMS, render as _render_base   # reuse the guarded key-edit

OUTDIR = ROOT / "data" / "ab3"
CELLS = ["control", "bank2", "bank6"]      # restraint dropped -- see docstring
SEEDS = [41, 42, 43]


def render(arm, seed):
    """Arm deltas applied, then the checkpoint path made unique per (arm, seed)."""
    txt = _render_base(arm)
    old = '"data/ab/policy_%s.pt"' % arm
    new = '"data/ab3/policy_%s_s%d.pt"' % (arm, seed)
    if old not in txt:
        raise SystemExit("[ab3] %s: could not find the checkpoint line to re-point" % arm)
    return txt.replace(old, new, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--launch", action="store_true")
    ap.add_argument("--matches", type=int, default=1500)
    ap.add_argument("--envs", type=int, default=96)
    ap.add_argument("--workers", type=int, required=False, default=0,
                    help="0 = proven in-process search; >1 = 5u worker-side search (see docstring)")
    ap.add_argument("--wave", type=int, default=9,
                    help="how many cells to run concurrently (9 = all at once)")
    args = ap.parse_args()

    if not (args.write or args.launch):
        raise SystemExit(__doc__)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    # GROUPED BY SEED, NOT BY ARM. A wave must be a complete 3-arm comparison so that each
    # wave yields a matched-m read across control/bank2/bank6 at one seed. Grouping by arm
    # would run all three control seeds first and give no cross-arm answer until the end.
    cells = [(a, sd) for sd in SEEDS for a in CELLS]
    for arm, seed in cells:
        (OUTDIR / ("%s_s%d.yaml" % (arm, seed))).write_text(render(arm, seed), encoding="utf-8")
    print("[ab3] wrote %d cell configs to %s" % (len(cells), OUTDIR))

    # LOAD EVERY CELL BACK AND ASSERT ITS DELTA TOOK AND ITS CHECKPOINT IS UNIQUE. The 4-arm
    # generator's identical check earned itself immediately (it caught invalid YAML from a dropped
    # space before a trailing '#'), so it is kept here rather than trusted.
    sys.path.insert(0, str(ROOT / "src"))
    from clashrl.config import Config
    seen = {}
    for arm, seed in cells:
        cfg = Config.load(OUTDIR / ("%s_s%d.yaml" % (arm, seed)))
        ck = cfg.get("train", "sim_ppo_checkpoint")
        if ck in seen:
            raise SystemExit("[ab3] %s_s%d shares a checkpoint with %s -- cells would collide"
                             % (arm, seed, seen[ck]))
        seen[ck] = "%s_s%d" % (arm, seed)
        for k, v in ARMS[arm][1].items():
            got = cfg.get("rewards", k)
            if abs(float(got) - float(v)) > 1e-9:
                raise SystemExit("[ab3] %s_s%d: %s is %r, expected %r" % (arm, seed, k, got, v))
    print("[ab3] all %d cells load; deltas verified and checkpoint paths distinct" % len(cells))

    if not args.launch:
        return
    if args.workers > 1 and args.wave > 2:
        print("[ab3] REFUSING --workers %d with --wave %d: nine cells already saturate 16 "
              "cores, so per-run workers only oversubscribe (5u/5x). Use --wave 1 or --workers 0."
              % (args.workers, args.wave))
        raise SystemExit(2)

    for i in range(0, len(cells), args.wave):
        batch = cells[i:i + args.wave]
        procs = []
        for arm, seed in batch:
            cfgp = OUTDIR / ("%s_s%d.yaml" % (arm, seed))
            log = OUTDIR / ("%s_s%d.log" % (arm, seed))
            cmd = [sys.executable, "run.py", "--config", str(cfgp), "train-sim-ppo",
                   "--matches", str(args.matches), "--envs", str(args.envs),
                   "--workers", str(args.workers), "--size", "432", "--device", "cpu",
                   "--seed", str(seed), "--search-interval", "4",
                   "--init", "data/policy_BEST_m18000_20260826.pt"]
            procs.append(subprocess.Popen(cmd, cwd=str(ROOT),
                                          stdout=log.open("w"), stderr=subprocess.STDOUT))
            print("[ab3] launched %s_s%d -> %s" % (arm, seed, log.name))
        for p in procs:
            p.wait()
    print("[ab3] all cells finished")


if __name__ == "__main__":
    main()
