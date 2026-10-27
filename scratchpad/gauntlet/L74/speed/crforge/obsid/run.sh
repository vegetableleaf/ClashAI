#!/usr/bin/env bash
# S3b-3a: compile the facade (CfCore at the work tree's HEAD copy) + the builders, then run the identity harness.
# usage (pod 32657): obsid/run.sh OUT.json [obs_id.py args: --n 56 --set extrapolate_ticks=0 ...]
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
RL=${OBSID_RL:-/workspace/f1/rl}
L=${CRFORGE_LIB:-/workspace/cfspeed/crforge/env/build/install/env/lib}
OUT=$1; shift
mkdir -p "$HERE/build"
javac -Xlint:all -d "$HERE/build" -cp "$L/*" "$RL/scratchpad/gauntlet/L74/crforge/facade/CfCore.java" \
  "$HERE/../CfSpeed.java" "$HERE/CfObsBind.java"
CRFORGE_FACADE_BUILD="$HERE/build" ROYALE_RUNTIME=fin16-linux ROYALE_ENGINE=crforge \
  exec /workspace/venvf16/bin/python -I "$HERE/obs_id.py" --build "$HERE/build" --out "$OUT" "$@"
