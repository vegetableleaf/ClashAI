MATCH MEMORY -- Phase A (code, offline tests, pod driver)

No job has been launched. No live launcher, LIVE_OPTIONS, deployment selection,
network, or Git commit was changed. pipeline/live_gen.py has only the required
GenPilot library input adapter; the existing live process is untouched.

Contract
  history_events defaults off. Checkpoints opt in with args.history_events=true,
  args.history_cap=256 and history.* weights. Old models and config hashes retain
  their old behavior. The memory transformer is width 64, two layers, four heads,
  with card/form/side/type embeddings, position and Fourier time encodings.
  Its tanh gate is zero initialized; the residual enters the trunk's global
  input token, before board/global attention. Default module: 100,928 parameters
  with the fast checkpoint's 124-card vocabulary and 128-wide trunk.

  Tokens, oldest first/newest last, then zero padding:
    kind, relative_side, card_id, form, x, y, match_seconds, hp_fraction,
    hp_fraction_delta, tower_kind_and_lane
  Kinds: 0 pad, 1 play, 2 tower HP, 3 tower death, 4 observed spell landing,
  5 confirmed ability press. Cap is configurable at conversion/build time and
  must match across model, dataset, and RL. Missing positions/HP are -1.
  PublicHistory is the ONLY event builder. PublicObserver uses the existing
  play detector for each side. No opponent hand, next card, deck, exact elixir,
  or ability-readiness field is read by this new input.

  Detection is observational: existing swarm/spell dedup can miss overlapping
  casts or events between sampled frames. No private command truth fills those
  gaps. Area-effect sightings certify spell landings; projectile disappearance
  alone does not. Confirmed OWN ability logs are included where already exposed
  by each adapter; an unobserved opponent press is not invented. Tower baselines,
  visible HP changes, explicit deaths, and disappearance from a complete public
  tower export are recorded (the existing board contract treats disappearance
  as death). Unreadable but present HP is not a death.

  Queries use strictly earlier ticks, matching the existing opponent-past rule
  and preventing replay-label leakage. SIM/live query the real observation tick,
  not extrapolated future time. Dataset queries are causal even after an entire
  replay has been scanned. Archives retain the match; only the newest cap events
  become inputs. Reset clears the archive. Full-match retention beyond 256 tokens
  requires increasing the configured cap; attention cost grows quadratically.

  P2 freezes every non-history parameter and keeps the trunk in eval mode.
  Mandatory positive KL(base || learner) covers gate/card/cell/wait/value;
  padded logits are excluded safely. Validation is replay-disjoint, and the best
  anchored validation loss is saved. Base tensors are verified unchanged each
  epoch. Histories stay CPU/file-backed and are gathered by batch. RL trains the
  full memory-enabled learner with its existing PPO/KL controls. No whole-policy
  imitation fine-tune is performed.

Pod commands (run from the populated l74-match-memory worktree)

  cd /workspace/cb_memory
  /workspace/venv/bin/python scratchpad/gauntlet/L74/memory/check_offline.py
  bash -n scratchpad/gauntlet/L74/memory/run_memory.sh
  mkdir -p /workspace/results/wk
  WAIT_FOR=/workspace/results/wk/ICEBOW_DONE nohup bash scratchpad/gauntlet/L74/memory/run_memory.sh > /workspace/results/wk/memory-launch.log 2>&1 &

  Omit WAIT_FOR to start immediately. It waits BEFORE taking locks. The worktree
  must have the existing pod runtime, checkpoint, census and corpus data links.
  No dependency download is attempted. The default corpus paths and sampling
  parameters come from gen_dataset_v32_fv5.npz metadata; if those paths refer to
  another host, append --corpus /pod/path/corpus1 /pod/path/corpus2 to the driver.
  The driver validates native/full recordings and exact checkpoint vocabulary.
  Use --init to choose the old-live model instead of the default fast base.
  PY and RESULTS override Python and /workspace/results/wk respectively.
  --cap, --epochs, --kl, --workers and --prefix expose the remaining budgets.

