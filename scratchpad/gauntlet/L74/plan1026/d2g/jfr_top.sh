#!/bin/bash
# jfr_top.sh FILE.jfr [N] -- JDK 17 has no `jfr view`: count jdk.ExecutionSample events by top frame (L = leaf method) and
# by class anywhere on the stack (I = inclusive), from `jfr print`; prints the N largest of each with % of samples.
F=$1; N=${2:-25}
jfr print --events jdk.ExecutionSample "$F" | awk '
  /jdk.ExecutionSample/ {n++; depth=0; delete seen}
  /stackTrace = \[/ {inst=1; next}
  inst && /^[[:space:]]*\]/ {inst=0; next}
  inst {
    line=$0; sub(/^[[:space:]]+/, "", line); sub(/[[:space:]]+line:.*/, "", line); gsub(/ /, "", line)
    if (depth == 0) leaf[line]++
    depth++
    cls=line; sub(/\.[^.(]*\(.*$/, "", cls)
    if (!(cls in seen)) {seen[cls]=1; inc[cls]++}
  }
  END {
    print "S", n
    for (m in leaf) printf "L %d %.1f%% %s\n", leaf[m], 100*leaf[m]/n, m
    for (c in inc) printf "I %d %.1f%% %s\n", inc[c], 100*inc[c]/n, c
  }' | sort -k1,1 -k2,2nr | awk -v N=$N '$1!=p{p=$1; k=0} k++<N'
