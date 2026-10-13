#!/usr/bin/env bash
# Every emulator client and compiler runs in the same offline namespace.
set -Eeuo pipefail
Q=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../common.sh
source "$Q/../common.sh"
linux_host
assert_isolated
case "${1:-}" in
    build)
        [[ $# == 1 ]] || exit 64
        ns_run bash "$Q/build.sh"
        ;;
    preflight|install|install-probe|collect)
        ns_run python3 "$Q/qualify.py" "$@"
        ;;
    *) printf '%s\n' 'usage: worker.sh build | preflight/install/install-probe/collect [qualify.py options]'; exit 64 ;;
esac
assert_isolated
