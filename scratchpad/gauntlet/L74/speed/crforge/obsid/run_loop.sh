#!/usr/bin/env bash
# S3b-4: compile the facade + every builder + CfLoop, then run cf_loop_obs.py (the full Java observation in the loop).
# usage (pod 30408): OBSID_RL=... OBSID_CLXIII=... obsid/run_loop.sh OUT.json [cf_loop_obs.py args]
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
export OBSID_RL=${OBSID_RL:-/workspace/f1/rl}
export OBSID_CFCORE=${OBSID_CFCORE:-$OBSID_RL/scratchpad/gauntlet/L74/crforge/facade/CfCore.java}
B=${OBSID_BUILD:-$HERE/build_loop}
L=${CRFORGE_LIB:-/workspace/cfspeed/crforge/env/build/install/env/lib}
OUT=$1; shift
mkdir -p "$B"
javac -Xlint:all -d "$B" -cp "$L/*" "$OBSID_CFCORE" "$HERE/../CfSpeed.java" "$HERE/CfObsBind.java" "$HERE/CfOppElixir.java" \
  "$HERE/CfIdent.java" "$HERE/CfCue.java" "$HERE/CfPubObj.java" "$HERE/CfLoop.java"
CRFORGE_XMX=${CRFORGE_XMX:-24g} CRFORGE_FACADE_BUILD="$B" ROYALE_RUNTIME=fin16-linux ROYALE_ENGINE=crforge \
  exec /workspace/venvf16/bin/python -I "$HERE/cf_loop_obs.py" --build "$B" --out "$OUT" "$@"
