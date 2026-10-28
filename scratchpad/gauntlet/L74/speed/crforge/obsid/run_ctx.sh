#!/usr/bin/env bash
# LOOP-CTX: compile the facade + the obs builders ctx_id.py runs + CfCtx, then run the identity harness.
# usage (pod 32657): OBSID_RL=<work tree> obsid/run_ctx.sh OUT.json [ctx_id.py args: --n 56 --hero-abilities ...]
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
export OBSID_RL=${OBSID_RL:-/workspace/f1/rl}
export OBSID_CFCORE=${OBSID_CFCORE:-$OBSID_RL/scratchpad/gauntlet/L74/crforge/facade/CfCore.java}
B=${OBSID_BUILD:-$HERE/build_ctx}
L=${CRFORGE_LIB:-/workspace/cfspeed/crforge/env/build/install/env/lib}
OUT=$1; shift
mkdir -p "$B"
javac -Xlint:all -d "$B" -cp "$L/*" "$OBSID_CFCORE" "$HERE/../CfSpeed.java" "$HERE/CfObsBind.java" "$HERE/CfOppElixir.java" \
  "$HERE/CfIdent.java" "$HERE/CfCue.java" "$HERE/CfPubObj.java" "$HERE/CfCtx.java"
CRFORGE_FACADE_BUILD="$B" ROYALE_RUNTIME=fin16-linux ROYALE_ENGINE=crforge \
  exec /workspace/venvf16/bin/python -I "$HERE/ctx_id.py" --build "$B" --out "$OUT" --threads "${CTX_THREADS:-4}" "$@"
