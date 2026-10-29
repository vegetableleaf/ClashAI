#!/bin/bash
# LEARNER-SCALE3 A/B eval part (= ab_m.sh step 2) on 33920, so the evals run while 33553 still trains the last arm.
# Tree /dev/shm/abm/cb (setup: SCALE.md 7f). The arms' u0008 checkpoints are copied into $CK/abm_s*_e*/ first.
# usage: CKS="b0 s1028_e32 ..." setsid nohup bash eval_m.sh >> /dev/shm/abm/eval_m.out 2>&1 < /dev/null &
#   A checkpoint missing at its turn is waited for (up to 4 h), so the last arm can be queued before it exists.
EVSEEDS=${EVSEEDS:-"7001 7002"}; CKS=${CKS:-"b0 s1028_e32 s1028_e256 s2029_e32 s2029_e256"}; EVE=${EVE:-256}
FA=${FA:-"--producers 4 --matches 128 --threads 4 --devices cuda:0 --server eager"}
CB=/dev/shm/abm/cb; L=scratchpad/gauntlet/L74/plan1026/pilot/loop; OUT=/dev/shm/abm/out; CK=icebow/data/bench/rl_royale
CFG=$L/ref_pilot_noiw.yaml
export PY=/workspace/venvf16/bin/python
O="G=4 critic_warmup_updates=1 n_actors=2 proagree_every=1000 screen_entries=2"
mkdir -p $OUT; cd $CB || exit 1
one() {
  RUN=$1; shift
  [ -e $OUT/$RUN.done ] && return 0
  REC=$OUT/rec_$RUN; mkdir -p $REC
  echo "$(date +%T) start $RUN $*"
  ( while true; do find $REC -name 'records_u*.pkl' -mmin +0.1 -delete 2>/dev/null; sleep 10; done ) &
  PR=$!
  CB=$CB CFG=$CFG FASTLOOP_RECORDS=$REC FAST_ARGS="$FA --out $OUT/$RUN" bash $L/run.sh fast $RUN 0-47 $O "$@"
  rc=$?
  echo "$(date +%T) end $RUN rc $rc"
  kill $PR
  rm -rf $REC
  cp /dev/shm/abm/logs/$RUN.log $OUT/ && [ $rc = 0 ] && touch $OUT/$RUN.done
}
for C in $CKS; do
  if [ $C = b0 ]; then P=$CK/b0/b0_clxiii_s3aux_grafted.pt; else P=$CK/abm_$C/abm_${C}_u0008.pt; fi
  for i in $(seq 1 480); do [ -s $P ] && break; sleep 30; done
  for V in $EVSEEDS; do one abm_ev${V}_$C E=$EVE max_updates=1 save_every=1 seed=$V init=$P; done
done
echo "$(date +%T) EVAL_M DONE"
