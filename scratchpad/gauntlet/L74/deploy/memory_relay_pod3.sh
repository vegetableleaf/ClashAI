#!/bin/bash
# Match-memory relay, pod 3 only (seed B), 2026-10-12. Replaces memory_relay.sh after pod 3 was reset (new container, port 37681);
# pod 4 (seed A) is finished and stopped. No Claude usage.
#   cd /c/Users/benpe/ClashBot && nohup bash scratchpad/gauntlet/L74/deploy/memory_relay_pod3.sh >> /c/Users/benpe/pod_backup_weekend/memory/relay.log 2>&1 &
# Every 10 min:
#  (a) live copy of results/wk (small files only) -> memory/pod3/results_live.tgz
#  (b) each MEMP<n>/DONE not yet marked memory/pod3/COPIED_MEMP<n>: copy that phase (results + its checkpoints), verify
#      (gzip -t + sha256 of every member, pod vs laptop), post "[weekend MEMP<n> done]" + "seed B" + SUMMARY.txt via post.py.
#      MEMP1/MEMP2 already have COPIED_ markers, so they are not re-copied or re-posted.
#  (c) STOP the pod only when its chain is over (MEMP4 DONE, or a phase DONE without SUCCESS), every DONE phase is copied+verified,
#      ADAPT + BAIT_CMP are marked copied (pod_backup_weekend/pod3) and no chain process ran for two checks 10 min apart.
# NEVER touches pod 1 or any other pod.
cd /c/Users/benpe/ClashBot || exit 1
BASE=/c/Users/benpe/pod_backup_weekend/memory
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -i $HOME/.ssh/runpod_clashbot"
PY=icebow/.venv/Scripts/python.exe
R=/workspace/results/wk
CK=cb_memory/icebow/data/bench/rl_royale
BUSY='[r]un_memory|[d]river.py|[r]l_royale|[s]earch_s0|[d]ataset_gen|[t]rain_memory|[f]lock /workspace'
EXCL="--exclude=v4_build_* --exclude=dataset_cache_* --exclude=smoke_cache_*"
mkdir -p $BASE/pod3
declare -A SSHC=([pod3]="ssh $K -p 37681 root@81.27.69.179")
declare -A SEED=([pod3]=B)
declare -A IDLE=([pod3]=0)
declare -A STOPPED=([pod3]=0)
log() { echo "$(date '+%F %T') $*"; }
post() { printf '%s\n' "$1" > $BASE/_msg.txt; $PY scratchpad/gauntlet/L69/discord/post.py $BASE/_msg.txt > /dev/null 2>&1 || log "post failed"; }

# copy_stage POD NAME PATHS...  (relative to /workspace; symlinks followed; spool/cache excluded)
copy_stage() {
  local pod=$1 name=$2; shift 2; local S="${SSHC[$pod]}" O=$BASE/$pod
  $S "cd /workspace && tar chzf - $EXCL $* 2>/dev/null; true" > $O/$name.tgz || return 1
  gzip -t $O/$name.tgz && rm -rf $O/x_$name && mkdir -p $O/x_$name && tar xzf $O/$name.tgz -C $O/x_$name || return 1
  tar tzf $O/$name.tgz | grep -v '/$' > $O/$name.members && [ -s $O/$name.members ] || return 1
  $S "cd /workspace && while read f; do sha256sum \"\$f\"; done" < $O/$name.members | sort -k2 > $O/$name.sha.remote || return 1
  (cd $O/x_$name && while read f; do sha256sum "$f"; done < $O/$name.members | sed 's/ \*/  /' | sort -k2) > $O/$name.sha.local || return 1
  cmp -s $O/$name.sha.remote $O/$name.sha.local && [ -s $O/$name.sha.local ]
}

