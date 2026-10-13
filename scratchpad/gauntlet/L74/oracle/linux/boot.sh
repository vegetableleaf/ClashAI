#!/usr/bin/env bash
# Boot empty AOSP guests only, in a namespace with no external interfaces.
# shellcheck source=common.sh
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
log_start boot
linux_host
instances "${1:-1}"
lock_state
[[ -r /dev/kvm && -w /dev/kvm ]] || fail 'KVM inaccessible; log in again after setup'
[[ -x $EMULATOR && -x $ADB ]] || fail 'Run setup_vm.sh first'
if ! sudo ip netns list | awk '{print $1}' | grep -Fxq "$ORACLE_NS"; then
    sudo ip netns add "$ORACLE_NS"
fi
sudo ip -n "$ORACLE_NS" link set lo up
assert_isolated
# Root re-enters the namespace, then immediately drops to the invoking user.
# No veth, NAT, proxy, host ADB server, or host networking is shared.
ns_run "$EMULATOR" -accel-check
ns_run "$ADB" start-server
for ((i=0; i<N; i++)); do
    avd="oracle_160402012_api31_$i"
    port=$((5554 + 2*i))
    service_port=$((37031 + i))
    serial="emulator-$port"
    [[ -f $ANDROID_AVD_HOME/$avd.ini ]] || fail "AVD missing: $avd"
    if ns_run "$ADB" -s "$serial" get-state >/dev/null 2>&1; then
        actual=$(ns_run "$ADB" -s "$serial" emu avd name | head -n 1 | tr -d '\r')
        [[ $actual == "$avd" ]] || fail "Port $port belongs to another AVD: $actual"
        printf 'Reusing %s\n' "$avd"
    else
        # Check both console and ADB ports before launch; never kill conflicts.
        ns_run python3 - "$port" <<'PY'
import socket, sys
sockets = []
for port in (int(sys.argv[1]), int(sys.argv[1])+1):
    s = socket.socket(); s.bind(('127.0.0.1', port)); sockets.append(s)
PY
        # Pass paths as positional arguments, not interpolated shell code.
        ns_run bash -c 'log=$1; shift; nohup "$@" </dev/null >>"$log" 2>&1 & echo $!' \
            oracle-launch "$ORACLE_STATE/logs/$serial.log" \
            "$EMULATOR" -avd "$avd" -port "$port" \
            -no-window -no-audio -no-boot-anim -no-snapshot \
            -gpu swiftshader_indirect -accel on -memory 4096 -cores 4 \
            > "$ORACLE_STATE/$serial.launcher-pid"
    fi
    deadline=$((SECONDS + 300))
    until [[ $(ns_run timeout 5 "$ADB" -s "$serial" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r') == 1 ]]; do
        ((SECONDS < deadline)) || fail "Boot timed out: $serial; inspect its log"
        sleep 2
    done
    ns_run "$ADB" -s "$serial" root
    ns_run timeout 30 "$ADB" -s "$serial" wait-for-device
    [[ $(ns_run "$ADB" -s "$serial" shell id -u | tr -d '\r') == 0 ]] || fail 'AOSP root check failed'
    [[ $(ns_run "$ADB" -s "$serial" shell getprop ro.build.version.sdk | tr -d '\r') == 32 ]] || fail 'Wrong guest API'
    [[ $(ns_run "$ADB" -s "$serial" shell getprop ro.product.cpu.abi | tr -d '\r') == x86_64 ]] || fail 'Wrong guest ABI'
    printf 'PREPARED_ONLY slot=%s serial=%s service_port=%s namespace=%s\n' "$i" "$serial" "$service_port" "$ORACLE_NS"
done
assert_isolated
printf '%s\n' 'Empty Android guests ready. Native game deployment remains blocked.'
