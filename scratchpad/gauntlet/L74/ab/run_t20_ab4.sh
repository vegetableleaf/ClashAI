#!/bin/bash
# Owner 2026-10-15 ~12:25: "let's run just 20 tornado fix matches, then move on to A/B4." (replaces the killed
# post_ab3_chain.sh's 40). Live was STOPPED by the owner (bait witness session); F1 u65 is CKPT_OVERRIDE. Launch via WMI;
# log scratchpad/gauntlet/L74/ab/t20_ab4.out; Discord at every stage.
#  1. LIVE_OPTIONS += --tornado-river on (backup first, --check must pass); start live (restart_live.py)
#  2. first-match guard (first_match_guard.py): MAIN account AND the icebow deck (the classic challenge may have left the
#     battle deck on bait) -- else STOP + alert, chain ends
#  3. 20 finished river-on matches -> reward/tornado_usage.py -> TORNADO_USAGE_20.txt + Discord
#  4. A/B4 = --tau-threatened 0.2 off (A) vs on (B), same model (F1 u65), river fix kept ON in both arms (same in both = no
#     confound); base LIVE_OPTIONS = current minus "--tau-threatened 0.2" (backup); B adds it back via --arm-extra, so either
#     winner leaves the right file live; 75/arm (not 150: frees MuMu sooner for a successor-to-F1 A/B; SIM said no difference).
cd /c/Users/benpe/ClashBot || exit 1
AB=scratchpad/gauntlet/L74/ab; L=scratchpad/gauntlet/L70/live; PY=icebow/.venv/Scripts/python.exe
LOGS=scratchpad/gauntlet/L68/live_reader
log() { echo "$(date '+%F %T') $*"; }
post() { printf '%s\n' "$*" > $AB/_chain_msg.txt; $PY scratchpad/gauntlet/L69/discord/post.py $AB/_chain_msg.txt > /dev/null 2>&1; log "discord: $*"; }
live_running() {   # bracket patterns never match this check's own command line
  [ "$(powershell -NoProfile -Command "@(Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -match '[l]ive_play\.py|[r]un_live\.sh' }).Count" | tr -d '\r')" != 0 ]; }

if live_running; then post ":rotating_light: [tornado-20 -> A/B4] live is already running; chain not started."; exit 1; fi
[ -e $AB/RUNNING.lock ] && { post ":rotating_light: [tornado-20 -> A/B4] an A/B holds RUNNING.lock; chain not started."; exit 1; }

# 1. tornado fix on, live started
STAMP=$(date +%Y%m%d_%H%M); cp -p $L/LIVE_OPTIONS $L/LIVE_OPTIONS.pre_tornado_river_$STAMP
grep -q -- "--tornado-river" $L/LIVE_OPTIONS || sed -i 's/$/ --tornado-river on/' $L/LIVE_OPTIONS
if ! bash $L/start_live.sh icebow --check 2>&1 | tail -1 | grep -q LIVE_CHECK_PASS; then
  cp -p $L/LIVE_OPTIONS.pre_tornado_river_$STAMP $L/LIVE_OPTIONS
  post ":rotating_light: [tornado-20 -> A/B4] --tornado-river on failed the live --check; LIVE_OPTIONS restored, chain stopped."; exit 3
fi
T0=$(date +%Y%m%d_%H%M%S)
$PY scratchpad/gauntlet/L74/deploy/restart_live.py "Tornado river fix ON for 20 matches (owner: see whether it ever gets used)" || {
  post ":rotating_light: [tornado-20 -> A/B4] live start with --tornado-river failed; check live."; exit 4; }

# 2. account + deck guard on the first match
$PY $AB/first_match_guard.py --after $T0 > $AB/t20_guard.out 2>&1; rc=$?
log "guard exit $rc: $(tail -1 $AB/t20_guard.out)"
if [ $rc != 0 ]; then
  [ $rc = 3 ] && post ":rotating_light: [tornado-20 -> A/B4] no live match within 45 min of the start; chain stopped (live left as is)."
  exit 5
fi
post "[ClashAI] Tornado river fix live for 20 matches (F1 u65); first match passed the guard: $(tail -1 $AB/t20_guard.out)"

# 3. 20 finished river-on matches
count_on() { $PY -c "
import glob, json, os, sys, time
n = []
for f in sorted(glob.glob('$LOGS/live_play_*.jsonl')):
    if os.path.basename(f)[10:25] < '$T0' or time.time() - os.path.getmtime(f) < 120: continue
    with open(f, encoding='utf8', errors='replace') as fh:
        head = json.loads(fh.readline()); body = fh.read()
    if head.get('dry_run') or ((head.get('live_options') or {}).get('from_file') or {}).get('tornado_river') != 'on': continue
    if '\"event\": \"end\"' in body: n.append(f)
print('\n'.join(n))"; }
until [ "$(count_on | grep -c .)" -ge 20 ]; do sleep 300; done
count_on | tr -d "" | head -20 > $AB/tornado_river_20.list   # python on Windows prints CRLF: strip it (10-15 bug)
PYTHONPATH=. $PY scratchpad/gauntlet/L74/reward/tornado_usage.py $(cat $AB/tornado_river_20.list) > scratchpad/gauntlet/L74/reward/TORNADO_USAGE_20.txt 2>&1
post "[ClashAI] Tornado river fix, 20 live matches: $(tail -1 scratchpad/gauntlet/L74/reward/TORNADO_USAGE_20.txt). Starting A/B4 (--tau-threatened off vs on, 75/arm)."

# 4. A/B4
touch $L/STOP
for i in $(seq 1 60); do live_running || break; sleep 30; done
if live_running; then post ":rotating_light: [tornado-20 -> A/B4] live did not stop within 30 min for A/B4; STOP left, chain stopped."; exit 6; fi
cp -p $L/LIVE_OPTIONS $L/LIVE_OPTIONS.pre_ab4_$(date +%Y%m%d_%H%M)
sed -i 's/ --tau-threatened 0\.2//' $L/LIVE_OPTIONS
if grep -q -- "--tau-threatened" $L/LIVE_OPTIONS; then post ":rotating_light: [tornado-20 -> A/B4] could not remove --tau-threatened from LIVE_OPTIONS; chain stopped."; exit 7; fi
CK=$(tr -d '\r\n' < $L/CKPT_OVERRIDE)
A="A:notau:$CK:off"; B="B:tau:$CK:off"; BX="B=--tau-threatened 0.2"
[ -e $AB/STOP_AB ] && mv $AB/STOP_AB $AB/STOP_AB.old_$(date +%H%M)
log "starting A/B4: $A | $B ($BX)"
$PY $AB/live_ab.py --arm "$A" --arm "$B" --arm-extra "$BX" --block 5 --total 75 >> $AB/ab4_run.out 2>&1 &
runner=$!
for i in $(seq 1 60); do [ -e $AB/RUNNING.lock ] && break; sleep 5; done
if [ -e $AB/RUNNING.lock ]; then
  RID=$(sed -n 's/.*"run_id": "\([^"]*\)".*/\1/p' $AB/RUNNING.lock)
  post "[ClashAI] A/B4 started (run $RID): A = --tau-threatened off, B = on (0.2), F1 u65 both, river fix on in both, 75/arm."
  $PY $AB/ab_autoswitch.py --run-id $RID --arm "$A" --arm "$B" --arm-extra "$BX" --total 75 >> $AB/ab4_autoswitch.out 2>&1 &
else
  post ":rotating_light: [tornado-20 -> A/B4] the A/B4 runner did not start (ab4_run.out); live is stopped."
fi
wait $runner; log "A/B4 runner exited $?"
wait; log "chain done"
