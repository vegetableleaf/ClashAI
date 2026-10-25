#!/bin/bash
# night_decide.sh DEADLINE_UTC "PORT:ARM ..." ["PORT:RUN ..." controls] -- laptop, night 10-25/26. Owner: deploy a memory
# successor by the morning (permission to stop / start live overnight); shut down idle pods overnight (copy results first:
# a stop wipes /workspace).
#   * polls each pod's /workspace/abl/res_ARM.txt (arm_chain.sh); when an arm FINISHES (DONE, a drift verdict other than PASS,
#     or no checkpoint): copies res + drift checks + its u100 raw / grafted checkpoints to $B/ARM/ (sha-verified), then STOPS
#     that pod (runpodctl from inside it). Controls (plain drift_test runs) are copied + stopped when their VERDICT appears.
#   * when every arm finished (or DEADLINE_UTC passed): the best candidate = drift PASS + gate PASS (pooled 3,840-game CI low
#     > 0 vs CLXIII) + memory used (ablation real - empty > 0), by pooled delta -> ICEBOW Mark CLXIV: ADAPTIVE via
#     deploy_ckpt.sh; deploy / first-match-guard failure -> back to CLXIII NOLEAK. No candidate -> live unchanged.
set -uo pipefail
DL=$1; LIST=$2; CTRL=${3:-}
cd /c/Users/benpe/ClashBot || exit 1
H=root@157.157.221.29; KEY=~/.ssh/runpod_clashbot; D=scratchpad/gauntlet/L74/memory/promote; mkdir -p $D; LOG=$D/night_decide.log
B=/c/Users/benpe/pod_backup_weekend/night1025; mkdir -p $B
PY=icebow/.venv/Scripts/python.exe
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $LOG; }
sshp() { local p=$1; shift; timeout 900 ssh -o BatchMode=yes -o ConnectTimeout=30 -i $KEY -p $p $H "$@"; }
post() { printf '%s\n' "$*" > $D/decide.msg; $PY scratchpad/gauntlet/L69/discord/post.py $D/decide.msg >> $LOG 2>&1; }
stop_pod() {   # $1 port $2 why
  sshp $1 'export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)="); runpodctl config --apiKey "$RUNPOD_API_KEY" > /dev/null; runpodctl stop pod "$RUNPOD_POD_ID"' >> $LOG 2>&1
  log "STOP pod $1 rc $? ($2)"; post "[ClashAI] night: pod $1 stopped ($2); results copied to the laptop."
}
fetch() {   # $1 port $2 run $3 tree -> copies into $B/$2; 0 = ok
  local p=$1 a=$2 t=$3 o=$B/$2; mkdir -p $o
  sshp $p "cat /workspace/abl/res_$a.txt 2>/dev/null" > $o/res.txt
  sshp $p "cd /workspace/exploit/drift/$a && tar cf - . 2>/dev/null" > $o/drift.tar
  for f in /workspace/$t/icebow/data/bench/rl_royale/rlarm_$a/rlarm_${a}_u0100.pt /workspace/exploit/ckpt/rlarm_${a}_u0100_grafted.pt; do
    sshp $p "[ -f $f ]" || continue
    sshp $p "cat $f" > $o/$(basename $f)
    [ "$(sha256sum $o/$(basename $f) | sed 's/ .*//')" = "$(sshp $p "sha256sum $f" | sed 's/ .*//')" ] || { log "$a: sha mismatch $(basename $f)"; return 1; }
  done
  log "$a: fetched $(ls $o | tr '\n' ' ')"
}
finished() {   # $1 res file
  grep -q " DONE$" $1 || { grep -q " DRIFT" $1 && ! grep -q " DRIFT PASS" $1; } || grep -q " no /workspace" $1
}
dl=$(date -u -d "$DL" +%s); declare -A done_
while :; do
  open=0
  for pa in $LIST; do p=${pa%%:*}; a=${pa#*:}; [ -n "${done_[$a]:-}" ] && continue
    sshp $p "cat /workspace/abl/res_$a.txt 2>/dev/null" > $D/res_$a.txt || { open=1; continue; }
    if finished $D/res_$a.txt; then
      if fetch $p $a cb_arm; then done_[$a]=1; stop_pod $p "arm $a finished: $(grep -oE 'DRIFT [A-Z]*|GATE (PASS|FAIL)' $D/res_$a.txt | tr '\n' ' ')"
      else open=1; fi
    else open=1; fi
  done
  for pa in $CTRL; do p=${pa%%:*}; a=${pa#*:}; [ -n "${done_[$a]:-}" ] && continue
    if [ -n "$(sshp $p "cat /workspace/exploit/drift/$a/VERDICT 2>/dev/null")" ]; then
      fetch $p $a cb_mem && { done_[$a]=1; stop_pod $p "control $a finished: $(sshp $p "cat /workspace/exploit/drift/$a/VERDICT" 2>/dev/null)"; }
    fi
  done
  [ $open = 0 ] && break
  [ "$(date -u +%s)" -ge $dl ] && { log "deadline $DL"; break; }
  sleep 600
done
best=""; bd=-999
for pa in $LIST; do a=${pa#*:}; f=$B/$a/res.txt; [ -f $f ] || f=$D/res_$a.txt
  pooled=$(grep "GATE pooled" $f | sed -E 's/.*delta=([-+0-9.]+) pp \[([-+0-9.]+), ([-+0-9.]+)\].*/\1 \2/')
  abl=$(grep "ABL real - empty" $f | sed -E 's/.*empty: ([-+0-9.]+) pp.*/\1/')
  log "$a: $(grep -oE 'DRIFT [A-Z]*' $f) | $(grep 'GATE' $f | sed 's/^GATE //' | tr '\n' ' ') | ablation real-empty ${abl:-none}"
  [ -n "$pooled" ] && [ -n "$abl" ] || continue
  d=${pooled% *}; lo=${pooled#* }
  if grep -q "GATE PASS" $f && awk "BEGIN{exit !($abl > 0 && $lo > 0 && $d > $bd)}"; then best=$a; bd=$d; fi
done
if [ -z "$best" ]; then
  post "[ClashAI] Night 10-25 memory arms: NO candidate passed (drift + gate vs CLXIII CI low > 0 + memory used). Live unchanged (CLXIII NOLEAK). Summary in $LOG."
  log "no candidate"; exit 1; fi
a=$best; f=$B/$a/res.txt
G=$B/$a/rlarm_${a}_u0100_grafted.pt; SHA=$(grep " CKPT " $f | awk '{print $4}')
[ -f $G ] && [ "$(sha256sum $G | sed 's/ .*//')" = "$SHA" ] || { log "$a: local grafted ckpt missing / sha mismatch"; post ":rotating_light: night_decide: $a checkpoint missing; live unchanged."; exit 2; }
CK=icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIV_ADAPTIVE.pt
cp -p $G $CK
$PY scratchpad/gauntlet/L74/models/register_ckpt.py $CK --deck ICEBOW --change ADAPTIVE --run $a \
  --note "Plan A memory v2 + aux-pretrained encoder; $(grep 'GATE pooled' $f | sed 's/^GATE //'); $(grep 'ABL real - empty' $f | sed 's/^ABL //')" >> $LOG 2>&1
WHY="Mark CLXIV ADAPTIVE (memory, $a): $(grep 'GATE pooled' $f | sed 's/^GATE pooled: //'), memory ablation $(grep 'ABL real - empty' $f | sed 's/^ABL real - empty: //' | cut -c1-60)"
bash scratchpad/gauntlet/L74/deploy/deploy_ckpt.sh $CK ${SHA:0:16} "$WHY" >> $LOG 2>&1; rc=$?
tail -5 $LOG | grep -q "guard exit [1-9]" && rc=5
log "deploy rc $rc"
if [ $rc != 0 ]; then
  bash scratchpad/gauntlet/L74/deploy/deploy_ckpt.sh icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt 8d328a43bf09fb7e "revert: Mark CLXIV deploy failed (rc $rc)" >> $LOG 2>&1
  log "reverted to CLXIII rc $?"; exit 4; fi
log "LIVE = Mark CLXIV ADAPTIVE ($a)"
