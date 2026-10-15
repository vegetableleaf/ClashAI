#!/bin/bash
# SIM side of opp_behaviour.py on a pod: 960 paired games (seeds 741200 + 742000), learner r1 under the deployed stack (gap.py arm D3),
# opponents drawn from the LIVE-MIRRORED pool (L74/mix/decks_live_eval.json, P(deck) ~ live frequency), opponent policy E4 at T .1
# (gap.py defaults).  Same isolated-copy telemetry patch as econ_r1_pod.sh / calib_opp_pod.sh: econ_sim_patch.py adds lr_dec /
# lr_frames / lr_plays to matches.jsonl and livecal gets --behaviour-telemetry.  The telemetry must not change play (check the win count
# against the same pool's un-instrumented LIVEEVAL run).  Then opp_behaviour.py turns the matches into data/sim_$NAME.json.gz.
#   Usage on a set-up pod (pod_setup_l74.sh):
#     nohup bash scratchpad/gauntlet/L74/human/opp_behaviour_pod.sh > /workspace/oppbeh.log 2>&1 &
#   Env: NAME (default LIVEPOOL_r1), OPP_T (default .1), OPP_CKPT (default: gap.py's E4), WORKERS (default 13), CK (learner)
#   Copy back (to the laptop): $O/sim_$NAME.json.gz -> scratchpad/gauntlet/L74/human/data/, then
#     python opp_behaviour.py report --sim ECON_r1 $NAME      (first --sim = the primary comparison; put $NAME first for the live-mirrored one)
set -Eeuo pipefail
CB=${CB:-/workspace/clashbot}; ISO=${ISO:-/workspace/oppbeh/repo}; NAME=${NAME:-LIVEPOOL_r1}; O=${O:-/workspace/results/OPPBEH_$NAME}
PY=${PY:-/workspace/venv33/bin/python}; W=${WORKERS:-13}; T=${OPP_T:-.1}
CK=${CK:-icebow/data/bench/rl_royale/newsim_r1/newsim_base_r1_final_grafted.pt}
rm -rf "$ISO"; mkdir -p "$ISO" "$O"
tar -C "$CB" --exclude=./icebow/data --exclude=./research -cf - . | tar -C "$ISO" -xf -
ln -s "$CB/icebow/data" "$ISO/icebow/data"; ln -s "$CB/research" "$ISO/research"
$PY "$ISO/scratchpad/gauntlet/L74/loss_review/econ_sim_patch.py" "$ISO/pipeline"
sed -i "s/'--hero-abilities', '--ability-policy'/'--hero-abilities', '--behaviour-telemetry', '--ability-policy'/" \
    "$ISO/scratchpad/gauntlet/L74/livecal/livecal.py"
grep -q "'--behaviour-telemetry'" "$ISO/scratchpad/gauntlet/L74/livecal/livecal.py"   # fail loudly if the layout moved
grep -q -- "--census-file" "$ISO/scratchpad/gauntlet/L74/gap/gap.py"
cd "$ISO"
for s in 741200 742000; do
  $PY scratchpad/gauntlet/L74/gap/gap.py --ckpt $CK --out "$O/g_$s" --arms D3 --seed-start $s --workers $W --opp-T $T \
      --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json ${OPP_CKPT:+--opp-ckpt "$OPP_CKPT"} \
      --python $PY > "$O/g_$s.log" 2>&1
done
echo "matches with telemetry: $(cat "$O"/g_*/D3/*/matches.jsonl | grep -c lr_frames) / $(cat "$O"/g_*/D3/*/matches.jsonl | wc -l)"
$PY scratchpad/gauntlet/L74/human/opp_behaviour.py sim "$NAME" "$O" > "$O/extract.log" 2>&1
cp scratchpad/gauntlet/L74/human/data/sim_$NAME.json.gz "$O/"
echo OPPBEH_DONE
