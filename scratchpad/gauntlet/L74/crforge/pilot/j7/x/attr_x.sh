#!/bin/bash
# pod 33920: concern-4 ablation on the 811 plans: crforge force lo minus exactly the commands fixed fin16 (lo) refused
cd /workspace/pilot/j7
A=attr/attrib.py
rm -rf attrx && mkdir -p attrx/runs
for o in all place ability; do
  a=""; [ $o != all ] && a="--only $o"
  python3 $A ablate --plans plans_x --fin runs_x/fin16_force_lo --out attrx/plans_$o $a
done
: > attrx/jobs.txt
for o in all place ability; do
  mkdir -p attrx/runs/crforge_drop16${o}_lo
  for p in $(cat plans_x/index.txt); do echo "attrx/plans_$o/$p.json force lo attrx/runs/crforge_drop16${o}_lo/$p.json" >> attrx/jobs.txt; done
done
L=/workspace/crforge/env/build/install/env/lib
java -Xmx8g -cp "$L/*:build" org.crforge.core.battle.match.J7Run /workspace/crforge_cache/tables/16.402.22 attrx/jobs.txt 12 > attrx/crforge.log 2>&1
cp -r runs_x/crforge_force_lo runs_x/fin16_force_lo runs_x/fin15_force_lo attrx/runs/
touch attrx/DONE
