#!/usr/bin/env bash
# usage: rd.sh TAG  -- RowDiff of the current fork build on both table sets, compared
L=/workspace/f635/crforge_fork/env/build/install/env/lib; B=/workspace/f635/rd_build; T=/workspace/f635/crforge_cache/tables
rm -rf $B; mkdir -p $B && javac -d $B -cp "$L/*" /workspace/f635/RowDiff.java || exit 1
for v in 16.402.22 16.635.3; do java -cp "$L/*:$B" RowDiff $T/$v > /workspace/f635/rd/$1_$v.tsv 2>/workspace/f635/rd/$1_$v.err; done
python3 /workspace/f635/rowdiff.py /workspace/f635/rd/$1_16.402.22.tsv /workspace/f635/rd/$1_16.635.3.tsv > /workspace/f635/rd/$1.txt
