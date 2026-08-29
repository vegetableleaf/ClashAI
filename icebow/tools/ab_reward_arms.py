r"""Generate and launch the 4-arm reward A/B for the elixir-banking failure (HANDOFF 5p/5q).

    python tools/ab_reward_arms.py                 # show the arms and their launch commands
    python tools/ab_reward_arms.py --write         # generate data/ab/<arm>.yaml
    python tools/ab_reward_arms.py --launch        # generate AND start all arms

WHAT IS BEING TESTED
--------------------
MEASURED (5p): of ~20 live reward terms, EVERY positive one requires a play. The only two that can
fire on a step where nothing was played are `threat_miss_idle` and `leak`, and both are penalties.
So waiting is worth at best 0 while playing carries +5.32/match of reachable credit -- waiting is a
strictly dominated ACTION CLASS. Downstream: elixir >=6 collapses 35.4% -> 1.0% and x_bow share
12.5% -> 2.7% against the m18000 reference.

EACH ARM IS GENERATED FROM config.yaml AT LAUNCH, never hand-maintained, so arms cannot drift apart
in anything except the deltas below. Every arm differs from the control in ONE key (the dose pair
differs only in a cap), which is what makes a win attributable.

/!\ PYTHONHASHSEED IS PINNED, AND IT IS NOT OPTIONAL. MEASURED: the same seeded rollout in two
processes gives elixir mean 1.9847 vs 2.0383 and 3980 vs 4083 steps with the hash seed unpinned,
and is bit-identical with it pinned. Arms are separate processes, so without this the comparison
carries uncontrolled variance before any reward change is applied. (`rollout_search` once tried
this with os.environ.setdefault AFTER interpreter start, which cannot work -- Python reads the
variable at startup. It must be set in the launching environment, which is what this does.)

/!\ BRANCH POINT IS m18000, NOT THE CURRENT RUN. At m18000 banking still works (>=6 elixir 35.4%),
so the CONTROL ARM IS EXPECTED TO REPRODUCE THE COLLAPSE. That is the point: it is the positive
control proving the experiment can detect the effect at all. If the control does NOT collapse, the
run is uninformative and nothing else in it can be read.

/!\ ENDPOINTS ARE MECHANISM METRICS, NOT WINRATE. At 150 matches winrate carries +/-5pp, far too
noisy to separate arms; `>=6 elixir`, `x_bow share` and `bank_to_six_then_bow` move by 35x in the
pathology. Winrate is a guardrail ("did we break anything"), not the discriminator. See
tools/ab_reward_report.py.

/!\ ONE SEED PER ARM IS A SCREEN, NOT A VERDICT. Gate collapse has a measured 4/6 escape rate, so a
four-arm single-seed design can hand you a spurious winner. Confirm the winner at 3 seeds.

WHY THERE IS NO "WIDEN GUARD 5" ARM. It was specced and then MEASURED OUT before costing a run:
restraint_hold pays +0.50/match at restraint_ignore_frac 0.20 AND +0.50/match at 0.50 -- identical,
because the 4 s `threat_miss_period` rate limit binds, not the threshold. It could not have
separated from the `restraint` arm. The knob still exists in env.py, defaulted to no change.
"""
import argparse
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = ROOT / "config" / "config.yaml"
OUTDIR = ROOT / "data" / "ab"          # generated; data/ is gitignored

# name -> (one-line rationale, {rewards key: value})
# DOSE is measured on the frozen m5400 policy against the +5.32/match play-side upside.
ARMS = {
    "control": ("current config; MUST reproduce the collapse (positive control)", {}),
    "restraint": ("restore the shipped-but-disabled fix; +0.33/m = 6% of play-side",
                  {"restraint_hold": "1.0"}),
    "bank2": ("pay for CLIMBING the bar, cap 2.0 -> +2.00/m = 38% of play-side",
              {"bank_hold": "1.0", "bank_hold_cap": "2.0"}),
    "bank6": ("same term, cap 6.0 -> +5.83/m = 110% of play-side (dose pair with bank2)",
              {"bank_hold": "1.0", "bank_hold_cap": "6.0"}),
}

