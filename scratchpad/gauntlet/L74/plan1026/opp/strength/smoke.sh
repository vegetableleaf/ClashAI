#!/usr/bin/env bash
# smoke.sh OPP_CKPT OUT [SEEDS] [OPP_T] -- a few closed-loop games through the exact D3 worker command (smoke_closed.py), on 33553.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); . "$HERE/pod_env.sh"
cd "$CB"
exec taskset -c ${CPUS:-0-27} "$PY" scratchpad/gauntlet/L74/plan1026/opp/smoke_closed.py --opp "$1" --out "$2" \
  --seeds "${3:-741200,741201}" --opp-T "${4:-1.0}" --python "$PY" ${DIAG:+--diag}
