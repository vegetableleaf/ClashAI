#!/bin/bash
# MEMFULL-LOOP tree /workspace/mfl/cb = links to /workspace/oplm/cb2, with the archive's pipeline / obsid / loop files on top.
# mfl.tar (laptop): git archive HEAD pipeline scratchpad/gauntlet/L74/plan1026/pilot/loop scratchpad/gauntlet/L74/speed/crforge/obsid
# (+ uncommitted loop files on top, CR stripped). The facade (CfCore / CfSpeed) stays cb2's (= HEAD's modulo CRLF, 10-30).
set -e
SRC=/workspace/oplm/cb2; T=${T:-/workspace/mfl/cb}; A=${A:-/workspace/mfl/arch}
rm -rf $T $A; mkdir -p $T $A; tar --no-same-owner -xf ${TAR:-/workspace/mfl/mfl.tar} -C $A
mat() { # $T/$1 = a REAL dir of links to SRC/$1's children (never writes through a link)
  [ -L "$T/$1" ] && rm "$T/$1"
  mkdir -p "$T/$1"
  for x in "$SRC/$1"/*; do [ -e "$x" ] || continue; b=$(basename "$x"); [ -e "$T/$1/$b" ] || [ -L "$T/$1/$b" ] || ln -s "$x" "$T/$1/$b"; done
}
mat .
L=scratchpad/gauntlet/L74
for d in scratchpad scratchpad/gauntlet $L $L/speed $L/speed/crforge $L/plan1026 $L/plan1026/pilot scratchpad/gauntlet/L68 scratchpad/gauntlet/L68/rl; do mat $d; done
rm -f $T/pipeline
cd $A
find . -type d | sort | while read d; do d=${d#./}; [ "$d" = . ] && continue; [ -d "$T/$d" ] && [ ! -L "$T/$d" ] || mat "$d"; done
find . -type f | while read f; do f=${f#./}; [ -L "$(dirname "$T/$f")" ] && { echo "LINKED $f"; exit 1; }; cp --remove-destination "$f" "$T/$f"; done
cmp $A/pipeline/rl_royale.py $T/pipeline/rl_royale.py
# icebow/data = /workspace/icebow_data (b0, externals) + cb2's (oplc runs); bench/rl_royale merged, a real dir (new run dirs)
mat icebow; rm -f $T/icebow/data; mkdir -p $T/icebow/data/bench/rl_royale
lnk() { for x in "$2"/*; do b=$(basename "$x"); [ -e "$1/$b" ] || [ -L "$1/$b" ] || ln -s "$x" "$1/$b"; done; }
lnk $T/icebow/data /workspace/icebow_data; lnk $T/icebow/data $SRC/icebow/data
lnk $T/icebow/data/bench/rl_royale /workspace/icebow_data/bench/rl_royale
lnk $T/icebow/data/bench/rl_royale $SRC/icebow/data/bench/rl_royale
echo TREE OK
