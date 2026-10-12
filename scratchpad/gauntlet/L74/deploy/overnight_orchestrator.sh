#!/bin/bash
# Unattended overnight orchestrator (owner asleep 2026-10-12; MuMu open, MAIN account). No Claude calls.
#   cd /c/Users/benpe/ClashBot && nohup bash scratchpad/gauntlet/L74/deploy/overnight_orchestrator.sh > /c/Users/benpe/pod_backup_weekend/overnight/orchestrator.out 2>&1 &
# Flow (all steps logged to $ON/orchestrator.log and posted to Discord with post.py; DRY=1 = offline test, see overnight_dryrun.sh):
#  ladder  : wait for the relay-copied TORNADO summary. candidate -> that model. not candidate -> up to 2 retries ON POD 5 (TORNADO_r1,_r2),
#            train args chosen from the failed gate in the order (c) ordinary play, (a) Tornado share, (b) wins with pipelining (helpers.py);
#            each retry = 960 ON + 960 OFF vs live on the harder opponent. All three fail -> post the summaries, deploy nothing.
#  deploy  : first passing attempt -> icebow/data/bench/rl_royale/tornado_fix/, CKPT_OVERRIDE backup + switch, start_live.sh --check
#            (LIVE_CHECK_PASS or revert), stop any running supervisor between matches, start_live.sh icebow.
#  test    : count completed ladder matches of THAT checkpoint (sha) from new live logs; after 20 write STOP, wait for the supervisor to end,
#            post W/L/D vs the old-model record, fast-play pairs and the Tornado share. Supervisor gone / stalled before 20: post, <=3 restarts.
#  adapt   : (in parallel) when pod 3's ADAPT summary is copied: pass if 960 paired lower bound > -3 pp. Not passing / failed -> post (the next
#            adaptive attempts are already running). Passing -> pod 5 runs the same pending-head fine-tune from the ADAPT final grafted
#            checkpoint (drift < 1%, 8-game smoke), adapt_fixed.pt copied back. After the Tornado test (or at once if nothing was deployed)
#            CKPT_OVERRIDE -> adapt_fixed.pt, --check, restart_live.py; runs until the owner wakes, W/L posted every 10 matches.
#  release : $ON/POD5_RELEASE once the ladder AND the ADAPT branch are resolved + copied (the pod-5 relay then stops pod 5 after 2 idle checks).
# Stop it any time: touch $ON/ORCH_STOP.   Restarting it re-reads state; it does not redo a retry that already exists on the pod.
cd /c/Users/benpe/ClashBot || exit 1
DRY=${DRY:-0}
BK=${BK:-/c/Users/benpe/pod_backup_weekend}
TD=${TD:-$BK/tornado}; P3=${P3:-$BK/pod3}; ON=${ON:-$BK/overnight}
L=${L:-scratchpad/gauntlet/L70/live}
LOGS=${LOGS:-scratchpad/gauntlet/L68/live_reader}
MODELS=${MODELS:-icebow/data/bench/rl_royale}
PY=icebow/.venv/Scripts/python.exe
H="$PY scratchpad/gauntlet/L74/deploy/overnight_helpers.py"
POLL=${POLL:-60}; STEP=${STEP:-15}; GRACE=${GRACE:-900}; STALL=${STALL:-2700}; N=${N:-20}; ADAPT_N=${ADAPT_N:-0}; MAXTRY=3
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -i $HOME/.ssh/runpod_clashbot"
S5="ssh $K -p 19084 root@64.247.206.120"
mkdir -p "$ON"
rm -f $ON/LAST_ATTEMPT $ON/LADDER_DONE $ON/ADAPT_RESOLVED $ON/ADAPT_STATUS $ON/POD5_RELEASE $ON/ORCH_STOP

