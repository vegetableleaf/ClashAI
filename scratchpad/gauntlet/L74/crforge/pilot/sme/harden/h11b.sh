# SME-HARDEN full dev-set run h11b (a10G1 command, sme11 code). Root disk is full (60G, vfy10/work 10G, f16 24G), so the
# run directory lives on /dev/shm and is copied back to /workspace/pilot/sme_live/h11b after run9 removed the work dirs.
cd /workspace/pilot && rm -rf sme_live/h11b /dev/shm/h11b && mkdir -p /dev/shm/h11b && ln -s /dev/shm/h11b sme_live/h11b && date -u > harden/h11b.start
SME_DIR=/workspace/pilot/sme11 WORKERS=48 BASE=/workspace/pilot/sme_live/a10G1 bash bp9/run9.sh h11b /workspace/pilot/lib_f635c /workspace/pilot/inputs_v29/inputs_rngfree.jsonl SME_LATE9=1 SME_MADE9=1
rm sme_live/h11b && cp -a /dev/shm/h11b sme_live/h11b && rm -rf /dev/shm/h11b
date -u >> harden/h11b.start
