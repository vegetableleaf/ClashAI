#!/bin/bash
# long_ckpt_driver.sh UPDATE -- 10-22 (lead, laptop): wait for the long run's u<UPDATE> checkpoint on 32525 (file unchanged for
# 2 min), relay it via the laptop to 32621 (sha-checked), launch ckpt_eval.sh there, wait for its DONE, pull + verify the
# tarball into pod_backup_weekend/tonight1021/long/. Prints "EVAL_DONE TAG" (or an error) and exits, waking the lead.
U=$(printf %04d $1); R=rlarm_tn_long_e1i_s74; TAG=long_u$U; H=157.157.221.29
K="-n -o StrictHostKeyChecking=no -o ConnectTimeout=20 -i $HOME/.ssh/runpod_clashbot"; C="-o StrictHostKeyChecking=no -i $HOME/.ssh/runpod_clashbot"
SRC=/workspace/cb_stepd/icebow/data/bench/rl_royale/$R/${R}_u$U.pt; D=/c/Users/benpe/pod_backup_weekend/tonight1021/long; mkdir -p $D
until timeout 60 ssh $K -p 32525 root@$H "[ -f $SRC ] && [ \$(( \$(date +%s) - \$(stat -c %Y $SRC) )) -gt 120 ]"; do
  timeout 60 ssh $K -p 32525 root@$H "pgrep -f $R > /dev/null" || { echo "LONG_DEAD before u$U"; exit 1; }
  sleep 300
done
scp -q $C -P 32525 root@$H:$SRC $D/ || { echo "PULL FAIL u$U"; exit 2; }
L=$(sha256sum $D/${R}_u$U.pt | awk '{print $1}'); Rm=$(timeout 60 ssh $K -p 32525 root@$H "sha256sum $SRC" | awk '{print $1}')
[ "$L" = "$Rm" ] || { echo "SHA FAIL down u$U"; exit 2; }
timeout 60 ssh $K -p 32621 root@$H "mkdir -p /workspace/ckev/ckpt"
scp -q $C -P 32621 $D/${R}_u$U.pt root@$H:/workspace/ckev/ckpt/ || { echo "PUSH FAIL u$U"; exit 2; }
[ "$(timeout 60 ssh $K -p 32621 root@$H "sha256sum /workspace/ckev/ckpt/${R}_u$U.pt" | awk '{print $1}')" = "$L" ] || { echo "SHA FAIL up u$U"; exit 2; }
timeout 60 ssh $K -p 32621 root@$H "(setsid nohup bash /workspace/ckpt_eval.sh $TAG /workspace/ckev/ckpt/${R}_u$U.pt > /dev/null 2>&1 < /dev/null &)"
until timeout 60 ssh $K -p 32621 root@$H "[ -f /workspace/ckev/out/$TAG/DONE ]"; do sleep 300; done
cd $D && scp -q $C -P 32621 root@$H:/workspace/ckev/out/$TAG.tgz root@$H:/workspace/ckev/out/$TAG.tgz.sha . \
  && [ "$(sha256sum $TAG.tgz | awk '{print $1}')" = "$(awk '{print $1}' $TAG.tgz.sha)" ] && tar xzf $TAG.tgz && echo "EVAL_DONE $TAG" || echo "EVAL PULL FAIL $TAG"