Standalone conversion (either syntax works)

  /workspace/venv/bin/python pipeline/add_memory.py icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel.pt /workspace/results/wk/memory_init.pt
  /workspace/venv/bin/python -m pipeline.add_memory icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt /workspace/results/wk/memory_live_init.pt

Phases
  MEMP1: CPU lock, one disk-spooled dataset builder, native pro histories.
  MEMP2: GPU lock THEN CPU lock; convert and memory-only imitation, 3 epochs,
         batch 128, learning rate 3e-4, KL coefficient 1, seed 74.
  MEMP3: GPU lock THEN CPU lock; existing adaptive PFSP/styles, hero abilities
         v2 on, plain policy (no live decoder rules), no anti-stall. Main learner
         reaches 20/40/60 updates; each frozen learner snapshot initializes its
         own memory-enabled exploiter for 15 updates. Final main segment reaches
         80 against all three exploiters. E=64, G=4, 20 CPU actors: 32,000 training
         matches total, plus existing held-out screens. Training guards can stop
         the run; that is failure, never silently treated as completion.
  MEMP4: CPU lock; graft_generic.py attaches the existing add-ons. Three arms,
         each 960 games: old live, memory, identical memory weights with input
         history zeroed. Evo census seeds 30000:30480 and ladder 30480:30960;
         fixed E4 u20 barrel2k_cellref_towerref_w2 opponent at T=0.1. Exactly the
         existing CAL/S2 live EVAL flags. Reports both paired contrasts and both
         per-archetype tables. Missing games, duplicate tags, changed decks or
         mismatched pairs fail. Improvement/memory benefit is shown only when
         its paired 95% CI lower bound exceeds zero, otherwise unestablished or
         negative. No result is assumed in advance and nothing is deployed.

Each phase writes SUMMARY.txt and DONE, even on caught failure/INT/TERM (SIGKILL
or host loss cannot run a trap). SUCCESS is separate. recipe.json pins source,
arguments, base and dataset template; COMPLETE.json hashes produced artifacts.
Completed phases verify their receipts before skipping. Changed recipes require
a fresh RESULTS directory AND --prefix; incompatible partial runs are refused.

Rough compute budget -- estimates, NOT measured throughput
  Assuming one contemporary 24-48 GB GPU, about 20 available CPU cores, fast local
  SSD and a corpus on the order of a few million decision rows:
    P1: 2-8 hours, CPU only, one worker (I/O and archive compression dominate).
    P2: 2-8 hours, one GPU, three epochs; frozen teacher plus student forwards.
    P3: 12-36 hours, one learner GPU plus 20 CPU actors (32,000 matches + screens).
    P4: 1-4 hours, 20 CPU workers (2,880 total evaluation games).
  Re-estimate from P1 row count, P2 batch timings and the first RL update. CPU
  memory-transformer inference may increase P3/P4 costs substantially. Dense
  cap-256 histories cost 10,240 bytes/row uncompressed (9.54 GiB/million rows).
  Dataset spool plus P2 mmap cache can exceed 70 GiB for 3.7 million rows before
  other arrays; allow at least 150 GiB free scratch for a corpus of that size.

Offline verification
  python scratchpad/gauntlet/L74/memory/check_offline.py
  Windows sandbox command used:
    C:/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/memory/check_offline.py
  See TEST_RESULTS.txt and real_checkpoint_check.json. Synthetic catalogs supply
  fixture data only: public detectors, adapters, tensor paths and training run.
  Dataset persistence and three-cycle orchestration use synthetic records/fake
  training; no simulator runtime runs. On restricted Windows the runner preserves
  workspace temp ACLs and excludes the existing named-pipe process-exit test.
  Bash startup is blocked on this host, so shell execution and bash -n remain pod
  checks. SIM performance, CUDA throughput, replay completeness and memory's
  playing-strength benefit are unmeasured until the pod phases finish.
