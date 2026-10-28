# CF-CLONE-2: h11b (a10G1 command, sme11 code, inputs_v29) with lib_cfclone2 (bec5811a + CF-CLONE + CF-CLONE-2 + TickProbe 0001/0002),
# compared to h11b; run dir on /dev/shm (root disk 82%), copied back after
cd /workspace/pilot && rm -rf sme_live/cf2 /dev/shm/cf2 && mkdir -p /dev/shm/cf2 && ln -s /dev/shm/cf2 sme_live/cf2 && date -u > harden/cf2.start
SME_DIR=/workspace/pilot/sme11 WORKERS=48 BASE=/workspace/pilot/sme_live/h11b bash bp9/run9.sh cf2 /workspace/pilot/lib_cfclone2 /workspace/pilot/inputs_v29/inputs_rngfree.jsonl SME_LATE9=1 SME_MADE9=1
rm sme_live/cf2 && cp -a /dev/shm/cf2 sme_live/cf2 && rm -rf /dev/shm/cf2
date -u >> harden/cf2.start
