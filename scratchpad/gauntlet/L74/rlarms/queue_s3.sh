#!/bin/bash
# Overnight 10-15 pod queue: wait for a running job's DONE, then run the next step-3 job from a fresh checkout
# (/workspace/cb_s3 from /workspace/in/repo_s3.tgz, data linked from /workspace/clashbot), never touching the running dir.
#   queue_s3.sh WAIT_DIR arm ARM          -> run_rlarm2.sh fresh ARM rlarm_ARM (one change vs arm gae)
#   queue_s3.sh WAIT_DIR audit            -> preflight_a1a2.py audit (IL gen_v1_s0 + r1 grafted), REWARD_ARCHITECTURE 9.3
#   AUD=name puts the audit in /workspace/results/NAME (default AUDIT_A1A2)
set -Eeuo pipefail
W=$1; shift
mkdir -p /workspace/results; exec >> /workspace/results/queue_s3.log 2>&1
echo "$(date -u +%T) queued: $* after $W"
until [ -e $W/DONE ]; do sleep 60; done
C=${CS:-/workspace/cb_s3}; RT=${RT:-/workspace/in/repo_s3.tgz}   # 10-15: CS/RT = a newer checkout (cb_s5, repo_s5.tgz)
if [ ! -d $C/pipeline ]; then
  mkdir -p $C && tar xzf $RT --no-same-owner -C $C
  mkdir -p $C/icebow && ln -sfn /workspace/clashbot/icebow/data $C/icebow/data && ln -sfn /workspace/clashbot/research $C/research
fi
cd $C
sed -i 's/\r$//' scratchpad/gauntlet/L74/rlarms/*.sh
echo "$(date -u +%T) start: $*"
case $1 in
  arm)
    CB=$C bash scratchpad/gauntlet/L74/rlarms/run_rlarm2.sh fresh $2 rlarm_$2 ;;
  audit)
    export PYTHONPATH=$C ROYALE_RUNTIME=20261012-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
    R=/workspace/results; A=${AUD:-AUDIT_A1A2}; mkdir -p $R/$A
    for CK in icebow/data/pipeline/gen_v1_s0/gen_s0.pt icebow/data/bench/rl_royale/newsim_r1/newsim_base_r1_final_grafted.pt; do
      N=$(basename $(dirname $CK))
      flock /workspace/cpu.lock /workspace/venv33/bin/python scratchpad/gauntlet/L74/reward/preflight_a1a2.py audit \
        --out $R/$A/$N --ckpt $CK --matches ${MATCHES:-100} --workers ${WORKERS:-25} > $R/$A/$N.log 2>&1 \
        || echo "AUDIT EXIT $? $N"
    done
    touch $R/$A/DONE ;;
esac
echo "$(date -u +%T) finished: $*"
