"""I10 behaviour probe: prove that stripping hogeq's inert icebow reward terms changed nothing.

WHAT IT PROVES
--------------
hogeq's `sim/env.py` carried the whole X-Bow / Rocket / Tornado reward apparatus, which is
unreachable for a deck holding none of those cards: `xbow_ids` and `rocket_ids` are built by
matching deck keys against "x_bow" / "rocket" and are the EMPTY SET, and `_register_nado` only
fires for a played spell whose spec has `pulls`. "Unreachable" is an argument, not a measurement,
so this script makes it one: drive the pre-strip and post-strip environments through an identical
fixed action stream and compare every per-step reward at full float precision, every reward-term
ledger entry, and the terminal engine state.

    RESULT: 24 matches x 400 decisions = 9,600 steps, 0 mismatches, 0 reward terms lost or gained.

⚠ THE SIM IS NOT REPRODUCIBLE ACROSS PROCESSES, AND THAT HAD TO BE SOLVED FIRST
------------------------------------------------------------------------------
The obvious design -- run the probe, strip, run it again, diff the digests -- is INVALID here, and
silently so. Three runs of the SAME code in three processes produced three different digests:

    71ec0b4a...   a1bd93f7...   244aa3fe...

PYTHONHASHSEED=0 does not fix it, so it is not string-hash randomisation. Inside ONE process two
identically-seeded runs agree. The cause is `id()` REUSE: `_settle_spell_casts` keys a spell's
before-picture on `id(Unit)` (`p["hp"]`, and `live = {id(u): u.hp ...}`), and CPython recycles the
address of a dead body for a newly allocated one. When that happens the settle reads a killed
victim as "still alive at full HP", `dealt` comes back 0, and the cast is billed `spell_waste`
instead of credited `spell_defence`. Whether it happens depends on the allocator, so it varies run
to run.

CONFIRMED by holding a reference to every Unit for the life of the run, which makes address reuse
impossible: of the 7 seeds that diverged, 0 diverge when pinned and 2 diverge when not. That is
also why the control below exists -- an A/B on this sim without pinning has a noise floor of about
2-3 matches in 12, which is LARGER than the effect being measured, and an unpinned "before vs
after" comparison of the strip reported 2 mismatching matches while an unpinned "before vs BEFORE"
control reported 3.

The reproducibility bug is PRE-EXISTING, is not what I10 set out to change, and is recorded in
conflicts.md for an owner ruling rather than fixed here.

HOW TO RUN
----------
Both versions must be imported into ONE process, so the "before" tree is materialised as a sibling
package. `Config.load()` resolves its root as `Path(__file__).resolve().parents[2]`, so a copy at
`<deck>/src/clashrl_old/` finds the same `config/` and needs no other change.

    cd hogeq
    git show <ref>:hogeq/src/clashrl/sim/env.py > /tmp/env_before.py
    PYTHONPATH=src python ../research/sim_parity/scripts/i10_reward_probe.py \
        --before /tmp/env_before.py            # A/B: pre-strip vs working tree
    PYTHONPATH=src python ../research/sim_parity/scripts/i10_reward_probe.py \
        --before /tmp/env_before.py --control  # sanity: pre-strip vs pre-strip, must be 0
    PYTHONPATH=src python ../research/sim_parity/scripts/i10_reward_probe.py \
        --before /tmp/env_before.py --no-pin   # exhibit the id()-reuse noise floor
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

# The DECK root (icebow/ or hogeq/), not the worktree root: `Config.load()` and the package
# copy both hang off it. Taken from the working directory, which is the deck you ran this in.
DECK_ROOT = os.path.abspath(os.environ.get("CLASHRL_DECK_ROOT") or os.getcwd())


def _materialise_before(deck_root: str, before_env: str) -> str:
    """Copy `src/clashrl` to `src/clashrl_old` with `sim/env.py` replaced. Returns the path."""
    src = os.path.join(deck_root, "src", "clashrl")
    dst = os.path.join(deck_root, "src", "clashrl_old")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(before_env, os.path.join(dst, "sim", "env.py"))
    return dst


def _rollout(EnvCls, Cfg, seed, steps, keep):
    import numpy as np

    env = EnvCls(Cfg.load(), seed=seed)
    env.reset()
    rng = np.random.RandomState(seed * 7919 + 13)
    rewards = []
    for _ in range(steps):
        act = (bool(rng.rand() < 0.45),
               int(rng.randint(0, len(env.deck_keys))),
               int(rng.randint(0, env.n_cells)))
        _obs, r, done, _info = env.step(act)
        if keep is not None:
            keep.extend(env.eng.units)      # pin: no Unit address can be recycled
        rewards.append(repr(float(r)))      # repr = full precision, no rounding
        if done:
            env.reset()
    terms = {k: t.as_dict() for k, t in sorted(env.rw_stats.run.items())}
    final = (repr(float(env.eng.t)), len(env.eng.units),
             tuple(repr(float(tw.hp)) for tw in list(env.eng.towers[0]) + list(env.eng.towers[1])))
    return rewards, terms, final


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", help="pre-strip sim/env.py to compare the working tree against")
    ap.add_argument("--control", action="store_true",
                    help="compare the BEFORE tree against itself (must report 0 mismatches)")
    ap.add_argument("--no-pin", action="store_true",
                    help="do not pin Unit objects -- exhibits the id()-reuse noise floor")
    ap.add_argument("--matches", type=int, default=24)
    ap.add_argument("--steps", type=int, default=400)
    ap.add_argument("--seed", type=int, default=101)
    a = ap.parse_args()

    sys.path.insert(0, os.path.join(DECK_ROOT, "src"))
    from clashrl.config import Config as CfgNew
    from clashrl.sim.env import SimMatchEnv as EnvNew

    made = None
    if a.before:
        made = _materialise_before(DECK_ROOT, a.before)
        from clashrl_old.config import Config as CfgOld
        from clashrl_old.sim.env import SimMatchEnv as EnvOld
    else:                       # no --before: the working tree against itself
        CfgOld, EnvOld = CfgNew, EnvNew
    if a.control:
        CfgNew, EnvNew = CfgOld, EnvOld

    keep = None if a.no_pin else []
    bad, old_terms, new_terms = 0, set(), set()
    try:
        for m in range(a.matches):
            s = a.seed + m
            # alternate the order so neither side systematically runs on a warmer allocator
            if m % 2 == 0:
                ro, to, fo = _rollout(EnvOld, CfgOld, s, a.steps, keep)
                rn, tn, fn = _rollout(EnvNew, CfgNew, s, a.steps, keep)
            else:
                rn, tn, fn = _rollout(EnvNew, CfgNew, s, a.steps, keep)
                ro, to, fo = _rollout(EnvOld, CfgOld, s, a.steps, keep)
            old_terms |= set(to)
            new_terms |= set(tn)
            shared = set(to) & set(tn)
            ok = (ro == rn and fo == fn and all(to[k] == tn[k] for k in shared)
                  and not (set(tn) - set(to)))
            if ok:
                print("seed %d  identical  (%d steps, %d terms)" % (s, a.steps, len(shared)))
                continue
            bad += 1
            print("seed %d  MISMATCH" % s)
            for i, (x, y) in enumerate(zip(ro, rn)):
                if x != y:
                    print("    first reward divergence at step %d: %s != %s" % (i, x, y))
                    break
            for k in sorted(shared):
                if to[k] != tn[k]:
                    print("    term %s: %r != %r" % (k, to[k], tn[k]))
    finally:
        if made and os.path.isdir(made):
            shutil.rmtree(made, ignore_errors=True)

    print()
    print("matches compared        : %d" % a.matches)
    print("decisions compared      : %d" % (a.matches * a.steps))
    print("unit pinning            : %s" % ("OFF (id-reuse noise floor)" if a.no_pin else "ON"))
    print("mismatching matches     : %d" % bad)
    print("reward terms, BEFORE    : %s" % ", ".join(sorted(old_terms)))
    print("reward terms, AFTER     : %s" % ", ".join(sorted(new_terms)))
    print("terms lost by the strip : %s" % (", ".join(sorted(old_terms - new_terms)) or "NONE"))
    print("terms gained            : %s" % (", ".join(sorted(new_terms - old_terms)) or "NONE"))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
