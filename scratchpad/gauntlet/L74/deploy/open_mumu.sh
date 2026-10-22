#!/bin/bash
# open_mumu.sh -- owner 10-21: "if a new model gets promoted, open MuMu yourself and start up a ranked run". Boots MuMu
# instance 0 (the only one) via MuMuManager and waits until Android reports started; start_live.sh then does the adb
# boot wait, launches Clash Royale and clears the MuMu store overlay. Exit 0 = Android up, 1 = not up within 5 min.
# Use before deploy_ckpt.sh when MuMu is closed. Does nothing (exit 0) if the instance is already running.
M='/c/Program Files/Netease/MuMuPlayer/nx_main/MuMuManager.exe'
up() { "$M" info -v 0 2>/dev/null | grep -q '"is_android_started": true'; }
up && { echo "MuMu already running"; exit 0; }
"$M" control -v 0 launch > /dev/null 2>&1
for i in $(seq 1 60); do up && { echo "MuMu Android started after $((i * 5)) s"; sleep 20; exit 0; }; sleep 5; done
echo "MuMu did not start within 5 min"; exit 1
