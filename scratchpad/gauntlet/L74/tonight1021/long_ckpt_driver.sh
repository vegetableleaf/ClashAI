#!/bin/bash
# long_ckpt_driver.sh UPDATE -- 10-22 (lead, laptop): wait for the long run's u<UPDATE> checkpoint on 32525 (file unchanged
# for 2 min), run ckpt_eval.sh on the SAME pod (owner budget: one pod; the eval's cpu_b lock lets it share the CPU with the
# training run), wait for DONE, pull + sha-verify the tarball into pod_backup_weekend/tonight1021/long/.
# Prints "EVAL_DONE TAG" (or an error) and exits, waking the lead.
U=$(printf %04d $1); R=rlarm_tn_long_e1i_s74; TAG=long_u$U; H=157.157.221.29; P=32525
K="-n -o StrictHostKeyChecking=no -o ConnectTimeout=20 -i $HOME/.ssh/runpod_clashbot"; C="-o StrictHostKeyChecking=no -i $HOME/.ssh/runpod_clashbot"
SRC=/workspace/cb_stepd/icebow/data/bench/rl_royale/$R/${R}_u$U.pt; D=/c/Users/benpe/pod_backup_weekend/tonight1021/long; mkdir -p $D
until timeout 60 ssh $K -p $P root@$H "[ -f $SRC ] && [ \$(( \$(date +%s) - \$(stat -c %Y $SRC) )) -gt 120 ]"; do
  timeout 60 ssh $K -p $P root@$H "pgrep -f $R > /dev/null" || { echo "LONG_DEAD before u$U"; exit 1; }
  sleep 300
done
timeout 60 ssh $K -p $P root@$H "mkdir -p /workspace/ckev/ckpt && cp $SRC /workspace/ckev/ckpt/ && (setsid nohup bash /workspace/ckpt_eval.sh $TAG /workspace/ckev/ckpt/${R}_u$U.pt > /dev/null 2>&1 < /dev/null &)"
until timeout 60 ssh $K -p $P root@$H "[ -f /workspace/ckev/out/$TAG/DONE ]"; do sleep 300; done
cd $D && scp -q $C -P $P root@$H:/workspace/ckev/out/$TAG.tgz root@$H:/workspace/ckev/out/$TAG.tgz.sha root@$H:/workspace/ckev/ckpt/${R}_u$U.pt . \
  && [ "$(sha256sum $TAG.tgz | awk '{print $1}')" = "$(awk '{print $1}' $TAG.tgz.sha)" ] && tar xzf $TAG.tgz && echo "EVAL_DONE $TAG" || echo "EVAL PULL FAIL $TAG"