# Fixed across every arm. --envs 96 rather than 192 because MEMORY binds, not CPU: a trainer is
# 2.66 GB and 2.54 cores while only 7.0 GB is available, so 4x192 does not fit and 4x96 does.
# Throughput is CPU-bound (workers 0 steps envs sequentially), so halving envs costs little.
COMMON = ["--envs", "96", "--workers", "0", "--size", "432", "--device", "cpu",
          "--seed", "41", "--search-interval", "4",
          "--init", "data/policy_BEST_m18000_20260826.pt"]


def render(arm):
    """The base config with this arm's deltas applied, comments and all."""
    txt = BASE.read_text(encoding="utf-8")
    deltas = dict(ARMS[arm][1])
    deltas["sim_ppo_checkpoint"] = '"data/ab/policy_%s.pt"' % arm   # arms MUST NOT share a file
    for key, val in deltas.items():
        # Keep any trailing comment INCLUDING the space before its '#'. Dropping that space wrote
        # `sim_ppo_checkpoint: "...pt"# PPO sibling`, which is not valid YAML -- a comment must be
        # preceded by whitespace. The load check in main() is what caught it.
        pat = re.compile(r"^(  " + re.escape(key) + r":)([^\n#]*)(#[^\n]*)?$", re.M)
        hits = len(pat.findall(txt))
        if hits != 1:
            raise SystemExit("[ab] %s: key %r matched %d lines in config.yaml, refusing to edit "
                             "ambiguously" % (arm, key, hits))
        txt = pat.sub(lambda m: m.group(1) + " " + val + ("  " + m.group(3) if m.group(3) else ""),
                      txt, count=1)
    return txt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="generate the arm configs")
    ap.add_argument("--launch", action="store_true", help="generate AND start every arm")
    ap.add_argument("--matches", type=int, default=10000)
    args = ap.parse_args()

    if args.write or args.launch:
        OUTDIR.mkdir(parents=True, exist_ok=True)
        for arm in ARMS:
            (OUTDIR / (arm + ".yaml")).write_text(render(arm), encoding="utf-8")
        print("[ab] wrote %d arm configs to %s" % (len(ARMS), OUTDIR))
        # PROVE EVERY ARM LOADS, and that its deltas actually took. A generated config that fails
        # to parse -- or silently keeps the control's value -- would run as a duplicate control,
        # and the report would show four arms that were really one.
        sys.path.insert(0, str(ROOT / "src"))
        from clashrl.config import Config                        # noqa: E402
        for arm in ARMS:
            cfg = Config.load(OUTDIR / (arm + ".yaml"))
            for key, val in ARMS[arm][1].items():
                got = float(cfg.get("rewards", key, default=-999.0))
                if abs(got - float(val)) > 1e-9:
                    raise SystemExit("[ab] %s: %s read back %s, expected %s" % (arm, key, got, val))
            ck = str(cfg.get("train", "sim_ppo_checkpoint", default=""))
            if arm not in ck:
                raise SystemExit("[ab] %s: checkpoint path is %r; arms would collide" % (arm, ck))
        print("[ab] all arms load; deltas and checkpoint paths verified distinct")

    env = dict(os.environ, PYTHONHASHSEED="0")     # see the module docstring; not optional
    procs = []
    for arm in ARMS:
        why, deltas = ARMS[arm]
        cmd = [sys.executable, "run.py", "--config", str(OUTDIR / (arm + ".yaml")),
               "train-sim-ppo", "--matches", str(args.matches)] + COMMON
        delta_s = ", ".join("%s=%s" % (k, v) for k, v in deltas.items()) or "(none)"
        print("\n[%s] %s\n    delta: %s\n    PYTHONHASHSEED=0 %s"
              % (arm, why, delta_s, " ".join(cmd[1:])))
        if args.launch:
            log = (OUTDIR / (arm + ".log")).open("w", encoding="utf-8")
            procs.append((arm, subprocess.Popen(cmd, cwd=ROOT, env=env,
                                                stdout=log, stderr=subprocess.STDOUT)))
    for arm, p in procs:
        print("[ab] %s launched pid %d -> %s" % (arm, p.pid, OUTDIR / (arm + ".log")))
    if not (args.write or args.launch):
        print("\n[ab] nothing written. --write to generate, --launch to start.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
