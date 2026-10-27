#!/usr/bin/env bash
# usage: bpp.sh LIBTAG VERSION OUT  -- F635b: ButtonProbeP (promised by-id presses) on the 27 forced-button forms x 40 reps,
# 8 threads, as bp402 / bp635 were run with ButtonProbe
cd /workspace/f635 && rm -rf bpp_$1 && mkdir -p bpp_$1 && javac -d bpp_$1 -cp "lib_$1/*" ButtonProbeP.java || exit 1
D=forms_decks_402c.tsv; [ $2 = 16.635.3 ] && D=forms_decks_635c.tsv
JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount=8 java -cp "lib_$1/*:bpp_$1" ButtonProbeP crforge_cache/tables/$2 $D 8 40 $3 > $3.log 2>&1
echo done $3
