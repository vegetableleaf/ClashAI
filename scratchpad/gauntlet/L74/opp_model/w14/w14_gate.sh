#!/bin/bash
# W14 gate watcher (pod-local; OPP_MODEL.md section 8). While RUN trains (w7_train.sh OUTD=/workspace/w14), evaluate every
# saved snapshot rlarm_RUN_uNNNN.pt: CLX vs it at T .1 / decide 40, fin15, all16, block 741200 (480 games) via
# opp_eval_fin15.sh (O3B=/workspace/o3w12 = its patched hard-link copy of cb_stepd) under EVLOCK=/workspace/w14/eval.lock, so
# the evals run beside the training job (which holds /workspace/cpu.lock). Exits when the run's DONE file exists and every
# snapshot is evaluated. Each snapshot is COPIED (cp, sha-checked) into the eval copy as icebow/data/pipeline/o2/w14/.
#   RUN=rlarm_oppW14A_lr3_s74 YAML=oppW14A_lr3_s74 setsid nohup bash /workspace/w14/w14_gate.sh > /dev/null 2>&1 < /dev/null &
# EVERY=5 (default): gate snapshots whose update is a multiple of EVERY.
set -uo pipefail
R=${RUN:?}; Y=${YAML:?}; EVERY=${EVERY:-5}
CK=/workspace/cb_stepd/icebow/data/bench/rl_royale/$R
export O3B=/workspace/o3w12 EVLOCK=/workspace/w14/eval.lock
DST=$O3B/cb/icebow/data/pipeline/o2/w14; mkdir -p $DST /workspace/w14
CLX=icebow/data/bench/rl_royale/rlarm_stepd_ctrl_nos2/rlarm_stepd_ctrl_nos2_u0130_grafted.pt
L=/workspace/w14/gate_$R.log
log() { echo "$(date -u +%FT%TZ) $*" >> $L; }
log "start $R every $EVERY"
while :; do
  done_now=0; [ -f /workspace/w14/$Y/DONE ] && done_now=1
  for f in $(ls $CK/${R}_u[0-9][0-9][0-9][0-9].pt 2>/dev/null | sort); do
    u=$(basename $f .pt); u=${u##*_u}; [ $((10#$u % EVERY)) -eq 0 ] || continue
    N=w14_${R#rlarm_}_u$u; [ -f $O3B/out/$N/ALL_DONE ] && continue
    sleep 20                                         # let the trainer finish writing the file
    cp $f $DST/ && [ "$(sha256sum < $f)" = "$(sha256sum < $DST/$(basename $f))" ] || { log "COPY FAIL $f"; continue; }
    log "eval $N sha $(sha256sum < $f | cut -c1-12)"
    bash /workspace/w14/opp_eval_fin15.sh $N $CLX icebow/data/pipeline/o2/w14/$(basename $f) 0.1 40 - 741200
    log "done $N: $(cat $O3B/out/$N/${N}_741200/D3/matches.jsonl 2>/dev/null | wc -l) merged rows; tgz $(ls $O3B/out/$N.tgz 2>/dev/null)"
  done
  if [ $done_now = 1 ]; then log "train DONE and all snapshots gated"; break; fi
  sleep 60
done
