#!/usr/bin/env bash
# usage: ct635.sh OUTDIR -- core tests on 16.635.3 with the guard bypass applied only for the run (reverted after)
cd /workspace/f635/crforge_fork && git apply /workspace/f635/guard_only.diff || exit 1
/workspace/f635/ct.sh 16.635.3 $1
cd /workspace/f635/crforge_fork && git apply -R /workspace/f635/guard_only.diff
