#!/bin/bash
# A1 (10-27) copy of w19/base_run.sh for /workspace/f16 (code tree $B/cb). W19: J1 (fights.py run) on every chunk dir of the cohorts, all chunks at once (W workers each), each chunk into its own dir
# (a chunk run scores its out dir at its end: separate dirs keep those reads off the files other chunks are writing), then the
# matches are linked into $OUT/<cohort>/all and $OUT/union and scored (--stamped: strict / core / all).
#   SIM=/workspace/w19/rsfork_fin15 OUT=/workspace/w19/res/BASE COHORTS="c13 c22" W=6 K=8 [PARITY_OVERRIDES=...] \
#     setsid nohup bash base_run.sh > /dev/null 2>&1 < /dev/null &
# -> $OUT/run.log, $OUT/DONE; per-cohort and union CEILING_strict.txt
set -uo pipefail
B=/workspace/f16; C=${CODE:-$B/cb}; P=$C/scratchpad/gauntlet/L74/parity
SIM=${SIM:?}; OUT=${OUT:?}; W=${W:-6}; K=${K:-8}
export PYTHONPATH=$C PARITY_SIM_PATH=$SIM OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
mkdir -p $OUT; exec >> $OUT/run.log 2>&1
echo "$(date -u +%T) start SIM=$SIM CODE=$C K=$K W=$W overrides=${PARITY_OVERRIDES:-none} cohorts=${COHORTS:-c13 c22}"
for c in ${COHORTS:-c13 c22}; do
  for d in $B/ch/${c}_*; do
    o=$OUT/$c/$(basename $d); mkdir -p $o
    [ -e $o/DONE ] && continue
    ( PARITY_ATTACKS=$d/attacks.json PARITY_BUFFS=$d/buffs.json nice -n 5 /workspace/venvf15/bin/python $P/fights.py run --out $o --live $d/live \
        --files 'live_play_*.jsonl' --workers $W --window 240 --ceiling $K > $o/run.log 2>&1 && touch $o/DONE || touch $o/FAILED ) &
  done
done
wait
echo "$(date -u +%T) runs end: $(ls $OUT/*/*/DONE 2>/dev/null | wc -l) done, $(ls $OUT/*/*/FAILED 2>/dev/null | wc -l) failed"
mkdir -p $OUT/union/matches
for c in ${COHORTS:-c13 c22}; do
  mkdir -p $OUT/$c/all/matches
  for f in $OUT/$c/${c}_*/matches/*.json; do ln -sf $f $OUT/$c/all/matches/; ln -sf $f $OUT/union/matches/; done
  /workspace/venvf15/bin/python $P/fights.py score --out $OUT/$c/all --stamped > $OUT/$c/all/score.log 2>&1
done
/workspace/venvf15/bin/python $P/fights.py score --out $OUT/union --stamped > $OUT/union/score.log 2>&1
echo "$(date -u +%T) scored"; touch $OUT/DONE
