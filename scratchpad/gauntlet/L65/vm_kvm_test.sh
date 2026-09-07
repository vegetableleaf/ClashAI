#!/bin/bash
# Does a headless Android x86_64 AVD boot under NESTED KVM on the GCP VM, and how fast?
#
# This is the one question that can kill the S3 cloud plan, and it is answerable with ZERO game
# binaries: the sandbox's engine slot is `app_process ... JniHost` running inside a stock AOSP AVD
# (scratchpad/gauntlet/L65/sandbox_portability.md section 1), so if the AVD will not boot, or boots
# so slowly that a worker slot costs more than it earns, nothing downstream matters -- and we learn
# that before moving 1.15 GB of non-redistributable runtime or asking the owner to rule on it.
#
# The specific risk: on Linux the emulator's `-accel on` means KVM, and this host is ITSELF a VM.
# That is KVM nested inside a guest. It works in general, is slower than bare metal, and is a known
# flakiness site (portability survey section 3, "the real unknown" -- untested, no measurement
# either way, which is why this script exists).
#
# Emulator flags are copied verbatim from native_core/worker.py:147-155 so that what boots here is
# what the sandbox would launch, not an easier configuration.
#
# Writes every step to ~/kvm_test.log and a machine-readable summary to ~/kvm_test.json.
set -u
LOG=$HOME/kvm_test.log
exec >>"$LOG" 2>&1
echo "=== $(date -u +%H:%M:%S) start"

SDK=$HOME/android-sdk
export ANDROID_SDK_ROOT=$SDK ANDROID_HOME=$SDK
export PATH=$SDK/cmdline-tools/latest/bin:$SDK/platform-tools:$SDK/emulator:$PATH

step() { echo "--- $(date -u +%H:%M:%S) $*"; }

step "kvm visibility"
ls -l /dev/kvm; id | tr ' ' '\n' | grep -o 'kvm' | head -1

if [ ! -d "$SDK/cmdline-tools/latest" ]; then
  step "apt deps (jdk17, unzip, cpu-checker)"
  sudo DEBIAN_FRONTEND=noninteractive apt-get -qq update
  sudo DEBIAN_FRONTEND=noninteractive apt-get -qq install -y openjdk-17-jdk-headless unzip wget cpu-checker libpulse0 libnss3 libxcursor1 libxdamage1 libxrandr2 libxcomposite1 libasound2 </dev/null
  step "kvm-ok"; sudo kvm-ok
  step "sdk cmdline-tools"
  mkdir -p "$SDK/cmdline-tools"
  wget -q https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -O /tmp/clt.zip
  unzip -q /tmp/clt.zip -d "$SDK/cmdline-tools"
  mv "$SDK/cmdline-tools/cmdline-tools" "$SDK/cmdline-tools/latest"
fi

step "sdk packages (platform-tools, emulator, aosp android-31 x86_64)"
yes | sdkmanager --licenses >/dev/null 2>&1
T0=$(date +%s)
sdkmanager "platform-tools" "emulator" "system-images;android-31;default;x86_64" 2>&1 | tail -3
DL=$(( $(date +%s) - T0 ))
echo "sdk_download_s=$DL"

step "create avd"
avdmanager delete avd -n royale_worker_api31 >/dev/null 2>&1
echo no | avdmanager create avd -n royale_worker_api31 -k "system-images;android-31;default;x86_64" -d pixel_5 2>&1 | tail -2

step "boot headless (worker.py:147-155 flags)"
T0=$(date +%s)
nohup emulator -avd royale_worker_api31 -port 5554 -no-window -no-audio -no-boot-anim -no-snapshot \
  -gpu swiftshader_indirect -accel on -memory 4096 -cores 4 > "$HOME/emulator.log" 2>&1 &
EPID=$!
adb start-server >/dev/null 2>&1
OK=0
for i in $(seq 1 120); do
  S=$(adb -s emulator-5554 shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')
  if [ "$S" = "1" ]; then OK=1; break; fi
  sleep 5
done
BOOT=$(( $(date +%s) - T0 ))
step "boot_completed=$OK after ${BOOT}s"

if [ "$OK" = "1" ]; then
  step "guest facts"
  adb -s emulator-5554 shell getprop ro.product.cpu.abi
  adb -s emulator-5554 root >/dev/null 2>&1; sleep 3
  adb -s emulator-5554 shell id | head -1
  step "guest cpu throughput (same loop as the host bench, 1 core)"
  adb -s emulator-5554 shell 'T=$(date +%s%N); i=0; while [ $i -lt 200000 ]; do i=$((i+1)); done; echo $(( ($(date +%s%N)-T)/1000000 ))ms'
fi
step "accel used (emulator.log)"
grep -iE "kvm|hax|accel|fail" "$HOME/emulator.log" | head -8

cat > "$HOME/kvm_test.json" <<JSON
{"boot_completed": $OK, "boot_seconds": $BOOT, "sdk_download_seconds": $DL,
 "emulator_pid": $EPID, "host": "$(hostname)", "when": "$(date -u +%FT%TZ)"}
JSON
step "done"
echo "KVM_TEST_EXIT $OK"
