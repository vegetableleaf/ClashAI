#!/bin/bash
# Laptop relay (factorial/pull.sh with the successor paths): copy finished successor jobs back, sha-verified, to
# pod_backup_weekend/pod1017_successor/<JOB>/, register each trained run as an ICEBOW Mark (parent Mark CXXXVIII), mark the
# pod's copy (runs/<JOB>/COPIED). Never stops a pod (no ALL_COPIED / LAST handshake: KEEP stays, owner 10-17).
#   pull.sh HOST PORT     one pass over one pod (safe to repeat)
#   pull.sh               loop every 10 min over successor/cfg/pods.txt (launch via WMI + Git bin/bash.exe: nohup dies with the session)
FD=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L74/successor/cfg; REPO=/c/Users/benpe/ClashBot
LOC=/c/Users/benpe/pod_backup_weekend/pod1017_successor; LOCW=C:/Users/benpe/pod_backup_weekend/pod1017_successor
PY=$REPO/icebow/.venv/Scripts/python.exe
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -o StrictHostKeyChecking=no -i $HOME/.ssh/runpod_clashbot"
declare -A WORD=([succ_ctl]=LONGER [succ_levels]=LEVELS [succ_tower]=TOWERSCORE [succ_hist]=HISTDECKS [succ_troops]=TROOPS
                 [succ_exploit]=EXPLOITERS)
mkdir -p $LOC
log() { echo "$(date +%FT%T) $*"; }

register() {  # trained succ_* runs only (fresh_ / gap13k_ jobs are evals of existing Marks); succ_X_s75 = a seed replicate of succ_X
  local r=$1 D=$LOC/$1 w b=${1%_s7[0-9]}
  [ -n "${WORD[$b]:-}" ] && [ -e $D/DONE ] && [ ! -e $D/REGISTERED ] || return 0
  w=$(cat $D/eval/${r}_741200/D3/matches.jsonl $D/eval/${r}_742000/D3/matches.jsonl | grep -c '"outcome": "win"')
  if (cd $REPO && $PY scratchpad/gauntlet/L74/models/register_ckpt.py "$LOCW/$r/rlarm_${r}_u0065.pt" \
      "$LOCW/$r/rlarm_${r}_u0065_grafted.pt" --deck ICEBOW --change ${WORD[$b]} --parent "ICEBOW Mark CXXXVIII" --run rlarm_$r \
      --note "successor $r: Mark CXXXVIII raw u0130 + 65 updates, seed 74, fork36-linux; one change vs succ_ctl (successor/cfg/$r.yaml)" \
      --eval "promotion eval (fork36 + troops + live levels, D3, 960 paired): $w/960 wins") > $D/REGISTERED.tmp 2>&1; then
    mv $D/REGISTERED.tmp $D/REGISTERED && log "registered $r: $(head -1 $D/REGISTERED)"
  else
    log "register $r FAILED: $(tail -1 $D/REGISTERED.tmp)"
  fi
}

one_pod() {  # HOST PORT -> 0 = reachable, 1 = unreachable
  local H=$1 P=$2 r want got ready
  ready=$(ssh -n $K -p $P root@$H 'cd /workspace/succ 2>/dev/null || exit 0; for s in out/*.tgz.sha; do
      [ -e "$s" ] || continue; r=$(basename $s .tgz.sha); [ -e runs/$r/COPIED ] || echo $r; done') || return 1
  for r in $ready; do
    if [ -e $LOC/$r/COPY_OK ] && [ "$(cut -d' ' -f1 $LOC/$r/COPY_OK)" != "$H:$P" ]; then   # same job name on two pods
      log "$P $r: already copied from $(cut -d' ' -f1 $LOC/$r/COPY_OK) -- NOT overwritten"; continue
    fi
    want=$(ssh -n $K -p $P root@$H "cat /workspace/succ/out/$r.tgz.sha" | awk '{print $1}')
    scp -q $K -P $P root@$H:/workspace/succ/out/$r.tgz $LOC/$r.tgz || { log "$P $r: scp failed"; continue; }
    got=$(sha256sum $LOC/$r.tgz | sed 's/ \*/  /' | awk '{print $1}')
    [ -n "$want" ] && [ "$got" = "$want" ] || { log "$P $r: SHA MISMATCH ($got vs $want)"; rm -f $LOC/$r.tgz; continue; }
    rm -rf $LOC/$r.part && mkdir -p $LOC/$r.part && tar xzf $LOC/$r.tgz -C $LOC/$r.part || { log "$P $r: untar failed"; continue; }
    if [ -f $LOC/$r.part/$r/final.sha ]; then
      (cd $LOC/$r.part/$r && sha256sum -c --quiet final.sha) || { log "$P $r: CKPT SHA MISMATCH"; continue; }
    fi
    rm -rf $LOC/$r && mv $LOC/$r.part/$r $LOC/$r && rm -rf $LOC/$r.part $LOC/$r.tgz
    echo "$H:$P $want" > $LOC/$r/COPY_OK
    ssh -n $K -p $P root@$H "touch /workspace/succ/runs/$r/COPIED" && log "COPY_OK $r <- $P$([ -e $LOC/$r/FAILED ] && echo ' (FAILED: logs only)')"
    register $r
  done
  return 0
}

if [ $# -ge 2 ]; then one_pod $1 $2; exit; fi
log "relay start pid $$"
while true; do
  while read -r H P; do [ -n "$H" ] && { one_pod $H $P || log "$P unreachable"; }; done < <(tr -d '\r' < $FD/pods.txt | tr ':' ' ')
  sleep 600
done
