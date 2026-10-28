#!/usr/bin/env bash
# tt.sh VERSION LOG -- CF-MAIN: all crforge core tests of a worktree (env WT, default the clashbot-main one, /workspace/cfmain/crforge_fork) on one
# data version (the branch's guard plays both ranges; no bypass); xml in LOG.xml/, totals + failures in LOG.failcat.txt
V=$1; LOG=$(realpath -m $2); cd ${WT:-/workspace/cfmain/crforge_fork}
./gradlew --no-daemon --max-workers=16 -Pcrforge.cache=/workspace/f635/crforge_cache -Pcrforge.assetSource=file:///workspace/f635/crforge_cache/none -Pcrforge.dataVersion=$V :core:test > $LOG 2>&1; rc=$?
rm -rf $LOG.xml; cp -r core/build/test-results/test $LOG.xml
python3 /workspace/f635/failcat.py $LOG.xml 6 > $LOG.failcat.txt 2>&1; echo "$V $(head -1 $LOG.failcat.txt) rc=$rc"
