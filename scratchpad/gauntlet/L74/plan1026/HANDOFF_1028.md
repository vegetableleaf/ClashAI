# HANDOFF 2026-10-28: full state for the next account (READ ALL OF THIS FIRST)

Written by the lead before the account switch; refreshed at the 98-99% usage stop. Labels: (a) measured, (b) plausible,
untested, (c) contradicted. Everything below is committed on origin/main unless marked local / pod-only.

## 0. Read order
1. This file.
2. `scratchpad/gauntlet/L74/plan1026/PLAN.md`, plus these owner changes not yet folded into it:
   - the fin16 fallback is struck (owner 10-27);
   - the R_exchange decision is pending (section 5);
   - the pilot track (section 4).
3. `scratchpad/gauntlet/L74/plan1026/pilot/LOOP_SPEC.md` (the fast loop's spec and tickets).
4. `scratchpad/gauntlet/L74/plan1026/REWARD_REVIEW.md` (the reward review; the owner's decision is pending).
5. `scratchpad/gauntlet/L74/crforge/pilot/sme/SME.md` (the exact-replay method, every round) and `results/SME.md`.
6. `scratchpad/gauntlet/L74/crforge/CRFORGE_S0.md` (engine pins, fork branches, 16.635 notes).
7. Memory index `C:\Users\benpe\.claude\projects\C--Users-benpe-ClashBot\memory\MEMORY.md`: the 10-27 / 10-28 entries are
   the newest and most important.

## 1. Owner decisions and rules from 10-27 / 10-28 (binding)
- **Engine = crforge, NO fin16 fallback.** Iterate crforge until SME >= 99/109 (D1) and >= 107/109 (D2) on FRESH
  held-out matches. Never reach a number by loosening the comparator.
- **Pilot successor approved:** B0 = CLXIII + memory encoder, trained on the D1-era crforge at several hundred thousand
  matches/h, and only via the FULL fast loop (the owner rejected the 50-130k/h shortcut). The owner rents an 8x RTX PRO
  6000 for a few hours when we're ready; we report the sim speed. When training ends, TELL THE OWNER TO SHUT IT DOWN
  IMMEDIATELY: we cannot stop pods ourselves (no RunPod CLI or API key on the laptop; never call runpodctl). Then a SIM
  gate vs CLXIII, then a live trial vs CLXIII. The owner wants it "today" (10-28) and asked for maximum parallelism.
- **Reward:** the owner accepted "tower terms + HF-fitted destroyed - committed" and sent it to X2/X3, BUT asked for a
  full review first. The review (REWARD_REVIEW.md) found that destroyed - committed REWARDS BANKING AND LEAKING (an
  identity from equal elixir income), and recommends potential-based shaping, Phi = P(win | state, time to go). X2/X3
  now run on 3 variants. **Do not finalise the reward in PLAN.md until the owner decides on that evidence.**
- **Live reader switched to merged_sf** (the step-flag reader) with the owner's go, 10-28 07:53. Trial: 0 torn frames
  of any class in 21,981 frames; play metrics unchanged.
- **Crawler (RoyaleAPI):** written permission for 2 req/s and 150k/day combined across all IPs and accounts; rotating
  IPs allowed within the limits; we may continue through Cloudflare challenges; a full stop only on a permanent ban.
  NEVER solve, script or bypass a challenge: only the owner clears them by hand. The owner finds clearing every ~30 min
  unworkable; the recommendation sent was to ask RoyaleAPI for a longer clearance or an endpoint exemption, and
  otherwise rely on the HF + live data. RunPod pods all share ONE exit-IP pool (185.226.156.3/.5), so more pods add no
  IPs. The multi-IP crawler is built (4d9d70e) but off.
- **Supercell permission:** the owner believes it is allowed; RoyaleAPI asked for it to be documented. Open with the owner.
- **Hooks:** killall AND `pkill -f` are blocked (4997158). Stop processes by exact PID only.
- **Start live ONLY with** `bash scratchpad/gauntlet/L70/live/start_live.sh icebow --no-fast-plays --ranked` (omitting
  --no-fast-plays turns fast plays ON: the 10-27 misdiagnosis).
- **Successor ETA given to the owner:** a 10M memory successor live ~12-15..12-22; best case early December. The owner
  thinks it can be much sooner, hence the pilot.
- **Evo Goblin Barrel decoy (owner report):** the live model responds on the decoy's side. Ticket GB-DECOY is
  diagnosing; any live change needs the owner's go plus a blind verifier.

## 2. Engine (crforge) state
- **Fork base:** clashbot-up-e5462c82 (head bec5811a) = upstream 16.635 + ours; accepts the 16.402.18-22 and 16.635.3
  tables.
- **Fixes on branches:**
  - clashbot-cfclone: 62558795 (Clone carries the spawner state) and bac75659 (deploying clones, Goblin Demolisher);
    the Fisherman pulled-state clone + Mirror + evo coverage are in progress;
  - clashbot-f1fix: c99784e4 (Rune Giant enchants FRIENDS: 136/136 live launches) and 89b93932 (enchant on Inferno
    Dragon).
  - CF-MAIN is consolidating all of these into **clashbot-main**, with the default libs on every pod and
    crforge/fork/MAIN.md. Use MAIN.md's libs.
- **Instrumentation patches** (never merged into main; applied at build time for SME): fork/bp/
  clashbot-bp_0001_TickProbe, 0002_TickProbeDrain, 0003/0004 MoveProbe, 0005 DmgProbe.
- **SME (exact replay):**
  - **Dev set** (the 109 unflagged matches of the A2b-1 138; the original flag list):
    - 109/109 with the HARDENED comparator (3bbf50c; a planted suite runs inside every match, 65,874 plants, 0 missed);
    - exact frames 250,797 on the 109 (278,872 is the 138 total; earlier reports mixed these up);
    - like-for-like with the current extractor flags: 113/120;
    - a blind verifier confirmed the fitter's ticks are pinned by evidence (no over-fit).
  - **FRESH1** (17 overnight matches, 7 unflagged; frozen in 4e7014d): 5/7 hardened, then 6/7 after SME-F1FIX
    (8010d5a). FRESH1 is now DEV data.
  - **Strict SME** (the plan's definition: only reader-flagged frames excluded) is now possible, because live runs
    merged_sf. **FRESH2 = live matches after 2026-10-28 07:53.** Freeze the list before running, then run hardened SME
    with no fixes. D1 needs >= 45/50 by the plan's bar (90%); a lower bound of 0.98 needs about 150 matches
    (about 3 days of live at ~50 RNG-free matches/day).
  - **The one open FRESH1 failure:** 000420@3519, a tower removed with nothing visible; an unseen Zap at 3517/3518 makes
    it exact. A rule would fire once, so it is proposed only.
- **D1 table:**
  - crown sequence: PASS (+0.209);
  - SME: needs FRESH2;
  - HF faults: PASS, 0.040% (7 after CF-CLONE-2, of 19,995);
  - cost: PASS (0.27 core-s/match);
  - parsed stats: 99.992%. The 2 hero Berserker fields are proven battle-inert (OnStartingAction cycles 3 identical
    attacks), so counting it as 100% is the OWNER's call.
- **D2:**
  - determinism: PASS with deterministic CUDA (learner_deterministic option, f42674c; the CPU learner is unusable);
  - time per update: PASS, 0.95-1.00x fin16 at 24 actors (D2-T2, 3 paired runs);
  - CLXIII re-baselined on crforge: E4 70.1% vs fin16 74.6%; iu40 56.0% vs 59.4% (tower troops were excluded then;
    re-run owed now that the facade supports them);
  - SME >= 0.98 on fresh: owed (FRESH2+).
- **Reader 160635001:** merged_sf live (local files only: icebow/data/reader_160635001/*,
  reader_notes/merged/live_env.sh; *.pre_sf.bak = rollback). The local default reader_config.json is the 16.635.3
  config (*.160402012.bak). Plain `python` on the laptop lacks sm_120: live needs icebow/.venv/Scripts/python.exe.

## 3. Training-loop and speed state
- **Measured:**
  - crforge engine 0.09 core-s/match; Java obs (all 20 GenModel keys byte-identical to production; 564,737 actor rows
    identical) about 0.27 core-s/match in CfLoop;
  - GPU forward on a 4090: 1.76M fp32 21k rows/s, bf16 47k (0.34-0.49% of decisions change); 10M fp32 4.6k;
    RTX PRO 6000 is 1.4-2.0x faster at 2.8x the price;
  - the async policy server keeps 98.6% of the bare forward rate (d685350);
  - today's rl_royale crforge path: 56-65 core-s/match (about 2k matches/h per pod); the forward on CUDA vs CPU per
    match: 15.6 vs 29.5 core-s.
- **Fast loop:** LOOP_SPEC.md. Tickets running at handoff (each reports DONE / BLOCKED in its commits and SPEED / pilot
  docs):
  - LOOP-INT: integrator; dev pod 33308, clean throughput pod 33553;
  - LOOP-MEM: memory v2 tables in Java;
  - LOOP-CTX: decide context in Java;
  - LOOP-IW: hero ability press observation in Java;
  - LOOP-OPP: frozen opponent pool (rdef_e4_u0020_barrel2k, w14opp_I, wk_adapt_exp1-3, newsim_base_exp1-2, u0015);
  - LOOP-SRV: multi-model / multi-GPU server;
  - LOOP-LRN: the learner + Phi reward + the new kl_stop_prev (rl_royale had NO KL early stop; beta 0 = no leash);
  - LOOP-OPS: B0 + pilot config + pod launcher. B0 = **GRAFTED** CLXIII + memory encoder,
    icebow/data/bench/rl_royale/b0/b0_clxiii_s3aux_grafted.pt sha 984bf572. Note that mem_best_ze (3d75a25d) was
    trained on the RAW succ48_o_s91 u75. "ICEBOW Mark CLXV" is reserved for the TRAINED pilot; B0 gets no Mark.
- **Before renting:**
  1. correctness: actions and outcomes identical to rl_royale's crforge path, log-probs within 1e-5, >= 2
     deterministic updates;
  2. measured matches/h on 33553 plus a projection to 8x RTX PRO 6000 (about 27 vCPU per GPU);
  3. a launcher dry run on 33308.
  Then ask the owner to rent.

## 4. Other workstreams (status at handoff)
- **Pillar 2 opponents:**
  - re-drive pass 1 of the HF 252k through crforge: ~20% tier A; tower-troop replays + the evo Elite Barbarians catalogue
    fix are being added (redrive/RD1.md; pod 33308 /workspace/redrive/full_bec5811a);
  - P2-OPP1: opponent model v0 (timing head, deck encoder, memory) pretraining;
  - P2-SCORE: closed-loop scorecard levels B-D;
  - **owner rule:** re-drive again after D1 AND after D2, aiming at 109/109 for the final pass;
  - closed-loop B-level numbers before D2 are provisional (engine-limited).
- **Pillar 3:**
  - RX-X23: X2 + X3 on 3 variants: (i) towers + a_lin, (ii) towers + destroyed, (iii) potential Phi; plus the numeric
    check of the bank/leak identity;
  - P3-FORK: lands cf_credit with the review fixes;
  - X1 history: the elixir terms add nothing over towers on live; on HF, destroyed / a_lin add +.005/+.006 AUC at 60 s
    only.
- **Pillar 4:**
  - P4-10M: curve v1 on HF + ours, plus a ~10M icebow + memory base (the start of the 10M successor);
  - SCALE v0 knee: 10-20M.
- **GB-DECOY:** evo Goblin Barrel decoy diagnosis and fix proposal (live change needs the owner).
- **CF-CLONE:** Fisherman / Mirror / evo Clone coverage.

## 5. Decisions waiting on the owner
1. Reward: which variant (after X2/X3); the review recommends potential Phi; do NOT adopt a_lin.
2. D1 stats line: count the 2 battle-inert Berserker fields as 100%?
3. Crawler: ask RoyaleAPI for a longer clearance / endpoint exemption, or stop crawling.
4. The proposed Zap rule for FRESH1 000420 (fires once): not built.
5. Supercell permission documentation.

## 6. Live and pods
- **Live:** CLXIII NOLEAK (8d328a43), Ranked, merged_sf reader, fast plays OFF; about 30-33% wins in league 5 (flat for
  2 days). The stuck watcher (scratchpad/gauntlet/L70/live/stuck_watch.sh) must be re-armed after each alert:
  - false alarms come from normal "unknown ... battle loading" handoff lines;
  - a real stall happened on a one-off "Supercell Support" Claim All screen (tapped 450,1460 once);
  - teaching the navigator that screen, and tightening the watcher, are owed.
- **The battle-log poller** runs (PIDs 33548 / 13956; crapi/own_poll.sh).
- **The crawler** runs in the Terminal tab "crawler single-lane" (paused on challenges; resume = `rc_crawl.py resume
  --lane 9222`).
- **Pods** (SSH key ~/.ssh/runpod_clashbot; the owner's id_ed25519 does not exist on the laptop):

  | pod | GPU / cores | notes |
  |---|---|---|
  | 32657 | 4090, 54 vCPU | owner-kept; root disk nearly full earlier, freed to 12 GB |
  | 33920 | 4090 | SME runs |
  | 30408 | 4090, 54 vCPU | fork builds; SSH timed out once |
  | 33308 | 2x4090, 108 cores, 251 GB | root@157.157.221.29 -p 33308; rebooted itself 02:22 10-28, /workspace survived |
  | 33553 | 4090, 54.4 cores, 251 GB | NEW 10-28; root@157.157.221.29 -p 33553; clean throughput pod for LOOP-INT |

  Never release kept pods without asking. Owner pods are all intentional.
- **Laptop:** shared and loaded (trade_council paper trader, Roblox Studio, MuMu). Never run two GPU jobs. A plain
  `ls -t` in live_reader takes about 60 s (thousands of files).

## 7. Traps learned 10-27 / 10-28
- Each worker that edits shared files (extract.py, sme_live.py, CfCore.java, rl_royale.py) must commit path-limited
  hunks only (git apply --cached / temp index); never stage or unstage others' files.
- Workers leave background whole-disk `find` processes: stop them by exact PID when found.
- Internal names mislead: EliteArcher = Magic Archer; GiantBuffer = Rune Giant, which has NO hero form (its
  GiantBuffer_hero row is a leftover). Name items by the real card and form from the tables.
- A fixed match becomes dev data: every gate number must come from a NEW frozen fresh set.
- The update-time ratio swings 10-20% with which CPU set a run gets: always run paired, with the sets swapped.
- Reading torn frames: the merged_sf reader removes them at the source; the comparator's torn classes stay for old logs.

## 8. Addendum (10-28 ~10:15 EDT, weekly usage 84%)
- **GB-DECOY (evo Goblin Barrel):**
  - live answers go to the real side only 30/50 vs 95.5% for the plain barrel; the model sees two identical mirrored
    barrel tokens; the real barrel is always created FIRST (50/50);
  - the fix pipeline/barrel_decoy.py relabels the later-created barrel as the decoy; recorded-play replay 30/50 -> 49/50
    (scratchpad/gauntlet/L74/gb_decoy/STATUS.md);
  - **the owner said GO and accepts creation order as the stand-in for the colour cue.** Steps in progress: a model
    replay on a pod, then a flag commit (--barrel-decoy on in LIVE_OPTIONS), then a blind verifier (the lead dispatches
    it), then deploy at a match boundary with the exact start command; rollback = flag off + restart;
  - the successor's Java obs needs the same rename (a LOOP interface note).
- **Pilot decisions:**
  - tables 16.635.3;
  - the opponent pool = init + 5 old externals + E4 + w14opp_I = 8 at 1/8 each; w14opp_I keeps its own exploiter slot
    (its calibrated decode) at share 0.125; league_pfsp_gamma 1e-9 (rl_royale refuses 0);
  - **gate decode = SAMPLED gate T 0.1 in training AND in the pilot's deploy** (PLAN Pillar 3; the threshold gate is not
    PPO-trainable);
  - KL: kl_stop_prev 0.02 (new; rl_royale had none), penalty beta 0;
  - B0 line-ending fix "A+": .gitattributes s1c/*.json eol=lf, B0 rebuilt with the LF hashes (a NEW sha; the old one
    is kept as *.crlf.bak); CLXIV and the 10-25 memory arms no longer load on the laptop (accepted).
- **LOOP-OPS:** the launcher is ready (pilot/ops/README.md; `loop_pod.sh up PORT`; a dry run passed on 33308 with a
  stand-in loop; boot 3m47s; 51 + 29 artifacts sha-checked).
- **LOOP-INT milestone 1 (a):** the skeleton runs end to end on 33308 (pilot/loop/{CfTrain.java, producer.py,
  fastloop.py, run.sh, ref_v0.yaml}). Unported parts raise rather than run wrong. Next: the same-device correctness A/B vs
  rl_royale, then throughput on 33553.
- **D2 update time PASSES** (0.95-1.00x fin16 at 24 actors; D2-T2). The Java obs is identical on 564,737 actor rows.
- **LOOP-IW** (a new worker) has the IW press obs port; D2-T2 is done.
- **Shared-checkout hazard (repeated today):** plain `git commit` sweeps in other agents' staged files (9f1c142, 6638a73,
  b2a1e7c). Always `git add <paths> && git commit -- <paths>`.

## 9. Final addendum at the account switch (10-28 ~12:00 EDT, weekly usage 95%)
All workers were sent STOP at 95%. Each one's STATUS section in its own doc is the restart point; subagent ids do NOT
carry over. Re-dispatch from the docs listed here.

### 9.1 Live
- CLXIII NOLEAK Ranked on the step-flag reader, `start_live.sh icebow --no-fast-plays --ranked` via the supervisor.
- **Evo Goblin Barrel decoy fix is LIVE since the 11:45 restart** (`--barrel-decoy on` appended to
  scratchpad/gauntlet/L70/live/LIVE_OPTIONS). Blind verifier: PASS_WITH_NOTES (flag off = 1,718/1,718 + 964/964
  identical; flag on changes only the decoy-row decisions; 0 marks on 14,486 plain frames). F1 (two REAL barrels at
  mirrored points, e.g. Mirror, would hide the 2nd; 0 cases in 16,261 frames) and F2 (malformed rows crash) went back to
  GB-DECOY before the deploy; see gb_decoy/STATUS.md for which landed. Rollback = delete the line + match-boundary restart.
- `--gate-sample T` (sampled play gate) now exists in live_play (63b0693, 92a0d37), OFF by default: flag off =
  1,718/1,718 identical; T 0.1 fire rate live 0.1405 vs trainer 0.1410 (expected 0.1390). The pilot deploys with it ON.
- Session tally at 11:43: 305 wins today; W 2660 / L 2749 lifetime counter.

### 9.2 Fast loop (pilot) - all parts exact vs production; speed is the open problem
- Java ports, all byte-identical to production: obs (20 keys), memory v2 (LOOP-MEM, 105,178 seat-rows, 20b324f),
  decide context (LOOP-CTX, 90,193 rows, 2542689), IW press (LOOP-IW, 657,699 rows, 55fe195), opponents
  (LOOP-OPP, 36,506 decisions, 8797e07).
- LOOP-INT: rl_royale vs fastloop with PPO-updated policy over 3 updates: every non-lp batch key byte-identical,
  outcomes 16/16, monitors identical; lp float noise <= 2.3e-6 (bar 1e-5). Bug fixed: Cohort.fill read evolved opp
  cards as form 0. fastloop FINAL bug fixed (d25839e). Exact vectorised decide halves producer cost.
- Throughput (clean 33553, 1 producer x 512 matches x 8 threads, in-process forwards): 12.5k/h -> 18.8k matches/h,
  0.82 core-s/match (Java engine 0.28, obs 0.04). TARGET <= ~0.5 core-s/match for 300k/h on ~128 cores. Next: LOOP-SRV
  server instead of in-process forwards; _record cost; ctx adapter (79 us/row: build lethal dicts only when Log/Rocket
  affordable).
- LOOP-SRV (d783df0, 08fa0ee): multi-model multi-GPU server, TF32 OFF (required: TF32 on gave lp_cell diffs up to 2.53 and
  1 action flip in 4,096 rows; off = 7.6e-6, 0 flips; costs 13-14%). 4090 ~96k matches/h at the pilot mix; RTX PRO 6000
  projected ~190k/h (scaled, not measured).
- LOOP-LRN (7a80ac6, bbf3fdf, 8c58db4, e9471f5): learner identity bit-exact; kl_stop_prev opt-in; TF32 off under
  learner_deterministic; tower_phat shaping (AUC .66/.81/.92). Shared ref+value no-grad pass: bit-identical, 115.6 ->
  67.6 s/update. **kl_stop_prev 0.02 binds at ~145 of 1,244 steps**, so updates use ~12% of rows. Larger minibatches
  buy nothing (cost linear in rows; 2,048+ OOM on 24 GB) - the minibatch-sweep premise was WRONG and is cancelled.
  APPROVED and being built: (iv) learner uses the server's stored lp_old + V (server adds the value head), KL stop via
  a ref forward of the sampled minibatch rows only; recompute mode stays as the identity check. Projection 20-35 s per
  update independent of size -> 2,048 matches/update = 210-370k/h on ONE 4090. matches_per_update is a config value,
  to be chosen after INT's bench. Then (i): cell/tower refine on played rows only. Entropy-floor guard KEPT (not a
  leash), its ref_init baseline computed on a row subsample.
- **Trade-off the owner must know:** at 2,048 matches/update each match teaches less (KL cap binds); the gain is in
  updates/hour (~100-180 vs ~40 for rl_royale at 512).
- LOOP-OPS: B0 LF rebuild sha 76d786192f7e, identity PASS laptop + 33308 CPU/CUDA; pilot.yaml 8 opponents at 0.125,
  T_gate 0.1; pod_boot gates: JVM FFI flags + LOOP-IW exact_gate.py (catches a missing flag: 83 libm mismatches);
  the 8x PRO 6000 box may be AVX512 Intel -> the gate runs at boot before any rollout.
- RX-X23 saw intermittent libtorch SIGSEGVs inside JVM processes; LOOP-INT made FastPool restart a dead producer and
  replay its whole share (no half match reaches the learner); injected-crash test was running at the stop.

### 9.3 Engine
- CF-MAIN: `clashbot-main` = 624eeb45 (bec5811a + cfclone x3 + f1fix x2). Passes core 2188/0, SME dev 109/109
  (results sha 15371187 = H2), FRESH1 6/7, Clone sweep 0. **FAILS HF 20k faults: 328 vs 7** - 319 are F1FIX's Rune Giant
  enchant reaching unmodelled paths (Little Prince 117, evo Angry Barbarian 130, hero Bowler 18, maker-left 23).
  Decision: F1FIX-3 (model them with evidence; no lib without F1FIX). HOLD: facade/training/re-drive keep current libs
  until F1FIX-3 passes, then merge + re-gate + ship_main.sh + switch together (fork/MAIN.md, 026afe6).
- F1FIX-3 ticket: branch clashbot-f1fix3 off 624eeb45; gates 1-6 in CRFORGE_S0.md F1FIX-3 STATUS. Heavy runs on 33920/
  33308, NOT 30408 (62 GB container limit; OOM killer fired 67 times today).

### 9.4 Reward (RX-X23 DONE; rx/x23/STATUS.md, rx/out/x23_final.*)
- All 3 variants PASS X2 (no exploit beats CLXIII 63.1%: hold10 6.9, alldef 6.4, nospell 14.0, rocket_tower 12.2,
  xbow_spam 27.4, rocket_tank 42.9, imitation 32.4). Spearman (i) 1.00, (ii) 1.00, (iii) 0.976.
- The review's banking incentive is real but small: (i)'s trade term pays alldef +.21/+.23 vs CLXIII +.003/+.053.
- (iii) potential-based is policy-invariant (discounted, asserted on 15,359 matches); best HF calibration.
- SIM opponents are weaker than live (iu40 elixir destroyed +5.6 at 120 s vs HF +0.2).
- **Lead recommendation sent to the owner: (iii) + terminal R_win, no committed term, no 0.5 cap. OWNER DECISION
  PENDING** before PLAN.md is finalised.

### 9.5 Opponents / scorecard
- P2-SCORE DONE_WITH_CONCERNS (HUMANLIKE.md s7-8, 8e42d4f): card.py scores A-D. E4 and iu40 FAIL by far (B-live RMS d
  0.57/0.67 vs limit 0.10; C-live AUC .979/.985). Owner decisions owed: (1) B-live passes humans only 31/40 at the real
  sample sizes (856 live vs 1,920 SIM) - change the rule (bootstrap-calibrate to the real n so humans pass >= 95%) or
  collect more live reference; (2) C-live limit 0.55 is below the human-halves upper CI 0.610 at 856 matches.
  4 NEEDS_CONTEXT tickets: timing-head SIM decode; HF deck-pair model-vs-model runner; persona fork test;
  predict_live.py. G2 off until e1_eval's follow_ups tap_loss/tap_slow error is fixed.

### 9.6 Final worker states at the stop (supersede the numbers above where they differ)
- **LOOP-INT** (27b0910, pilot/loop/LOOP_INT.md): correctness DONE (16/16, 3 PPO-updating updates identical except lp
  bits). Crash recovery: injected-crash run ends with weights identical to crash-free; 0 real crashes in ~1.5
  producer-h. Clean 33553, one 4090: 4 producers x 256 + LOOP-SRV server = **48.9k matches/h, 0.70 core-s/match
  all-in** (engine 0.25, obs 0.04, decide 0.055, forward wait 0.088); GPU util 57%. Projection: ~160k/h per PRO 6000
  inference GPU; 300k/h needs ~58 cores. NEXT: (1) re-run compare.py in SERVER mode (v_old/wver) - not yet done;
  (2) wire CfMem, CfAbil, loop_opp, CfCtx (APIs landed; B0/pilot.yaml raise NotImplementedError until CfMem is wired);
  (3) learner running alongside + a bench; graphs mode. 33553 = KEEP. stash@{0} (autostash backup of 50 shared-tree
  files) - drop only after GB-DECOY / LOOP-OPS confirm their WIP.
- **LOOP-LRN** (6c4c9b0, pilot/lrn/LRN.md): (iv) stored lp/V DONE, bit-identical weights vs recompute on one update,
  ~1e-8 over 3. Measured 4090: 512 matches/update 49.9 s; 1,024 -> 58.1 s = ~63k matches/h per learner GPU (BELOW the
  210-370k projection; 2,048 likely ~100k/h). 300k/h on the 8x box needs multi-GPU learner (DDP <= 2.2x at 4-way) +
  lazy refine. Decisions open: (a) entropy-guard baseline - 20k-row sample is ~3% off (5 s); lead recommends computing
  it on the rows PPO already visits; (b) lazy_refine (refine on played rows) - weights differ <= 6.4e-6 (batch-size-
  dependent kernels), A/returns/stop step unchanged, 68.5 -> 57.7 s; lead recommends adopting. The stored-mode half of
  the lazy gate was running on 33920 (/workspace/lrn/logs/lazy_gate.log).
- **LOOP-OPS** (90981d8, pilot/ops/README.md): real-fastloop dry run PASS on 33308 (84 artifacts, exact gate, 3 updates
  x 256, exit 0, FINAL u0003 sha dc1d7d39 copied, "DONE, safe to shut down"). Next: pilot.yaml in fastloop once
  MEM/IW/OPP/CTX are wired; re-check checkpoint copy while running. `.foreman/scratch/loop_ops/safe_commit.sh` commits
  only given paths. Dry-run dirs on 33308 deletable.
- **LOOP-IW** (55fe195): DONE. **LOOP-MEM** (20b324f): DONE; Rocket+Tornado combo column never fired (needs a forced
  scenario). **LOOP-CTX** (2542689): DONE. **LOOP-OPP** (8797e07): DONE; opponents' GPU-server path not checked.
- **P3-FORK** (1091bd7, plan1026/cf/STATUS.md): cf_credit landed (off = unchanged, smokes PASS, 23/23 tests); fork cost
  1.67-1.97x match ticks (target <= 1x). Pilot cfpilot1 + trigger audit were RUNNING on 32657 (resumable). Next: pilot
  report (SNR >= 0.5, critic slope 0.7-1.3), tune trigger defaults. 6 pre-existing test failures on clean HEAD
  (test_rl_gae, test_search_s0, test_league).
- **P2-OPP1** (5850d45, plan1026/opp/README.md): heads built (off = bit-identical); 60,102 HF replays re-driven at a
  10-tick grid; pretrain run 2 RUNNING on 33308 GPU1 (PID 96607, step 10k/40k, ~1.8 h left) + level A on run 1 (PID
  112745). Blocked: live opp row builder (step 3), SIM timing-head decoder (step 4 = P2-SCORE NEEDS_CONTEXT (a)).
  Sealed live split opp/live_split.json untouched.
- **P4-10M** (758aecf, scale/v1/P4_10M.md): 10M base pretrain RUNNING on 30408 (step 15k/51k, held-out 6.512 -> 5.825);
  queue continues (icebow fine-tune, evals, curve v1). Re-run queue.sh once after DONE for step 6b. **Latency gate:
  p99 < 100 ms on the RTX 5050 already FAILS at 1.76M (113 ms); forward ~45 ms flat 1.8M-14.7M -> needs the one-forward
  decide, not a smaller model.** 30408 holds ~50 of 62 GB for this run.
- **F1FIX-3** (6f1ea22, CRFORGE_S0.md F1FIX-3 STATUS): fork head ea7f623f on 30408 /workspace/f1fix3/crforge_fork (NOT
  pushed, no remote; re-take the patch from the pod, the laptop copy has CRLF). Little Prince enchant evidenced (2 live
  matches frame-exact; zeroing the enchant diverges at ticks 866/3658). **The other paths (evo Angry Barbarian, hero
  Bowler, hero Elite Archer, evo Musketeer/Archer/Princess, riders, maker-left, Berserker) are plausible but NOT
  evidenced - get evidence (decompiled client logic) before merging.** Still refused: Three Musketeers (~9/17k), hero
  E-Wizard -> expect ~16 HF faults. Gates 1-6 not run. HF gate cannot run on 30408 while P4 holds its memory; a laptop
  tar copy of HF data to 33920 /dev/shm/d1c was ~40% done (may need restart).
- **CF-MAIN** (ba00df9): stopped, holding. **RX-X23** (63965cd): DONE. **P2-SCORE** (8e42d4f): stopped; local data
  humanlike/cache, rows/, data/hf_ref_bec5811a.json.gz (sha256 e981d634) are local-only.

### 9.7 Owner decisions at the stop (10-28 ~12:30)
- **Reward = variant (iii)**: R_win + potential-based P_hat(win) shaping + R_fork; no committed term, no 0.5 cap;
  revisit (ii) only if (iii)'s results point to it. Recorded in PLAN.md P2.
- Owner asked: skip the pilot if the full setup is close. Lead answer: NOT close (see 9.8) -> run the pilot first.

### 9.8 Distance to the pilot and to full training (lead estimate at the stop)
- Pilot remaining: LOOP-INT wires CfMem/CfAbil/loop_opp/CfCtx + compare.py in server mode; learner alongside
  producers + choose matches_per_update / learner GPUs; adopt lazy_refine + entropy-on-visited-rows; pilot.yaml dry run
  on 33308 with the training lib (CF-CLONE; F1FIX not in it - acceptable for the pilot); then ask the owner to rent 8x
  RTX PRO 6000 (needs >= ~100 vCPU; boot gate checks AVX512 exactness).
- Full training remaining: human-like opponents (no model passes the gate; P2-OPP1 steps 3-4 + P2-SCORE's 4 tickets),
  10M base + curve v1, engine fresh gates (FRESH2 ~150 matches, F1FIX-3 with evidence), one-forward decide (latency
  gate fails today), fork-credit tuning (<= 1x cost), multi-GPU learner.
- **GB-DECOY final (809f3f0, 37b552d):** live with --barrel-decoy on since 11:45; --check shows barrel_decoy true; first 3
  matches clean (no evo barrel seen yet). F1 tightened (the two barrels must be created back to back; true for all 52
  live two-barrel casts), F2/F3/F5 fixed; replay unchanged (29/50 -> 43/50; 1,572 plain decisions identical). Backup
  scratchpad/gauntlet/L70/live/LIVE_OPTIONS.pre_gbdecoy_20261028; rollback in gb_decoy/STATUS.md. Owed: measure evo
  answers on post-deploy matches (.foreman/scratch/gb_decoy/newlogs.py). At the stop, every pipeline/ live-path file is
  committed (live runs committed code). stash@{0}/{1} (autostash) kept as backups - safe to drop after a diff check.

### 9.9 Owner decisions, final (10-28 ~12:45)
- **P2-SCORE thresholds (B-live rule and C-live limit): set BOTH from real human data across ALL recorded live matches
  (thousands, not only the 856-match calibration block), weighted toward recent matches (harder opponents at higher
  trophies).** Implementation notes for the worker: (1) calibrate with the SAME weights used for scoring and size the
  bootstrap by the weighted effective n (Kish n_eff), so humans pass >= 95% at the n we actually score with;
  (2) check older matches for reader-version detection differences (pre-merged_sf / pre-160635001) before including
  them, and drop or correct any stat a reader change shifts; (3) keep the sealed D block untouched; (4) pre-register the
  new THRESHOLDS version (sha) before scoring any model, as v4 was. Owner said yes to this; it is a re-calibration
  against human controls, not loosening for a model (E4/iu40 fail by far either way).
- **8x RTX PRO 6000 box: ~32 cores per GPU = up to 256 cores.** At 0.70 core-s/match, 300k/h needs ~58 producer cores,
  so CPU is not the limit on that box. The owner rents it when the lead gives the go-ahead (the pilot is ready per 9.8).
- **The owner switches accounts only after everything is closed out.** At 12:45 every subagent shows completed, no laptop
  copy jobs remain, live runs committed code. Still running on pods by design (no agent attached): P4-10M queue on 30408,
  P2-OPP1 pretrain run 2 + level A on 33308, P3-FORK cfpilot1 + trigger audit on 32657, LOOP-LRN lazy gate on 33920.
  F1FIX-3's laptop tar copy to 33920 /dev/shm/d1c is gone (re-run it from its STATUS).