log() { echo "$(date '+%F %T') $*" >> $ON/orchestrator.log; }
post() {
  local f=$ON/_msg.$BASHPID.$RANDOM; printf '%s\n' "$1" > $f; log "POST: $(printf '%s' "$1" | head -c 400 | tr '\n' ' ')"
  if [ "$DRY" = 1 ]; then { echo "--- $(date +%T)"; cat $f; } >> $ON/discord_dry.log
  else $PY scratchpad/gauntlet/L69/discord/post.py $f > /dev/null 2>&1 || log "post failed"; fi
  rm -f $f
}
jv() { $PY -c 'import json,sys;v=json.loads(sys.argv[1]).get(sys.argv[2],"");print(json.dumps(v) if isinstance(v,(dict,list)) else v)' "$1" "$2"; }
halt_check() { if [ -e $ON/ORCH_STOP ]; then post "[overnight] orchestrator stopped by ORCH_STOP (live and pods left as they are)"; exit 0; fi; }
waitf() { until [ -e "$1" ]; do halt_check; sleep $POLL; done; }
ckpt_path() { case $1 in /*|C:*) echo "$1";; *) echo "C:/Users/benpe/ClashBot/$1";; esac; }
adir() { if [ $1 = TORNADO ]; then echo $TD/x_TORNADO/results/wk/TORNADO; else echo $ON/x_$1/results/wk/$1; fi; }
live_count() { local r; r=$(jv "$($H running)" running); echo "${r:-1}"; }       # failure -> assume running

# ---------------------------------------------------------------- pod 5 (DRY: fixtures under $FAKE_POD/<NAME>/)
copy_stage() {   # name remote-dir : tar, verify (gzip -t, sha256 of every member remote vs laptop), unpack into $ON/x_name
  local name=$1 dir=$2
  $S5 "cd /workspace && tar czf - --exclude='dataset_cache_*' --exclude='*/hard_*/live_*' $dir 2>/dev/null; true" > $ON/$name.tgz || return 1
  gzip -t $ON/$name.tgz && rm -rf $ON/x_$name && mkdir -p $ON/x_$name && tar xzf $ON/$name.tgz -C $ON/x_$name || return 1
  tar tzf $ON/$name.tgz | grep -v '/$' > $ON/$name.members && [ -s $ON/$name.members ] || return 1
  $S5 "cd /workspace && while read f; do sha256sum \"\$f\"; done" < $ON/$name.members | sort -k2 > $ON/$name.sha.remote || return 1
  (cd $ON/x_$name && while read f; do sha256sum "$f"; done < $ON/$name.members | sort -k2) > $ON/$name.sha.local || return 1
  cmp -s $ON/$name.sha.remote $ON/$name.sha.local && [ -s $ON/$name.sha.local ]
}
pod_wait_done() {   # name
  if [ "$DRY" = 1 ]; then waitf $FAKE_POD/$1/SUMMARY.txt; return 0; fi
  until $S5 "test -e /workspace/results/wk/$1/DONE" 2>/dev/null; do halt_check; sleep $POLL; done
}
pod_fetch() {   # name : bring results/wk/name to $ON/x_name (3 tries)
  if [ "$DRY" = 1 ]; then mkdir -p $(adir $1)/icebow; cp -r $FAKE_POD/$1/. $(adir $1)/; return 0; fi
  local t; for t in 1 2 3; do copy_stage $1 results/wk/$1 && { log "$1 copied + verified"; return 0; }; log "copy of $1 failed (try $t)"; sleep 120; done; return 1
}
pod_launch_retry() {   # name train-args
  log "pod 5: launch retry $1 [$2]"
  [ "$DRY" = 1 ] && return 0
  $S5 "nohup bash /workspace/retry/run_retry.sh $1 '$2' > /workspace/retry/$1.out 2>&1 < /dev/null &" || return 1
}
pod_adaptfix() {   # local ADAPT final grafted checkpoint -> $ON/x_ADAPTFIX/results/wk/ADAPTFIX/{adapt_fixed.pt,SUMMARY.txt}
  if [ "$DRY" = 1 ]; then pod_wait_done ADAPTFIX; pod_fetch ADAPTFIX; return 0; fi
  local g=$1 sha rsha
  until $S5 "test -e /workspace/results/wk/TORNADO/DONE" 2>/dev/null; do halt_check; sleep $POLL; done      # TORNADO's training/eval first
  sha=$(sha256sum "$g" | cut -d' ' -f1)
  $S5 "mkdir -p /workspace/adaptfix" && scp $K -P 19084 "$g" root@64.247.206.120:/workspace/adaptfix/adaptive_final_grafted.pt || return 1
  rsha=$($S5 "sha256sum /workspace/adaptfix/adaptive_final_grafted.pt" | cut -d' ' -f1)
  [ "$sha" = "$rsha" ] || { log "adapt ckpt sha mismatch after scp"; return 1; }
  $S5 "nohup bash /workspace/retry/run_adaptfix.sh /workspace/adaptfix/adaptive_final_grafted.pt > /workspace/retry/adaptfix.out 2>&1 < /dev/null &" || return 1
  pod_wait_done ADAPTFIX; pod_fetch ADAPTFIX
}

