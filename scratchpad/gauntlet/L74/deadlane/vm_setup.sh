#!/bin/bash
# Isolated VM code tree ~/deadlane/DIR = TAR (git archive) over symlinks to ~/ClashBot data. With TEL=1 also the
# push-Rocket telemetry (~/pipeline_plays/tel, measurement only) patched by vm_tel_patch.py (the SIM tree only; the
# pytest trees stay exactly the archive).  [TEL=1] bash vm_setup.sh TAR DIR
set -e
T=$1; D=~/deadlane/$2; rm -rf $D; mkdir -p $D; cd $D
tar xf $T
rm -rf icebow research; ln -s ~/ClashBot/icebow icebow; ln -s ~/ClashBot/research research
for g in ~/ClashBot/scratchpad/*; do b=$(basename $g); [ -e scratchpad/$b ] || ln -s $g scratchpad/$b; done
for g in ~/ClashBot/scratchpad/gauntlet/*; do b=$(basename $g); [ -e scratchpad/gauntlet/$b ] || ln -s $g scratchpad/gauntlet/$b; done
for L in L68 L69 L70 L73 L74 L68/live_reader L70/gen_v31; do
  for g in ~/ClashBot/scratchpad/gauntlet/$L/*; do b=$(basename $g); [ -e scratchpad/gauntlet/$L/$b ] || ln -s $g scratchpad/gauntlet/$L/$b; done
done
find . -path ./icebow -prune -o -path ./research -prune -o -name "*.py" -type f -print0 | xargs -0 sed -i 's/\r$//'
if [ -n "$TEL" ]; then
  cp ~/pipeline_plays/tel/behaviour_telemetry.py ~/pipeline_plays/tel/push_refine.py pipeline/
  ~/venv/bin/python ~/deadlane/vm_tel_patch.py pipeline
fi
echo "built $D"
