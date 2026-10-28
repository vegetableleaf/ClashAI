# CF-CLONE: h11b (a10G1 command, sme11 code, inputs_v29) with lib_cfclone (bec5811a + CF-CLONE + TickProbe 0001/0002),
# compared to h11b; run dir on /dev/shm (root disk 82%), copied back after
cd /workspace/pilot && rm -rf sme_live/cf1 /dev/shm/cf1 && mkdir -p /dev/shm/cf1 && ln -s /dev/shm/cf1 sme_live/cf1 && date -u > harden/cf1.start
SME_DIR=/workspace/pilot/sme11 WORKERS=48 BASE=/workspace/pilot/sme_live/h11b bash bp9/run9.sh cf1 /workspace/pilot/lib_cfclone /workspace/pilot/inputs_v29/inputs_rngfree.jsonl SME_LATE9=1 SME_MADE9=1
rm sme_live/cf1 && cp -a /dev/shm/cf1 sme_live/cf1 && rm -rf /dev/shm/cf1
date -u >> harden/cf1.start
