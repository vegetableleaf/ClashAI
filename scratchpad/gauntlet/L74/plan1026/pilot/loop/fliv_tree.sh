#!/bin/bash
# FAST-LIVEOPP: own tree /workspace/fliv/cb = symlinks to /workspace/oplm/cb2 except the loop dir (copied + FAST-LIVEOPP files)
set -e
SRC=/workspace/oplm/cb2; T=/workspace/fliv/cb
mkdir -p $T
cd $T
for x in $SRC/*; do b=$(basename $x); [ "$b" = scratchpad ] || [ -e $b ] || ln -s $x $b; done
farm() { # farm DIR_REL KEEP_CHILD: real dir whose children link to SRC except KEEP_CHILD
  mkdir -p $T/$1
  for x in $SRC/$1/*; do b=$(basename $x); [ "$b" = "$2" ] || [ -e $T/$1/$b ] || ln -s $x $T/$1/$b; done
}
farm scratchpad gauntlet; farm scratchpad/gauntlet L74; farm scratchpad/gauntlet/L74 plan1026
farm scratchpad/gauntlet/L74/plan1026 pilot; farm scratchpad/gauntlet/L74/plan1026/pilot loop
L=scratchpad/gauntlet/L74/plan1026/pilot/loop
mkdir -p $T/$L
for x in $SRC/$L/*; do b=$(basename $x); case $b in jbuild*|__pycache__) ;; *) [ -e $T/$L/$b ] || cp -a $x $T/$L/$b;; esac; done
cp /workspace/fliv/in/producer.py /workspace/fliv/in/CfTrain.java /workspace/fliv/in/msg_live.py $T/$L/
# L68/rl must be a real dir (new run dirs); L68 farm
rm -f $T/scratchpad/gauntlet/L68; farm scratchpad/gauntlet/L68 rl; mkdir -p $T/scratchpad/gauntlet/L68/rl
ls -la $T/$L | head -40
