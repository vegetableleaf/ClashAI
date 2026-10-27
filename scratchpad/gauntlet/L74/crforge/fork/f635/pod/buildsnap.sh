#!/usr/bin/env bash
# usage: buildsnap.sh NAME -- F635c: SCRATCH build of the fork working tree plus clashbot-bp TickProbe 0001+0002 (instrumentation,
# for SnapRun2), installed into /workspace/f635/lib_NAME; the patches are reverted after the build, never committed
P=/workspace/f635c; cd /workspace/f635/crforge_fork
git apply $P/clashbot-bp_0001_TickProbe.patch && git apply $P/clashbot-bp_0002_TickProbeDrain.patch || exit 1
./gradlew --no-daemon -q --max-workers=8 -Pcrforge.cache=/workspace/f635/crforge_cache -Pcrforge.assetSource=file:///workspace/f635/crforge_cache/none :env:installDist > /workspace/f635/build_$1.log 2>&1; rc=$?
git apply -R $P/clashbot-bp_0002_TickProbeDrain.patch && git apply -R $P/clashbot-bp_0001_TickProbe.patch
[ $rc = 0 ] || { tail -20 /workspace/f635/build_$1.log; exit 1; }
rm -rf /workspace/f635/lib_$1 && cp -r env/build/install/env/lib /workspace/f635/lib_$1 && echo built lib_$1
