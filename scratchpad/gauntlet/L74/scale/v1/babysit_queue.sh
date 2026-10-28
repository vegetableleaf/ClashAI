#!/bin/bash
# babysit_queue.sh [MAX_MIN] -- P4-10M: poll pod 30408's queue (queue.sh) every 5 min for up to MAX_MIN minutes (default 9),
# print one status line per poll, and exit with a code a worker can act on. Idempotent: re-run it after exit 20.
#   exit 0  = the queue printed DONE and no queue.sh is running (a round is complete; stdout says the DONE count)
#   exit 20 = MAX_MIN reached, queue still running normally (just run it again)
#   exit 10 = queue.sh is NOT running and the log does not end in DONE (died or was stopped): diagnostics printed
#   exit 11 = the train_gen / scale_eval process used NO CPU for 15 min (hung): diagnostics printed
#   exit 12 = the queue has waited on "gpu busy" for > 90 min (another tenant holds the GPU): diagnostics printed
#   exit 30 = ssh failed 3 times in a row
# Read-only on the pod. Log (appended): .foreman/scratch/a2/p4/babysit.log ; hang state: .foreman/scratch/a2/p4/cpu_state
MAX=${1:-9}; D=/c/Users/benpe/ClashBot/.foreman/scratch/a2/p4; LOG=$D/babysit.log; ST=$D/cpu_state; mkdir -p $D
SSH="ssh -o BatchMode=yes -o ConnectTimeout=25 -i $HOME/.ssh/runpod_clashbot -p 30408 root@157.157.221.29"
END=$(( $(date +%s) + MAX * 60 )); FAILS=0
# one remote snapshot: n_DONE | last queue.log line | queue pids | train/eval "pid:cpu_ticks" | gpu free MiB | n "gpu busy" lines
SNAP='W=/workspace/p4; nd=$(grep -c "Z DONE" $W/queue.log); last=$(tail -n 1 $W/queue.log);
 qp=$(pgrep -f "scale/v1/[q]ueue.sh" | tr "\n" " ");
 tp=$(pgrep -f "[p]ipeline.train_gen|[s]cale_eval_v1" | head -n 1); tt=""; [ -n "$tp" ] && tt="$tp:$(awk "{print \$14+\$15}" /proc/$tp/stat)";
 gf=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits -i 0);
 echo "$nd|$last|$qp|$tt|$gf"'
diag() { $SSH 'W=/workspace/p4; tail -n 25 $W/queue.log; echo ---; for f in $(ls -t $W/runs/*/train.out $W/runs/*/eval.out 2>/dev/null | head -2); do echo "== $f"; tail -n 8 $f | cut -c1-300; done;
  nvidia-smi --query-gpu=memory.used,memory.free,utilization.gpu --format=csv; ps -eo pid,etimes,args | grep -E "queue.sh|train_gen|scale_eval" | grep -v grep | cut -c1-200'; }
while true; do
  R=$($SSH "$SNAP" 2>/dev/null)
  if [ -z "$R" ]; then FAILS=$((FAILS + 1)); echo "$(date -u +%FT%TZ) ssh fail $FAILS" | tee -a $LOG; [ $FAILS -ge 3 ] && exit 30
  else FAILS=0; IFS='|' read -r ND LAST QP TT GF <<< "$R"; NOW=$(date +%s)
    echo "$(date -u +%FT%TZ) done_count=$ND queue_pids='${QP}' train_cpu=$TT gpu_free=$GF last='$LAST'" | tee -a $LOG
    if [ -z "${QP// /}" ]; then
      case "$LAST" in *" DONE") echo "ROUND COMPLETE: DONE count $ND"; exit 0;; esac
      echo "QUEUE NOT RUNNING and no DONE"; diag; exit 10
    fi
    if [ -n "$TT" ]; then   # hang check: same pid and same cumulative CPU ticks for >= 15 min
      SPID=; [ -f $ST ] && read -r SPID STICK STIME < $ST
      if [ "${SPID:-}:${STICK:-}" = "$TT" ]; then
        [ $((NOW - STIME)) -ge 900 ] && { echo "HUNG: ${TT} unchanged for $((NOW - STIME)) s"; diag; exit 11; }
      else echo "${TT%%:*} ${TT##*:} $NOW" > $ST; fi
    fi
    case "$LAST" in
      *"gpu busy"*) [ -f $D/busy_state ] || echo $NOW > $D/busy_state; B0=$(cat $D/busy_state)
        [ $((NOW - B0)) -ge 5400 ] && { echo "GPU BUSY > 90 min"; diag; exit 12; } ;;
      *) rm -f $D/busy_state ;;
    esac
  fi
  [ $(date +%s) -ge $END ] && exit 20
  sleep 300
done
