#!/usr/bin/env bash
# Never misreport infrastructure readiness as native acceptance.
# ORACLE v3: native acceptance requires the complete qualified target bridge.
# shellcheck source=common.sh
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
log_start health
if [[ ${1:-} == --infrastructure ]]; then
    linux_host
    instances "${2:-1}"
    assert_isolated
    ns_run "$EMULATOR" -accel-check
    for ((i=0; i<N; i++)); do
        serial="emulator-$((5554 + 2*i))"
        [[ $(ns_run "$ADB" -s "$serial" shell getprop sys.boot_completed | tr -d '\r') == 1 ]] || fail 'Guest not booted'
        [[ $(ns_run "$ADB" -s "$serial" shell id -u | tr -d '\r') == 0 ]] || fail 'Guest not rootable'
    done
    printf '%s\n' 'INFRASTRUCTURE_ONLY: native acceptance has NOT run.'
fi
blocked
