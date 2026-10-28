#!/usr/bin/env bash
# usage: buildlib.sh NAME [snap] -- CF-CLONE: installDist of the cfclone worktree into /workspace/cfclone/lib_NAME
# (snap: clashbot-bp TickProbe 0001 + 0002 applied for the build only, as F635c buildsnap.sh / lib_f635c)
cd /workspace/cfclone/crforge_fork; P=/workspace/f635c
[ "$2" = snap ] && { git apply $P/clashbot-bp_0001_TickProbe.patch && git apply $P/clashbot-bp_0002_TickProbeDrain.patch || exit 1; }
./gradlew --no-daemon -q --max-workers=16 -Pcrforge.cache=/workspace/f635/crforge_cache -Pcrforge.assetSource=file:///workspace/f635/crforge_cache/none :env:installDist > /workspace/cfclone/build_$1.log 2>&1; rc=$?
[ "$2" = snap ] && { git apply -R $P/clashbot-bp_0002_TickProbeDrain.patch && git apply -R $P/clashbot-bp_0001_TickProbe.patch; }
[ $rc = 0 ] || { tail -20 /workspace/cfclone/build_$1.log; exit 1; }
rm -rf /workspace/cfclone/lib_$1 && cp -r env/build/install/env/lib /workspace/cfclone/lib_$1 && echo built lib_$1 $(sha256sum /workspace/cfclone/lib_$1/core-1.0-SNAPSHOT.jar | cut -c1-16)
