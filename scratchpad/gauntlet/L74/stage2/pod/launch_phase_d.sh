#!/bin/bash
# S2-09 launcher (LAPTOP side; prepared 10-18 night, for the LEAD to run in the morning on a free factorial pod -- it was NOT run).
# One pod per seed: ships the Stage-2 overlay (stage2 files + gen_v32_s0 + RAW E4 rdef_e4_u0020.pt), runs pod/setup_s2.sh
# (cb_13k / cb_tel copies, /workspace/s2), queues "smoke" then "train" for cfg/s2_all_<ARM>_s<SEED>.yaml and starts s2chain.sh.
# Never stops the pod; no watchdog. Refuses if the pod still runs any rl_royale / gap.py / search_s0 python (factorial busy).
#   bash launch_phase_d.sh build                    -> $S/s2_overlay.tar + $S/s2_manifest.sha
#   bash launch_phase_d.sh HOST PORT RUN            RUN = a cfg/ name: s2_all_{e4,il}_s{A,B} (Phase D) or s2_hog_il_ts (C iteration)
# e.g. F1: bash launch_phase_d.sh 81.27.69.177 23363 s2_hog_il_ts ;  F2: bash launch_phase_d.sh 64.247.206.79 19400 s2_all_il_sA
set -euo pipefail
S=/c/Users/benpe/AppData/Local/Temp/claude/C--Users-benpe-ClashBot/f4e7cd66-2122-4134-a1d2-d45291b5bc2a/scratchpad/s2
R=/c/Users/benpe/ClashBot; L=scratchpad/gauntlet/L74/stage2
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -o StrictHostKeyChecking=no -i $HOME/.ssh/runpod_clashbot"
if [ "$1" = build ]; then
  cd $R; mkdir -p $S
  FILES="$L/mkcfg_stage2.py $L/mkcfg_phase_d.py $L/cfg/base_exploit.yaml $L/cfg/s2_hog_e4.yaml $L/cfg/s2_hog_il.yaml $L/cfg/s2_all_e4_sA.yaml
    $L/cfg/s2_all_e4_sB.yaml $L/cfg/s2_all_il_sA.yaml $L/cfg/s2_all_il_sB.yaml $L/cfg/s2_hog_il_ts.yaml $L/mkcfg_c_iter.py $L/pools/decks_hog_train.json $L/pools/mk_hog_train.py
    $L/pod/s2chain.sh $L/pod/dry.py $L/pod/cfgcheck_s2.py $L/pod/setup_s2.sh $L/levels/levels13k.json $L/mvp/decks_hog_eval.json
    $L/gate/gate_fit.py $L/gate/gate_s2.py icebow/data/pipeline/gen_v32_s0/gen_s0.pt icebow/data/pipeline/gen_v32_s0/final_gen_s0.json
    icebow/data/pipeline/gen_v32_s0/hist_gen_s0.json icebow/data/bench/rl_royale/rdef_e4/rdef_e4_u0020.pt"
  ! grep -lU $'\r' $L/pod/*.sh $L/cfg/*.yaml || { echo "CRLF in a shipped file"; exit 1; }
  tar cf $S/s2_overlay.tar $FILES && sha256sum $FILES | sed 's/ \*/  /' > $S/s2_manifest.sha
  grep -q "^7fb666811d8b46de12463bc497aded98fcfde62f732917f64b0f76244b24a830  icebow/data/bench/rl_royale/rdef_e4/rdef_e4_u0020.pt" $S/s2_manifest.sha
  grep -q "^61011b6ce5e655c0f66c875ee844685373cc6370051f9eccba1e1d79de1a0569  icebow/data/pipeline/gen_v32_s0/gen_s0.pt" $S/s2_manifest.sha
  echo "built: $(wc -l < $S/s2_manifest.sha) files, $(du -h $S/s2_overlay.tar | cut -f1)"; exit 0
fi
H=$1; P=$2; RUN=$3; CFG=$L/cfg/$RUN.yaml
[ -f $R/$CFG ] || { echo "no $CFG"; exit 1; }
busy=$(ssh -n $K -p $P root@$H 'ps -eo args | grep -v grep | grep -cE "python.*(rl_royale|gap\.py|search_s0|livecal)"' || true)
[ "$busy" = 0 ] || { echo "pod $H:$P busy ($busy python jobs): not launched"; exit 2; }
scp -q $K -P $P $S/s2_overlay.tar $S/s2_manifest.sha root@$H:/workspace/in/
ssh -n $K -p $P root@$H "cd /workspace/cb_tt && tar xf /workspace/in/s2_overlay.tar --no-same-owner $L/pod/setup_s2.sh && bash $L/pod/setup_s2.sh | tail -6 && \
  cd /workspace/cb_tt && PYTHONPATH=. /workspace/venvf36/bin/python $L/pod/cfgcheck_s2.py | tail -2 && \
  printf 'smoke ${RUN}_smoke $CFG\ntrain $RUN $CFG\n' >> /workspace/s2/queue.txt && cat /workspace/s2/queue.txt && \
  { [ "$(ps -eo args | grep -c '^bash /workspace/s2/s2chain[.]sh')" != 0 ] || (setsid nohup bash /workspace/s2/s2chain.sh > /dev/null 2>&1 < /dev/null &); } && \
  sleep 3 && tail -2 /workspace/s2/chain.log"
