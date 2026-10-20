#!/bin/bash
# pod_smoke.sh (l16) for the fin15 runtime: RUN=<tn_* arm name>; runtime fin15-linux, python /workspace/venvf15/bin/python.
# Real `pipeline.rl_royale --smoke` of that yaml; SMOKE PASS or exit non-zero. Starts no chain, writes only under
# /workspace/stepd/tn_smoke_$RUN.
set -euo pipefail
RUNN=${RUN:?set RUN to the tn_* arm}
CB=/workspace/cb_stepd
O=/workspace/stepd/tn_smoke_$RUNN
PY=/workspace/venvf15/bin/python
Y=scratchpad/gauntlet/L74/stepd/cfg/$RUNN.yaml
mkdir -p "$O"
cd "$CB"
unset ROYALE_HEROIW_PRESS
export PYTHONPATH=$CB ROYALE_RUNTIME=fin15-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
sha256sum "$Y" > "$O/yaml.sha"
echo "$(date -u +%FT%TZ) smoke start pid $$ run $RUNN rt fin15-linux" >> "$O/status.log"
flock /workspace/cpu.lock "$PY" -m pipeline.rl_royale --config "$Y" --run smoke_$RUNN --smoke \
  critic_warmup_updates=1 > "$O/smoke.log" 2>&1
grep -q 'SMOKE PASS' "$O/smoke.log"
touch "$O/SMOKE_OK"
echo "$(date -u +%FT%TZ) SMOKE PASS $RUNN" | tee -a "$O/status.log"
