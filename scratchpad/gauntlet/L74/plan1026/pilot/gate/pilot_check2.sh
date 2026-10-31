#!/bin/bash
# pilot_check2.sh RUN ARM CPUS [START] -- LAPTOP loop, account 3 10-31: for u0000, u0020, ... read RUN's checkpoint from the laptop backup
# C:/Users/benpe/pod_backup_weekend/pilot2/ARM/ (PILOT2-BUILD's watcher copies every u%20 + FINAL there, sha-checked, so this works
# after the pod is stopped), upload it to 33308 /workspace/pgate2/ck/, run pchk2.sh there on CPUS, post the result to Discord.
# Waits for CLXIII's base2_iu40_741200 (480 rows). Exits after FINAL. Launch via WMI. Stop: touch STOP_PILOT_CHECK2 here.
RUN=$1; ARM=$2; C=${3:-0-47}; cd /c/Users/benpe/ClashBot || exit 1
B="ssh -o BatchMode=yes -o ConnectTimeout=30 -i $HOME/.ssh/runpod_clashbot -p 33308 root@157.157.221.29"; P=/workspace/pgate2
D=$(dirname "$0"); STOP=$D/STOP_PILOT_CHECK2; PY=icebow/.venv/Scripts/python.exe; SRC=/c/Users/benpe/pod_backup_weekend/pilot2/$ARM
post() { printf '%s\n' "$1" > "$D/.pilot_check2_msg_$ARM.txt"; $PY scratchpad/gauntlet/L69/discord/post.py "$D/.pilot_check2_msg_$ARM.txt" >/dev/null 2>&1; echo "$(date -u +%FT%TZ) $1"; }
$B "cat > $P/pchk2.sh" < "$D/pchk2.sh" || exit 1
until [ "$($B "grep -c outcome $P/ev/base2_iu40/base2_iu40_741200/D3/matches.jsonl 2>/dev/null")" = 480 ] || [ -f "$STOP" ]; do sleep 300; done
for i in $(seq ${4:-20} 20 600); do                # START = $4 (resumed runs: first numbered ckpt)
  N=${RUN}_u$(printf %04d $i)
  until [ -f "$SRC/$N.pt" ] || [ -f "$STOP" ]; do
    ls "$SRC" 2>/dev/null | grep -qi final && { post "$RUN checks done: FINAL in $SRC, no $N"; exit 0; }
    sleep 300
  done
  [ -f "$STOP" ] && exit 0
  sleep 30                                                    # the watcher's copy finishes before its sha check
  h1=$(sha256sum "$SRC/$N.pt" | cut -c1-64); $B "cat > $P/ck/$N.pt" < "$SRC/$N.pt"; h2=$($B "sha256sum $P/ck/$N.pt" | cut -c1-64)
  [ -n "$h1" ] && [ "$h1" = "$h2" ] || { post ":rotating_light: $N upload sha mismatch ($h1 vs $h2)"; continue; }
  post "$N (iu40 480, sampled gate, stripped live stack): $($B "bash $P/pchk2.sh $N $C" | tail -n 1)"
done
