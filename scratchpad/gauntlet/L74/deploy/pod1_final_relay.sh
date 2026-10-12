#!/bin/bash
# Pod-1 final relay (2026-10-12), no Claude usage.
#   cd /c/Users/benpe/ClashBot && nohup bash <this file> > /c/Users/benpe/pod_backup_weekend/pod1_final/relay.log 2>&1 &
# Every 10 min: when /workspace/results/wk/ICEBOW_DONE exists on pod 1 (written after S9XL2b + S10XL2b): stream results/wk (all stage dirs incl.
# CAL, S9XL2b, S10XL2b) + the trained wk_* checkpoint dirs of /workspace/clashbot and /workspace/wk_xl2 -> $OUT, verify (gzip -t + sha256 of
# every member, remote vs laptop).  Then STOP POD 1 only after: copied+verified AND no busy process for two checks 10 min apart.
# NEVER touches any other pod.
cd /c/Users/benpe/ClashBot || exit 1
OUT=/c/Users/benpe/pod_backup_weekend/pod1_final; mkdir -p $OUT
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -i $HOME/.ssh/runpod_clashbot"
S1="ssh $K -p 17497 root@64.247.206.76"
PY=icebow/.venv/Scripts/python.exe
R=/workspace/results/wk
BUSY='[s]earch_s0|[r]l_royale|[f]lock /workspace|[x]l2|[m]ech_fork|[w]k_driver|[r]un_wk|[d]river.py'
log() { echo "$(date '+%F %T') $*"; }
post() { printf '%s\n' "$1" > $OUT/_msg.txt; $PY scratchpad/gauntlet/L69/discord/post.py $OUT/_msg.txt > /dev/null 2>&1 || log "post failed"; }

copy_all() {
  local name=pod1
  $S1 "cd /workspace && tar czf - results/wk clashbot/icebow/data/bench/rl_royale/wk_* wk_xl2/icebow/data/bench/rl_royale/wk_* 2>/dev/null; true" > $OUT/$name.tgz || return 1
  gzip -t $OUT/$name.tgz && rm -rf $OUT/x_$name && mkdir -p $OUT/x_$name && tar xzf $OUT/$name.tgz -C $OUT/x_$name || return 1
  tar tzf $OUT/$name.tgz | grep -v '/$' > $OUT/$name.members && [ -s $OUT/$name.members ] || return 1
  grep -q 'results/wk/S10XL2b/' $OUT/$name.members && grep -q 'results/wk/S9XL2b/' $OUT/$name.members && grep -q 'results/wk/CAL/' $OUT/$name.members || return 1
  $S1 "cd /workspace && while read f; do sha256sum \"\$f\"; done" < $OUT/$name.members | sort -k2 > $OUT/$name.sha.remote || return 1
  (cd $OUT/x_$name && while read f; do sha256sum "$f"; done < $OUT/$name.members | sed 's/ \*/  /' | sort -k2) > $OUT/$name.sha.local || return 1
  cmp -s $OUT/$name.sha.remote $OUT/$name.sha.local && [ -s $OUT/$name.sha.local ]
}

idle=0
while true; do
  if [ ! -e $OUT/COPIED_OK ]; then
    if $S1 "test -e $R/ICEBOW_DONE" 2>/dev/null; then
      if copy_all; then touch $OUT/COPIED_OK; log "pod 1 final copied + verified ($(du -h $OUT/pod1.tgz | cut -f1), $(wc -l < $OUT/pod1.members) files)"
      else log "copy/verify failed; retry in 10 min"; fi
    else log "ICEBOW_DONE not there yet / ssh failed"; fi
  fi
  if [ -e $OUT/COPIED_OK ]; then
    n=$($S1 "pgrep -fc '$BUSY' || true" 2>/dev/null | tr -d '\r')
    if [ -z "$n" ]; then log "ssh failed"
    else
      if [ "$n" = 0 ]; then idle=$((idle+1)); else idle=0; fi
      log "pod 1 busy processes: $n (quiet checks $idle/2)"
      if [ $idle -ge 2 ]; then
        if $S1 'export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)="); runpodctl config --apiKey "$RUNPOD_API_KEY" > /dev/null; runpodctl stop pod "$RUNPOD_POD_ID"'; then
          log "pod 1 stop requested"; post "pod 1 stopped (all of results/wk incl. CAL, S9XL2b, S10XL2b and the wk_* checkpoints copied and verified on the laptop, idle for two checks)"
        else
          log "pod 1 stop FAILED"; post "pod 1 stop FAILED -- please stop it on the RunPod page"
        fi
        exit 0
      fi
    fi
  fi
  sleep 600
done
