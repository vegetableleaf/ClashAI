#!/usr/bin/env bash
# Runs every case in block_stdin_python_cases.txt (expected exit code <TAB> hook JSON) through the hook; prints failures.
cd "$(dirname "$0")"
fail=0; n=0
while IFS=$'\t' read -r want json; do
  [ -z "$want" ] && continue
  n=$((n+1))
  printf '%s' "$json" | bash block_stdin_python.sh >/dev/null 2>&1; got=$?
  [ "$got" = "$want" ] || { echo "FAIL want $want got $got: $json"; fail=$((fail+1)); }
done < block_stdin_python_cases.txt
echo "$((n-fail))/$n cases pass"
[ "$fail" = 0 ]
