#!/bin/bash
# Owner 10-15 ~17:00: "back to icebow. did a new model win?" -> F1 seed 76 (rlarm_gae_s76_u0065_grafted, 4987c582): live-mirrored
# SIM 550/960 57.3% vs the live F1 s74 52.7%: +4.58 pp [+0.62, +8.65] (best of 6 candidates; also +2.9 vs s74 on the old set).
# Staged by hand before this script: CKPT_OVERRIDE = s76 (backup CKPT_OVERRIDE.pre_s76_*), LIVE_OPTIONS = default tau-phase
# 0.35/0.45/0.55 (the measured setting; the defensive-tau file is LIVE_OPTIONS.pre_s76_*). Start icebow, fast plays OFF (as
# measured), emotes off; first-match guard (main account + icebow deck).
cd /c/Users/benpe/ClashBot || exit 1
L=scratchpad/gauntlet/L70/live; AB=scratchpad/gauntlet/L74/ab; PY=icebow/.venv/Scripts/python.exe
log() { echo "$(date '+%F %T') $*"; }
post() { printf '%s\n' "$*" > $AB/_s76_msg.txt; $PY scratchpad/gauntlet/L69/discord/post.py $AB/_s76_msg.txt > /dev/null 2>&1; log "discord: $*"; }
T0=$(date +%Y%m%d_%H%M%S)
bash $L/start_live.sh icebow --no-fast-plays > $AB/s76_start.out 2>&1; log "start_live exit $?: $(tail -n 2 $AB/s76_start.out | tr '\n' ' ')"
$PY $AB/first_match_guard.py --after $T0 > $AB/s76_guard.out 2>&1; rc=$?
log "guard exit $rc: $(tail -1 $AB/s76_guard.out)"
if [ $rc = 0 ]; then
  post "[ClashAI] Live = F1 seed 76 (4987c582; live-mirrored SIM 57.3% vs 52.7% for the previous F1: +4.6 pp [+0.6, +8.7]), default thresholds, fast plays off; first match passed the guard (main account, icebow)."
else
  post ":rotating_light: [deploy s76] first-match guard failed (exit $rc): $(tail -1 $AB/s76_guard.out). Live STOP set."
fi
