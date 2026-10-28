#!/bin/bash
# run2.sh ENGINE RUN CPUS JAVA_OPTS [args] -- run.sh + JAVA_TOOL_OPTIONS ("-" = none)
J=$4; A=("$1" "$2" "$3"); shift 4
[ "$J" != "-" ] && export JAVA_TOOL_OPTIONS="$J"
exec /workspace/d2/run.sh "${A[@]}" "$@"
