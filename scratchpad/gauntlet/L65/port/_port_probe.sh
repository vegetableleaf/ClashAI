#!/bin/bash
# Test the two lines of the Linux port that can silently fail -- using NO game binaries.
#
# 1. THE LAUNCH NESTING. start_direct_service.sh builds
#      nohup sh -c "cd '<root>' && exec env CLASSPATH='...' LD_LIBRARY_PATH='...' <prog> ..." >log 2>&1 </dev/null &
#    and hands that whole string to `adb shell` as ONE argument, so the guest's shell re-parses it. The
#    failure mode is a service that starts and instantly exits with nothing but an in-guest log. Here the
#    same nesting is run with `env` and `sleep` standing in for app_process: if CLASSPATH and
#    LD_LIBRARY_PATH arrive intact in the guest's environment, and the backgrounded process survives the
#    adb session closing, and `ps -A -o PID,ARGS` can still find it by root+subcommand, then the real
#    launch differs only in which binary is exec'd.
#
# 2. MY OWN CLAIM ABOUT tar. The port replaces the .ps1's `tar.exe -xf <asset-pack>.apk` with `unzip`,
#    on the claim that Windows tar is bsdtar (reads zip) while GNU tar is not. That claim is load-bearing
#    -- if it is wrong the substitution is pointless churn; if it is right and I had transliterated, the
#    script would die there. Tested against a real zip, not asserted.
set -u
ROOT=/data/local/tmp/cr-port-probe
S=emulator-5554
A=$HOME/android-sdk/platform-tools/adb
echo "=== port probe $(date -u +%H:%M:%S)"

echo "--- 1. launch nesting"
$A -s $S shell "rm -rf '$ROOT'; mkdir -p '$ROOT'" >/dev/null
INNER="cd '$ROOT' && exec env CLASSPATH='$ROOT/lifecycle-probe.jar:$ROOT/base.apk' LD_LIBRARY_PATH='$ROOT' env"
LAUNCH="nohup sh -c \"$INNER\" >'$ROOT/env.log' 2>&1 </dev/null &"
$A -s $S shell "$LAUNCH" >/dev/null
sleep 1
echo "CLASSPATH seen by guest : $($A -s $S shell "grep '^CLASSPATH=' '$ROOT/env.log'" | tr -d '\r')"
echo "LD_LIBRARY_PATH in guest: $($A -s $S shell "grep '^LD_LIBRARY_PATH=' '$ROOT/env.log'" | tr -d '\r')"

echo "--- 1b. background survival + ps matching (stand-in for JniHost serve-direct)"
INNER2="cd '$ROOT' && exec env CLASSPATH='$ROOT/x.jar' LD_LIBRARY_PATH='$ROOT' sleep 45 royale.nativehost.JniHost '$ROOT' serve-direct 37031"
LAUNCH2="nohup sh -c \"$INNER2\" >'$ROOT/service.log' 2>&1 </dev/null &"
$A -s $S shell "$LAUNCH2" >/dev/null
sleep 2
PIDS=$($A -s $S shell "ps -A -o PID,ARGS" | tr -d '\r' \
  | awk -v r="$ROOT" '$0 ~ /royale\.nativehost\.JniHost/ && index($0, r) && /serve-direct/ {print $1}')
echo "service_pids() found     : [${PIDS:-none}]"
echo "survived session close   : $([ -n "$PIDS" ] && echo yes || echo NO)"
for p in $PIDS; do $A -s $S shell "kill '$p' 2>/dev/null || true" >/dev/null; done

echo "--- 1c. adb forward round trip"
$A -s $S forward --remove tcp:37031 >/dev/null 2>&1
$A -s $S forward tcp:37031 tcp:37031 >/dev/null && echo "forward established     : yes"
$A -s $S forward --list | tr -d '\r' | head -2
$A -s $S forward --remove tcp:37031 >/dev/null 2>&1

echo "--- 1d. push_verified sha round trip"
head -c 100000 /dev/urandom > /tmp/probe.bin
H=$(sha256sum /tmp/probe.bin | awk '{print $1}')
$A -s $S push /tmp/probe.bin "$ROOT/probe.bin.upload" >/dev/null 2>&1
G=$($A -s $S shell "sha256sum '$ROOT/probe.bin.upload' 2>/dev/null || true" | tr -d '\r' | awk '{print $1}')
echo "host sha == guest sha    : $([ "$H" = "$G" ] && echo yes || echo "NO ($H vs $G)")"

echo "--- 2. can GNU tar read a zip?"
mkdir -p /tmp/zt/assets/locations && echo "a,b,c" > /tmp/zt/assets/locations/training_arena.csv
(cd /tmp/zt && zip -qr /tmp/fake_asset_pack.apk assets) 2>/dev/null || \
  (cd /tmp/zt && python3 -c "import shutil;shutil.make_archive('/tmp/fake_asset_pack','zip','.')" && mv /tmp/fake_asset_pack.zip /tmp/fake_asset_pack.apk)
echo -n "GNU tar -tf on an apk    : "; tar -tf /tmp/fake_asset_pack.apk >/dev/null 2>&1 && echo "READS IT (my claim is WRONG)" || echo "fails (claim holds)"
echo -n "tar version              : "; tar --version | head -1
echo -n "unzip on the same apk    : "; unzip -o -j /tmp/fake_asset_pack.apk "assets/locations/training_arena.csv" -d /tmp/zt_out >/dev/null 2>&1 && echo "works" || echo "FAILS"

$A -s $S shell "rm -rf '$ROOT'" >/dev/null 2>&1
echo "=== done"
