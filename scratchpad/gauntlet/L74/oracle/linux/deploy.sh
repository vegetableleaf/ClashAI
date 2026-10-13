#!/usr/bin/env bash
# ORACLE v3 permits scheduling data writes; required target bindings remain gated.
# A non-deployable private binding must not enable native installation or execution.
# Do not turn this into an allow-unsafe/skip-guard switch.
# shellcheck source=common.sh
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
log_start deploy
blocked
