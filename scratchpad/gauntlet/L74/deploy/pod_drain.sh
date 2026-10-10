#!/bin/bash
# Overnight pod drain (2026-10-09/10). Waits until the pod's job queue is empty, copies everything worth keeping to the
# laptop, verifies the copy, posts one Discord line. It stops the pod ONLY if the owner's approval flag exists
# ($OUT/STOP_POD_APPROVED). It checks for that flag until 09:00. Stopping wipes /workspace (container disk).
# Run: nohup bash scratchpad/gauntlet/L74/deploy/pod_drain.sh > $OUT/drain.log 2>&1 &
cd /c/Users/benpe/ClashBot
OUT=/c/Users/benpe/pod_backup_20261010; mkdir -p $OUT
SSH="ssh -o BatchMode=yes -o ConnectTimeout=20 -i $HOME/.ssh/runpod_clashbot -p 48431 root@64.247.206.120"
SCP="scp -o BatchMode=yes -i $HOME/.ssh/runpod_clashbot -P 48431"
PY=icebow/.venv/Scripts/python.exe
log() { echo "$(date '+%F %T') $*"; }
post() { printf '%s\n' "$1" > $OUT/_msg.txt; $PY scratchpad/gauntlet/L69/discord/post.py $OUT/_msg.txt; }
# ponytail: the idle test is a process-name scan; it does not know about jobs started later by hand
BUSY='[f]lock /workspace|[r]equeue2.sh|[m]ech_pod_launch|[m]ech_pod_queue|[p]od_e2_driver|[s]earch_s0|[r]l_royale|[r]un_probe|[r]ocket_chain'   # [x] = no self-match

idle=0
while [ $idle -lt 2 ]; do                       # two quiet checks in a row, 5 min apart
  n=$($SSH "pgrep -fc '$BUSY' || true" 2>/dev/null | tr -d '\r')
  [ -z "$n" ] && { log "ssh failed"; sleep 300; continue; }
  if [ "$n" = 0 ]; then idle=$((idle+1)); else idle=0; fi
  log "busy processes: $n (quiet checks $idle/2)"; [ $idle -lt 2 ] && sleep 300
done

log "queue empty -- packing"
$SSH 'cd /workspace && git -C clashbot bundle create /workspace/branches.bundle --all 2>/dev/null;
  tar czf /workspace/drain.tgz results branches.bundle POD_README.md *.sh $(ls -d wt_*/scratchpad/gauntlet/L74 2>/dev/null) 2>/dev/null;
  sha256sum /workspace/drain.tgz' > $OUT/remote_sha.txt || { log "pack failed"; post "Pod drain: packing FAILED, pod left running"; exit 1; }
$SCP root@64.247.206.120:/workspace/drain.tgz $OUT/drain.tgz || { log "copy failed"; post "Pod drain: copy FAILED, pod left running"; exit 1; }
r=$(cut -d' ' -f1 $OUT/remote_sha.txt); l=$(sha256sum $OUT/drain.tgz | cut -d' ' -f1)
if [ "$r" != "$l" ] || ! tar tzf $OUT/drain.tgz > /dev/null; then
  log "verify failed ($r vs $l)"; post "Pod drain: copy did not verify, pod left running"; exit 1; fi
sz=$(du -h $OUT/drain.tgz | cut -f1); touch $OUT/COPIED_OK
log "copied and verified ($sz)"
post "Pod queue finished; all results copied to the laptop and verified ($sz). Pod is idle (\$0.82/h) until stopped."

until [ "$(date +%H)" -ge 9 ]; do                # owner approval may arrive later in the night
  if [ -f $OUT/STOP_POD_APPROVED ]; then
    $SSH 'export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)="); runpodctl config --apiKey "$RUNPOD_API_KEY" > /dev/null; runpodctl stop pod "$RUNPOD_POD_ID"' \
      && { log "pod stop requested"; post "Pod stopped (owner-approved) after the copy-back."; } \
      || { log "pod stop failed"; post "Pod stop FAILED -- please stop it from the RunPod page"; }
    exit 0
  fi
  sleep 300
done
log "no approval flag by 09:00 -- pod left running"
