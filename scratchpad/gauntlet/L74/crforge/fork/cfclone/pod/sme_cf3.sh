# CF-CLONE-3: h11b (a10G1 command, sme11 code, inputs_v29) with lib_cfclone3 (bec5811a + CF-CLONE + CF-CLONE-2 + CF-CLONE-3 + TickProbe 0001/0002),
# compared to h11b; run dir on /dev/shm (root disk 82%), copied back after
cd /workspace/pilot && rm -rf sme_live/cf3 /dev/shm/cf3 && mkdir -p /dev/shm/cf3 && ln -s /dev/shm/cf3 sme_live/cf3 && date -u > harden/cf3.start
SME_DIR=/workspace/pilot/sme11 WORKERS=48 BASE=/workspace/pilot/sme_live/h11b bash bp9/run9.sh cf3 /workspace/pilot/lib_cfclone3 /workspace/pilot/inputs_v29/inputs_rngfree.jsonl SME_LATE9=1 SME_MADE9=1
rm sme_live/cf3 && cp -a /dev/shm/cf3 sme_live/cf3 && rm -rf /dev/shm/cf3
date -u >> harden/cf3.start
