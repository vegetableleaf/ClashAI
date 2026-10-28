#!/usr/bin/env bash
# gates30408.sh TAG -- CF-MAIN gates on pod 30408 for the HEAD of worktree WT (default clashbot-main, /workspace/cfmain/crforge_fork); results in /workspace/cfmain/g_TAG/:
# core tests 16.402.22 + 16.635.3; libs plain + TickProbe (build_main.sh) into /workspace/crforge_main/SHA8/{plain,tickprobe};
# determinism Probe on both versions (both libs); D1-C HF fault sample (faults.sh --limit 20000, plain lib) + summary, per
# replay vs FBASE (default CF-CLONE-2's f20k_cfclone2). The Clone sweep (clone_sweep.sh) and SME (sme_gate.sh) run on
# other pods: 30408's container has 62 GB, and the sweep's JVMs were OOM-killed next to the HF run and RX-X23.
set -uo pipefail
TAG=$1; H=/workspace/cfmain; G=$H/g_$TAG; mkdir -p $G; cd $H
export WT=${WT:-$H/crforge_fork}; FBASE=${FBASE:-/workspace/d1c/f20k_cfclone2}
SHA=$(git -C $WT rev-parse HEAD); L=/workspace/crforge_main/${SHA:0:8}; echo "head $SHA" > $G/head.txt
T=/workspace/f635/crforge_cache/tables
bash $H/tt.sh 16.402.22 $G/ct_402.log > $G/ct.txt; bash $H/tt.sh 16.635.3 $G/ct_635.log >> $G/ct.txt
bash $H/build_main.sh $SHA $L/plain > $G/build.txt 2>&1 && bash $H/build_main.sh $SHA $L/tickprobe tp >> $G/build.txt 2>&1 || { echo BUILD FAILED >> $G/build.txt; exit 1; }
for k in plain tickprobe; do rm -rf $G/probe_$k; mkdir -p $G/probe_$k; javac -d $G/probe_$k -cp "$L/$k/lib/*" /workspace/f635c/Probe.java
  for v in 16.402.22 16.635.3; do echo "== $k $v"; java -cp "$L/$k/lib/*:$G/probe_$k" Probe $T/$v determinism 2>&1 | tail -3; done; done > $G/det.txt
[ -n "${NO_HF:-}" ] && { echo done > $G/done; exit 0; }
rm -rf /workspace/d1c/f20k_main_$TAG
CRFORGE_LIB=$L/plain/lib bash /workspace/d1c/cb/scratchpad/gauntlet/L74/plan1026/d1c/faults.sh /workspace/d1c/f20k_main_$TAG --limit 20000 > $G/faults.log 2>&1
tail -n +$(grep -n "^{" $G/faults.log | tail -1 | cut -d: -f1) $G/faults.log > $G/faults_summary.json   # run ends with its summary
python3 $H/grades_cmp.py $FBASE/grades /workspace/d1c/f20k_main_$TAG/grades > $G/faults_vs_base.txt 2>&1
echo done > $G/done
