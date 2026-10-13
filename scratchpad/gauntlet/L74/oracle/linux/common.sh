#!/usr/bin/env bash
# Infrastructure only. No game binaries or address constants belong here.
# Shared configuration variables are consumed by the entry scripts.
# shellcheck disable=SC2034
set -Eeuo pipefail
umask 077
ORACLE_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
ORACLE_STATE="$ORACLE_DIR/.local"
export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}"
export ANDROID_HOME="$ANDROID_SDK_ROOT"
export ANDROID_AVD_HOME="$ORACLE_STATE/avd"
# Whichever JDK is installed (17 on Ubuntu 22.04, 21 on Debian 13); 17 before setup_vm.sh has installed one.
_java=$(readlink -f "$(command -v java 2>/dev/null)" 2>/dev/null || true)
export JAVA_HOME="${JAVA_HOME:-${_java:+${_java%/bin/java}}}"
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}"
export PATH="$JAVA_HOME/bin:$ANDROID_SDK_ROOT/platform-tools:$PATH"
SDKMANAGER="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin/sdkmanager"
AVDMANAGER="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin/avdmanager"
EMULATOR="$ANDROID_SDK_ROOT/emulator/emulator"
ADB="$ANDROID_SDK_ROOT/platform-tools/adb"
SYSTEM_IMAGE='system-images;android-32;default;x86_64'  # 160402012 needs minSdk 32 (API 31 install fails INSTALL_FAILED_OLDER_SDK)
ORACLE_NS="cr-oracle-$UID"
ORACLE_USER=$(id -un)
mkdir -p "$ORACLE_STATE/logs"
log_start() {
    local label=$1
    exec > >(tee -a "$ORACLE_STATE/logs/$label.log") 2>&1
    printf '\n%s %s\n' "$(date -u +%FT%TZ)" "$label"
}
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
blocked() {
    local result=0
    python3 "$ORACLE_DIR/binding_status.py" || result=$?
    if [[ $result != 78 ]]; then
        printf '%s\n' 'BLOCKED_BINDING_INCOMPLETE: assessment failed or target launcher is absent.'
    fi
    exit 78
}
linux_host() {
    [[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || fail 'Ubuntu x86_64 required'
    [[ $UID -ne 0 ]] || fail 'Run as the VM login user; scripts use sudo for system operations'
}
instances() {
    N=${1:-1}
    [[ $N =~ ^[12]$ ]] || fail 'This 8-vCPU VM supports N=1 or N=2 at the upstream 4 cores per AVD'
}
lock_state() {
    exec 9>"$ORACLE_STATE/control.lock"
    flock -n 9 || fail 'Another ORACLE setup/boot operation holds the lock'
}
ns_run() {
    sudo ip netns exec "$ORACLE_NS" sudo -u "$ORACLE_USER" -- env \
        HOME="$HOME" USER="$ORACLE_USER" LOGNAME="$ORACLE_USER" \
        ANDROID_SDK_ROOT="$ANDROID_SDK_ROOT" ANDROID_HOME="$ANDROID_HOME" \
        ANDROID_AVD_HOME="$ANDROID_AVD_HOME" JAVA_HOME="$JAVA_HOME" \
        PATH="$PATH" "$@"
}
assert_isolated() {
    sudo ip -n "$ORACLE_NS" -j link show | python3 -c \
        'import json,sys; x=json.load(sys.stdin); assert len(x)==1 and x[0]["ifname"]=="lo", "non-loopback interface in ORACLE namespace"'
    local family
    for family in -4 -6; do
        sudo ip -n "$ORACLE_NS" "$family" -j route show table all | python3 -c \
            'import json,sys; assert all(r.get("dev")=="lo" for r in json.load(sys.stdin)), "non-loopback route"'
    done
}
