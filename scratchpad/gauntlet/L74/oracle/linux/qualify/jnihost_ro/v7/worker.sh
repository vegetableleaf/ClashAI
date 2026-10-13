#!/usr/bin/env bash
set -Eeuo pipefail
Q=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$Q/../../../common.sh"
linux_host
assert_isolated
case "${1:-}" in
    build|run|review)
        action=$1
        shift
        ns_run python3 "$Q/${action}.py" "$@"
        ;;
    *) echo 'usage: worker.sh build | run --emulator-pid PID [--stage-limit STAGE] [--preload-dependencies] [options] | review RUN [--finding FILE]'; exit 64 ;;
esac
assert_isolated
