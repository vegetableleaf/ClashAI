#!/usr/bin/env bash
# CF-CLONE-3: core tests both versions, the libs (plain + snap), then the Clone sweep in four modes x two versions
cd /workspace/cfclone
bash tt.sh 16.402.22 /workspace/cfclone/ct3_402.log > chain3.out 2>&1
bash tt.sh 16.635.3 /workspace/cfclone/ct3_635.log >> chain3.out 2>&1
bash buildlib.sh fix3 >> chain3.out 2>&1 && bash buildlib.sh fix3snap snap >> chain3.out 2>&1
rm -rf probe_fix3 && mkdir probe_fix3 && javac -d probe_fix3 -cp "lib_fix3/*" CloneProbe.java >> chain3.out 2>&1
echo built >> chain3.out
for mode in scene match cm mc; do
  for v in 16.402.22 16.635.3; do
    s=$(echo $v | cut -d. -f2)
    SECONDS=0
    CLONEPROBE_MODE=$mode java -Xmx24g -cp "lib_fix3/*:probe_fix3" CloneProbe /workspace/f635/crforge_cache/tables/$v \
      /workspace/f635/census_decks.tsv cp3_${mode}_$s.tsv 24 > cp3_${mode}_$s.log 2>&1
    echo "sweep $mode $v ${SECONDS}s" >> chain3.out
  done
done
echo done >> chain3.out
