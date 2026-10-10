"""XL2-only adapter around the unchanged mechanic runner.

run_wk.sh invokes this through PY="python xl2_fork.py". Spawned workers install
the same adapter. Each variant keeps its legacy records/NPZ files; only the
own-policy ALT/Acheck branch is shared, within one post-decide snapshot.
"""
import copy
import json
import os
from pathlib import Path
import sys


def project(row, variant):
    """Recover one legacy match record from a shared DEV match."""
    row = copy.deepcopy(row)
    mech = row["mech"]
    mech["opps"] = [o for o in mech["opps"] if o.get("variant", variant) == variant]
    for key in ("no_arm", "skipped_unsnapshottable"):
        mech[key] = [{k: v for k, v in o.items() if k != "variant"}
                     for o in mech[key] if o.get("variant", variant) == variant]
    mech["episodes"] = len(mech["opps"])
    return row


def install(M, outputs):
    """Patch only this XL2 subprocess; M is also injectable for offline tests."""
    fork, save_row = M.mech_fork, M.DA.save_row
    build, branch = M.DA.build_arms, M.run_branch
    active = [None]

    def save(_rows, name, learner, ctx, extra=None):
        targets = [active[0]] if active[0] is not None else outputs
        for variant in targets:
            save_row(outputs[variant], name, learner, ctx, extra)

    def shared_fork(self, m, todo, ctx, first=True, moment=None):
        if moment is None:
            return fork(self, m, todo, ctx, first=first)
        # The original runner saves/restores global Python/numpy/torch RNG and
        # fork_into deep-copies both sides' generators on every actual branch.
        # Do not cache B, even when a WHEN gate passes through to own A.
        cached_a, alt_root = [], [None]
        checks = M._CHECKS[0]
        final_checks = checks

        def arms(mo, match, learner, context):
            result = build(mo, match, learner, context)
            if "_skip" not in result:
                alt = result["alt"]
                if alt["script"] is not None or alt["root"] != ctx["d"]:
                    raise ValueError("XL2 shared A requires the complete own decision")
                alt_root[0] = alt["root"]
            return result

        def run(match, decisions, decision, blob, tick, env, hold, blockers=(), script=None):
            is_a = decision is alt_root[0] or decision is ctx["d"]
            if not is_a:
                return branch(match, decisions, decision, blob, tick, env, hold, blockers, script)
            if not cached_a:
                cached_a.append((blob, branch(match, decisions, decision, blob, tick, env, hold, blockers, script)))
            elif blob != cached_a[0][0]:
                raise ValueError("XL2 variants changed the root snapshot")
            return copy.deepcopy(cached_a[0][1])

        M.DA.build_arms, M.run_branch = arms, run
        try:
            for variant in outputs:
                active[0] = variant
                M._CHECKS[0] = checks  # same check budget in each virtual pass
                before = {k: len(m._mech[k]) for k in ("no_arm", "skipped")}
                fork(self, m, todo, ctx, first=first, moment={**moment, "variant": variant})
                final_checks = max(final_checks, M._CHECKS[0])
                for key, start in before.items():
                    for rec in m._mech[key][start:]:
                        rec["variant"] = variant
        finally:
            active[0] = None
            M._CHECKS[0] = final_checks
            M.DA.build_arms, M.run_branch = build, branch

    M.DA.save_row = save
    M.S.Runner._mech_fork = shared_fork


def bootstrap():
    sys.path[:0] = [os.getcwd(), str(Path(__file__).resolve().parent.parent / "mechanic_fork")]
    import mech_fork as M
    outputs = json.loads(os.environ["XL2_VARIANT_ROWS"])
    install(M, outputs)
    return M


if __name__ in ("__main__", "__mp_main__"):
    module = bootstrap()
    if __name__ == "__main__":
        # The first argument is the script selected by the unchanged run_wk.sh.
        if Path(sys.argv[1]).name != "mech_fork.py":
            raise ValueError("XL2 adapter only accepts the mechanic runner")
        sys.exit(module.S.main(sys.argv[2:]))
