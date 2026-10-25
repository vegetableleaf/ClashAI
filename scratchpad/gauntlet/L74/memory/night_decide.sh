#!/bin/bash
# night_decide.sh DEADLINE_UTC "PORT:ARM ..." -- laptop (owner 10-25: deploy a memory successor by the morning; permission to
# stop / start live overnight). Polls each pod's /workspace/abl/res_ARM.txt (arm_chain.sh) until every arm is DONE or failed,
# or DEADLINE_UTC (e.g. 2026-10-26T10:30Z) passes. A candidate = drift PASS + gate PASS (pooled 3,840-game CI low > 0 vs CLXIII)
# + memory used (ablation real - empty > 0). The best by pooled delta is copied, registered (ICEBOW Mark CLXIV: ADAPTIVE) and
# deployed with deploy_ckpt.sh; deploy or first-match-guard failure -> back to CLXIII NOLEAK. No candidate -> live unchanged.
set -uo pipefail
DL=$1; LIST=$2
cd /c/Users/benpe/ClashBot || exit 1
H=root@157.157.221.29; KEY=~/.ssh/runpod_clashbot; D=scratchpad/gauntlet/L74/memory/promote; mkdir -p $D; LOG=$D/night_decide.log
PY=icebow/.venv/Scripts/python.exe
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $LOG; }
sshp() { local p=$1; shift; timeout 900 ssh -o BatchMode=yes -o ConnectTimeout=30 -i $KEY -p $p $H "$@"; }
post() { printf '%s\n' "$*" > $D/decide.msg; $PY scratchpad/gauntlet/L69/discord/post.py $D/decide.msg >> $LOG 2>&1; }
dl=$(date -u -d "$DL" +%s)
while :; do
  open=0
  for pa in $LIST; do p=${pa%%:*}; a=${pa#*:}
    sshp $p "cat /workspace/abl/res_$a.txt 2>/dev/null" > $D/res_$a.txt
    f=$D/res_$a.txt                                  # finished = DONE, or a drift verdict other than PASS, or no ckpt
    if grep -q " DONE$" $f || { grep -q " DRIFT" $f && ! grep -q " DRIFT PASS" $f; } || grep -q " no /workspace" $f; then
      continue; fi
    open=1
  done
  [ $open = 0 ] && break
  [ "$(date -u +%s)" -ge $dl ] && { log "deadline $DL"; break; }
  sleep 600
done
best=""; bd=-999
for pa in $LIST; do p=${pa%%:*}; a=${pa#*:}; f=$D/res_$a.txt
  pooled=$(grep "^GATE pooled" $f | sed -E 's/.*delta=([-+0-9.]+) pp \[([-+0-9.]+), ([-+0-9.]+)\].*/\1 \2/')
  abl=$(grep "^ABL real - empty" $f | sed -E 's/.*empty: ([-+0-9.]+) pp.*/\1/')
  log "$a: drift $(grep -o 'DRIFT [A-Z]*' $f) | gate $(grep '^GATE' $f | tr '\n' ' ') | ablation real-empty ${abl:-none}"
  [ -n "$pooled" ] && [ -n "$abl" ] || continue
  d=${pooled% *}; lo=${pooled#* }
  if grep -q "^GATE PASS" $f && awk "BEGIN{exit !($abl > 0 && $lo > 0 && $d > $bd)}"; then best=$pa; bd=$d; fi
done
if [ -z "$best" ]; then
  post "[ClashAI] Night 10-25 memory arms: NO candidate passed (drift + gate vs CLXIII CI low > 0 + memory used). Live unchanged (CLXIII NOLEAK). $(tail -4 $LOG | cut -c22- | tr '\n' ' ')"
  log "no candidate"; exit 1; fi
p=${best%%:*}; a=${best#*:}
G=$(grep "^.* CKPT " $D/res_$a.txt | awk '{print $3}'); SHA=$(grep "^.* CKPT " $D/res_$a.txt | awk '{print $4}')
CK=icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIV_ADAPTIVE.pt
sshp $p "cat $G" > $CK
[ "$(sha256sum $CK | sed 's/ .*//')" = "$SHA" ] || { log "fetch sha mismatch"; post ":rotating_light: night_decide: $a fetch sha mismatch; live unchanged."; exit 2; }
$PY scratchpad/gauntlet/L74/models/register_ckpt.py $CK --deck ICEBOW --change ADAPTIVE --run $a \
  --note "Plan A memory v2 + aux-pretrained encoder; $(grep '^GATE pooled' $D/res_$a.txt); $(grep '^ABL real - empty' $D/res_$a.txt)" >> $LOG 2>&1
WHY="Mark CLXIV ADAPTIVE (memory, $a): $(grep '^GATE pooled' $D/res_$a.txt | cut -c6-), memory ablation $(grep '^ABL real - empty' $D/res_$a.txt | cut -c5- | cut -c1-60)"
bash scratchpad/gauntlet/L74/deploy/deploy_ckpt.sh $CK ${SHA:0:16} "$WHY" >> $LOG 2>&1; rc=$?
tail -5 $LOG | grep -q "guard exit [1-9]" && rc=5
log "deploy rc $rc"
if [ $rc != 0 ]; then
  bash scratchpad/gauntlet/L74/deploy/deploy_ckpt.sh icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt 8d328a43bf09fb7e "revert: Mark CLXIV deploy failed (rc $rc)" >> $LOG 2>&1
  log "reverted to CLXIII rc $?"; exit 4; fi
log "LIVE = Mark CLXIV ADAPTIVE ($a)"
