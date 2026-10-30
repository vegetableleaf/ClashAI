#!/usr/bin/env bash
# rebuild_gate.sh -- SME-REBUILD (10-30): build the SME gate (= f1fix/sme11f) from the TRACKED tree on a pod.
# Before: the laptop ships the tree with LF endings to $S (git -c core.autocrlf=false archive HEAD:<sme dir>) and the
# frozen inputs + frames to $R/data/freshN/. Needs JDK 17, the 5e8089a4 tickprobe lib, tables 16.635.3.
set -e
R=${R:-/workspace/smeR}; S=$R/sme
LIB=${SME_LIB:-/workspace/crforge_main/5e8089a4/tickprobe/lib}
T=/workspace/crforge_cache/tables/16.635.3
[ -d $T ] || cp -a ${TSRC:-/workspace/oplm/tables/16.635.3} $T
echo "tables $(cd $T && find . -type f | LC_ALL=C sort | xargs cat | sha256sum | cut -c1-16) $(find $T -type f | wc -l) files"
(cd $LIB/.. && sha256sum -c SHA256SUMS | tail -3)
cd $S
rm -rf build build_snap && mkdir build build_snap
javac -d build -cp "$LIB/*" SmeRun.java
javac -d build_snap -cp "$LIB/*" bp/SnapRun2.java
SME_LIB=$LIB SME_TABLES=$T python3 sme.py selftest 2>&1 | tail -2 || true
echo built $(ls build build_snap | wc -l)
