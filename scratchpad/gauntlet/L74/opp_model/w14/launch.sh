#!/bin/bash
# W14 launcher (laptop, Git Bash): install + start one W14 opponent-training arm and its gate watcher on a pod.
#   [EVERY=5] bash scratchpad/gauntlet/L74/opp_model/w14/launch.sh PORT YAML [WAIT_RUN]   (EVERY = gate every N updates)
#     PORT 48148 (root@64.247.206.80) | 19899 (root@64.247.206.76); YAML = a name under opp_model/cfg (no .yaml)
#     WAIT_RUN = the pod's own chain that must show ALL_DONE first (e.g. tn_base_s79); refuses if rl_royale / gap.py run.
# Copies (sha-checked): the yaml, R6 u20 as cb_stepd/icebow/data/pipeline/o2/w14/r6u20.pt,
# O2b (kl_ref_gate) + CLIX when the pod lacks them, w7_train.sh / opp_eval_fin15.sh / w14_gate.sh into /workspace/w14/.
# Starts: flock -s claim.lock (SHARED: two W14 arms per pod; exclusive claimers such as stepd_chain wait) w7_train.sh
# (smoke, then training; OUTD=/workspace/w14, venvf15, fin15-linux, its own TLOCK instead of cpu.lock) + w14_gate.sh.
set -uo pipefail
PORT=$1; Y=$2; WAIT=${3:-}
case $PORT in 48148) H=root@64.247.206.80 ;; 19899) H=root@64.247.206.76 ;; 40116) H=root@213.192.2.123 ;; *) echo "unknown port"; exit 2 ;; esac
KEY=$HOME/.ssh/runpod_clashbot; R=/c/Users/benpe/ClashBot; L=scratchpad/gauntlet/L74/opp_model; CB=/workspace/cb_stepd
on() { ssh -i $KEY -p $PORT $H "$@"; }
put() {  # LOCAL REMOTE: copy to a temp name, then an atomic mv (a running bash keeps reading the old inode) + sha check
  scp -q -i $KEY -P $PORT "$1" $H:"$2.w14tmp" && on "mv $2.w14tmp $2" || { echo "SCP FAIL $1"; exit 3; }
  [ "$(sha256sum "$1" | awk '{print $1}')" = "$(on "sha256sum $2" | awk '{print $1}')" ] || { echo "SHA FAIL $2"; exit 3; }
}
if [ -n "$WAIT" ]; then on "grep -q ALL_DONE /workspace/stepd/rl_$WAIT/chain.log" || { echo "$WAIT not ALL_DONE"; exit 1; }; fi
on "ps -eo args | grep -E 'rl_royale|gap\.py|stepd_chain' | grep -v -e grep -e oppW14" && { echo "BUSY"; exit 1; }   # a W14 arm is fine
on "mkdir -p /workspace/w14 $CB/icebow/data/pipeline/o2/w14 $CB/$L/w14 $CB/$L/cfg"
put $R/$L/cfg/$Y.yaml $CB/$L/cfg/$Y.yaml
put $R/$L/optC/w7_train.sh /workspace/w14/w7_train.sh
put $R/$L/pod/opp_eval_fin15.sh /workspace/w14/opp_eval_fin15.sh
put $R/$L/w14/w14_gate.sh /workspace/w14/w14_gate.sh
put $R/$L/w14/decks_live_train_beat3.json $CB/$L/w14/decks_live_train_beat3.json   # round 3 (oppW14E)
put /c/Users/benpe/pod_backup_weekend/w7/rlarm_oppC6_gate_s74_u0020.pt $CB/icebow/data/pipeline/o2/w14/r6u20.pt
on "mkdir -p /workspace/o3w12/cb/icebow/data/pipeline/o2/w14 && cp $CB/icebow/data/pipeline/o2/w14/r6u20.pt /workspace/o3w12/cb/icebow/data/pipeline/o2/w14/r6u20.pt"   # for eval probes
for f in icebow/data/pipeline/o2/gen_live_b.pt icebow/data/bench/rl_royale/rlarm_gae_cue_ab2/rlarm_gae_cue_ab2_u0065_grafted.pt; do
  on "test -f $CB/$f" || { on "mkdir -p $CB/$(dirname $f)"; put $R/$f $CB/$f; echo "installed $f"; }
done
on "cd $CB && sha256sum \$(sed -n 's/^init: //p; s/^kl_ref_gate: //p; s/^- \(icebow.*\.pt\)$/\1/p' $L/cfg/$Y.yaml)" || { echo "MISSING INPUT"; exit 3; }
on "RUN=$Y OUTD=/workspace/w14 VENV=/workspace/venvf15 RT=fin15-linux SMOKE_EXTRA=outlived_pp=100 TLOCK=/workspace/w14/train_$Y.lock setsid nohup flock -s /workspace/stepd/claim.lock bash /workspace/w14/w7_train.sh > /dev/null 2>&1 < /dev/null &
    RUN=rlarm_$Y YAML=$Y EVERY=${EVERY:-5} setsid nohup bash /workspace/w14/w14_gate.sh > /dev/null 2>&1 < /dev/null & sleep 3; echo started; ps -eo pid,args | grep -E 'w7_train|w14_gate' | grep -v grep"
