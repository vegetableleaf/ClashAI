#!/bin/bash
# S2-01 pod setup (run ON the pod after the laptop copied s2_overlay.tar + s2_manifest.sha into /workspace/in). Starts NOTHING.
#   extract + sha-verify the overlay into /workspace/cb_tt (stage2 files + gen_v32_s0); build two pod-local checkout copies
#   (icebow/data + research symlinked to cb_tt, never synced back):
#     /workspace/cb_13k  = cb_tt with L74/levels/live_levels.json REPLACED by stage2/levels/levels13k.json (S2-03 zero-code route)
#     /workspace/cb_tel  = cb_tt + loss_review/econ_sim_patch.py telemetry + livecal --behaviour-telemetry (opp_behaviour_pod.sh's
#                          isolated-copy recipe; style-distance runs only)
#   /workspace/s2/{s2chain.sh, queue.txt}; touch /workspace/KEEP.
set -euo pipefail
PY=/workspace/venvf36/bin/python; L=scratchpad/gauntlet/L74; CB=/workspace/cb_tt
touch /workspace/KEEP
cd $CB && tar xf /workspace/in/s2_overlay.tar --no-same-owner && sha256sum -c --quiet /workspace/in/s2_manifest.sha && echo MANIFEST_OK
mk() {
  rm -rf $1; mkdir -p $1
  tar -C $CB --exclude=./icebow/data --exclude=./research --exclude=./scratchpad/gauntlet/L68/rl -cf - . | tar -C $1 -xf -
  ln -s $CB/icebow/data $1/icebow/data; ln -s $CB/research $1/research
}
mk /workspace/cb_13k
cp $L/stage2/levels/levels13k.json /workspace/cb_13k/$L/levels/live_levels.json
cmp $L/stage2/levels/levels13k.json /workspace/cb_13k/$L/levels/live_levels.json && echo "CB_13K_OK $(sha256sum /workspace/cb_13k/$L/levels/live_levels.json | cut -c1-12)"
mk /workspace/cb_tel
$PY /workspace/cb_tel/$L/loss_review/econ_sim_patch.py /workspace/cb_tel/pipeline
sed -i "s/'--hero-abilities', '--ability-policy'/'--hero-abilities', '--behaviour-telemetry', '--ability-policy'/" /workspace/cb_tel/$L/livecal/livecal.py
grep -q "'--behaviour-telemetry'" /workspace/cb_tel/$L/livecal/livecal.py && echo CB_TEL_OK
mkdir -p /workspace/s2; cp $L/stage2/pod/s2chain.sh /workspace/s2/.new && mv -f /workspace/s2/.new /workspace/s2/s2chain.sh
[ -e /workspace/s2/queue.txt ] || touch /workspace/s2/queue.txt
echo S2_SETUP_OK
