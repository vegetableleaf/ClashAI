#!/bin/bash
# lead_d3_loop.sh -- lead 10-29: OPP-LEARN-C's D3 eval babysitter (Codex C_5) was not running, so the lead runs D3 itself.
# Every 40 updates per arm: strip the ckpt on 33308 (strip_ckpt.py, drops the ~90 MB RL state), copy via the laptop to
# 33903, run one 480-game D3 block (seed 741200, fe364ceb, G2 on, opp T 1 = the ftR baseline's setting), print the CLXIII
# win count. Stop: touch STOP_LEAD_D3 next to this script. Never edit this file while it runs.
# env: ARMS="l003:120-239 l001:0-119" (arm suffix : 33903 CPUs), UPDATES="0120 0160 ..."
# 10-29 06:55: arm A (l01) stopped at u100 (stalled: u40 82.9%, u80 86.0%); arm C l001 (beta 0.01) started on GPU1.
S="ssh -o BatchMode=yes -o ConnectTimeout=20 -i $HOME/.ssh/runpod_clashbot root@157.157.221.29 -p"
R=/workspace/d2/cb/icebow/data/bench/rl_royale
H=/workspace/opp/cb/scratchpad/gauntlet/L74/opp_model/humanlike
STOP=$(dirname "$0")/STOP_LEAD_D3
ARMS=${ARMS:-"l003:120-239 l001:0-119"}
for U in ${UPDATES:-0120 0160 0200 0240 0280 0320 0360 0400}; do
  for A in $ARMS; do
    a=${A%%:*}; C=${A##*:}; N=oplc_ftR_${a}_a10_u$U
    until $S 33308 "test -f $R/oplc_ftR_${a}_a10/$N.pt" || [ -f "$STOP" ]; do sleep 300; done
    [ -f "$STOP" ] && exit 0
    $S 33308 "cd /workspace/oplc && /workspace/venvf16/bin/python strip_ckpt.py $R/oplc_ftR_${a}_a10/$N.pt /workspace/oplc/strip/$N.pt" || continue
    $S 33308 "cat /workspace/oplc/strip/$N.pt" | $S 33903 "cat > /workspace/oplc_eval/ck/$N.pt"
    $S 33903 "cd /workspace/oplc_eval && CB=/workspace/opp/cb G2_ON=on OPP_T=1.0 WORKERS=100 CPUS=$C OPP_CKPT=/workspace/oplc_eval/ck/$N.pt nohup bash $H/run_closed.sh $N /workspace/oplc_eval/rows/$N 741200 > /workspace/oplc_eval/$N.out 2>&1 &"
  done
  for A in $ARMS; do
    a=${A%%:*}; N=oplc_ftR_${a}_a10_u$U; F=/workspace/oplc_eval/rows/$N/${N}_741200/D3/matches.jsonl
    until [ "$($S 33903 "grep -c outcome $F 2>/dev/null")" = 480 ] || $S 33903 "grep -q -i 'error\|traceback' /workspace/oplc_eval/$N.out"; do sleep 120; done
    echo "$(date -u +%FT%TZ) $N CLXIII W $($S 33903 "grep -c '\"outcome\": \"win\"' $F") / 480"
  done
done
