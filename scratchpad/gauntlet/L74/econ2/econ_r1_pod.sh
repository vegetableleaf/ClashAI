#!/bin/bash
# Owner plan 10-14 (step 3 follow-up): does r1 meet pushes with low elixir in the SIM too, or only live?
# Same definitions as the live loss review (econ2 / econ_gap: push = enemy value on my half >= 7 after >= 80 ticks below;
# elixir at push start = raw elixir then). Learner = r1 full graft (live), gap.py arm D3 (the deployed rule stack),
# standard 960 pairs (seed sets 741200 + 742000), runtime 20261012-linux.
# Runs in an ISOLATED copy (never $CB): econ_sim_patch.py adds lr_dec / lr_frames / lr_plays telemetry, and livecal's
# search command gets --behaviour-telemetry. Output: $O/econ/r1_{evo,lad}/matches.jsonl for `econ2.py sim $O/econ r1`.
# Usage on a set-up pod (pod_setup_l74.sh): nohup bash econ_r1_pod.sh > /workspace/econ_r1.log 2>&1 &
set -Eeuo pipefail
CB=${CB:-/workspace/clashbot}; ISO=${ISO:-/workspace/econ_r1/repo}; O=${O:-/workspace/results/ECON_r1}
PY=${PY:-/workspace/venv33/bin/python}; W=${WORKERS:-13}
CK=icebow/data/bench/rl_royale/newsim_r1/newsim_base_r1_final_grafted.pt
rm -rf "$ISO"; mkdir -p "$ISO" "$O/econ/r1_evo" "$O/econ/r1_lad"
tar -C "$CB" --exclude=./icebow/data --exclude=./research -cf - . | tar -C "$ISO" -xf -
ln -s "$CB/icebow/data" "$ISO/icebow/data"; ln -s "$CB/research" "$ISO/research"
$PY "$ISO/scratchpad/gauntlet/L74/loss_review/econ_sim_patch.py" "$ISO/pipeline"
sed -i "s/'--hero-abilities', '--ability-policy'/'--hero-abilities', '--behaviour-telemetry', '--ability-policy'/" \
    "$ISO/scratchpad/gauntlet/L74/livecal/livecal.py"
grep -q "'--behaviour-telemetry'" "$ISO/scratchpad/gauntlet/L74/livecal/livecal.py"   # fail loudly if the layout moved
cd "$ISO"
for s in 741200 742000; do
  $PY scratchpad/gauntlet/L74/gap/gap.py --ckpt $CK --out "$O/g_$s" --arms D3 --seed-start $s --workers $W \
      --python $PY > "$O/g_$s.log" 2>&1
done
# gap writes one chunk per job; route each chunk's matches to its census (cal_evo.json / cal_lad.json)
for run in "$O"/g_*/D3/*/run.json; do
  c=$(grep -o 'cal_\(evo\|lad\)\.json' "$run" | head -1); c=${c#cal_}; c=${c%.json}
  cat "$(dirname "$run")/matches.jsonl" >> "$O/econ/r1_$c/matches.jsonl"
done
grep -c lr_dec "$O/econ/r1_evo/matches.jsonl" "$O/econ/r1_lad/matches.jsonl"
$PY scratchpad/gauntlet/L74/econ2/econ2.py sim "$O/econ" r1 > "$O/econ2_sim.log" 2>&1
cp scratchpad/gauntlet/L74/econ2/data/sim_r1.json.gz "$O/"
# the telemetry must not change play: r1 full graft D3 on these 960 pairs was 402 wins (REFIT_RESULT.md)
wins=$(cat "$O"/econ/r1_*/matches.jsonl | grep -c '"outcome": "win"' || true)
echo "D3 wins with telemetry: $wins / $(cat "$O"/econ/r1_*/matches.jsonl | wc -l) (reference 402 / 960)"
echo ECON_R1_DONE
