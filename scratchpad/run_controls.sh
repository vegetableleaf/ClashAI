#!/bin/sh
# CONTROL ARMS. Every one of these exists to try to KILL the search result.
cd /c/Users/benpe/ClashBot/icebow || exit 1
PY=./.venv/Scripts/python.exe
RS=/c/Users/benpe/ClashBot/scratchpad/rollout_search.py
SP=/c/Users/benpe/ClashBot/scratchpad
COMMON="--matches 300 --seed0 5000000"

# 1. MINIMAL HORIZON. If 0.6 s of lookahead buys as much as 12 s, the gain is not lookahead.
PYTHONHASHSEED=0 $PY $RS $COMMON --tag h06   --horizon 0.6 --interval 5 --topk 4 > $SP/log_h06.txt   2>&1
# 2. NO SEARCH AT ALL: at every 5th decision override the gate and play the policy's top card.
PYTHONHASHSEED=0 $PY $RS $COMMON --tag fplay --horizon 5   --interval 5 --topk 4 --force-play > $SP/log_fplay.txt 2>&1
# 3. GATE THRESHOLD. Cheap tau scan first (60 matches) to find the tau that MATCHES the search
#    arm's plays/match; the winner is then re-run at n=300 as a paired control.
for T in 0.15 0.10 0.05 0.02; do
  PYTHONHASHSEED=0 $PY $RS --matches 60 --seed0 5000000 --tag tau$T --horizon 0 --gate-tau $T > $SP/log_tau$T.txt 2>&1
done
# 4. PERFECT PERCEPTION for the policy -- how much of the gap is the observation, not judgement?
PYTHONHASHSEED=0 $PY $RS $COMMON --tag pobs  --horizon 0 --perfect-obs > $SP/log_pobs.txt 2>&1
echo CONTROLSDONE
