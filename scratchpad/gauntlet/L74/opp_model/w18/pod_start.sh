#!/bin/bash
# W18 laptop launcher (Git Bash) for the dedicated opponent pod (DIAG_12.md section 5):
#   bash scratchpad/gauntlet/L74/opp_model/w18/pod_start.sh ship     # W18 code onto cb_stepd (git archive, autocrlf off, sha-checked)
#   bash scratchpad/gauntlet/L74/opp_model/w18/pod_start.sh check    # inputs present with the right sha
#   bash scratchpad/gauntlet/L74/opp_model/w18/pod_start.sh jobs     # append the first queue (streams A, B) and start both runners
#   bash scratchpad/gauntlet/L74/opp_model/w18/pod_start.sh status   # runner logs + job rows
# Pod: 157.157.221.29 -p 33401 (owner-rented 10-22, dedicated to W18). Never touches 32525 / 33572.
set -uo pipefail
H=root@157.157.221.29; PORT=33401; KEY=$HOME/.ssh/runpod_clashbot; R=/c/Users/benpe/ClashBot; CB=/workspace/cb_stepd
L=scratchpad/gauntlet/L74/opp_model
on() { ssh -o ConnectTimeout=20 -i $KEY -p $PORT $H "$@"; }
CLX=icebow/data/bench/rl_royale/rlarm_stepd_ctrl_nos2/rlarm_stepd_ctrl_nos2_u0130_grafted.pt
OPP=icebow/data/pipeline/o2/w14opp_I.pt
FILES="pipeline/e1_eval.py pipeline/search_s0.py pipeline/tests/test_tap_loss.py $L/w18/w18_eval.sh $L/w18/w18_runner.sh
       $L/w18/paired.py $L/cfg/oppW18R1_redirect_s74.yaml $L/pod/o3_patch.py $L/w14/pos_patch.py"
case ${1:-} in
ship)
  cd $R && git -c core.autocrlf=false archive HEAD $FILES | on "tar -x -C $CB" || { echo "ARCHIVE FAIL"; exit 3; }
  for f in $FILES; do
    a=$(git -C $R show HEAD:$f | sha256sum | cut -c1-64); b=$(on "sha256sum $CB/$f" | cut -c1-64)
    [ "$a" = "$b" ] || { echo "SHA FAIL $f"; exit 3; }
  done
  on "mkdir -p /workspace/w18 && cp $CB/$L/w18/w18_eval.sh $CB/$L/w18/w18_runner.sh /workspace/w18/"
  echo "shipped $(echo $FILES | wc -w) files, sha ok" ;;
check)
  on "cd $CB && sha256sum $CLX $OPP | cut -c1-16 && ls /workspace/venvf15/bin/python && nproc && nvidia-smi --query-gpu=name,memory.used --format=csv,noheader
      grep -c parse_tap_loss pipeline/e1_eval.py; ps -eo pid,args | grep -E 'gap.py|rl_royale|w18_runner' | grep -v grep | head" ;;
jobs)
  on "cd /workspace/w18 && cat >> jobs_A.txt <<'EOF'
