L=$1; OUT=$2; T=/workspace/crforge_cache/tables/16.402.22; J7=/workspace/pilot/j7
mkdir -p $OUT/j7build $OUT/j7runs && /workspace/s4_jdk21/jdk-21.0.13+9/bin/javac -d $OUT/j7build -cp "$L/*" $J7/src/J7Run.java
: > $OUT/j7jobs.txt
for t in lo hi; do mkdir -p $OUT/j7runs/crforge_force_$t
  for p in $(cat $J7/plans_x/index.txt); do echo "$J7/plans_x/$p.json force $t $OUT/j7runs/crforge_force_$t/$p.json" >> $OUT/j7jobs.txt; done
done
( cd $J7 && /workspace/s4_jdk21/jdk-21.0.13+9/bin/java -Xmx8g -cp "$L/*:$OUT/j7build" org.crforge.core.battle.match.J7Run $T $OUT/j7jobs.txt 12 ) > $OUT/j7run.log 2>&1
for a in fin15_force_lo fin15_force_hi; do ln -sfn $J7/runs_x/$a $OUT/j7runs/$a; done
( cd $J7 && PYTHONPATH=$J7/cb python3 cb/scratchpad/gauntlet/L74/crforge/pilot/j7/j7.py score --truth truth_j7x.jsonl \
    --runs $OUT/j7runs --inputs inputs_j7x.jsonl --out $OUT/j7score ) > $OUT/j7score.log 2>&1
grep -A3 'subset deck8' $OUT/j7score/SCORE.md | grep -m1 '^| crforge_force' | tee $OUT/j7_line.txt
for t in lo hi; do echo "$t pin $(cat $J7/runs_x/crforge_force_$t/*.json | sha256sum | cut -c1-16) new $(cat $OUT/j7runs/crforge_force_$t/*.json | sha256sum | cut -c1-16)"; done | tee $OUT/j7_identity.txt
