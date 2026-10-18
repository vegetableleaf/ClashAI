#!/bin/bash
# Overpress diagnosis evals (10-18), same paired design as the cue_ab promotion eval (fork36, D3, seeds 741200 + 742000,
# live-eval census, EXTRA flags).  Arms, one change each vs the promotion eval's cxxxviii arm (live IW rule):
#   cx_off    Mark CXXXVIII + the GENERIC IW range rule (ROYALE_HEROIW_PRESS unset = the TRAINING env's rule)
#   cx_never  Mark CXXXVIII, Hero IW never pressed
#   cx_live   Mark CXXXVIII + live rule again, with ability_stats (determinism check vs the promotion eval rows)
#   ab_head   cue_ab head again, with ability_stats
#   setsid nohup bash run_overpress.sh > /dev/null 2>&1 < /dev/null &
set -uo pipefail
A=/workspace/ab; CB=$A/cb; P=$CB/scratchpad/gauntlet/L74/ability_live/overpress; O=$A/overpress; RL=icebow/data/bench/rl_royale
CX=$RL/rlarm_gae_cue_u250/rlarm_gae_cue_u250_u0130_grafted.pt; AB=$RL/rlarm_gae_cue_ab/rlarm_gae_cue_ab_u0065_grafted.pt
EXTRA='--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --record-plays'
mkdir -p $O; exec >> $O/run.log 2>&1
log() { echo "$(date -u +%FT%TZ) $*"; }
trap 'log exit; touch $O/DONE' EXIT
cd $CB
export PYTHONPATH=$CB OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
sed -e "s|^HERE = Path(__file__).resolve().parent\$|HERE = Path(__file__).resolve().parents[2]/'gap'|" \
    -e "s|choices=('live', 'never'), default='live'|choices=('live', 'never', 'off'), default='live'|" \
    scratchpad/gauntlet/L74/gap/gap.py > $P/gap_off.py
grep -q "'never', 'off'" $P/gap_off.py && grep -q "parents\[2\]/'gap'" $P/gap_off.py || { log "gap_off patch failed"; exit 2; }
chmod +x $P/pyout.sh
for SPEC in cx_off:$CX:off cx_never:$CX:never cx_live:$CX:live ab_head:$AB:live; do
  IFS=: read n ck pr <<< "$SPEC"
  for S in 741200 742000; do
    [ -e $O/${n}_$S/D3/matches.jsonl ] && continue
    rm -rf $O/${n}_$S; log "$n $S press=$pr"
    bash scratchpad/gauntlet/L74/cue_ab/hide_run.sh flock /workspace/cpu.lock $A/venvf36/bin/python $P/gap_off.py --ckpt $ck \
      --out $O/${n}_$S --arms D3 --seed-start $S --runtime fork36-linux --python $P/pyout.sh --iw-press $pr \
      --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json --workers 26 --extra="$EXTRA" > $O/${n}_$S.log 2>&1 \
      || log "GAP EXIT $? $n $S"
  done
done
touch $O/ALL_DONE; log ALL_DONE
