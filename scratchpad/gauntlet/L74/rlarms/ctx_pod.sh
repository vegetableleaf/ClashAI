#!/bin/bash
# C2 / F2 arms (owner 10-15: "Let's try C2/F2, then C1 afterwards"): one change vs arm gae (F1), 2 RL seeds each.
#   ctx_pod.sh ARM SEED [smoke]     ARM = gae_c2 | gae_f2 | gae_f6lo; SEED 74 -> run rlarm_ARM (seed 74 is mkcfg's default, as F1's
#                                   rlarm_gae), else rlarm_ARM_sSEED with seed=SEED (as F1's s75 / s76 replicates).
# smoke: first a `rl_royale --smoke` of the ARM's own config (the verifiers' unchecked item: a real training smoke with the
# new code on); the arm starts only on SMOKE PASS. Then run_rlarm2.sh fresh (train 65 updates, graft OLD's heads, D1 + D3 960 pairs).
set -Eeuo pipefail
ARM=$1; SEED=$2; CB=${CB:-/workspace/clashbot}; PY=${PY:-/workspace/venv33/bin/python}; RT=${RT:-20261012-linux}; R=/workspace/results
mkdir -p $R; exec >> $R/ctx_pod_${ARM}_$SEED.log 2>&1
cd $CB
export PYTHONPATH=$CB ROYALE_RUNTIME=$RT OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
sed -i 's/\r$//' scratchpad/gauntlet/L74/rlarms/*.sh
if [ "${3:-}" = smoke ]; then
  SM=smoke_${ARM}_$SEED; echo "$(date -u +%T) smoke $ARM"
  $PY scratchpad/gauntlet/L74/rlarms/mkcfg_arms.py $ARM $R/$SM.yaml
  flock /workspace/cpu.lock $PY -m pipeline.rl_royale --config $R/$SM.yaml --run $SM --smoke > $R/$SM.out 2>&1 || true
  if ! grep -q "SMOKE PASS" $R/$SM.out 2>/dev/null; then
    echo "$(date -u +%T) SMOKE NOT PASSED -- arm not started"; tail -n 30 $R/$SM.out; touch $R/${SM}_FAILED; exit 3
  fi
  echo "$(date -u +%T) SMOKE PASS"; touch $R/${SM}_OK
fi
if [ "$SEED" = 74 ]; then RUN=rlarm_$ARM; X=(); else RUN=rlarm_${ARM}_s$SEED; X=(seed=$SEED); fi
echo "$(date -u +%T) start $RUN"
CB=$CB bash scratchpad/gauntlet/L74/rlarms/run_rlarm2.sh fresh $ARM $RUN "${X[@]}"
echo "$(date -u +%T) done $RUN"
