#!/bin/bash
# simprice_run.sh RUN CPUS N_ACTORS [rl_royale k=v overrides...] -- SIMPRICE incentive audit on pod 33903 (/workspace/simprice).
# Config = pilot2.yaml (the pilot2 opponent pool, sampled gate T_gate .1, CLXIII's press head kept: ability_head_from_init, init
# p2init = b0_full_v2_tgt.pt cdde779a) with the policy FIXED (critic_warmup_updates = max_updates), learner on CPU, the speed
# keys off (learner-only). Engine: crforge 5e8089a4 plain lib (core bd1be8f1 = the lead's SIM gate lib) + facade c003fc74
# (/workspace/pgate/facade) + tables 16.635.3. Fork triggers: iw_pressed (every press) / iw_press (held buttons) + the Rocket
# family. Returns at once (setsid); log logs/RUN.log, samples logs/RUN.jsonl (CF_DUMP), memwatch kills only this run's tree if
# the shared 125 GB cgroup passes GUARD_GB (default 118; memory.current counts page cache).
set -e
RUN=$1; CPUS=$2; NA=$3; shift 3
W=/workspace/simprice; cd $W/cb
mkdir -p $W/logs
unset ROYALE_HEROIW_PRESS
export PYTHONPATH=$W/cb ROYALE_RUNTIME=fin16-linux ROYALE_ENGINE=crforge ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 RL_BATCH_SHA=1 CRFORGE_BARREL_DECOY_SIM=1 CRFORGE_XMX=1g \
  CRFORGE_LIB=/workspace/crforge_main/5e8089a4/plain/lib CRFORGE_TABLES=/workspace/crforge_cache/tables/16.635.3 \
  CRFORGE_FACADE_BUILD=/workspace/pgate/facade JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1" \
  CF_DUMP=$W/logs/$RUN.jsonl
CFP=${CFP:-"{iw_pressed: 1.0, iw_press: 0.03, rocket_played: 1.0, rocket: 0.01, wincon: 0.05, rocket_tornado: 0.3, rocket_cycle: 0.5, tornado_redirect: 0.004, xbow_after_fail: 0.05, siege: 0.0, xbow: 0.0, idle_full: 0.0, log_bait: 0.0, random: 0.0}"}
MAXU=${MAXU:-2}
setsid nohup taskset -c $CPUS timeout ${TIMEOUT_S:-28800} /workspace/venvf16/bin/python -u -m pipeline.rl_royale --run $RUN \
  --config scratchpad/gauntlet/L74/plan1026/pilot2/pilot2.yaml \
  max_updates=$MAXU critic_warmup_updates=$MAXU n_actors=$NA in_flight=2 actor_timeout_s=14400 E=${E:-32} G=${G:-4} \
  learner_device=cpu critic_warmup_minibatch=4096 ppo_epochs=1 trunk_graph=null mem_row_cache=null split_attn=null \
  ppo_decoupled=null stored_values=null screen_every=1000 screen_entries=1 "screen_seeds=[0]" proagree_every=1000 proagree_rows=200 save_every=1000 \
  cf_credit=true cf_diag=true cf_rocket_empty=true cf_rocket_lead=drift cf_alt_afford=true cf_redirect_king_tiles=9.0 cf_max_alts=4 \
  cf_horizon_ticks=900 "cf_horizon_sweep=[150,300,450,600]" cf_audit_p=0.3 cf_cap_ticks=60000 "cf_p=$CFP" \
  "$@" < /dev/null > $W/logs/$RUN.log 2>&1 &
for i in $(seq 1 20); do
  sleep 1
  PID=$(pgrep -n -f "python -u -m pipeline.rl_royale --run $RUN( |\$)" || true)
  [ -n "$PID" ] && break
done
[ -z "$PID" ] && { echo "run $RUN did not start"; tail -5 $W/logs/$RUN.log; exit 1; }
setsid nohup python3 $W/memwatch.py $W/logs/$RUN.mem.tsv $PID 1e9 ${GUARD_GB:-118} 10 < /dev/null > /dev/null 2>&1 &
echo "started $RUN root pid $PID"