cd /workspace/w18 && EVLOCK=/workspace/w18/evalA.lock bash w18_eval.sh w18_Iu40_base $CLX $OPP 0.1 40 - 741200
cd /workspace/w18 && EVLOCK=/workspace/w18/evalA.lock W18_EXTRA='--tap-loss 1x:0.0180,2x:0.0363,ot2x:0.0388,ot3x:0.0890 --tap-slow 0.151:17' bash w18_eval.sh w18_Iu40_tl $CLX $OPP 0.1 40 - 741200 742000 743000 744000 745000 746000
EOF
cat >> jobs_B.txt <<'EOF'
cd /workspace/w18 && EVLOCK=/workspace/w18/evalB.lock O3_POS=1 W18_EXTRA='--opp-tau 0.45' bash w18_eval.sh w18_Iu40_tau45_pos $CLX $OPP 0.1 40 - 741200
cd /workspace/w18 && EVLOCK=/workspace/w18/evalB.lock O3_POS=1 W18_EXTRA='--opp-tau 0.35' bash w18_eval.sh w18_Iu40_tau35_pos $CLX $OPP 0.1 40 - 741200
cd /workspace/w18 && EVLOCK=/workspace/w18/evalB.lock O3_POS=1 W18_EXTRA='--opp-tau 0.55' bash w18_eval.sh w18_Iu40_tau55_pos $CLX $OPP 0.1 40 - 741200
EOF
for s in A B; do ( pgrep -f \"w18_runner.sh \$s\" || setsid nohup bash /workspace/w18/w18_runner.sh \$s ) > /dev/null 2>&1 < /dev/null & done
sleep 3; ps -eo pid,args | grep w18_runner | grep -v grep" ;;
r1)   # opponent round R1 inputs + queue: training at the end of stream A, its gate watcher at the end of stream B
  for f in icebow/data/bench/rl_royale/rlarm_gae_cue_ab2/rlarm_gae_cue_ab2_u0065_grafted.pt \
           icebow/data/bench/rl_royale/rlarm_gae_cue_u250/rlarm_gae_cue_u250_u0130_grafted.pt; do
    on "test -f $CB/$f" && continue
    on "mkdir -p $CB/$(dirname $f)" && scp -q -i $KEY -P $PORT $R/$f $H:$CB/$f.w18tmp && on "mv $CB/$f.w18tmp $CB/$f"
    [ "$(sha256sum $R/$f | cut -c1-64)" = "$(on "sha256sum $CB/$f" | cut -c1-64)" ] || { echo "SHA FAIL $f"; exit 3; }
    echo "shipped $f"
  done
  cd $R && git -c core.autocrlf=false archive HEAD $L/w18/w18_gate.sh | on "tar -x -C $CB && cp $CB/$L/w18/w18_gate.sh /workspace/w18/"
  # I's recipe needs the MIRRORED Ranked 3:00 states at rl_royale.OT_STATES (the learner is the opponent-to-be; W14 8.x):
  # new inode via mv (never write through a hard link into an eval copy); the original is kept beside it
  on "cd $CB && mkdir -p icebow/data/pipeline/o2/w14 && cp icebow/data/pipeline/o2/w14opp_I.pt icebow/data/pipeline/o2/w14/i_u40.pt
      sha256sum icebow/data/pipeline/o2/w14/i_u40.pt | grep -q ^4ff9fe93b02d || { echo I_U40_SHA_FAIL; exit 3; }
      N=scratchpad/gauntlet/L74/nextround; M=scratchpad/gauntlet/L74/opp_model/w14/ot_states_mirror.json
      [ -f \$N/ot_states_original.json ] || cp \$N/ot_states.json \$N/ot_states_original.json
      cp \$M \$N/ot_states.json.w18tmp && mv \$N/ot_states.json.w18tmp \$N/ot_states.json
      cmp -s \$M \$N/ot_states.json && echo MIRROR_OK || { echo MIRROR_FAIL; exit 3; }
      cd /workspace/w18 && echo 'RUN=oppW18R1_redirect_s74 OUTD=/workspace/w18 VENV=/workspace/venvf15 RT=fin15-linux SMOKE_EXTRA=outlived_pp=100 TLOCK=/workspace/w18/train.lock bash $CB/$L/optC/w7_train.sh' >> jobs_A.txt
      echo 'cd /workspace/w18 && RUN=rlarm_oppW18R1_redirect_s74 YAML=oppW18R1_redirect_s74 EVERY=5 EVLOCK=/workspace/w18/evalB.lock bash /workspace/w18/w18_gate.sh' >> jobs_B.txt
      tail -1 jobs_A.txt; tail -1 jobs_B.txt" ;;
status)
  on "tail -5 /workspace/w18/runner_A.log /workspace/w18/runner_B.log 2>/dev/null; for d in /workspace/w18/o3/out/*/; do
      echo \"\$(basename \$d): \$(cat \$d/*/D3/matches.jsonl 2>/dev/null | wc -l) rows \$(ls \$d/ALL_DONE 2>/dev/null)\"; done; uptime" ;;
*) echo "usage: pod_start.sh ship|check|jobs|status"; exit 2 ;;
esac
