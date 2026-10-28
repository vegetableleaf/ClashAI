#!/usr/bin/env bash
# usage: probe.sh LIBDIR CLASSDIR TAG -- CF-CLONE: CloneProbe on 16.402.22 then 16.635.3 tables -> cp_TAG_{402,635}.tsv
L=$1; C=$2; T=$3; cd /workspace/cfclone
for v in 16.402.22 16.635.3; do
  s=$(echo $v | cut -d. -f2)
  SECONDS=0; java -Xmx24g -cp "$L/*:$C" CloneProbe /workspace/f635/crforge_cache/tables/$v /workspace/f635/census_decks.tsv cp_${T}_$s.tsv 20 > cp_${T}_$s.log 2>&1; echo wall $SECONDS s >> cp_${T}_$s.log
done
echo done > cp_$T.done
