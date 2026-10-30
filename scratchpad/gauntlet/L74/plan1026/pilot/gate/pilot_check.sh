#!/bin/bash
# pilot_check.sh [RUN] -- LAPTOP loop, account 3 10-30 (owner OK: 480 games every 20 updates): for u0000, u0020, u0040 ... copy the
# pilot checkpoint 33308 -> 33903 (sha checked), run pchk.sh there, post the paired result to Discord + pilot_check.log.
# Waits for CLXIII's base_iu40_741200 (480 rows) first. Exits after FINAL. Launch via WMI. Stop: touch STOP_PILOT_CHECK here.
RUN=${1:-pilot_box3}; cd /c/Users/benpe/ClashBot || exit 1
K="-o BatchMode=yes -o ConnectTimeout=30 -i $HOME/.ssh/runpod_clashbot"; A="ssh $K -p 33308 root@157.157.221.29"; B="ssh $K -p 33903 root@157.157.221.29"
D=$(dirname "$0"); STOP=$D/STOP_PILOT_CHECK; PY=icebow/.venv/Scripts/python.exe; P=/workspace/pgate
SRC=/workspace/loop/cb/icebow/data/bench/rl_royale/$RUN; BASE=$P/ev/base_iu40/base_iu40_741200/D3/matches.jsonl
post() { printf '%s\n' "$1" > "$D/.pilot_check_msg.txt"; $PY scratchpad/gauntlet/L69/discord/post.py "$D/.pilot_check_msg.txt" >/dev/null 2>&1; echo "$(date -u +%FT%TZ) $1"; }
$B "cat > $P/pchk.sh" < "$D/pchk.sh" || exit 1
until [ "$($B "grep -c outcome $BASE 2>/dev/null")" = 480 ] || [ -f "$STOP" ]; do sleep 300; done
for i in $(seq 0 20 1000); do
  N=${RUN}_u$(printf %04d $i)
  until $A "test -f $SRC/$N.pt" || [ -f "$STOP" ]; do
    $A "test -f /workspace/loop/pilot/$RUN/FINAL" && { post "$RUN checks done: FINAL written, no $N"; exit 0; }
    sleep 300
  done
  [ -f "$STOP" ] && exit 0
  h1=$($A "sha256sum $SRC/$N.pt" | cut -c1-64); $A "cat $SRC/$N.pt" | $B "cat > $P/ck/$N.pt"; h2=$($B "sha256sum $P/ck/$N.pt" | cut -c1-64)
  [ -n "$h1" ] && [ "$h1" = "$h2" ] || { post ":rotating_light: $N copy sha mismatch ($h1 vs $h2)"; continue; }
  post "$N (iu40, 480 games, sampled gate T .1): $($B "bash $P/pchk.sh $N" | tail -n 1)"
done
