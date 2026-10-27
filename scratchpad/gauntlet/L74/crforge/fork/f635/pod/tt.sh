#!/usr/bin/env bash
# usage: tt.sh VERSION LOG TESTFILTER...  -- F635b: only the named core test classes on one data version (16.635.3: guard
# bypass applied for the run only); prints the tail of the log
V=$1; LOG=$2; shift 2; cd /workspace/f635/crforge_fork
[ $V = 16.635.3 ] && { git apply /workspace/f635/guard_only.diff || exit 1; }
A=(); for t in "$@"; do A+=(--tests "$t"); done
./gradlew --no-daemon --max-workers=8 -Pcrforge.cache=/workspace/f635/crforge_cache -Pcrforge.assetSource=file:///workspace/f635/crforge_cache/none -Pcrforge.dataVersion=$V :core:test "${A[@]}" > $LOG 2>&1; rc=$?
[ $V = 16.635.3 ] && git apply -R /workspace/f635/guard_only.diff
grep -E "FAILED|tests completed|BUILD|error:|Exception at" $LOG | head -20; echo rc=$rc
