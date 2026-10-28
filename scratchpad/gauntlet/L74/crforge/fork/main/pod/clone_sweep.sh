#!/usr/bin/env bash
# clone_sweep.sh LIB OUT [MODES] -- CF-MAIN Clone sweep (CF-CLONE's CloneProbe, cfclone/CloneProbe.java next to this script)
# on LIB for 16.402.22 and 16.635.3 in each mode (default "scene match"; CloneProbe's header lists them), 4 at a time
# (12 threads, 20 GB each: pod 30408's 62 GB container OOM-killed 4 x 24 GB on 2026-10-28, so run it on 33920 / 32657).
# OUT/cp_MODE_VER.tsv, OUT/cp_sum.txt (sweep_sum.py), OUT/cp_clone_refusals.txt (Clone mechanics refused; gate: empty).
# Tables: TABLES (default /workspace/crforge_cache/tables); census decks: OUT/../census_decks.tsv or DECKS.
set -uo pipefail
LIB=$1; OUT=$2; MODES=${3:-scene match}; H=$(cd $(dirname $0) && pwd)
T=${TABLES:-/workspace/crforge_cache/tables}; DECKS=${DECKS:-$H/census_decks.tsv}
mkdir -p $OUT/cls && javac -d $OUT/cls -cp "$LIB/*" $H/CloneProbe.java || exit 1
for m in $MODES; do for v in 16.402.22 16.635.3; do
  ( CLONEPROBE_MODE=$m java -Xmx20g -cp "$LIB/*:$OUT/cls" CloneProbe $T/$v $DECKS $OUT/cp_${m}_$v.tsv 12 > $OUT/cp_${m}_$v.log 2>&1; echo "rc=$? $m $v" >> $OUT/rc.txt ) &
  while [ $(jobs -rp | wc -l) -ge 4 ]; do sleep 5; done
done; done; wait
for f in $OUT/cp_*.tsv; do python3 $H/sweep_sum.py $f; echo; done > $OUT/cp_sum.txt 2>&1
# a refusal line whose message names a clone (the non-form Clone_hero row's "in a hero slot" is not a Clone mechanic)
awk -F' [|] ' '/^[0-9]+ forms [|]/ && tolower($2) ~ /clon/ && $2 !~ /in a hero slot/' $OUT/cp_sum.txt > $OUT/cp_clone_refusals.txt
echo "done $(wc -l < $OUT/cp_clone_refusals.txt) clone refusal lines" >> $OUT/rc.txt
