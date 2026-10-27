#!/usr/bin/env bash
# usage: ct.sh VERSION OUTDIR  -- core tests of the clashbot-635 fork on one data version; prints totals
V=$1; O=$(realpath -m $2); mkdir -p $O
cd /workspace/f635/crforge_fork
./gradlew --no-daemon --max-workers=8 -Pcrforge.cache=/workspace/f635/crforge_cache -Pcrforge.assetSource=file:///workspace/f635/crforge_cache/none -Pcrforge.dataVersion=$V :core:test > $O/coretest.log 2>&1
rm -rf $O/xml; cp -r core/build/test-results/test $O/xml
python3 /workspace/f635/failcat.py $O/xml 6 > $O/failcat.txt; head -1 $O/failcat.txt
