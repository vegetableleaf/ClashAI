
## L64b -- 2026-09-06 05:0x UTC -- S1 first run DISCARDED (row-format leak), datasets rebuilt, 6 seeds relaunched
- Leak (a): gate bal-acc 0.98 came from play frames carrying kind->deploying + effects that compact wait frames lack. Fix `_as_compact`; after it token cols 8-13 identical (0.000) across row types, both decks. Leaked log kept as LEAKED_train_icebow_s0.log (tile 16.8% best -- NOT an S1 number).
- Rebuilt: same row counts (icebow 21,687/56,590; hogeq 9,797/23,421); 24 tests OK; baselines identical (icebow tile 8.90%, hogeq 11.45%).
- TRAP: TaskStop on a bash chain leaves the script's bash + python alive (advanced to seed 1) -- kill the PID tree and verify.
- Running: run_seeds.sh (icebow s0-2, hogeq s0-2, 20 ep) ETA ~1h45. Next: icebow finals, gate sanity (<0.98 expected), then re-score old trunk on new rows.
