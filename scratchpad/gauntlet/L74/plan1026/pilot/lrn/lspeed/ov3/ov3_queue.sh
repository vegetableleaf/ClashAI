#!/bin/bash
# LEARNER-SPEED overlap A/B v3 on 33903 (= LOOP-ASYNC ab_queue.sh v2, arm-L learner settings): fastloop --overlap 0 vs 1,
# both with ppo_decoupled 2.0; ref_pilot_noiw + E 32 x G 4 (128 matches / update), 8 updates, critic warm-up 1 (256-row
# warm-up steps), minibatch 32768, micro_batch 256 (exact accumulation; 256 for the 6 GB GPU share), lr 2e-5.
# usage: setsid nohup bash ov3_queue.sh "SEEDS" > /workspace/lspeed/logs/ov3.out 2>&1 &
SEEDS=${1:-"1028 2029"}; TAG=v3
CB=/workspace/lspeed/cbo; L=scratchpad/gauntlet/L74/plan1026/pilot/loop; OUT=/workspace/lspeed/ov3; CPUS=146-153
CFG=$L/ref_pilot_noiw.yaml; PY=/workspace/venvf16/bin/python
O="E=32 G=4 max_updates=8 critic_warmup_updates=1 n_actors=2 save_every=1 proagree_every=1000 screen_entries=2 ppo_decoupled=2.0 minibatch=32768 micro_batch=256 lr=2e-5 critic_warmup_minibatch=256 mem_row_cache=true"
export PYTHONPATH=$CB/$L/hook:$CB ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 RL_BATCH_SHA=1 ROYALE_ENGINE=crforge CRFORGE_LIB=/workspace/crforge_main/5e8089a4/plain/lib \
  CRFORGE_TABLES=/workspace/opplearn/tables/16.635.3 CRFORGE_FACADE_BUILD=/workspace/lspeed/jbuild_loop CUBLAS_WORKSPACE_CONFIG=:4096:8
mkdir -p $OUT; cd $CB || exit 1
$PY -c "import sys; sys.path.insert(0, \"$L\"); import producer, pathlib, os; producer.compile_java(pathlib.Path(os.environ[\"CRFORGE_FACADE_BUILD\"]), pathlib.Path(os.environ[\"CRFORGE_LIB\"]))" || exit 1
for S in $SEEDS; do for M in 0 1; do
  RUN=lsp_ov3_s${S}_m$M; REC=$OUT/rec_$RUN
  [ -e $OUT/$RUN.done ] && continue
  mkdir -p $REC
  echo "$(date +%T) start $RUN; mem $(cat /sys/fs/cgroup/memory.current); gpu $(nvidia-smi --query-gpu=memory.used --format=csv,noheader | head -1)"
  ( while true; do find $REC -name "records_u*.pkl" ! -name "records_u0000.pkl" -mmin +0.1 -delete 2>/dev/null; sleep 10; done ) &
  PR=$!
  ( while true; do echo "$(date +%s) $(cat /sys/fs/cgroup/memory.current) $(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader | tr "\n" " ") $(cut -d" " -f1 /proc/loadavg)"; sleep 5; done ) > $OUT/$RUN.samples &
  SM=$!
  FASTLOOP_RECORDS=$REC taskset -c $CPUS $PY -u $L/fastloop.py --producers 2 --matches 64 --threads 4 --devices cuda:0 --server eager --overlap $M --out $OUT/$RUN \
    -- --run $RUN --config $CFG $O seed=$S > $OUT/$RUN.log 2>&1
  echo "$(date +%T) end $RUN rc $?"
  kill $PR $SM
  find $REC -name "records_u*.pkl" ! -name "records_u0000.pkl" -delete
  touch $OUT/$RUN.done
done; done
set -- $SEEDS
if [ $# -ge 2 ]; then
  for S in $SEEDS; do H=$( [ $S = $1 ] && echo $2 || echo $1 )
    taskset -c $CPUS $PY -u $L/async/ab_eval.py --config $CFG --held $OUT/rec_lsp_ov3_s${H}_m0/records_u0000.pkl \
      --arm m0=icebow/data/bench/rl_royale/lsp_ov3_s${S}_m0 --arm m1=icebow/data/bench/rl_royale/lsp_ov3_s${S}_m1 \
      --out $OUT/eval_s$S.json $O seed=$S > $OUT/eval_s$S.log 2>&1
  done
fi
echo "$(date +%T) QUEUE DONE"
