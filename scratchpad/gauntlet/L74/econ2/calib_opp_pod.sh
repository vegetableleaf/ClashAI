#!/bin/bash
# Owner 10-14: SIM opponents tuned to LIVE pressure. Learner = r1 full graft, gap.py D3 (the deployed stack), seed set
# 741200 (480 games: evo + lad censuses); one arm per opponent generalist x sampling temperature. Econ telemetry in an
# ISOLATED copy (as econ_r1_pod.sh). Baseline E4 @ .1 = CAL set c = the econ run's g_741200 (no rerun).
# Targets (live r1, punish.py / econ2): lost-episode rate 45.7% (< 4 elixir) / 18.8% (>= 4), pushes met < 4 elixir 66%,
# push rate / value (econ2 calib), win rate 50.7%.
# Usage on a set-up pod: nohup bash calib_opp_pod.sh NAME:OPP_CKPT:T [NAME:OPP_CKPT:T ...] > /workspace/calib.log 2>&1 &
set -Eeuo pipefail
CB=${CB:-/workspace/clashbot}; ISO=${ISO:-/workspace/calib/repo}; O=${O:-/workspace/results/CALIB}
PY=${PY:-/workspace/venv33/bin/python}; W=${WORKERS:-12}; SEED=${SEED:-741200}
CK=icebow/data/bench/rl_royale/newsim_r1/newsim_base_r1_final_grafted.pt
mkdir -p "$O"
if [ ! -d "$ISO/pipeline" ]; then
  mkdir -p "$ISO"
  tar -C "$CB" --exclude=./icebow/data --exclude=./research -cf - . | tar -C "$ISO" -xf -
  ln -s "$CB/icebow/data" "$ISO/icebow/data"; ln -s "$CB/research" "$ISO/research"
  $PY "$ISO/scratchpad/gauntlet/L74/loss_review/econ_sim_patch.py" "$ISO/pipeline"
  sed -i "s/'--hero-abilities', '--ability-policy'/'--hero-abilities', '--behaviour-telemetry', '--ability-policy'/" \
      "$ISO/scratchpad/gauntlet/L74/livecal/livecal.py"
fi
# the pods' $CB predates gap.py --opp-ckpt/--opp-T (running jobs use it): the isolated copy gets the uploaded version
[ -f /workspace/in/gap.py ] && cp /workspace/in/gap.py "$ISO/scratchpad/gauntlet/L74/gap/gap.py"
grep -q -- "--opp-ckpt" "$ISO/scratchpad/gauntlet/L74/gap/gap.py"
grep -q "'--behaviour-telemetry'" "$ISO/scratchpad/gauntlet/L74/livecal/livecal.py"
[ -e /root/ClashBot ] || ln -s "$ISO" /root/ClashBot          # econ2/econ_gap read ~/ClashBot (VM layout)
cd "$ISO"
for spec in "$@"; do
  IFS=: read -r N OPP T <<< "$spec"
  [ -f "$OPP" ] || { echo "missing opponent $OPP"; continue; }
  echo "$(date -u +%T) arm $N: opponent $OPP $(sha256sum $OPP | cut -c1-12) T $T"
  $PY scratchpad/gauntlet/L74/gap/gap.py --ckpt $CK --out "$O/g_$N" --arms D3 --seed-start $SEED --workers $W \
      --opp-ckpt "$OPP" --opp-T "$T" --python $PY > "$O/g_$N.log" 2>&1 || { echo "arm $N FAILED"; continue; }
  grep -E "^D3:" "$O/g_$N/SUMMARY.txt" || true
  mkdir -p "$O/econ/${N}_evo" "$O/econ/${N}_lad"; rm -f "$O/econ/${N}"_*/matches.jsonl
  for run in "$O/g_$N"/D3/*/run.json; do
    c=$(grep -o 'cal_\(evo\|lad\)\.json' "$run" | head -1); c=${c#cal_}; c=${c%.json}
    cat "$(dirname "$run")/matches.jsonl" >> "$O/econ/${N}_$c/matches.jsonl"
  done
  $PY scratchpad/gauntlet/L74/econ2/econ2.py sim "$O/econ" "$N" > "$O/econ2_$N.log" 2>&1 \
    && cp scratchpad/gauntlet/L74/econ2/data/sim_$N.json.gz "$O/" || echo "econ2 $N FAILED"
done
echo CALIB_DONE
