#!/bin/bash
# pod 33920 /workspace/pilot/j7: J7 A2b-2b on the 811 RNG-free plans (plans_x): crforge gate/force x lo/hi, then fin15/fin16
cd /workspace/pilot/j7
rm -rf plans_x runs_x && tar xf plans_x.tar --no-same-owner && mkdir -p runs_x
: > jobs_x.txt
for m in gate force; do for t in lo hi; do
  mkdir -p runs_x/crforge_${m}_$t
  for p in $(cat plans_x/index.txt); do echo "plans_x/$p.json $m $t runs_x/crforge_${m}_$t/$p.json" >> jobs_x.txt; done
done; done
L=/workspace/crforge/env/build/install/env/lib
( time java -Xmx8g -cp "$L/*:build" org.crforge.core.battle.match.J7Run /workspace/crforge_cache/tables/16.402.22 jobs_x.txt 12 ) > runs_x/crforge.log 2>&1
PL=plans_x R=runs_x ./run_fin.sh
echo $(date -u +%T) done >> runs_x/crforge.log
