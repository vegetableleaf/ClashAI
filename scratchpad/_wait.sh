#!/usr/bin/env bash
# poll a file for a pattern, up to N seconds (Bash sleep is blocked in the tool shell, not in a script)
f=$1; pat=$2; n=${3:-120}
for i in $(seq 1 $n); do grep -q "$pat" "$f" 2>/dev/null && { grep -n "$pat" "$f" | head -3; exit 0; }; sleep 1; done
echo "timeout waiting for '$pat'"; tail -5 "$f"
