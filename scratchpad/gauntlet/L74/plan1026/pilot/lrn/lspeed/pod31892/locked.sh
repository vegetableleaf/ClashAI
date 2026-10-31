#!/bin/bash
# locked.sh TAG CMD...: wait for /workspace/BENCH_LOCK to clear, take it, run CMD, release (LEARNER-SPEED)
TAG=$1; shift
until ( set -o noclobber; echo "LEARNER-SPEED $(date -u +%FT%TZ) $TAG" > /workspace/BENCH_LOCK ) 2>/dev/null; do sleep 15; done
trap "rm -f /workspace/BENCH_LOCK" EXIT
"$@"
