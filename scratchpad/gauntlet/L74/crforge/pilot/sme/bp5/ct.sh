#!/usr/bin/env bash
# ct.sh TAG [WT] -- A2c-BP5: core tests on 16.402.22 and 16.635.3 (head accepts both; no guard bypass)
WT=${2:-/workspace/pilot/bp5/crforge}; cd $WT
for V in 16.402.22 16.635.3; do O=/workspace/pilot/bp5/ct_$1_$V
./gradlew --no-daemon --max-workers=16 -Pcrforge.cache=/workspace/crforge_cache -Pcrforge.assetSource=file:///workspace/crforge_cache/none -Pcrforge.dataVersion=$V :core:test > $O.log 2>&1; echo "gradle rc=$?" >> $O.log
rm -rf $O.xml; cp -r core/build/test-results/test $O.xml
echo "$V $(python3 /workspace/pilot/bp2/junit_sum.py $O.xml)"; done
