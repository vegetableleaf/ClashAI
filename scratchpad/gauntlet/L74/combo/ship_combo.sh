#!/bin/bash
# Laptop: ship the combo code (working tree, LF) into a pod's /workspace/cb_combo = a copy of its /workspace/cb_tt (the fast-plays eval
# tree) + this overlay + pod_patch.py; prints the shipped files' sha256.   ship_combo.sh HOST PORT
set -euo pipefail
H=$1; P=$2; REPO=/c/Users/benpe/ClashBot
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -o StrictHostKeyChecking=no -i $HOME/.ssh/runpod_clashbot"
FILES="pipeline/decision_options.py pipeline/e1_eval.py pipeline/live_gen_v2.py pipeline/live_gen.py pipeline/royale_env.py
  pipeline/spell_value.py pipeline/search_s0.py pipeline/tests/test_rocket_tornado_v2.py pipeline/tests/test_rocket_value2.py
  pipeline/tests/test_e1_follow_up_selfplay.py pipeline/tests/test_tornado_river.py pipeline/tests/test_e1_pipeline_decisions.py
  $(for f in bridge_probe.py combo_arms.py combo_jobs.py cur_picks_741200.json cur_picks_742000.json combo_queue.sh combo_smoke.py dump_live_board.py fit_window.py identity_check.py measure_shim.py pod_patch.py ship_combo.sh scen_combo.sh analyze_combo.py; do [ -e $REPO/scratchpad/gauntlet/L74/combo/$f ] && echo scratchpad/gauntlet/L74/combo/$f; done; true)"
ST=$(mktemp -d); cd $REPO
for f in $FILES; do mkdir -p $ST/$(dirname $f); tr -d '\r' < $f > $ST/$f; done
(cd $ST && sha256sum $FILES | sed 's/ \*/  /') > $ST/overlay.sha
ssh -n $K -p $P root@$H "test -d /workspace/cb_combo || cp -a /workspace/cb_tt /workspace/cb_combo"
(cd $ST && tar cf - $FILES overlay.sha) | ssh $K -p $P root@$H "cd /workspace/cb_combo && tar xf - --no-same-owner && sha256sum -c --quiet overlay.sha && echo OVERLAY_OK && /workspace/venvf36/bin/python scratchpad/gauntlet/L74/combo/pod_patch.py /workspace/cb_combo"
cat $ST/overlay.sha; rm -rf $ST
