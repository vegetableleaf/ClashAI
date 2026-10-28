# LEARNER-SCALE_2 DDP probe

Pod 33308; 2026-10-28 UTC. Execution order: NCCL, concurrent c0/GPU0 + c1/GPU1, alone/GPU1. All runs exited 0; no OOM. Steps 3-5 completed in approximately 5 minutes (within 20 minutes).

NCCL values: 
{"world": 2, "params": 2004016, "ms_p50": 0.8541570005036192, "ms_p90": 0.8733329996175598, "deterministic": true}

| run | mb | total ms | gen_batch ms | forward_ex_gen ms | backward ms | rows_per_s | peak_mb | kernels_per_step |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| alone | 256 | 147.785 | 43.750 | 40.874 | 57.062 | 1732.240 | 2574.449 | 5257.000 |
| alone | 1024 | 435.055 | 167.421 | 99.669 | 161.717 | 2353.724 | 8403.523 | 5710.667 |
| alone | 2048 | 809.813 | 329.197 | 164.316 | 310.120 | 2528.980 | 16058.461 | 5905.000 |
| c0 | 256 | 148.962 | 43.776 | 44.601 | 57.836 | 1718.561 | 2574.449 | 5257.000 |
| c0 | 1024 | 443.097 | 172.283 | 100.785 | 163.158 | 2311.007 | 8403.523 | 5710.667 |
| c0 | 2048 | 824.816 | 337.959 | 166.194 | 313.127 | 2482.979 | 16058.461 | 5905.000 |
| c1 | 256 | 146.035 | 42.855 | 43.889 | 56.787 | 1753.002 | 2574.449 | 5257.000 |
| c1 | 1024 | 436.877 | 168.700 | 99.617 | 161.725 | 2343.908 | 8403.523 | 5711.667 |
| c1 | 2048 | 810.552 | 328.595 | 164.216 | 310.029 | 2526.673 | 16058.461 | 5905.000 |

concurrent / alone rows_per_s, mb 256: c0 = 0.992; c1 = 1.012.
concurrent / alone rows_per_s, mb 1024: c0 = 0.982; c1 = 0.996.
concurrent / alone rows_per_s, mb 2048: c0 = 0.982; c1 = 0.999.

Step 5 memory.usage_in_bytes: 22504927232 bytes at elapsed 00:01:11 while both processes ran. Combined learner RSS at that sample: (3888132 + 3827460) KiB = 7900766208 bytes. Both runs finished after approximately 114 seconds, before the requested approximately 2-minute sample; no 120-second in-flight reading exists. This is an observed sample, not a peak-memory measurement.

Prelaunch memory bytes: NCCL 15761059840; c0 15785820160; c1 15786606592; alone 15791587328. Initial compute-process query was empty on both GPUs. No memory-gate waits were needed.

SHA-256 matched local/pod before execution:
- prof_step.py: 147e642653184224d89adf0a167630ef35aa2d7ad8d2b2d744da136bea7f963b
- nccl_probe.py: f83d62051efd9f0cea8a871d42a3056d6913f733f3ed466a3c2248d6518b8931

Artifacts: four JSON files and nine prof_*_mb*_table.txt files copied from /workspace/lscale/out/ into this directory. No pod files deleted. No probe source code edited.
