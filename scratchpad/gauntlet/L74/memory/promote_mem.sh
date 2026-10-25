#!/bin/bash
# promote_mem.sh RUN TRAIN_PORT MARK WORD [SKIP_IF_LIVE_MATCHES] -- owner 10-25 night: a memory candidate that passes goes live.
#   1. wait for the drift test VERDICT of RUN on TRAIN_PORT (PASS = no gate flag at u0100 vs u0000, pro agreement inside bars)
#   2. relay its u0100 grafted ckpt to the gate pod (33522), gate it there: E4 + calibrated I u40, 4 seed blocks = 3,840 games,
#      the same command as CLXIII's rows (g48_succ48_o_s91_u0075_{e4,cal}) -> pair_both.py; PASS = pooled 95% CI low > 0
#   3. PASS: copy to icebow/data/models/ICEBOW/ICEBOW_Mark_MARK_WORD.pt, register, deploy_ckpt.sh (restart between matches +
#      first-match guard); deploy failure -> back to CLXIII NOLEAK. SKIP_IF_LIVE_MATCHES: do not deploy if CKPT_OVERRIDE
#      already names that substring (a later candidate is live).
set -uo pipefail
RUN=$1; TP=$2; MARK=$3; WORD=$4; SKIP=${5:-}
cd /c/Users/benpe/ClashBot || exit 1
H=root@157.157.221.29; GP=33522; KEY=~/.ssh/runpod_clashbot
D=scratchpad/gauntlet/L74/memory/promote; mkdir -p $D; LOG=$D/$RUN.log
PY=icebow/.venv/Scripts/python.exe
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $LOG; }
sshp() { local p=$1; shift; timeout 900 ssh -o BatchMode=yes -o ConnectTimeout=30 -i $KEY -p $p $H "$@"; }
post() { printf '%s\n' "$*" > $D/$RUN.msg; $PY scratchpad/gauntlet/L69/discord/post.py $D/$RUN.msg >> $LOG 2>&1; }
DR=/workspace/exploit/drift/$RUN

log "wait for drift verdict $RUN on $TP"
until [ -n "$(sshp $TP "cat $DR/VERDICT 2>/dev/null")" ]; do sleep 300; done
V=$(sshp $TP "cat $DR/VERDICT"); log "drift VERDICT $V: $(sshp $TP "cat $DR/STOP_REASON 2>/dev/null")"
if [ "$V" != PASS ]; then post "[ClashAI] memory candidate $RUN FAILED the drift test ($(sshp $TP "cat $DR/STOP_REASON 2>/dev/null")); not gated, live unchanged."; exit 1; fi

G=/workspace/exploit/ckpt/rlarm_${RUN}_u0100_grafted.pt
T=$D/${RUN}_u0100_grafted.pt
sshp $TP "cat $G" > $T || { log "fetch failed"; exit 2; }
SHA=$(sha256sum $T | sed 's/ .*//'); RSHA=$(sshp $TP "sha256sum $G" | sed 's/ .*//')
[ "$SHA" = "$RSHA" ] || { log "sha mismatch $SHA vs $RSHA"; exit 2; }
sshp $GP "mkdir -p /workspace/cb_gate_ck"; cat $T | sshp $GP "cat > /workspace/cb_gate_ck/$(basename $T)"
[ "$(sshp $GP "sha256sum /workspace/cb_gate_ck/$(basename $T)" | sed 's/ .*//')" = "$SHA" ] || { log "relay sha mismatch"; exit 2; }
cat scratchpad/gauntlet/L74/memory/pair_both.py | sshp $GP "cat > /workspace/pushcal/pair_both.py"
TAG=g48m_${RUN}_u0100; Q=/workspace/pushcal/q_$TAG.txt
sshp $GP "printf '%s\n' '${TAG}_e4|e4||741200 742000 743000 744000' '${TAG}_cal|iu40|--opp-decide-every 20 --opp-tau 0.2|741200 742000 743000 744000' > $Q;
  CB=/workspace/cb_gate G=/workspace/cb_gate_ck/$(basename $T) LOCK=/workspace/cpu_b.lock WORKERS=26 setsid nohup bash /workspace/pushcal/gate_eval.sh $Q > /workspace/pushcal/$TAG.log 2>&1 < /dev/null &"
log "gate started $TAG (sha ${SHA:0:16})"
until sshp $GP "grep -q 'QUEUE DONE' /workspace/pushcal/$TAG.log"; do sleep 300; done
X=/workspace/pushcal/ev; B=g48_succ48_o_s91_u0075
R=$(sshp $GP "/workspace/venvf15/bin/python /workspace/pushcal/pair_both.py '$X/${TAG}_e4/${TAG}_e4_{s}/D3/matches.jsonl' '$X/${TAG}_cal/${TAG}_cal_{s}/D3/matches.jsonl' '$X/${B}_e4/${B}_e4_{s}/D3/matches.jsonl' '$X/${B}_cal/${B}_cal_{s}/D3/matches.jsonl'")
log "gate vs CLXIII: $(echo $R | tr '\n' ' ')"
if [ "$(echo "$R" | tail -1)" != PASS ]; then post "[ClashAI] memory candidate $RUN gate vs CLXIII: $(echo "$R" | head -3 | tr '\n' ';') -> FAIL (pooled CI low <= 0); live unchanged."; exit 1; fi

if [ -n "$SKIP" ] && grep -q "$SKIP" scratchpad/gauntlet/L70/live/CKPT_OVERRIDE; then
  post "[ClashAI] $RUN PASSED the gate ($(echo "$R" | sed -n 3p)) but $SKIP is already live; not switched."; exit 0; fi
CK=icebow/data/models/ICEBOW/ICEBOW_Mark_${MARK}_${WORD}.pt
cp -p $T $CK && $PY scratchpad/gauntlet/L74/models/register_ckpt.py $CK --deck ICEBOW --change $WORD --run $RUN \
  --note "Plan A memory candidate; gate vs CLXIII $(echo "$R" | sed -n 3p)" >> $LOG 2>&1
bash scratchpad/gauntlet/L74/deploy/deploy_ckpt.sh $CK ${SHA:0:16} "Mark $MARK $WORD (memory, $RUN): gate vs CLXIII $(echo "$R" | sed -n 3p), drift PASS" >> $LOG 2>&1
rc=$?; log "deploy rc $rc"
tail -5 $LOG | grep -q "guard exit [1-9]" && rc=5                 # first-match guard failed (deploy_ckpt only posts it)
if [ $rc != 0 ]; then
  bash scratchpad/gauntlet/L74/deploy/deploy_ckpt.sh icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt 8d328a43bf09fb7e "revert: Mark $MARK deploy failed (rc $rc)" >> $LOG 2>&1
  log "reverted to CLXIII rc $?"; exit 4; fi
log "LIVE = Mark $MARK $WORD"
