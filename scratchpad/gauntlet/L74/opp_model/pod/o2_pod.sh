#!/bin/bash
# O2 on a pod (GPU): fine-tune gen_v32_s0 on O1's opponent-seat live rows, 2 seeds (the seed gap is the noise yardstick).
#   setsid nohup bash /workspace/o2/o2_pod.sh > /dev/null 2>&1 < /dev/null &
# Needs /workspace/o2/{o2_finetune.py, o1_train_v32.npz, o1_holdout_v32.npz} (laptop relay, sha-checked against o1_v32.sha) and
# /workspace/cb_stepd (pipeline code + icebow/data/pipeline/gen_v32_s0/gen_s0.pt). Output /workspace/o2/out + o2_out.tgz(.sha).
set -uo pipefail
B=/workspace/o2; PY=/workspace/venvf13/bin/python; INIT=icebow/data/pipeline/gen_v32_s0/gen_s0.pt
exec >> $B/run.log 2>&1
log() { echo "$(date -u +%FT%TZ) $*"; }
trap 'log exit' EXIT
cd /workspace/cb_stepd || exit 2
export PYTHONPATH=/workspace/cb_stepd PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
sha256sum $INIT $B/o1_train_v32.npz $B/o1_holdout_v32.npz $B/o2_finetune.py > $B/inputs.sha
for S in 0 1; do
  log "seed $S"
  $PY $B/o2_finetune.py --init $INIT --train $B/o1_train_v32.npz --val $B/o1_holdout_v32.npz --out-dir $B/out --seed $S \
      --epochs ${EPOCHS:-10} --lr ${LR:-3e-5} > $B/seed$S.log 2>&1 || log "FINETUNE EXIT $? seed $S"
  tail -1 $B/seed$S.log
done
cd $B && tar czf o2_out.tgz.part out inputs.sha seed*.log && mv o2_out.tgz.part o2_out.tgz && sha256sum o2_out.tgz > o2_out.tgz.sha
touch $B/ALL_DONE; log ALL_DONE