# ---------------------------------------------------------------- live
live_check() {
  if [ "$DRY" = 1 ]; then [ "${FAKE_CHECK:-pass}" = fail ] && echo FAIL || echo '{"check": "LIVE_CHECK_PASS"}'; return 0; fi
  bash $L/start_live.sh icebow --check 2>&1 | tail -5
}
stop_and_wait() {   # touch STOP; wait <= $1 s for the supervisor to end (never kills)
  touch $L/STOP; local t=0
  while [ "$(live_count)" -gt 0 ] && [ $t -lt ${1:-1800} ]; do halt_check; sleep $STEP; t=$((t+STEP)); done
  [ "$(live_count)" -eq 0 ]
}
live_start() {   # mode(start|restart) why
  log "live $1: $2"
  if [ "$DRY" = 1 ]; then $H fakelive $LOGS $SHA ${FAKE_N:-25} >> $ON/orchestrator.log; return 0; fi
  rm -f $L/STOP
  if [ $1 = start ]; then bash $L/start_live.sh icebow >> $ON/live_start.out 2>&1
  else $PY scratchpad/gauntlet/L74/deploy/restart_live.py "$2" >> $ON/live_start.out 2>&1; fi
}
deploy_model() {   # src tag(tornado|adapt) dstname label  -> 0 and global SHA, or 1 with CKPT_OVERRIDE reverted
  local src=$1 tag=$2 dst=$MODELS/${2}_fix/$3 label=$4 bk=$L/CKPT_OVERRIDE.pre_${2}_backup out
  mkdir -p $MODELS/${tag}_fix; cp "$src" "$dst" || { post "[overnight] $label: could not copy the model; live unchanged"; return 1; }
  SHA=$(sha256sum "$dst" | cut -d' ' -f1)
  [ -e $bk ] || cp $L/CKPT_OVERRIDE $bk
  ckpt_path "$dst" > $L/CKPT_OVERRIDE; log "CKPT_OVERRIDE -> $(cat $L/CKPT_OVERRIDE) (backup $bk)"
  out=$(live_check)
  if ! echo "$out" | grep -q LIVE_CHECK_PASS; then
    cp $bk $L/CKPT_OVERRIDE
    post "[overnight] $label: start_live.sh icebow --check did NOT print LIVE_CHECK_PASS, CKPT_OVERRIDE reverted, live unchanged. Last output: $(echo "$out" | tail -2 | tr '\n' ' ' | head -c 300)"
    return 1
  fi
  UNDO="cp $L/CKPT_OVERRIDE.pre_${tag}_backup $L/CKPT_OVERRIDE; $PY scratchpad/gauntlet/L74/deploy/restart_live.py 'undo $tag'   (or: touch $L/STOP to stop between matches)"
  post "[overnight] $label: live model change. CKPT_OVERRIDE -> $dst (sha256 ${SHA:0:12}), --check LIVE_CHECK_PASS. Undo: $UNDO"
}
live_phase() {   # label target(0 = until ORCH_STOP / broken) first-mode -> PHASE_END=done|broken ; uses SHA
  local label=$1 target=$2 mode=$3 tries=0 last_n=0 need=1 started=0 last_prog=0 c n r now
  T0=$(date +%Y%m%d_%H%M%S); PHASE_END=broken
  while :; do
    halt_check
    if [ $need = 1 ]; then
      if [ $tries -gt $MAXTRY ]; then post "[overnight] $label: live needed more than $MAXTRY restarts, giving up (not retrying). $(( last_n )) matches counted. Undo/inspect: $L/supervisor.log"; return; fi
      live_start $mode "$label" || { post "[overnight] $label: live start returned an error (try $tries)"; tries=$((tries+1)); mode=start; sleep $POLL; continue; }
      started=$(date +%s); last_prog=$started; need=0
    fi
    c=$($H count $LOGS $T0 $SHA); n=$(jv "$c" n); n=${n:-0}; now=$(date +%s)
    if [ "$n" != "$last_n" ]; then
      last_prog=$now
      if [ $((n/10)) -gt $((last_n/10)) ]; then post "$($H summarize "$label (running, $n matches)" "$c")"; fi
      last_n=$n
    fi
    if [ "$target" -gt 0 ] && [ "$n" -ge "$target" ]; then
      touch $L/STOP; stop_and_wait 2400 || post "[overnight] $label: supervisor still running 40 min after STOP (left alone)"
      c=$($H count $LOGS $T0 $SHA $target)
      post "$($H summarize "$label, $target-match test" "$c" old) STOP written; live is stopped. Undo/restart: $UNDO"
      PHASE_END=done; return
    fi
    r=$(live_count)
    if [ "$r" -eq 0 ] && [ $((now-started)) -ge $GRACE ]; then
      tries=$((tries+1)); post "[overnight] $label: live supervisor ended after $n counted matches (restart $tries of $MAXTRY). See $L/supervisor.log"; need=1; mode=start
    elif [ "$r" -gt 0 ] && [ $((now-last_prog)) -ge $STALL ]; then
      tries=$((tries+1)); post "[overnight] $label: no completed match for $((STALL/60)) min ($n counted); stopping between matches and restarting ($tries of $MAXTRY)"
      if stop_and_wait 1800; then need=1; mode=start; else post "[overnight] $label: cannot stop the stalled live; leaving it alone, giving up"; return; fi
    fi
    sleep $POLL
  done
}

