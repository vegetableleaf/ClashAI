#!/usr/bin/env bash
# usage: buildlib.sh NAME [guard]  -- installDist of the fork working tree into /workspace/f635/lib_NAME (guard: bypass applied for the build only)
cd /workspace/f635/crforge_fork
[ "$2" = guard ] && { git apply /workspace/f635/guard_only.diff || exit 1; }
./gradlew --no-daemon -q --max-workers=8 -Pcrforge.cache=/workspace/f635/crforge_cache -Pcrforge.assetSource=file:///workspace/f635/crforge_cache/none :env:installDist > /workspace/f635/build_$1.log 2>&1; rc=$?
[ "$2" = guard ] && git apply -R /workspace/f635/guard_only.diff
[ $rc = 0 ] || { tail -20 /workspace/f635/build_$1.log; exit 1; }
rm -rf /workspace/f635/lib_$1 && cp -r env/build/install/env/lib /workspace/f635/lib_$1 && echo built lib_$1
