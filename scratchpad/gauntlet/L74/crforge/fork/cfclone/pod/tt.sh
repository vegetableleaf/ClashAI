#!/usr/bin/env bash
# usage: tt.sh VERSION LOG [TESTFILTER...] -- CF-CLONE: core tests (all, or the named classes) of the cfclone worktree
# on one data version (the F635c guard plays both ranges; no bypass); writes xml to LOG.xml/, prints the tail
V=$1; LOG=$(realpath -m $2); shift 2; cd /workspace/cfclone/crforge_fork
A=(); for t in "$@"; do A+=(--tests "$t"); done
./gradlew --no-daemon --max-workers=16 -Pcrforge.cache=/workspace/f635/crforge_cache -Pcrforge.assetSource=file:///workspace/f635/crforge_cache/none -Pcrforge.dataVersion=$V :core:test "${A[@]}" > $LOG 2>&1; rc=$?
rm -rf $LOG.xml; cp -r core/build/test-results/test $LOG.xml
python3 /workspace/f635/failcat.py $LOG.xml 6 > $LOG.failcat.txt 2>&1; head -3 $LOG.failcat.txt
grep -E "FAILED|BUILD|error:" $LOG | head -20; echo rc=$rc
