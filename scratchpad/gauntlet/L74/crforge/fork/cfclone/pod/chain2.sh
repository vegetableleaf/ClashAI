#!/usr/bin/env bash
# CF-CLONE-2: core tests both versions, then the libs (plain + snap), then the Clone sweep on the plain lib
cd /workspace/cfclone
bash tt.sh 16.402.22 /workspace/cfclone/ct2_402.log > chain2.out 2>&1
bash tt.sh 16.635.3 /workspace/cfclone/ct2_635.log >> chain2.out 2>&1
bash buildlib.sh fix2 >> chain2.out 2>&1 && bash buildlib.sh fix2snap snap >> chain2.out 2>&1
rm -rf probe_fix2 && mkdir probe_fix2 && javac -d probe_fix2 -cp "lib_fix2/*" CloneProbe.java >> chain2.out 2>&1
bash probe.sh /workspace/cfclone/lib_fix2 probe_fix2 fix2 >> chain2.out 2>&1
echo done >> chain2.out
