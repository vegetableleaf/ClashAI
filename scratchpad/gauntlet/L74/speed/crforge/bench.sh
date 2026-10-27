#!/usr/bin/env bash
# S3 step 1 grid on pod 32657 (/workspace/cfspeed): K concurrent JVMs x T threads each, steady-state core matches.
# usage: bench.sh <label> <K> <T> <envsPerJvm> <warmSeconds> <target> <decideEvery> <pPlay> <obs> <xmx> [extra JVM flags...]
# Writes runs/<label>/jvm<k>.json (one CfSpeed JSON line each) and prints the sum: matches/h and core-s per match.
set -euo pipefail
cd /workspace/cfspeed
L=crforge/env/build/install/env/lib T=crforge_cache/tables/16.402.22
label=$1 K=$2 TH=$3 ENVS=$4 WARM=$5 TARGET=$6 DE=$7 P=$8 OBS=$9 XMX=${10}; shift 10
out=runs/$label; mkdir -p "$out"; rm -f "$out"/jvm*.json
for k in $(seq 1 "$K"); do
  java -Xmx"$XMX" -XX:ActiveProcessorCount="$TH" "$@" -cp "$L/*:build" CfSpeed core $T decks.tsv "$TH" "$ENVS" "$WARM" "$TARGET" "$DE" "$P" "$OBS" 1 \
    > "$out/jvm$k.json" 2> "$out/jvm$k.err" &
done
wait
cat /proc/loadavg > "$out/loadavg.txt"
python3 -c '
import json, glob, sys
rows = [json.loads(open(f).read()) for f in sorted(glob.glob(sys.argv[1] + "/jvm*.json"))]
m = sum(r["matches"] for r in rows); c = sum(r["cpu_s"] for r in rows)
print(json.dumps(dict(label=sys.argv[2], jvms=len(rows), threads=rows[0]["threads"], matches=m,
      matches_per_h=round(sum(r["matches_per_h"] for r in rows)), core_s_per_match=round(c / m, 4),
      plays_per_side=round(sum(r["plays_per_side"] * r["matches"] for r in rows) / m, 1),
      ticks_per_match=round(sum(r["ticks_per_match"] * r["matches"] for r in rows) / m),
      gc_s=round(sum(r["gc_s"] for r in rows), 1), rss_mb=sum(r["rss_hwm_mb"] for r in rows),
      wall_s=max(r["wall_s"] for r in rows))))' "$out" "$label" | tee "$out/sum.json"
