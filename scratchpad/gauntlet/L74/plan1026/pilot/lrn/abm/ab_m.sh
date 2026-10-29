#!/bin/bash
# LEARNER-SCALE3 SIM A/B (SCALE.md 7c): matches per update M 128 (E 32) vs 1,024 (E 256), G 4, at EQUAL updates, 2 seeds;
# then the SIM win rate of every arm's final checkpoint (and B0) vs the training pool on common eval seeds.
# Pattern = LOOP-ASYNC async/ab_queue.sh (ref_pilot_noiw, critic warm-up 1, fastloop + serve.py eager), on pod 33553.
# usage (33553): setsid nohup bash ab_m.sh > /workspace/abm/ab_m.out 2>&1 < /dev/null &
#   env: U (updates, 8), SEEDS ("1028 2029"), EVSEEDS ("7001 7002"; empty = no eval), ES (arm E list, "32 256"), EVE (eval E, 256), FA, XO
U=${U:-8}; SEEDS=${SEEDS:-"1028 2029"}; EVSEEDS=${EVSEEDS-"7001 7002"}; ES=${ES:-"32 256"}; EVE=${EVE:-256}
FA=${FA:-"--producers 4 --matches 128 --threads 4 --devices cuda:0 --server eager"}
CB=/workspace/abm/cb; L=scratchpad/gauntlet/L74/plan1026/pilot/loop; OUT=/workspace/abm/out; CK=$CB/icebow/data/bench/rl_royale
CFG=$L/ref_pilot_noiw.yaml
B0=icebow/data/bench/rl_royale/b0/b0_clxiii_s3aux_grafted.pt
export PY=/workspace/venv/bin/python
O="G=4 critic_warmup_updates=1 n_actors=2 proagree_every=1000 screen_entries=2 ${XO:-}"
mkdir -p $OUT; cd $CB || exit 1
rssb() { awk '/^total_rss |^total_shmem /{s+=$2} END{print s}' /sys/fs/cgroup/memory/memory.stat; }   # rss + shmem (usage_in_bytes counts ~35 GB page cache)
mem() { echo "mem $(( $(rssb) / 1000000000 )) GB gpu $(nvidia-smi --query-gpu=memory.used --format=csv,noheader | head -1)"; }
one() {   # one(RUN, k=v ...): a fastloop run; records deleted as they land (disk); log + .done into OUT
  RUN=$1; shift
  [ -e $OUT/$RUN.done ] && return 0
  REC=$OUT/rec_$RUN; mkdir -p $REC
  echo "$(date +%T) start $RUN $*; $(mem)"
  ( while true; do find $REC -name 'records_u*.pkl' -mmin +0.1 -delete 2>/dev/null; sleep 10; done ) &
  PR=$!
  ( while true; do echo "$(date +%s) $(rssb) $(nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader | head -1 | tr -d ' ')"; sleep 15; done ) > $OUT/$RUN.samples &
  SM=$!
  CB=$CB CFG=$CFG FASTLOOP_RECORDS=$REC FAST_ARGS="$FA --out $OUT/$RUN" bash $L/run.sh fast $RUN 0-47 $O "$@"
  rc=$?
  echo "$(date +%T) end $RUN rc $rc; $(mem)"
  kill $PR $SM
  rm -rf $REC
  cp /workspace/abm/logs/$RUN.log $OUT/ && [ $rc = 0 ] && touch $OUT/$RUN.done
}
# 1. training arms: equal updates U, save every update
for S in $SEEDS; do for E in $ES; do
  one abm_s${S}_e$E E=$E max_updates=$U save_every=1 seed=$S
done; done
# 2. eval: init = the arm's u$U checkpoint (or B0), 1 critic-only update (no policy step) of E 256 x G 4 = 1,024 matches
#    vs the pool; the u0000 W/L/D line is the win rate. Same eval seeds for every checkpoint (common matchups).
UU=$(printf %04d $U)
for V in $EVSEEDS; do
  one abm_ev${V}_b0 E=$EVE max_updates=1 save_every=1 seed=$V init=$B0
  for S in $SEEDS; do for E in $ES; do
    one abm_ev${V}_s${S}_e$E E=$EVE max_updates=1 save_every=1 seed=$V init=icebow/data/bench/rl_royale/abm_s${S}_e$E/abm_s${S}_e${E}_u$UU.pt
  done; done
done
echo "$(date +%T) AB_M DONE"
