#!/usr/bin/env bash
# trace_ident.sh RUNDIR LIB_A LIB_B : SmeRun full traces of every plan of a run under two engine libs; per-match sha256
set -e
RUN=$1; A=$2; B=$3; W=/workspace/pilot/bp/work/ident; mkdir -p $W
> $W/jobsA.txt; > $W/jobsB.txt
for d in $RUN/live_play_*/; do m=$(basename $d); [ -f $d/plan.json ] || continue
  python3 -c "import json,sys; p=json.load(open('$d/plan.json')); p['cmds']=[{k:v for k,v in c.items() if k!='_src'} for c in p['cmds']]; json.dump(p,open('$W/$m.p.json','w'))"
  echo "$W/$m.p.json 7000 $W/$m.A.jsonl 0" >> $W/jobsA.txt; echo "$W/$m.p.json 7000 $W/$m.B.jsonl 0" >> $W/jobsB.txt; done
java -Xmx24g -cp "$A/*:/workspace/pilot/sme/build_008aa626" SmeRun /workspace/crforge_cache/tables/16.402.22 $W/jobsA.txt 16 | tail -1
java -Xmx24g -cp "$B/*:/workspace/pilot/sme/build_008aa626" SmeRun /workspace/crforge_cache/tables/16.402.22 $W/jobsB.txt 16 | tail -1
n=0; same=0
for f in $W/*.A.jsonl; do g=${f%.A.jsonl}.B.jsonl; n=$((n+1))
  # object identity hashes in ability outcome strings ("CharacterEntity@5823f091") are not battle state: masked
  if cmp -s <(sed "s/@[0-9a-f]*//g" $f) <(sed "s/@[0-9a-f]*//g" $g); then same=$((same+1)); else echo "DIFF $(basename $f)"; fi; rm -f $f $g; done
echo "traces $n identical $same"
