#!/bin/bash
# Laptop-side (10-16): early live-pool reads of T1 checkpoints while training continues. For each U in UPDATES, wait for
# t1_sSEED_uU.pt on the training pod, copy it (sha-verified) to the eval pod, graft + live_eval_pod.sh (0.1.35) there.
#   early_eval.sh SEED SRC_HOST SRC_PORT DST_HOST DST_PORT "150 250 350"
S=$1; SH=$2; SP=$3; DH=$4; DP=$5; UPDATES=$6
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -i $HOME/.ssh/runpod_clashbot"
T=/c/Users/benpe/AppData/Local/Temp/claude/t1_early; mkdir -p $T
R=icebow/data/bench/rl_royale/t1_s$S
for U in $UPDATES; do
  f=t1_s${S}_u$(printf '%04d' $U).pt
  until ssh -n $K -p $SP root@$SH "test -s /workspace/cb_t1/$R/$f" 2>/dev/null; do sleep 300; done; sleep 60
  h=$(ssh -n $K -p $SP root@$SH "sha256sum /workspace/cb_t1/$R/$f" | awk '{print $1}')
  scp -q $K -P $SP root@$SH:/workspace/cb_t1/$R/$f $T/$f && scp -q $K -P $DP $T/$f root@$DH:/workspace/in/$f || { echo "copy failed $f"; continue; }
  [ "$(ssh -n $K -p $DP root@$DH "sha256sum /workspace/in/$f" | awk '{print $1}')" = "$h" ] || { echo "sha mismatch $f"; continue; }
  ssh -n $K -p $DP root@$DH "C=/workspace/cb_par; mkdir -p \$C/$R && cp /workspace/in/$f \$C/$R/$f && cd \$C && export PYTHONPATH=\$C ROYALE_RUNTIME=20261016-linux && /workspace/venv35/bin/python scratchpad/gauntlet/L74/weekend/graft_generic.py $R/$f icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt $R/${f%.pt}_grafted.pt > /workspace/results/graft_$f.log 2>&1 && (CB=\$C RT=20261016-linux PY=/workspace/venv35/bin/python O=/workspace/results/T1EARLY WORKERS=13 setsid nohup bash scratchpad/gauntlet/L74/mix/live_eval_pod.sh none t1_s${S}_u$U $R/${f%.pt}_grafted.pt D3 > /dev/null 2>&1 < /dev/null &)" && echo "$(date +%T) queued eval t1_s${S}_u$U on $DP"
done
