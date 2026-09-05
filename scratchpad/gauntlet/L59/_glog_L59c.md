
## L59c (2026-09-05 12:4x-13:2x UTC) -- G read m5k/m10k: placements COLLAPSED; owner: no control, go to E
- Wakeup at 05:4x UTC never fired; 7 h unattended. arm_gates.py (detached) took and posted both reads anyway.
- G m5k (3 seeds): tesla@234 13/27, 20/28, 16/31 (distinct 11/7/14); knight@426 18/36, 22/38, 16/36; credits
  16 (+26/+30); tesla P1 0.104/0.153 (baseline 0.039). m10k: tesla 21/28, 27/31, 24/28 (distinct 5/5/5);
  KNIGHT 41/41, 36/36, 35/36 (distinct 1/1/2); credits 8-9 (baseline 23); watchdog CELL HEAD COLLAPSED
  1.08-1.16 of 5.08 nats. Eval ladder 37/39/27/23/36/27/35% m2k..m14k. (a, one training seed)
- Not attributable to the reward (no geometry-off resume) -- (b). Owner: "No control ... Go straight to E."
- G stopped at 15,750 eps (procs 19 -> 1, final weights data/bench/armG_m15k7_final.pt sha 3d7713b7).
- ARM E launched 13:0x UTC: c2r + sim.ppo_cell_entropy_floor 0.05, geometry OFF, same CLI, rail x0.0430;
  200 eps 12%, 0.8 ep/s. Monitors detached with python -u. m5k ETA ~15:0x UTC.
- Leak: hung stt.ps1 (PID 22200, 2.3 GB, since 09-04 21:43) -- kill blocked by the classifier; owner to kill.
