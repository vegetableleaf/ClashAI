#!/bin/bash
# switch_fast.sh [U] -- POD side (33308), account 3 10-30 (owner: more updates/h, switch at a good checkpoint). Waits for the
# numbered checkpoint pilot_box3_uU.pt (default 0025 = 25 updates done; the run is then starting update U's rollout), stops the
# pilot by exact PIDs (auto_stop.py is kept), saves the log, and resumes from _latest with:
#   - 512 matches / update (32 producers x 16 matches, E=128; was 16 x 128, E=512): KL stop already ends each update after
#     ~29-89 of 512 minibatches (~6-17 % of rows), and SCALE.md 6f/7g: 128 vs 1,024 matches/update not resolvably different
#     per update -> ~4x updates / h at ~the same movement per update (b);
#   - serve.py --server graphs (SPEED2 F1: 1.65x rows/s per server, LOOP-SRV lp_cell <= 7.6e-6, identical actions);
#   - JVM per 16-match producer: CRFORGE_XMX=450m, SerialGC, ActiveProcessorCount=4 (SPEED2 section 2: -26 % memory).
# Old command = RESTORE below. Log: /workspace/loop/pilot/pilot_box3/switch_fast.log.
U=${1:-0025}; R=pilot_box3; CB=/workspace/loop/cb; O=/workspace/loop/pilot/$R; CK=$CB/icebow/data/bench/rl_royale/$R
cd $CB || exit 1
until [ -f $CK/${R}_u$U.pt ]; do sleep 15; done
sleep 20                                                    # let the save (numbered + _latest) finish
echo "$(date -u +%FT%TZ) u$U present; _latest $(stat -c %y $CK/${R}_latest.pt)"
P=$(ps -eo pid,args | grep "[v]envf16" | grep -v auto_stop | awk '{print $1}' | tr '\n' ' ')
echo "killing $P"; kill $P; sleep 20
L=$(ps -eo pid,args | grep "[v]envf16" | grep -v auto_stop | awk '{print $1}' | tr '\n' ' ')
[ -n "$L" ] && { echo "SIGKILL leftovers $L"; kill -9 $L; sleep 5; }
rm -f $O/STOP $O/FINAL $CB/scratchpad/gauntlet/L68/rl/$R/STOP
cp /workspace/loop/logs/$R.log /workspace/loop/logs/$R.33308b_u$U.log         # run.sh truncates the log
export CUDA_VISIBLE_DEVICES=0,1 CFG=scratchpad/gauntlet/L74/plan1026/pilot/ops/pilot.yaml CF_LIB=/workspace/crforge_main/5e8089a4/plain/lib \
  FACADE_BUILD=$CB/scratchpad/gauntlet/L74/plan1026/pilot/loop/jbuild_5e8089a4 CRFORGE_XMX=450m \
  JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=4" \
  FAST_ARGS="--producers 32 --matches 16 --threads 2 --devices cuda:0,cuda:1 --server graphs --out $O"
setsid nohup bash scratchpad/gauntlet/L74/plan1026/pilot/loop/run.sh fast $R 0-127 E=128 n_actors=4 save_every=5 \
  memory_encoder_frozen=false --resume > /workspace/loop/logs/$R.launch 2>&1 < /dev/null &
echo "$(date -u +%FT%TZ) relaunched (512 / update, graphs, SerialGC 450m)"
# RESTORE (the pre-switch command): FAST_ARGS="--producers 16 --matches 128 --threads 4 --devices cuda:0,cuda:1 --server eager
#   --out $O", no CRFORGE_XMX / JAVA_TOOL_OPTIONS, run.sh ... E=512 (same other args, --resume).
