#!/bin/bash
# ~/tau_threat/repo = this branch's pipeline/ (git archive) over symlinks to ~/ClashBot data, + the VM's behaviour telemetry
# (~/pipeline_plays/tel, measurement only) + tau_tel.py hook. Never touches ~/ClashBot.   bash vm_setup.sh TAR
set -e
T=$1; D=~/tau_threat/repo; rm -rf $D; mkdir -p $D; cd $D
tar xf $T
ln -s ~/ClashBot/icebow icebow; ln -s ~/ClashBot/research research; ln -s ~/ClashBot/scratchpad scratchpad
find pipeline -name "*.py" -type f -print0 | xargs -0 sed -i 's/\r$//'
cp ~/pipeline_plays/tel/behaviour_telemetry.py ~/pipeline_plays/tel/push_refine.py pipeline/
cp ~/tau_threat/tau_tel.py pipeline/tau_tel.py
~/venv/bin/python ~/tau_threat/vm_tel_patch.py pipeline
echo "built $D"
