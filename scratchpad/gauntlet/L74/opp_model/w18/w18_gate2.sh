#!/bin/bash
# W18 gate watcher v2 (O4 gate v2, owner 10-22: CLX plays WITH its measured live handicap, G2) (pod-local): w14/w14_gate.sh's rule on the W18 eval path. While RUN trains (optC/w7_train.sh OUTD=/workspace/w18),
# evaluate every saved snapshot rlarm_RUN_uNNNN.pt whose update is a multiple of EVERY: CLX vs it at T .1 / decide 40, fin15,
# all16, block 741200 (480 games), via w18_eval.sh (its own eval copy /workspace/w18/o3/cb) under EVLOCK. The snapshot is COPIED
# (sha-checked) into the eval copy as icebow/data/pipeline/o2/w18/. A failed eval (GAP EXIT or != 480 rows) is moved aside and
# retried once. Exits when the run's DONE file exists and every gated snapshot is evaluated.
#   RUN=rlarm_oppW18R1_redirect_s74 YAML=oppW18R1_redirect_s74 [EVERY=5] [EVLOCK=...] bash /workspace/w18/w18_gate.sh
set -uo pipefail
R=${RUN:?}; Y=${YAML:?}; EVERY=${EVERY:-5}
CK=/workspace/cb_stepd/icebow/data/bench/rl_royale/$R
export O3B=/workspace/w18/o3 EVLOCK=${EVLOCK:-/workspace/w18/evalB.lock}
DST=$O3B/cb/icebow/data/pipeline/o2/w18; mkdir -p $DST
CLX=icebow/data/bench/rl_royale/rlarm_stepd_ctrl_nos2/rlarm_stepd_ctrl_nos2_u0130_grafted.pt
L=/workspace/w18/gate2_$R.log
log() { echo "$(date -u +%FT%TZ) $*" >> $L; }
log "start $R every $EVERY"
while :; do
  done_now=0; [ -f /workspace/w18/$Y/DONE ] && done_now=1
  for f in $(ls $CK/${R}_u[0-9][0-9][0-9][0-9].pt 2>/dev/null | sort); do
    u=$(basename $f .pt); u=${u##*_u}; [ $((10#$u % EVERY)) -eq 0 ] && [ $((10#$u)) -gt 0 ] || continue   # u0 = the init: its row set is the baseline run
    N=w18h_${R#rlarm_}_u$u; [ -f $O3B/out/$N/ALL_DONE ] && continue
    sleep 20                                         # let the trainer finish writing the file
    cp $f $DST/ && [ "$(sha256sum < $f)" = "$(sha256sum < $DST/$(basename $f))" ] || { log "COPY FAIL $f"; continue; }
    log "eval $N sha $(sha256sum < $f | cut -c1-12)"
    W18_EXTRA="--tap-loss 1x:0.0180,2x:0.0363,ot2x:0.0388,ot3x:0.0890 --tap-slow 0.151:17" bash /workspace/w18/w18_eval.sh $N $CLX icebow/data/pipeline/o2/w18/$(basename $f) 0.1 40 - 741200
    n=$(cat $O3B/out/$N/${N}_741200/D3/matches.jsonl 2>/dev/null | wc -l)
    if [ "$n" != 480 ] || grep -q "GAP EXIT" $O3B/out/$N/run.log; then
      k=$(ls -d $O3B/out/${N}_FAILED_* 2>/dev/null | wc -l); F=$O3B/out/${N}_FAILED_$k
      mv $O3B/out/$N $F; mv $O3B/out/$N.tgz $O3B/out/$N.tgz.sha $F/ 2>/dev/null
      log "FAIL $N ($n merged rows), attempt $((k + 1)) -> $F"
      [ $k -ge 1 ] && { mkdir -p $O3B/out/$N; touch $O3B/out/$N/ALL_DONE $O3B/out/$N/GAVE_UP; log "GAVE UP $N"; }
    else log "done $N: $n rows"; fi
  done
  if [ $done_now = 1 ]; then log "train DONE and all snapshots gated"; break; fi
  sleep 60
done