# ---------------------------------------------------------------- branches
adapt_branch() {
  waitf $P3/COPIED_ADAPT
  local s=$P3/x_ADAPT/results/wk/ADAPT/SUMMARY.txt a v g
  a=$($H adapt $s); v=$(jv "$a" verdict); log "ADAPT summary: $a"
  case $v in
    pass)
      post "[overnight] ADAPT passes: 960 paired vs old live $(jv "$a" delta) pp, 95% CI [$(jv "$a" lo), $(jv "$a" hi)] (lower bound > -3). Building the pending-head fix on pod 5 from the ADAPT final grafted checkpoint."
      g=$(find $P3/x_ADAPT -name adaptive_final_grafted.pt | head -1)
      if [ -n "$g" ] && pod_adaptfix "$g" && head -1 $(adir ADAPTFIX)/SUMMARY.txt | grep -q '^VERDICT: built'; then
        echo built > $ON/ADAPT_STATUS
        post "[overnight] ADAPT+fix model built and copied: $(adir ADAPTFIX)/adapt_fixed.pt. $(tail -n +3 $(adir ADAPTFIX)/SUMMARY.txt | tr '\n' ' ' | head -c 400)"
      else
        echo fixfailed > $ON/ADAPT_STATUS
        post "[overnight] ADAPT passed but the pending-head fix did not build (see pod 5 /workspace/results/wk/ADAPTFIX and $ON/orchestrator.log). Keeping the current live model."
      fi ;;
    nopass) echo nopass > $ON/ADAPT_STATUS
      post "[overnight] ADAPT did NOT pass: $(jv "$a" delta) pp, 95% CI [$(jv "$a" lo), $(jv "$a" hi)] (needs lower bound > -3). No overnight retry (a rerun is about 10 h). Keeping the Tornado-fix model. The next adaptive attempts are already running: memory seeds A on pod 4 and B on pod 3 both train in the adaptive league with exploiters." ;;
    *) echo failed > $ON/ADAPT_STATUS
      post "[overnight] ADAPT failed or has no readable result ($(head -1 $s 2>/dev/null | head -c 160)). No overnight retry. Keeping the Tornado-fix model. The next adaptive attempts are already running: memory seeds A on pod 4 and B on pod 3 both train in the adaptive league with exploiters." ;;
  esac
  touch $ON/ADAPT_RESOLVED
}
release_watch() {
  until [ -e $ON/LADDER_DONE ] && [ -e $ON/ADAPT_RESOLVED ]; do sleep $POLL; done
  touch $ON/POD5_RELEASE; log "POD5_RELEASE written"; post "[overnight] pod-5 work is finished and copied; the pod-5 relay will stop pod 5 after two idle checks (hard limit: 2 h idle)."
}
gate_lines() { grep -E '^(hard|old)_(on|off): paired|fixed-live|^VERDICT' "$(adir $1)/SUMMARY.txt" 2>/dev/null | cut -c1-170; }
ladder() {   # sets WINNER (attempt name or NONE)
  local name=TORNADO attempt=0 params='{}' v rule nx args r names=(TORNADO)
  waitf $TD/COPIED_OK; waitf $(adir TORNADO)/SUMMARY.txt
  while :; do
    v=$($H verdict $(adir $name)/SUMMARY.txt); log "verdict $name: $v"
    case $(jv "$v" verdict) in
      candidate) WINNER=$name; post "[overnight] $name verdict: candidate. Deploying it to live for the $N-match test."; break ;;
    esac
    rule=$(jv "$v" rule)
    if [ "$(jv "$v" verdict)" = failed ] && [ $attempt -gt 0 ]; then rule=c; fi         # a retry that could not train under the drift cap -> stronger anchor
    if [ "$rule" = none ] || [ $attempt -ge 2 ]; then WINNER=NONE; echo $name > $ON/LAST_ATTEMPT; break; fi   # ended on evidence (not infra)
    attempt=$((attempt+1)); r=TORNADO_r$attempt
    nx=$($H nextparams "$params" $rule); params=$(jv "$nx" params); args=$(jv "$nx" args)
    post "[overnight] $name verdict: $(jv "$v" verdict), failed-gate rule ($rule): $(jv "$v" gates | head -c 300). Retry $attempt on pod 5 as $r with train args [$args]; eval = 960 ON + 960 OFF vs live, harder opponent."
    pod_launch_retry $r "$args" || { post "[overnight] could not launch $r on pod 5; ladder stops, nothing deployed"; WINNER=NONE; break; }
    pod_wait_done $r
    pod_fetch $r || { post "[overnight] $r finished but its copy failed 3 times; ladder stops, nothing deployed (results stay on pod 5)"; WINNER=NONE; break; }
    name=$r; names+=($r)
  done
  if [ "$WINNER" = NONE ]; then
    local m="[overnight] Tornado fix: no attempt passed ($(( ${#names[@]} )) tried). Nothing deployed; live stays as it is. Summaries:"
    for r in "${names[@]}"; do m="$m
