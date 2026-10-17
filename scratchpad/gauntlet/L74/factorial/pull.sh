#!/bin/bash
# Laptop: copy finished factorial runs back from the pods, sha-verified, to pod_backup_weekend/pod1017_factorial/<RUN>/,
# register each trained run as an ICEBOW Mark (word FACTORIAL, parent Mark CXXIV), and tell the pod (runs/<RUN>/COPIED;
# ALL_COPIED once its chain is done and every queued run is copied -> the pod's chain touches LAST -> pod_watchdog stops it).
#   pull.sh HOST PORT     one pass over one pod (safe to repeat: copied runs are skipped)
#   pull.sh               loop: every 10 min over every pod in pods.txt until each has ALL_COPIED (or is unreachable 6 h)
# A run is ready when the pod has out/<RUN>.tgz.sha (written after its bundle; FAILED runs are bundled too, logs only).
# Results stay on the pod until copied: a pod only stops after ALL_COPIED, or 4 h after its chain ends (chain.sh backstop).
FD=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L74/factorial; REPO=/c/Users/benpe/ClashBot
LOC=/c/Users/benpe/pod_backup_weekend/pod1017_factorial; LOCW=C:/Users/benpe/pod_backup_weekend/pod1017_factorial
PY=$REPO/icebow/.venv/Scripts/python.exe
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -o StrictHostKeyChecking=no -i $HOME/.ssh/runpod_clashbot"
mkdir -p $LOC
log() { echo "$(date +%FT%T) $*"; }

register() {  # RUN: a trained run that finished (DONE), once (REGISTERED marker); the refs are Marks already
  local r=$1 D=$LOC/$1 sg w
  [ "${r:0:4}" = fact ] && [ -e $D/DONE ] && [ ! -e $D/REGISTERED ] || return 0
  sg=$(awk -v r=$r '$1 == r {print $2 " seed " $3}' $FD/design.txt)
  w=$(cat $D/eval/${r}_741200/D3/matches.jsonl $D/eval/${r}_742000/D3/matches.jsonl | grep -c '"outcome": "win"')
  if (cd $REPO && $PY scratchpad/gauntlet/L74/models/register_ckpt.py "$LOCW/$r/rlarm_${r}_u0065.pt" \
      "$LOCW/$r/rlarm_${r}_u0065_grafted.pt" --deck ICEBOW --change FACTORIAL --parent "ICEBOW Mark CXXIV" --run rlarm_$r \
      --note "factorial $r: $sg (A cue layer, B exploiter league, C opp tower troops, D live levels, E tower shaping; 2^(5-1) E=ABCD; u250 raw + 65 updates)" \
      --eval "factorial eval (fork36 + troops + live levels, D3, 960 paired): $w/960 wins") > $D/REGISTERED.tmp 2>&1; then
    mv $D/REGISTERED.tmp $D/REGISTERED && log "registered $r: $(head -1 $D/REGISTERED)"
  else
    log "register $r FAILED: $(tail -1 $D/REGISTERED.tmp)"
  fi
}

one_pod() {  # HOST PORT -> 0 = reachable, 1 = unreachable
  local H=$1 P=$2 r want got ready
  ready=$(ssh -n $K -p $P root@$H 'cd /workspace/fact 2>/dev/null || exit 0; for s in out/*.tgz.sha; do
      [ -e "$s" ] || continue; r=$(basename $s .tgz.sha); [ -e runs/$r/COPIED ] || echo $r; done') || return 1
  for r in $ready; do
    want=$(ssh -n $K -p $P root@$H "cat /workspace/fact/out/$r.tgz.sha" | awk '{print $1}')
    scp -q $K -P $P root@$H:/workspace/fact/out/$r.tgz $LOC/$r.tgz || { log "$P $r: scp failed"; continue; }
    got=$(sha256sum $LOC/$r.tgz | sed 's/ \*/  /' | awk '{print $1}')
    [ -n "$want" ] && [ "$got" = "$want" ] || { log "$P $r: SHA MISMATCH ($got vs $want)"; rm -f $LOC/$r.tgz; continue; }
    rm -rf $LOC/$r.part && mkdir -p $LOC/$r.part && tar xzf $LOC/$r.tgz -C $LOC/$r.part || { log "$P $r: untar failed"; continue; }
    if [ -f $LOC/$r.part/$r/final.sha ]; then              # the checkpoints' own shas, recorded on the pod
      (cd $LOC/$r.part/$r && sha256sum -c --quiet final.sha) || { log "$P $r: CKPT SHA MISMATCH"; continue; }
    fi
    rm -rf $LOC/$r && mv $LOC/$r.part/$r $LOC/$r && rm -rf $LOC/$r.part $LOC/$r.tgz
    echo "$H:$P $want" > $LOC/$r/COPY_OK
    ssh -n $K -p $P root@$H "touch /workspace/fact/runs/$r/COPIED" && log "COPY_OK $r <- $P$([ -e $LOC/$r/FAILED ] && echo ' (FAILED run: logs only)')"
    register $r
  done
  ssh -n $K -p $P root@$H 'cd /workspace/fact 2>/dev/null && [ -e CHAIN_DONE ] || exit 0; [ -e ALL_COPIED ] && { echo ALL_COPIED; exit 0; }
    while read -r r _; do [ -z "$r" ] || [ "${r:0:1}" = "#" ] || [ -e runs/$r/COPIED ] || exit 0; done < queue.txt
    touch ALL_COPIED && echo ALL_COPIED' | grep -q ALL_COPIED && { [ -e $LOC/ALL_COPIED_$P ] || log "$P ALL_COPIED"; touch $LOC/ALL_COPIED_$P; }
  return 0
}

if [ $# -ge 2 ]; then one_pod $1 $2; exit; fi
declare -A gone
log "relay start pid $$"
while true; do
  left=0
  while read -r H P; do
    [ -z "$H" ] || [ -e $LOC/ALL_COPIED_$P ] && continue
    if one_pod $H $P; then gone[$P]=0; else gone[$P]=$(( ${gone[$P]:-0} + 1 )); log "$P unreachable (${gone[$P]})"; fi
    [ -e $LOC/ALL_COPIED_$P ] || [ ${gone[$P]} -ge 36 ] || left=1
  done < <(tr -d '\r' < $FD/pods.txt | tr ':' ' ')
  [ $left = 0 ] && { log "relay done (every pod ALL_COPIED or unreachable 6 h)"; exit 0; }
  sleep 600
done
