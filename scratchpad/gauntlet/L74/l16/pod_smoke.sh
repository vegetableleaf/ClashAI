#!/bin/bash
# Real all16 smoke for one requested arm, before its training chain is launched.
set -euo pipefail
RUNN=${RUN:?set RUN to the requested L16 arm}
CB=/workspace/cb_stepd
O=/workspace/stepd/l16_smoke_$RUNN
PY=/workspace/venvf13/bin/python
Y=scratchpad/gauntlet/L74/stepd/cfg/$RUNN.yaml
mkdir -p "$O"
cd "$CB"
unset ROYALE_HEROIW_PRESS
export PYTHONPATH=$CB ROYALE_RUNTIME=fin13-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
grep -q '^live_levels: all16$' "$Y"
sha256sum "$Y" > "$O/yaml.sha"
echo "$(date -u +%FT%TZ) smoke start pid $$ run $RUNN" >> "$O/status.log"
flock /workspace/cpu.lock "$PY" -m pipeline.rl_royale --config "$Y" --run smoke_$RUNN --smoke \
  critic_warmup_updates=1 > "$O/smoke.log" 2>&1
grep -q 'SMOKE PASS' "$O/smoke.log"
touch "$O/SMOKE_OK"
echo "$(date -u +%FT%TZ) SMOKE PASS $RUNN" | tee -a "$O/status.log"