phase_paths() {   # NAME -> paths to copy
  case $1 in
    MEMP1|MEMP2|MEMP4) echo "results/wk/$1" ;;
    MEMP3) echo "results/wk/MEMP3 $(ls -d /dev/null >/dev/null; echo cb_memory/icebow/data/bench/rl_royale/wk_memory_main cb_memory/icebow/data/bench/rl_royale/wk_memory_exp1 cb_memory/icebow/data/bench/rl_royale/wk_memory_exp2 cb_memory/icebow/data/bench/rl_royale/wk_memory_exp3)" ;;
  esac
}

stop_pod() {
  local pod=$1 S="${SSHC[$1]}"
  if $S 'export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)="); runpodctl config --apiKey "$RUNPOD_API_KEY" > /dev/null; runpodctl stop pod "$RUNPOD_POD_ID"'; then
    log "$pod stop requested"; post "$pod stopped (match memory seed ${SEED[$pod]}: chain over, every finished phase copied and verified on the laptop, idle for two checks)"
  else
    log "$pod stop FAILED"; post "$pod stop FAILED: please stop it on the RunPod page"
  fi
  STOPPED[$pod]=1
}

while true; do
  for pod in pod3; do
    [ ${STOPPED[$pod]} = 1 ] && continue
    S="${SSHC[$pod]}"; O=$BASE/$pod
    $S "cd /workspace && tar chzf - --exclude='*.pt' --exclude='*.npz' $EXCL results/wk 2>/dev/null; true" > $O/results_live.tmp 2>/dev/null && gzip -t $O/results_live.tmp 2>/dev/null && mv $O/results_live.tmp $O/results_live.tgz
    over=0; allcopied=1; any=0
    for n in 1 2 3 4; do
      st=MEMP$n
      state=$($S "test -e $R/$st/DONE && { test -e $R/$st/SUCCESS && echo OK || echo FAILED; } || echo NO" 2>/dev/null | tr -d '\r')
      [ -z "$state" ] && { log "$pod ssh failed"; allcopied=0; over=0; break; }
      [ "$state" = NO ] && { [ $n = 4 ] || true; continue; }
      any=1
      [ "$state" = FAILED ] && over=1
      [ "$n" = 4 ] && [ "$state" = OK ] && over=1
      if [ ! -e $O/COPIED_$st ]; then
        if copy_stage $pod $st $(phase_paths $st); then
          touch $O/COPIED_$st; log "$pod $st copied + verified ($(du -h $O/$st.tgz | cut -f1))"
          { echo "[weekend $st done]"; echo "seed ${SEED[$pod]}"; [ "$state" = FAILED ] && echo "(phase FAILED)"; $S "cat $R/$st/SUMMARY.txt"; } > $O/_summ_$st.txt 2>/dev/null
          post "$(cat $O/_summ_$st.txt)"
        else log "$pod $st copy/verify failed; retry in 10 min"; allcopied=0; fi
      fi
    done
    if [ $over = 1 ] && [ $allcopied = 1 ]; then
      ok=1
      if [ $pod = pod3 ]; then [ -e $BASE/../pod3/COPIED_ADAPT ] && [ -e $BASE/../pod3/COPIED_BAIT_CMP ] || ok=0; fi
      if [ $ok = 1 ]; then
        c=$($S "pgrep -fc '$BUSY' || true" 2>/dev/null | tr -d '\r')
        if [ -z "$c" ]; then log "$pod ssh failed"
        else
          if [ "$c" = 0 ]; then IDLE[$pod]=$((IDLE[$pod]+1)); else IDLE[$pod]=0; fi
          log "$pod chain over, busy processes: $c (quiet checks ${IDLE[$pod]}/2)"
          [ ${IDLE[$pod]} -ge 2 ] && stop_pod $pod
        fi
      else log "$pod chain over; waiting for ADAPT/BAIT_CMP copies"; IDLE[$pod]=0; fi
    else IDLE[$pod]=0; fi
  done
  [ ${STOPPED[pod3]} = 1 ] && exit 0
  sleep 600
done
