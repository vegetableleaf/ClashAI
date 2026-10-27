#!/usr/bin/env bash
# usage: sweep2.sh LIBTAG VERSION DECKS REPS OUT -- ability sweep with kill-after-press, 8 threads
cd /workspace/f635
JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount=8 java -cp "lib_$1/*:sw_$1" AbilitySweep crforge_cache/tables/$2 $3 8 $4 $5 kill > $5.log 2>&1
