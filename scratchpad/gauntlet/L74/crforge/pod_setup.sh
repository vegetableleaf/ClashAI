#!/usr/bin/env bash
# crforge pin on a pod (plan1026 Pillar 1 Stage 0), as run on pod 33920 on 2026-10-27.
# Tables: copied from the laptop cache (C:\Users\benpe\crforge_eval\cache\tables, built there from the CDN on 10-25);
# do not fetch from the CDN on every pod:
#   tar czf - -C /c/Users/benpe/crforge_eval/cache tables fingerprints | ssh ... 'mkdir -p /workspace/crforge_cache && tar xzf - -C /workspace/crforge_cache --no-same-owner'
set -euo pipefail
COMMIT=ad8ef3a532ada8dea732bf1ecdeb01beef0fb4b0
cd /workspace
[ -d crforge ] || git clone -q https://github.com/voonhous/crforge.git crforge
cd crforge && git checkout -q "$COMMIT" && git log -1 --format=%H
command -v javac >/dev/null || { apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openjdk-17-jdk-headless; }
java -version 2>&1 | head -1                                  # 10-27: openjdk 17.0.20.1
./gradlew --no-daemon --max-workers=8 :env:installDist        # 10-27: BUILD SUCCESSFUL in 46s
# Smoke + tools (sources in this repo: crforge/Census.java, seeds/SeedSearch.java; Probe.java from crforge_eval/scripts):
#   L=/workspace/crforge/env/build/install/env/lib T=/workspace/crforge_cache/tables/16.402.22
#   cd /workspace/seeds && javac -d build -cp "$L/*" Census.java SeedSearch.java Probe.java
#   java -cp "$L/*:build" Probe $T towers        # princess 4858 at L16
#   java -cp "$L/*:build" Probe $T determinism   # IDENTICAL, obs sha256 a0bd88c41f98b46d (= laptop det.txt)
