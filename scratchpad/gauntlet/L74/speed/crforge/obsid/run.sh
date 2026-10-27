#!/usr/bin/env bash
# S3b-3a: compile the facade (CfCore) + the builders, then run the identity harness.
# usage (pod 32657): obsid/run.sh OUT.json [obs_id.py args: --n 56 --set extrapolate_ticks=0 ...]
#   OBSID_RL      the work tree whose pipeline/ runs (default /workspace/f1/rl, the facade work tree)
#   OBSID_CFCORE  the CfCore.java to compile (default that tree's facade copy); OBSID_BUILD the class dir
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
export OBSID_RL=${OBSID_RL:-/workspace/f1/rl}
export OBSID_CFCORE=${OBSID_CFCORE:-$OBSID_RL/scratchpad/gauntlet/L74/crforge/facade/CfCore.java}
B=${OBSID_BUILD:-$HERE/build}
L=${CRFORGE_LIB:-/workspace/cfspeed/crforge/env/build/install/env/lib}
OUT=$1; shift
mkdir -p "$B"
javac -Xlint:all -d "$B" -cp "$L/*" "$OBSID_CFCORE" "$HERE/../CfSpeed.java" "$HERE/CfObsBind.java" "$HERE/CfOppElixir.java" "$HERE/CfIdent.java"
CRFORGE_FACADE_BUILD="$B" ROYALE_RUNTIME=fin16-linux ROYALE_ENGINE=crforge \
  exec /workspace/venvf16/bin/python -I "$HERE/obs_id.py" --build "$B" --out "$OUT" "$@"
