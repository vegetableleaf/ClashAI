#!/bin/bash
# Owner 2026-10-14 ~20:50: "after A/B3 finishes, deploy the tornado fix for 40 matches just to see if it ever gets put to use,
# then move on to A/B4." Launched via WMI; log scratchpad/gauntlet/L74/ab/post_ab3_chain.out; Discord at every stage.
#  1. wait for A/B3 + its auto-switch to finish; abort (alert) unless the auto-switch put an arm live
#  2. LIVE_OPTIONS += --tornado-river on (backup first, --check must pass), restart live between matches (restart_live.py)
#  3. wait for 40 finished river-on matches; usage audit (reward/tornado_usage.py) -> TORNADO_USAGE_40.txt + Discord
#  4. A/B4 = --tau-threatened 0.2 off (A) vs on (B), one change, same checkpoint, river fix kept ON in both arms:
#     stop live between matches; base LIVE_OPTIONS = current minus "--tau-threatened 0.2" (backup); B adds it back via
#     --arm-extra, so either winner leaves the right file live (auto-switch carries B's flag); 150/arm.
cd /c/Users/benpe/ClashBot || exit 1
AB=scratchpad/gauntlet/L74/ab; L=scratchpad/gauntlet/L70/live; PY=icebow/.venv/Scripts/python.exe
LOGS=scratchpad/gauntlet/L68/live_reader
log() { echo "$(date '+%F %T') $*"; }
post() { printf '%s\n' "$*" > $AB/_chain_msg.txt; $PY scratchpad/gauntlet/L69/discord/post.py $AB/_chain_msg.txt > /dev/null 2>&1; log "discord: $*"; }
live_running() {   # bracket patterns never match this check's own command line
  [ "$(powershell -NoProfile -Command "@(Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -match '[l]ive_play\.py|[r]un_live\.sh' }).Count" | tr -d '\r')" != 0 ]; }

# 1. A/B3 done?
until grep -q "auto-switch exited" $AB/ab3_launch.out 2>/dev/null; do sleep 120; done
if ! grep -q "started live on" $AB/ab3_autoswitch.out; then
  post ":rotating_light: [post-A/B3 chain] A/B3 ended without an auto-switch (see ab3_autoswitch.out); chain stopped, live left as is."; exit 2
fi
if ! grep -q "account check: True" $AB/ab3_autoswitch.out; then   # a failed guard set STOP; restart_live would clear it
  post ":rotating_light: [post-A/B3 chain] A/B3's auto-switch did not pass the main-account check; chain stopped, live left as is."; exit 2
fi
log "A/B3 done: $(grep 'started live on' $AB/ab3_autoswitch.out | tail -1)"
sleep 300    # let the auto-switch's account check and first match settle

# 2. tornado fix on
STAMP=$(date +%Y%m%d_%H%M); cp -p $L/LIVE_OPTIONS $L/LIVE_OPTIONS.pre_tornado_river_$STAMP
grep -q -- "--tornado-river" $L/LIVE_OPTIONS || sed -i 's/$/ --tornado-river on/' $L/LIVE_OPTIONS
if ! bash $L/start_live.sh icebow --check 2>&1 | tail -1 | grep -q LIVE_CHECK_PASS; then
  cp -p $L/LIVE_OPTIONS.pre_tornado_river_$STAMP $L/LIVE_OPTIONS
  post ":rotating_light: [post-A/B3 chain] --tornado-river on failed the live --check; LIVE_OPTIONS restored, chain stopped."; exit 3
fi
T0=$(date +%Y%m%d_%H%M%S)
$PY scratchpad/gauntlet/L74/deploy/restart_live.py "Tornado river fix ON for 40 matches (owner: see whether it ever gets used)" || {
  post ":rotating_light: [post-A/B3 chain] restart with --tornado-river failed; check live."; exit 4; }

# 3. 40 finished river-on matches
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
until [ "$(count_on | grep -c .)" -ge 40 ]; do sleep 300; done
count_on | head -40 > $AB/tornado_river_40.list
PYTHONPATH=. $PY scratchpad/gauntlet/L74/reward/tornado_usage.py $(cat $AB/tornado_river_40.list) > scratchpad/gauntlet/L74/reward/TORNADO_USAGE_40.txt 2>&1
post "[ClashAI] Tornado river fix, 40 live matches: $(tail -1 scratchpad/gauntlet/L74/reward/TORNADO_USAGE_40.txt). Starting A/B4 (--tau-threatened off vs on)."

# 4. A/B4
touch $L/STOP
for i in $(seq 1 60); do live_running || break; sleep 30; done
if live_running; then post ":rotating_light: [post-A/B3 chain] live did not stop within 30 min for A/B4; STOP left, chain stopped."; exit 5; fi
cp -p $L/LIVE_OPTIONS $L/LIVE_OPTIONS.pre_ab4_$(date +%Y%m%d_%H%M)
sed -i 's/ --tau-threatened 0\.2//' $L/LIVE_OPTIONS
if grep -q -- "--tau-threatened" $L/LIVE_OPTIONS; then post ":rotating_light: [post-A/B3 chain] could not remove --tau-threatened from LIVE_OPTIONS; chain stopped."; exit 6; fi
CK=$(tr -d '\r\n' < $L/CKPT_OVERRIDE)
A="A:notau:$CK:off"; B="B:tau:$CK:off"; BX="B=--tau-threatened 0.2"
[ -e $AB/STOP_AB ] && mv $AB/STOP_AB $AB/STOP_AB.old_$(date +%H%M)
log "starting A/B4: $A | $B ($BX)"
$PY $AB/live_ab.py --arm "$A" --arm "$B" --arm-extra "$BX" --block 5 --total 150 >> $AB/ab4_run.out 2>&1 &
runner=$!
for i in $(seq 1 60); do [ -e $AB/RUNNING.lock ] && break; sleep 5; done
if [ -e $AB/RUNNING.lock ]; then
  RID=$(sed -n 's/.*"run_id": "\([^"]*\)".*/\1/p' $AB/RUNNING.lock)
  post "[ClashAI] A/B4 started (run $RID): A = --tau-threatened off, B = on (0.2), same model, river fix on in both, 150/arm."
  $PY $AB/ab_autoswitch.py --run-id $RID --arm "$A" --arm "$B" --arm-extra "$BX" --total 150 >> $AB/ab4_autoswitch.out 2>&1 &
else
  post ":rotating_light: [post-A/B3 chain] the A/B4 runner did not start (ab4_run.out); live is stopped."
fi
wait $runner; log "A/B4 runner exited $?"
wait; log "chain done"
