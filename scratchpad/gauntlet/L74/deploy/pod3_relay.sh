#!/bin/bash
# Pod-3 relay (2026-10-11), no Claude usage.  cd /c/Users/benpe/ClashBot && nohup bash <this file> > /c/Users/benpe/pod_backup_weekend/pod3/relay.log 2>&1 &
# Every 10 min: (a) pull a live copy of pod 3's results/wk (small files, no checkpoints) -> $OUT/results_live.tgz;
#  (b) when ADAPT/DONE (resp. BAIT_CMP/DONE) exists on pod 3: copy the stage (ADAPT: also the wk_adapt_* checkpoint dirs), verify
#      (gzip -t + sha256 of every member, remote vs laptop), post "[weekend ADAPT done]" / "[weekend BAIT_CMP done]" + SUMMARY via post.py;
#  (c) STOP POD 3 only when both stages are done AND copied+verified AND no [s]earch_s0|[r]l_royale|[f]lock /workspace|[d]river.py|[b]ait_base_s0
#      process on pod 3 for two checks 10 min apart.  NEVER touches pod 1's power.
cd /c/Users/benpe/ClashBot || exit 1
OUT=/c/Users/benpe/pod_backup_weekend/pod3; mkdir -p $OUT
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -i $HOME/.ssh/runpod_clashbot"
S3="ssh $K -p 37410 root@81.27.69.179"
PY=icebow/.venv/Scripts/python.exe
R=/workspace/results/wk
BUSY='[s]earch_s0|[r]l_royale|[f]lock /workspace|[d]river.py|[b]ait_base_s0'
log() { echo "$(date '+%F %T') $*"; }
post() { printf '%s\n' "$1" > $OUT/_msg.txt; $PY scratchpad/gauntlet/L69/discord/post.py $OUT/_msg.txt > /dev/null 2>&1 || log "post failed"; }

# copy_stage NAME REMOTE_PATHS...  (paths relative to /workspace)
copy_stage() {
  local name=$1; shift
  $S3 "cd /workspace && tar czf - $* 2>/dev/null; true" > $OUT/$name.tgz || return 1
  gzip -t $OUT/$name.tgz && rm -rf $OUT/x_$name && mkdir -p $OUT/x_$name && tar xzf $OUT/$name.tgz -C $OUT/x_$name || return 1
  tar tzf $OUT/$name.tgz | grep -v '/$' > $OUT/$name.members && [ -s $OUT/$name.members ] || return 1
  $S3 "cd /workspace && while read f; do sha256sum \"\$f\"; done" < $OUT/$name.members | sort -k2 > $OUT/$name.sha.remote || return 1
  (cd $OUT/x_$name && while read f; do sha256sum "$f"; done < $OUT/$name.members | sort -k2) > $OUT/$name.sha.local || return 1
  cmp -s $OUT/$name.sha.remote $OUT/$name.sha.local && [ -s $OUT/$name.sha.local ]
}

summ() { { echo "[weekend $1 done]"; $S3 "cat $R/$1/SUMMARY.txt"; } > $OUT/_summ_$1.txt 2>/dev/null; }

idle=0
while true; do
  $S3 "cd /workspace && tar czf - --exclude='*.pt' --exclude='*.npz' results/wk 2>/dev/null; true" > $OUT/results_live.tmp 2>/dev/null && gzip -t $OUT/results_live.tmp 2>/dev/null && mv $OUT/results_live.tmp $OUT/results_live.tgz
  for st in ADAPT BAIT_CMP; do
    [ -e $OUT/COPIED_$st ] && continue
    if $S3 "test -e $R/$st/DONE" 2>/dev/null; then
      if [ $st = ADAPT ]; then paths="results/wk/ADAPT wk_adapt/icebow/data/bench/rl_royale/wk_adapt_main wk_adapt/icebow/data/bench/rl_royale/wk_adapt_exp1 wk_adapt/icebow/data/bench/rl_royale/wk_adapt_exp2 wk_adapt/icebow/data/bench/rl_royale/wk_adapt_exp3"
      else paths="results/wk/BAIT_CMP"; fi
      if copy_stage $st $paths; then
        touch $OUT/COPIED_$st; log "$st copied + verified ($(du -h $OUT/$st.tgz | cut -f1))"
        summ $st; post "$(cat $OUT/_summ_$st.txt)"
      else log "$st copy/verify failed; retry in 10 min"; fi
    else log "$st not done yet / ssh failed"; fi
  done
  if [ -e $OUT/COPIED_ADAPT ] && [ -e $OUT/COPIED_BAIT_CMP ]; then
    n=$($S3 "pgrep -fc '$BUSY' || true" 2>/dev/null | tr -d '\r')
    if [ -z "$n" ]; then log "ssh failed"
    else
      if [ "$n" = 0 ]; then idle=$((idle+1)); else idle=0; fi
      log "pod 3 busy processes: $n (quiet checks $idle/2)"
      if [ $idle -ge 2 ]; then
        if $S3 'export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)="); runpodctl config --apiKey "$RUNPOD_API_KEY" > /dev/null; runpodctl stop pod "$RUNPOD_POD_ID"'; then
          log "pod 3 stop requested"; post "pod 3 stopped (ADAPT and BAIT_CMP copied and verified on the laptop, idle for two checks)"
        else
          log "pod 3 stop FAILED"; post "pod 3 stop FAILED: please stop it on the RunPod page"
        fi
        exit 0
      fi
    fi
  fi
  sleep 600
done
