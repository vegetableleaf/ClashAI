#!/bin/bash
# Pod-5 (Tornado second-card fix) relay (2026-10-12), no Claude usage.
#   cd /c/Users/benpe/ClashBot && nohup bash <this file> > /c/Users/benpe/pod_backup_weekend/tornado/relay.log 2>&1 &
# Every 10 min: when /workspace/results/wk/TORNADO/DONE exists on pod 5: copy results/wk/TORNADO (minus the 13 GB dataset_cache_*; includes
# icebow/fixed.pt) -> $OUT, verify (gzip -t + sha256 of every member, remote vs laptop), post "[weekend TORNADO done]" + SUMMARY.
# Then STOP POD 5 only after: copied+verified AND no [s]earch_s0|[r]un_tornado_fix|[t]rain_pending|[p]ending_states|[d]river.py|[f]lock /workspace
# process for two checks 10 min apart.  NEVER touches any other pod.
cd /c/Users/benpe/ClashBot || exit 1
OUT=/c/Users/benpe/pod_backup_weekend/tornado; mkdir -p $OUT
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -i $HOME/.ssh/runpod_clashbot"
S5="ssh $K -p 19084 root@64.247.206.120"
PY=icebow/.venv/Scripts/python.exe
R=/workspace/results/wk
BUSY='[s]earch_s0|[r]un_tornado_fix|[t]rain_pending|[p]ending_states|[d]river.py|[f]lock /workspace'
log() { echo "$(date '+%F %T') $*"; }
post() { printf '%s\n' "$1" > $OUT/_msg.txt; $PY scratchpad/gauntlet/L69/discord/post.py $OUT/_msg.txt > /dev/null 2>&1 || log "post failed"; }

copy_stage() {
  local name=TORNADO
  $S5 "cd /workspace && tar czf - --exclude='dataset_cache_*' results/wk/TORNADO 2>/dev/null; true" > $OUT/$name.tgz || return 1
  gzip -t $OUT/$name.tgz && rm -rf $OUT/x_$name && mkdir -p $OUT/x_$name && tar xzf $OUT/$name.tgz -C $OUT/x_$name || return 1
  tar tzf $OUT/$name.tgz | grep -v '/$' > $OUT/$name.members && [ -s $OUT/$name.members ] || return 1
  grep -q 'icebow/fixed.pt$' $OUT/$name.members || return 1
  $S5 "cd /workspace && while read f; do sha256sum \"\$f\"; done" < $OUT/$name.members | sort -k2 > $OUT/$name.sha.remote || return 1
  (cd $OUT/x_$name && while read f; do sha256sum "$f"; done < $OUT/$name.members | sort -k2) > $OUT/$name.sha.local || return 1
  cmp -s $OUT/$name.sha.remote $OUT/$name.sha.local && [ -s $OUT/$name.sha.local ]
}

idle=0
while true; do
  if [ ! -e $OUT/COPIED_OK ]; then
    if $S5 "test -e $R/TORNADO/DONE" 2>/dev/null; then
      if copy_stage; then
        touch $OUT/COPIED_OK; log "TORNADO copied + verified ($(du -h $OUT/TORNADO.tgz | cut -f1))"
        { echo "[weekend TORNADO done]"; cat $OUT/x_TORNADO/results/wk/TORNADO/SUMMARY.txt; } > $OUT/_summ.txt
        post "$(cat $OUT/_summ.txt)"
      else log "copy/verify failed; retry in 10 min"; fi
    else log "TORNADO not done yet / ssh failed"; fi
  fi
  if [ -e $OUT/COPIED_OK ]; then
    n=$($S5 "pgrep -fc '$BUSY' || true" 2>/dev/null | tr -d '\r')
    if [ -z "$n" ]; then log "ssh failed"
    else
      if [ "$n" = 0 ]; then idle=$((idle+1)); else idle=0; fi
      log "pod 5 busy processes: $n (quiet checks $idle/2)"
      if [ $idle -ge 2 ]; then
        if $S5 'export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)="); runpodctl config --apiKey "$RUNPOD_API_KEY" > /dev/null; runpodctl stop pod "$RUNPOD_POD_ID"'; then
          log "pod 5 stop requested"; post "pod 5 stopped (Tornado fix results + fixed checkpoint copied and verified on the laptop, idle for two checks)"
        else
          log "pod 5 stop FAILED"; post "pod 5 stop FAILED: please stop it on the RunPod page"
        fi
        exit 0
      fi
    fi
  fi
  sleep 600
done
