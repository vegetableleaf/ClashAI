#!/bin/bash
# Owner 10-15 ~16:30: "please work to get a better model deployed". Live-mirrored SIM eval (L74/mix/live_cmp.py, 960 paired,
# D3, F1 u65): --tau-phase 0.45 0.55 0.65 ("defensive") 56.0% vs the deployed 0.35 0.45 0.55 52.7%: +3.33 pp [-0.52, +7.19]
# (beatdown +7.1 +- 5.8, rest +0.9 +- 5.1); aggressive 0.25/0.35/0.45 +2.40 n.s. Best measured option, not worse anywhere.
# Swap the tau-phase in LIVE_OPTIONS (backup), --check, restart between matches, first-match guard. Revert = the backup file.
cd /c/Users/benpe/ClashBot || exit 1
L=scratchpad/gauntlet/L70/live; AB=scratchpad/gauntlet/L74/ab; PY=icebow/.venv/Scripts/python.exe
log() { echo "$(date '+%F %T') $*"; }
post() { printf '%s\n' "$*" > $AB/_dep_msg.txt; $PY scratchpad/gauntlet/L69/discord/post.py $AB/_dep_msg.txt > /dev/null 2>&1; log "discord: $*"; }
BK=$L/LIVE_OPTIONS.pre_def_tau_$(date +%Y%m%d_%H%M); cp -p $L/LIVE_OPTIONS $BK
sed -i 's/--tau-phase 0.35 0.45 0.55/--tau-phase 0.45 0.55 0.65/' $L/LIVE_OPTIONS
grep -q -- "--tau-phase 0.45 0.55 0.65" $L/LIVE_OPTIONS || { cp -p $BK $L/LIVE_OPTIONS; post ":rotating_light: [deploy def tau] tau-phase swap failed; unchanged."; exit 2; }
if ! bash $L/start_live.sh icebow --check 2>&1 | tail -1 | grep -q LIVE_CHECK_PASS; then
  cp -p $BK $L/LIVE_OPTIONS; post ":rotating_light: [deploy def tau] live --check failed; LIVE_OPTIONS restored."; exit 3
fi
T0=$(date +%Y%m%d_%H%M%S)
$PY scratchpad/gauntlet/L74/deploy/restart_live.py "defensive gate thresholds (tau-phase 0.45/0.55/0.65) on F1 u65: live-mirrored SIM +3.3 pp vs deployed" || {
  post ":rotating_light: [deploy def tau] restart failed; check live."; exit 4; }
$PY $AB/first_match_guard.py --after $T0 > $AB/def_tau_guard.out 2>&1; rc=$?
log "guard exit $rc: $(tail -1 $AB/def_tau_guard.out)"
[ $rc = 0 ] && post "[ClashAI] Live now F1 u65 with DEFENSIVE gate thresholds (tau-phase 0.45/0.55/0.65): live-mirrored SIM 56.0% vs 52.7% deployed (+3.3 pp [-0.5, +7.2]; beatdown +7.1). Revert = $BK."
