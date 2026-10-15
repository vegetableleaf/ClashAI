#!/bin/bash
# Overnight 10-14/15 follow-ons to the F1 result (gae +6.77 pp vs r1 deployed, 960 pairs):
#   replicate:  run_rlarm2.sh fresh ARM RUN key=value ...   (a new run of ARM's config with overrides, e.g. seed=75)
#   continue:   run_rlarm2.sh resume ARM RUN N [key=value]  (RUN's own config, --resume to N updates; a replicate:
#               ARM=gae_s76 RUN=rlarm_gae_s76 ... seed=76, its fresh-time override)
# Then graft OLD's heads and score D1 + D3 on the 960 pairs (as run_rlarm.sh). Results /workspace/results/$RUN.
set -Eeuo pipefail
CB=${CB:-/workspace/clashbot}; PY=/workspace/venv33/bin/python; MODE=$1; ARM=$2; RUN=$3; shift 3
RL=icebow/data/bench/rl_royale; OLD=$RL/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt
O=/workspace/results/$RUN; mkdir -p $O
exec >> $O/run.log 2>&1
trap 'echo "exit_code=$?" > $O/DONE' EXIT
cd $CB
export PYTHONPATH=$CB ROYALE_RUNTIME=20261012-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
if [ "$MODE" = fresh ]; then
  $PY scratchpad/gauntlet/L74/rlarms/mkcfg_arms.py $ARM $O/$RUN.yaml
  N=$(grep -E '^max_updates:' $O/$RUN.yaml | awk '{print $2}')
  echo "$(date -u +%T) fresh $RUN ($ARM) overrides: $*"
  ROYALE_HEROIW_FORM=normal flock /workspace/cpu.lock $PY -m pipeline.rl_royale --config $O/$RUN.yaml --run $RUN "$@" > $O/train.log 2>&1
else
  N=$1; shift; CFG=/workspace/results/rlarm_$ARM/rlarm_$ARM.yaml   # extra key=value (e.g. seed=76: a replicate's own seed)
  [ "$RUN" = "rlarm_$ARM" ] || { echo "resume must continue the arm's own run"; exit 2; }
  O=/workspace/results/${RUN}_to$N; mkdir -p $O; exec >> $O/run.log 2>&1
  trap 'echo "exit_code=$?" > $O/DONE' EXIT
  echo "$(date -u +%T) resume $RUN to $N"
  ROYALE_HEROIW_FORM=normal flock /workspace/cpu.lock $PY -m pipeline.rl_royale --config $CFG --run $RUN --resume max_updates=$N "$@" > $O/train.log 2>&1
fi
cp scratchpad/gauntlet/L68/rl/$RUN/train_log.jsonl $O/ || true
CK=$RL/$RUN/${RUN}_u$(printf '%04d' $N).pt; [ -f $CK ] || { echo "no final checkpoint $CK"; exit 3; }
G=${CK%.pt}_grafted.pt
$PY scratchpad/gauntlet/L74/weekend/graft_generic.py $CK $OLD $G > $O/graft.log 2>&1
sha256sum $CK $G > $O/final.sha
for S in 741200 742000; do
  flock /workspace/cpu.lock $PY scratchpad/gauntlet/L74/gap/gap.py --ckpt $CK --out $O/D1_$S --arms D1 --seed-start $S \
    --workers ${WORKERS:-25} > $O/D1_$S.log 2>&1
  flock /workspace/cpu.lock $PY scratchpad/gauntlet/L74/gap/gap.py --ckpt $G --out $O/D3_$S --arms D3 --seed-start $S \
    --workers ${WORKERS:-25} > $O/D3_$S.log 2>&1
done
{ echo "$RUN ($MODE $ARM): final $(cut -c1-16 $O/final.sha | head -1)"
  for d in $O/D?_*/; do echo "== $(basename $d)"; grep -E "^D[0-3]:" $d/SUMMARY.txt; done; } > $O/SUMMARY.txt
echo "$(date -u +%T) done"
