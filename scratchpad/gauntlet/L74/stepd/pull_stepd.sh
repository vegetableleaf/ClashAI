#!/bin/bash
# Laptop relay: copy finished step-d jobs (stepd_chain.sh pack -> /workspace/stepd/out/<NAME>.tgz + .sha) back, sha-verified, to
# pod_backup_weekend/stepd/<NAME>/ and mark the pod copy (out/<NAME>.COPIED). Never stops a pod.
#   bash pull_stepd.sh HOST PORT [HOST PORT ...]          one pass (safe to repeat)
#   LOOP=1 bash pull_stepd.sh HOST PORT ...               every 10 min until every listed pod has no unpulled job and LOOP_UNTIL
#                                                         (default 12 jobs pulled) is reached; launch via WMI (Git bin/bash.exe)
LOC=/c/Users/benpe/pod_backup_weekend/stepd; mkdir -p $LOC
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -o StrictHostKeyChecking=no -i $HOME/.ssh/runpod_clashbot"
pass() {
  local a=("$@")
  while [ ${#a[@]} -ge 2 ]; do
    H=${a[0]}; P=${a[1]}; a=("${a[@]:2}")
    for j in $(ssh -n $K -p $P root@$H 'cd /workspace/stepd/out 2>/dev/null && ls *.tgz.sha 2>/dev/null' | sed 's/\.tgz\.sha$//'); do
      [ -e $LOC/$j/COPY_OK ] && cmp -s $LOC/$j.tgz.sha <(ssh -n $K -p $P root@$H "cat /workspace/stepd/out/$j.tgz.sha") && continue
      scp -q $K -P $P root@$H:/workspace/stepd/out/$j.tgz root@$H:/workspace/stepd/out/$j.tgz.sha $LOC/ || { echo "$(date +%T) scp $j failed"; continue; }
      want=$(awk '{print $1}' $LOC/$j.tgz.sha); got=$(sha256sum $LOC/$j.tgz | awk '{print $1}')   # Git-Bash prints "hash *path"
      [ "$want" = "$got" ] || { echo "$(date +%T) SHA MISMATCH $j"; continue; }
      rm -rf $LOC/$j $LOC/rl_$j; tar xzf $LOC/$j.tgz -C $LOC && mv $LOC/rl_$j $LOC/$j && touch $LOC/$j/COPY_OK \
        && ssh -n $K -p $P root@$H "touch /workspace/stepd/out/$j.COPIED" && echo "$(date +%T) copied $j ($H:$P) sha $want"
    done
  done
}
if [ -z "${LOOP:-}" ]; then pass "$@"; exit 0; fi
while :; do
  pass "$@"
  [ "$(ls -d $LOC/*/COPY_OK 2>/dev/null | wc -l)" -ge "${LOOP_UNTIL:-12}" ] && { echo "$(date +%T) all pulled"; exit 0; }
  sleep 600
done
