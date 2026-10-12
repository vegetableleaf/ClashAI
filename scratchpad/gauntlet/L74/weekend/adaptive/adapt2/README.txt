ADAPT2 status: implemented and offline-tested; uncommitted on l74-adapt2.
No pod job, simulator, network, deployment, or live-file changes were performed.

Code
  ../driver.py: --init, --extra-exploiters, --cycles (3), --tag (adapt).
  ../run_adapt2.sh: opt-in production wrapper; output /workspace/results/wk/ADAPT2.
  pipeline/tests/test_adaptive_opponents.py: continuation and default regression tests.

Continuation semantics
  ADAPT's main latest is update 60, before graft. With rl.league, copy its full
  resume state into wk_adapt2_main, retaining optimizer, RNG, guards, baselines,
  snapshots and PFSP ratings. The original init remains the frozen KL reference
  and PFSP init opponent; the learner weights come from the supplied checkpoint.
  Main targets are 80/100/120, so this adds 60 main updates. Each fresh exploiter
  still starts at the fast base and trains 15 updates. No guard is relaxed.
  Without rl.league, start from the supplied weights with fresh training/league
  state and targets 20/40/60. The driver logs which branch it uses.
  Existing snapshot IDs/ratings survive relocation from the old pod's absolute
  /workspace/wk_adapt paths to the staged checkpoint subtree. Missing referenced
  files fail before training. The trainer only deletes snapshots owned by its
  new run, so ADAPT's input snapshots remain untouched.
  Extra exploiters are enrolled before the first main segment, with p=.5 and
  games=0 for new opponents. Existing path identities retain their ratings.
  The wrapper uses exp1-3 u0015 files already enrolled in ADAPT. Offline tensor
  comparison verified these equal each corresponding latest file at update 15;
  using numbered paths avoids duplicate opponents and keeps learned ratings.
  Restart with identical arguments and the same output directory. Conflicting
  continuation options or an existing main checkpoint without its manifest fail.

Unchanged yardstick
  The existing graft_generic.py grafts OLD's add-ons onto the final main.
  OLD and the grafted ADAPT2 candidate each play 480 evo + 480 ladder games,
  paired seeds 30000:30480 / 30480:30960 against CAL set c at T=.1, unchanged
  live flags and unweighted census. SUMMARY.txt starts with the plain-language
  verdict and contains paired intervals and wk_compare's per-archetype table.
  The original no-new-options plan, configs and eval argv match a golden hash
  captured independently from 2bfafbf. run_adaptive.sh is unchanged.

Pod setup and exact launch command (not executed)
  Use a complete checkout of 2bfafbf at /workspace/wk_adapt2, overlay the two
  runtime files listed in POD_FILES.tsv, and stage its data files at the exact
  destinations there. Retain the existing ADAPT pod's /workspace/venv with the
  pinned 20261006-linux runtime and dependencies. This is not a network/install
  script. The full checkout supplies the tracked deck censuses, YAML, build
  manifest, pipeline modules and weekend weighting/graft/comparison helpers.
  Output checkpoint and run directories must be writable under this worktree.

  cd /workspace/wk_adapt2
  WAIT_FOR=/workspace/results/wk/ADAPT/DONE nohup bash scratchpad/gauntlet/L74/weekend/adaptive/run_adapt2.sh > /workspace/adapt2-launch.log 2>&1 < /dev/null &

  WAIT_FOR may be replaced with the file for the job that must finish first.
  The manifest includes the laptop's completed ADAPT/DONE sentinel for this
  exact command on a freshly staged pod. Waiting precedes gpu.lock, then
  cpu.lock. Serial 20-actor/worker stages retain ADAPT's <=28-process budget.
  ETA: 10-14 hours after the gate and locks clear on comparable hardware.
  ADAPT logs show 7.59 hours for 105 rollout/update steps plus 1.46 hours eval;
  the estimate allows screens/startup/overhead. ADAPT2 itself is unmeasured.
  EXIT/INT/TERM write SUMMARY.txt and DONE, including caught failures. SIGKILL,
  host loss, or an unwritable output filesystem cannot guarantee trap output.
  Nothing is deployed; read SUMMARY.txt even when DONE exists.

Needed laptop files (exact source, byte count and destination in POD_FILES.tsv)
  26 files, 748,615,393 bytes including the zero-byte ADAPT/DONE gate.
  ADAPT backup root:
    C:/Users/benpe/pod_backup_weekend/pod3/x_ADAPT/wk_adapt/
  Paths below it are under icebow/data/bench/rl_royale/:
    wk_adapt_main/wk_adapt_main_latest.pt                 18,691,098 bytes
    wk_adapt_exp1/wk_adapt_exp1_u0015.pt                  18,693,876 bytes
    wk_adapt_exp2/wk_adapt_exp2_u0015.pt                  18,693,876 bytes
    wk_adapt_exp3/wk_adapt_exp3_u0015.pt                  18,693,876 bytes
    wk_adapt_main/wk_adapt_main_snap_uNNNN.pt             6,242,805 bytes each
      NNNN=0005,0010,0015,0020,0025,0030,0035,0040,0045,0050,0055,0060.
  These 16 ADAPT inputs total 149,686,386 bytes. The grafted ADAPT checkpoint,
  frozen_c files and exploiter snapshots are not needed.
  The manifest also lists the original fast base, OLD, CAL_C, fv5 dataset,
  S1 specialist, ghost pool and split, measured read-only on the laptop, plus
  the two new/changed runtime files. Already-present identical inputs need not
  be transferred again. The ghost pool SHA matches both ADAPT's checkpoint and
  its frozen split: c37cb7bd7fe3d1fd1985c789ae610502f0d0b35687e6000e794f82a407badc80.

Tests (no SIM)
  C:/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/weekend/adaptive/check_offline.py
  96 passed, 1 deselected, 22 existing transformer warnings, 43.42 seconds.
  The existing Windows named-pipe exit test is deselected by check_offline.py.
  TEST_RESULTS.txt holds the output. Tests cover default config/plan/eval
  compatibility, real trainer league/RNG restoration, fresh/restored driver
  orchestration, pre-seeding, path relocation, missing snapshots, source-byte
  preservation, update offsets, tags, restart and the wrapper contract.
  Git Bash cannot start in this sandbox (CreateFileMapping, Win32 error 5).
  Bash syntax/runtime is manually reviewed, with pytest checking wait/lock/
  trap/argument contracts; no bash -n or actual pod runtime pass is claimed.
