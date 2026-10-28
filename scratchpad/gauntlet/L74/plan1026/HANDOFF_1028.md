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