== $r"$'\n'"$(gate_lines $r)"; done
    post "$m"
  fi
  echo $WINNER > $ON/LADDER_DONE
}

# ---------------------------------------------------------------- main
log "orchestrator start pid $$ dry=$DRY"
post "[overnight] orchestrator armed (pid $$). Waits for the Tornado verdict; retry ladder on pod 5 if it fails; deploys the first passing model to live for $N matches; then ADAPT+fix if it passes. Stop: touch $ON/ORCH_STOP."
adapt_branch & ADAPT_PID=$!
release_watch & REL_PID=$!
trap 'kill $ADAPT_PID $REL_PID 2>/dev/null' EXIT
WINNER=NONE; LIVE_BROKEN=0
ladder
if [ "$WINNER" != NONE ]; then
  if deploy_model $(adir $WINNER)/icebow/fixed.pt tornado fixed_$WINNER.pt "Tornado fix ($WINNER)"; then
    if [ "$(live_count)" -gt 0 ]; then
      post "[overnight] a live supervisor is running; stopping it between matches before starting the icebow deck on the Tornado fix"
      if ! stop_and_wait 2400; then
        cp $L/CKPT_OVERRIDE.pre_tornado_backup $L/CKPT_OVERRIDE; post "[overnight] live did not stop in 40 min; CKPT_OVERRIDE reverted, Tornado fix NOT deployed"; WINNER=NONE
      fi
    fi
    if [ "$WINNER" != NONE ]; then
      live_phase "Tornado fix ($WINNER)" $N start
      [ "$PHASE_END" = broken ] && LIVE_BROKEN=1
    fi
  fi
fi
waitf $ON/ADAPT_RESOLVED
# owner 10-12: if the Tornado fix CLEARLY failed (no grey area), the adaptive model deploys by itself (without the pending-head fix)
AST=$(cat $ON/ADAPT_STATUS 2>/dev/null); CF=gray; SRC=
[ "$WINNER" = NONE ] && [ -e $ON/LAST_ATTEMPT ] && CF=$($H clearfail $(adir $(cat $ON/LAST_ATTEMPT))/SUMMARY.txt)
log "ADAPT status $AST, Tornado clear-fail check: $CF"
if [ "$CF" = clear ] && { [ "$AST" = built ] || [ "$AST" = fixfailed ]; }; then
  SRC=$(find $P3/x_ADAPT -name adaptive_final_grafted.pt | head -1); DST=adapt_alone.pt; LBL="ADAPT alone (Tornado fix clearly failed)"
elif [ "$AST" = built ]; then
  SRC=$(adir ADAPTFIX)/adapt_fixed.pt; DST=adapt_fixed.pt; LBL="ADAPT+fix"
fi
if [ -n "$SRC" ]; then
  if [ $LIVE_BROKEN = 1 ]; then
    post "[overnight] $LBL is ready ($SRC) but live is broken, so it was not switched in."
  elif deploy_model "$SRC" adapt $DST "$LBL"; then
    # start (not restart): whatever runs now may be another deck (bait); stop it between matches, then start icebow
    if [ "$(live_count)" -gt 0 ] && ! stop_and_wait 2400; then
      cp $L/CKPT_OVERRIDE.pre_adapt_backup $L/CKPT_OVERRIDE; post "[overnight] live did not stop in 40 min; CKPT_OVERRIDE reverted, $LBL NOT deployed"
    else
      live_phase "$LBL" $ADAPT_N start
    fi
  fi
fi
log "orchestrator finished"; post "[overnight] orchestrator finished. Log: $ON/orchestrator.log"
