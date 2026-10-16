#!/bin/bash
# Switch the live icebow checkpoint between matches (generic; 10-15 owner: "please work to get a better model deployed").
#   deploy_ckpt.sh CKPT SHA16 "why" [wire]   CKPT = repo path under icebow/data/...; SHA16 = expected first 16 hex of its sha256
#   wire = owner 10-15 night ("wire it into live_play.py/start_live.sh, but don't start a live run yourself"): stop after the
#          offline --check (start_live.sh --check exits before any MuMu/ADB side effect); no restart, no guard.
# Backs up CKPT_OVERRIDE, writes CKPT, --check (sha must match), restart_live.py (between matches), first-match guard
# (main account + icebow deck), Discord. LIVE_OPTIONS / deck / fast / emotes unchanged. Revert = the CKPT_OVERRIDE backup.
cd /c/Users/benpe/ClashBot || exit 1
CK=$1; SHA=$2; WHY=$3; MODE=${4:-}
L=scratchpad/gauntlet/L70/live; AB=scratchpad/gauntlet/L74/ab; PY=icebow/.venv/Scripts/python.exe
log() { echo "$(date '+%F %T') $*"; }
post() { printf '%s\n' "$*" > $AB/_dep_msg.txt; $PY scratchpad/gauntlet/L69/discord/post.py $AB/_dep_msg.txt > /dev/null 2>&1; log "discord: $*"; }
[ "$(sha256sum $CK | cut -c1-16)" = "$SHA" ] || { post ":rotating_light: [deploy] $CK sha is not $SHA; nothing changed."; exit 2; }
BK=$L/CKPT_OVERRIDE.pre_$(date +%Y%m%d_%H%M); cp -p $L/CKPT_OVERRIDE $BK
printf 'C:/Users/benpe/ClashBot/%s\n' "$CK" > $L/CKPT_OVERRIDE
if ! bash $L/start_live.sh icebow --no-fast-plays --check 2>&1 | tail -1 | grep -q "LIVE_CHECK_PASS.*$SHA"; then
  cp -p $BK $L/CKPT_OVERRIDE; post ":rotating_light: [deploy] live --check failed for $CK; CKPT_OVERRIDE restored."; exit 3
fi
if [ "$MODE" = wire ]; then
  post "[ClashAI] Live checkpoint WIRED (not started) -> $(basename $CK) ($SHA): $WHY. start_live.sh icebow --no-fast-plays will use it; offline --check passed. Revert = $BK."; exit 0
fi
T0=$(date +%Y%m%d_%H%M%S)
$PY scratchpad/gauntlet/L74/deploy/restart_live.py "checkpoint -> $(basename $CK): $WHY" || { post ":rotating_light: [deploy] restart failed; check live."; exit 4; }
$PY $AB/first_match_guard.py --after $T0 > $AB/deploy_guard.out 2>&1; rc=$?
log "guard exit $rc: $(tail -1 $AB/deploy_guard.out)"
if [ $rc = 0 ]; then post "[ClashAI] Live checkpoint -> $(basename $CK) ($SHA): $WHY. First match passed the guard. Revert = $BK."
else post ":rotating_light: [deploy] first-match guard failed (exit $rc): $(tail -1 $AB/deploy_guard.out)"; fi
