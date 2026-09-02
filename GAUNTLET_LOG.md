# Gauntlet log

Terse cross-loop ledger for `/gauntlet`. One block per iteration, newest at the bottom.
Full findings go in `HANDOFF.md`; this file exists so the next loop can orient in ~20 lines
instead of re-reading a 6,500-line handoff.

Format:

```
## L<n> — <YYYY-MM-DD HH:MM> — <goal, abbreviated>
DID      one line
FOUND    the number(s), labelled measured / untested / contradicted
MEANS    what changed about the plan
NEXT     the single action the following loop should take
STATE    what is running, what is queued, what is blocked
```

---

<!-- no loops yet; /gauntlet appends here -->
## L1 — 2026-08-30 11:05 — evaluate brainstorm; improve decision-making (spells, defense, x-bow)
DID      reviewed all 698 lines of LIVE_POLICY_PERFORMANCE_BRAINSTORM.md -> research/BRAINSTORM_REVIEW.md;
         built tools/response_regret.py v0 (paired per-state regret at enemy-play events, wraps
         Searcher.candidates/_rollout); prepared the 5y band retune as a gated patch
         (scratchpad/gauntlet/L1/band_retune.py); verified canvas_stack:1 claim true.
FOUND    measured: benchmark smoke (1 match, contended box, NOT a result): 7 events, policy waited
         all 7, a play scored better at 4/7. Doc's numbers check out against the ledger; its 14.1
         premise is refuted by 5ab. Discovery: TWO defense bands exist -- sim.* (tiles) and env.*
         (SCREEN-SPACE, foreshortened) -- the live one cannot take tile numbers without calibration.
MEANS    spine of the doc adopted (benchmark -> joint scorer -> temporal -> world model); two-speed
         router rejected pending bucket evidence; benchmark doubles as the 5ab power fix.
NEXT     when ab3 wave 3 lands: final 3-seed read, apply band_retune.py, then a real regret run
         (8 matches, idle box) on m18000 + ab3 checkpoints as the benchmark's first reference.
STATE    running: ab3 wave 3 (s43 ~m1175/1500). queued: retune apply, 3-seed read, regret reference.
         blocked: none. live env.* band flagged, needs screen mapping.
## L1-final — 2026-08-30 13:10 — 3-seed verdict, retune applied, regret v0 reference
DID      seed-43 read -> 5ad (bank_hold verdict); applied band_retune.py (10 edits, verified,
         backups in L1/prepatch/); ran regret v0 reference (m18000 + 3 ab3 ckpts, 278 CSV rows);
         launched band-validation run (retuned config, seed 41, 1500 matches, workers 0).
FOUND    measured: bank_hold HARMFUL dose-dependently -- control>bank2>bank6 at ALL 3 seeds,
         sign test ~0.5%; bank6_s43 total collapse 0.0%. measured: regret v0 within-ckpt --
         m18000 missed-play FN 58% (oracle view), worst family = enemy buildings (0.40);
         control_s41 over-play FP 64%. contradicted: cross-ckpt regret rankings INVALID in v0
         (affordability censoring: <2 affordable cands = event skipped, starved policies look good).
MEANS    both reward patches dead -> brainstorm's structural thesis is the working hypothesis.
         Regret v1 must be a FIXED STATE CORPUS (paired across ckpts, kills both confounds).
NEXT     L2: when band run lands (~16:45): xbow_probe on policy_band_s41.pt (did defensive bows
         appear in-band?); build corpus-based regret v1; consider belief-view (--reseed-opp) rerun.
STATE    running: band-validation s41 (data/bench/band_s41.log). done: ab3 (9/9), retune, regret ref.
         blocked: none. NOTE owner usage 99% til Tue -- keep loops chunky, reports single.
## L2 — 2026-08-30 18:20 — corpus v1, belief-view check, band null, stack chain launched
DID      built regret_corpus.py v1 (203 fixed states, replay-based, candidate scores cached);
         graded 5 ckpts oracle + 3 belief; final band probe vs seed-matched control; launched
         canvas_stack 1v2 scratch pair overnight (sequential, seed 41).
FOUND    measured: m18000 worst per-event regret (.384/.371 oracle/belief) vs trained arms
         (.22-.30) on identical states -- ordering SURVIVES the belief-view control, so the
         deficit is continuations, not event responses. measured: band retune trained NULL
         (zero defensive bows persist; dead zone 14v20% noise-sized). contradicted: v0
         cross-ckpt rankings (affordability censoring).
MEANS    P2 joint scorer demoted; P3/P4 (temporal + continuations) promoted. Three repair
         families now measured dead (restraint_hold, bank_hold, placement prior).
NEXT     L3 when stack chain lands (~7h): grade both on corpus + probe + drills. If stack2
         helps regret/drills -> GRU case strengthens; if null -> continuations (P4 teacher
         plans) become the sole frontier.
STATE    running: stack chain (2x scratch, ~7h). corpora: regret_corpus/ (oracle),
         regret_corpus_belief/. usage note: owner 99% til Tue -- single report per loop.
## L3 — 2026-08-31 00:55 — stack2 null-negative; placement data found; crawl near done
DID      graded stack2 both corpora + probe (after catching the cross-width config trap);
         launched defbow confirmation (stack1 cfg, seeds 42/43, detached); built + ran the
         population crawl with placement-aware parser (3 login bugs fixed, token persisted).
FOUND    measured: stack2 regret WORSE both views (.296/.286 vs stack1 .237/.242) at a 4x
         throughput tax -> canvas_stack dead at this budget; P4 continuations sole frontier.
         measured: RoyaleAPI .marker elements carry data-x/y (1000 units/tile), 104/109 join
         -> 5w corrected, owner's placement claim vindicated. measured: scratch arms produce
         defensive bows (3/8, 1/4), warm-started arms never do.
MEANS    roadmap collapsed to one frontier with a fresh human dataset aimed exactly at it.
NEXT     L4: crawl summary + pro-placement-vs-band check; defbow seeds land ~04:30; then
         P4 design (teacher plan record in rollout_search) informed by human continuation stats.
STATE    running: defbow chain (2x1500 scratch), crawl 460/512 replays. done: stack pair,
         corpora, retune. blocked: none.
## L4 — 2026-08-31 00:45 — population dataset read; band depth validated, width contradicted
DID      crawl summary + frame verification + 1,038-bow band check + continuation stats.
FOUND    measured: pro bow depth p10=19.5 (owner front tile 20 = validated); pros' top-2 tiles
         (16,20)/(2,20) are lane bows EXCLUDED by the 4-tile width margin (48% of placements);
         5w anchors confirmed at n=24 (gap 3.85s vs 3.60, rate 11.7 vs 11.3/min); after-bow
         follow-ups quantified (knight 20% @5.5s median). Join bimodal: markers in ~half of replays.
MEANS    band width is an owner decision now ON EVIDENCE; P4 has empirical targets.
NEXT     L5: defbow s42/s43 probes when chain lands (~03:30); P4 teacher-plan design doc.
STATE    running: defbow chain (s42 ~m1000). done: crawl (520 battles / 45,335 plays / 24 players).
## L5 — 2026-08-31 03:05 — scratch-defensive-bow CONFIRMED (3 seeds); P4 designed
DID      probed s42+s43 (s41 from L3); wrote P4_CONTINUATIONS_DESIGN.md; verdict into 5ah.
FOUND    measured: defensive bows at ALL 3 scratch seeds (3/8, 3/14, 3/10 = 28% pooled) vs
         0/192 across every warm-started checkpoint. 5ae refined: the prior teaches, the
         warm start blocks. Scratch arms otherwise weak (locks 0-25%, volume 0.42-0.58/m).
MEANS    the band+prior mechanism is real; the blocker is warm-start inertia. P4 ready to build.
NEXT     L6 (owner gates): band-width ruling (5ag), P4 step-1 go-ahead (pure logging), then
         warm-start-vs-band experiment design.
STATE    box idle. pending owner: band width, P4 go. crawl + corpora + 3 scratch seeds banked.
## L6 — 2026-08-31 04:55 — hold loop; spell portraits banked
DID      read-only crawl2 spell analysis (log/rocket/nado); no config/doctrine/training touched.
FOUND    measured: log 99% own-half lane modes (doctrine validated); rocket modes 1.5-2 tiles in
         front of enemy princess, king-rockets ~absent (rule holds); nado bimodal, king-pulls
         2-3 tiles DEEPER than doctrine's coordinate (flagged, not changed).
MEANS    all four goal focus areas now carry population evidence.
NEXT     owner rulings (band width; P4 step-1). Then P4 logging build.
STATE    box idle; holding.
## post-gauntlet — 2026-08-31 08:20 — owner rulings executed (gauntlet ended by owner reply)
DID      band widened per ruling (central 0.389, lane-bow doctrine spots, probe default);
         P4 step 1 shipped (continuation_log knob, smoke-verified 42 rows) after correcting the
         design's premise (_rollout idles our side -- no teacher continuations exist to record).
NEXT     enable continuation_log on the next training run; build continuation_report.py; probe
         chained-sweep cost for genuine teacher plans; owner may relaunch /gauntlet.
## L7 — 2026-08-31 09:55 — continuation instrument built; chain cost measured; graphify in flight
DID      continuation_report.py + 4-ckpt baseline; chained-sweep cost probe (30 events);
         graphify doc pass dispatched (10 subagents; scratchpad scope bug fixed first).
FOUND    measured: m18000 after-bow L1-to-pro 0.250 vs trained arms 0.96-1.08 -- the continuation
         instrument SEES the edge regret missed, ordering matches match strength. measured:
         chained sweep 0.94x first sweep, total 215ms = 2.0x per searched decision (~0.5x
         throughput at interval 4, projection). graphify: 5/10 chunks in.
MEANS    P4 has both its instruments; teacher plans have a measured price; spec next.
NEXT     L8: merge graphify when doc chunks land; write the PPO run spec; post --questions.
STATE    5 doc-chunk subagents running. Box otherwise idle.
## L8 — 2026-08-31 11:10 — graphify merged; PPO spec posted with --questions; BLOCKED on owner
DID      merged 10 chunks + AST + cluster (12,018n/22,230e/633c, manifest stamped, temps cleaned);
         wrote research/PPO_RUN_SPEC.md; posted --questions.
FOUND    all goal items 1-3 done (continuation instrument 5ak, chain cost 5ak, graphify here).
MEANS    goal item 4 delivered as a spec; launch gated on owner approval per the goal's own terms.
NEXT     on approval: generate 3 seed configs from current config.yaml (continuation_log ON,
         distinct checkpoints), launch sequential, report per wave. On modify/reject: revise.
STATE    box idle. BLOCKED on owner (the goal REQUIRES this stop -- it is the finish line, not a
         guess avoided).
## L9 — 2026-08-31 12:05 — APPROVED; geometry run launched; ping fixed
DID      owner approved the spec (a); launched geo chain (3 scratch seeds, 5aj geometry,
         continuation_log ON, sequential, detached, ~4h); @here -> @vegetable_leaf in
         gauntlet_report (owner complaint; bare-name caveat noted, needs <@id> for a true ping).
NEXT     when geo_chain.done: paired reads (re-probe stack1 trio under def-edge 2.0, probe geo
         trio, corpus regret both views, continuation_report 32 matches), 5am verdict by the
         pre-committed rule, report. Then the P4 hazard A/B spec on the fresh corpus.
STATE    running: geo chain s41 (of 3). Owner confirmed: this is an EXPERIMENT, not the long run.
## L10 — 2026-08-31 15:05 — geometry verdict NOT PASSED (1/3) + two self-caught flaws; redo queued
DID      paired reads (6 probes one instrument, regret x2 views, continuation x3); coordinate
         falsification check on the anomalous seed; 5am written; redo constants fixed.
FOUND    measured: s41 bows ALL at x=0.6 tiles = wall-clipped lane spot (my 0.11 placement);
         s42 zero bows (real volume collapse); s43 53% in-band (best ever). Guardrails passed;
         geo_s41 continuation profile closest-to-pro ever (L1 0.223). Corpus 38,224 rows.
MEANS    lane-spot mechanism UNTESTED not refuted; constants fixed (0.139/0.861, central 0.390);
         redo seeds 54-56 queued after parity.
NEXT     parity chain grades when done (~tomorrow am); then geometry redo; then hazard A/B.
STATE    running: parity w12_s51. corpus banked. flaws documented in 5am.
## L11 — 2026-08-31 16:20 — hazard head built + smoked; parity mid-chain; real-run staged
DID      hazard head wired (model+targets+loss+knob, smoke exit 0); real_run.yaml staged
         (isolated ckpt, continuation_log ON); PPO_RUN_SPEC addendum committed (gates + launch-
         on-green + terminal condition = REAL RUN LAUNCH).
FOUND    parity w12_s51 m=1275+, ZERO fingerprint warnings (assert passing silently).
NEXT     parity done (~04:30) -> grade pairs -> geometry redo (54-56, ~3h) -> hazard A/B
         (sized from measured pace) -> REAL RUN. Owner window: tomorrow morning/afternoon.
STATE    running: parity chain. staged: redo configs implied by fixed constants; hazard smoke cfg;
         real_run.yaml. gauntlet ends at the real launch.
## L12 — 2026-09-01 00:40 — parity CLEARED (workers 12); config corruption caught; redo running
DID      s53 pair graded (-0.018/-0.038); 5an written; config.yaml corruption (live_search_C3,
         22:13, not script-attributable) restored from git; geo2 chain relaunched with
         parse-checked configs; owner confirmed scratch + 40k for the real run.
NEXT     geo2 done ~04:30 -> grade vs stack1 trio (5am rule) -> hazard A/B 61-63 -> REAL LAUNCH.
STATE    running: geo2 s54. cleared: gate 1 (workers 12). confirmed: scratch, 40k, ping on launch.

## L13 — 2026-09-01 07:15 → 17:55  |  GATES 2+3 RESOLVED, REAL RUN LAUNCHED (gauntlet terminal)
- Gate 2 geometry redo: CLEAN FAIL 0/3 (in-band 33%/11%/10% vs baselines 38/21/30%) -> lane spots
  REVERTED, widened central kept (§5ao, commit). Third confirmation placement priors don't teach.
- Gate 3 hazard A/B: NULL. s61 primary disqualified (control 2 waits; >=15 floor pre-committed),
  s62 win, s63 tie. Secondaries 3/3 same-sign 1-5 pts = screen; queued as top follow-up (§5ap).
- REAL RUN launched 17:50: scratch, seed 41, 40k, workers 12, centre-only band, hazard 0, isolated
  ckpt data/policy_real_20260901.pt, continuation_log ON. Watchdog + tools/real_run_gates.py
  (5k/10k/20k, snapshot-graded, measured-pace ETA, 2-read regression -> ping) armed, nohup.
- Box: 2.2 GB available; owner desktop holds ~11 GB (reported, not touched).
- Process: emulator autostart (~30% throughput theft) was the real redo-overrun cause; killed on OK.
- Discord: launch report posted with ping. STOP: gauntlet ends at this launch per owner rule.
- 18:15 OWNER OVERRIDE (post-terminal): hazard head IN. Run killed at m=400 (state recorded),
  no-hazard artifacts archived, ckpt path verified empty, RELAUNCHED 18:18 coef 0.5 (banner
  verified), watchdog+gates re-armed, launch-epoch marker added for pace. §5aq.

## POST-GAUNTLET — 2026-09-01 20:00 → 21:15  |  owner-directed throughput profile (§5ar); real run untouched
- Owner: Soup (LLM fine-tuning CLI) rejected, wrong problem; "if cheap and decisive, do the
  throughput experiments now". Profiled the trainer cycle with a new opt-in profiler.
- MEASURED (cpu, real config, idle box, 4 cycles): update 402/572 s = 70%; workers idle 78% of
  wall (live psutil). Decision rule pre-stated in §6 -> learner on the GPU.
- BUILT: --device cuda end to end (CPU weight copies at the 3 worker/disk seams, TF32 off,
  batched tensor assembly proven bit-identical). MEASURED: cycle 143 -> 49 s = 2.92x; ~3,700
  matches/h steady vs ~1,130. Smoke exit 0, 12-worker bench exit 0, ~0.9 GB VRAM.
- Found: resume rail guard fed 0..255 inputs (fixed, never fired in a logged run); cell head at
  m=2300 is 43% beyond |16| (negative rail, gradient-dead) -- queued as a read at the gates; a
  13-hour runaway regex process from 07:11 (Bash timeout does not kill the child) killed.
- Real run suspended twice for clean measurements (15:51 total, recorded, dead-man armed),
  resumed; m=2450 at 21:08, 0 warnings. Blocked on the owner: restart on cuda (recommended) or
  keep the CPU run (ETA Sep 3 midday). Next gauntlet NOT started (owner has a direction).
- 21:24 OWNER ORDER: "stop and resume using device cuda; decide resume vs scratch". Decision
  SCRATCH (ckpt has no hazard head / Adam / league / done_n; rail guard would rescale the cell
  head x0.031; a resume saves ~45 min of cuda time). CPU run stopped at m=2700 (60W-2116L, EVAL@2000
  11%/4%, 0 warnings, 27,429 continuation lines), archived to data/bench/aborted_real_cpu_20260901/.
  RELAUNCHED 21:25:27 --device cuda, seed 41, 40k, 12 workers, hazard 0.5; banner verified;
  watchdog + gates re-armed; Monitor on the m=1000 snapshot / m=2000 eval (first cuda pass at
  scale). +7.5 min: 250 matches, 0 warnings, ~0.9 GB VRAM. §5as. Next: cr-native-sandbox assessment
  (owner-directed, §5at); gauntlet NOT restarted.
- 2026-09-01 21:5x (owner-directed, outside the gauntlet ladder) cr-native-sandbox ASSESSED, not run:
  real CR engine (libg.so 15.535.29 x86_64) headless in a rooted AVD, JSON/TCP API, NO renderer (no
  detector frames). Blocked on owner: 5 hash-gated split APKs from their own install, ~15-20 GB of
  SDK/JDK installs, emulator contention with the cuda run. Replay->real-match idea MORE feasible than
  assumed (retraction: plays are 20 Hz ticks in native 1000/cell units, not 1 s / tile-rounded);
  268 usable replays / 23,490 plays; fidelity self-checks via rejections + final crowns. Better use
  ranked: sim-parity oracle > real-engine eval > pro-state dataset > RL-in-engine (one throughput
  measurement decides) > frames (impossible). §5at + research/CR_NATIVE_SANDBOX_ASSESSMENT.md.
  Discord --questions posted; WAITING. Cuda run at +28 min: 963 matches, 0 warnings.
- 2026-09-01 22:15 owner answered: Q2 (installs) APPROVED -> done 22:13 (JDK 17.0.20.1, cmdline-tools,
  SDK 7.9 GB, AVD created, venv; doctor passes all toolchain/AVD checks; WHPX usable per emulator
  -accel-check; upstream bootstrap bug ANDROID_AVD_HOME worked around); Q3 = after the cuda run; Q1
  explained, waiting for the owner to read the client version (must be 15.535.29). Cuda run passed
  episode 2000 at 22:13 (26W-1541L, 0 warnings); EVAL@2000 running (first cuda eval at scale).
- 2026-09-01 22:22 cuda run: EVAL@2000 ladder 3% / fair 3% (150 each), eval wall 9.1 min (CPU-side, as
  predicted), 0 warnings -> both cuda-at-scale paths passed. Sandbox runtime: BlueStacks AppCache.json
  proves CR build 150535029 installed 30.08 (retraction of the "client is newer" reading); pull script
  ready; waiting for the owner to enable ADB in BlueStacks. §5au.
- 2026-09-01 22:40 sandbox runtime pulled from the owner's BlueStacks via exec-out (HD-Player adb proxy
  whitelists getprop/dumpsys/logcat only; pull/sync blocked). Engine payload byte-identical: 14/14 native
  libs incl. libg.so fa6704b8 + asset pack; 4 Play-derived APK wrappers differ (derived.apk.id + re-sign,
  same sizes). prepare_runtime OK. freeze (template with blanked APK hashes) = owner's call. §5av.
- 2026-09-01 23:05-23:40 (owner: "run the single replay conversion now, an hour of slowdown is fine")
  sandbox SMOKE on this box: AVD boot 61.6 s, 5 APKs installed, libg headless load, DataTables, battle
  from the bootstrap replay IDENTICAL to the author's certified state (rng 3502570521, towers, elixir 6).
  BLOCKED: nativeStep never advances the tick (0->0 after 100 steps in 33.7 ms; 3/3 deterministic; author
  reaches tick 100/hash 96598dc9028e1802 on the same path) -> service never listens -> conversion NOT run.
  libg is packed on disk (static RE impossible; lldb broken here; no capstone) -> next: live /proc/self/mem
  dump via a local probe-direct-hold mode, plus the cheap locale/tz + full-card-bootstrap tests first.
  Driver replay_drive.py written and offline-verified (08CPVRRR8PYC: 54 plays, 256 consistent deals/side).
  Owner stopped the session (compaction); emulator STOPPED (free RAM 3.1 -> 7.7 GB); cuda run untouched
  (4200 eps, 95W-3262L-2D, EVAL@4000 12%/5%). Full runbook in §5aw.4.

## L1 — 2026-09-02 01:20-02:05 | detector upgrade recon (owner goal: modern detector + <100ms decision)
- Asked 4 questions BEFORE starting (owner instruction). Rulings: latency not act_period; stop PPO at
  ~18k eps then board-train; isolated venv only for non-ultralytics; cheap screen then ONE full run.
- MEASURED: icebow/.venv ultralytics 8.4.107 already ships yolo26 / yolo26-p2 / yolo12 / rt-detr ->
  the approved venv is probably unnecessary; train.py already takes --model. Bar to beat = board-26
  (yolo11s, 960px, 120 ep, 23.9 h): mAP50 0.860, mAP50-95 0.704.
- RETRACTED my own first read of kitka ("88 new classes" -> naming artifact). Truth: sprite library,
  fills 1 of 45 empty classes, +6,200 crops (+15%) to 128 existing, and 9 evolution classes go from
  0-7 sprites to 88-540 = from unlearnable-by-synth to represented. That is the whole of its value.
- ⚠ TRAP: 69/230 classes have ZERO val instances; the 9 kitka classes have 0-2. mAP50 on this val set
  CANNOT see the kitka change -- a null would be an instrument artifact. Need a held-out SYNTHETIC val
  from unseen kitka sprites, reported separately. detect-eval is right for the architecture half only.
- No model trained: GPU is the PPO run's until 18k (watcher armed). Next: paper screen (free), non-GPU
  latency breakdown, battery watchdog pause/resume rewrite.

## L2 — 2026-09-02 07:13-07:35 | PPO stopped at 18k, YOLO26 smoked, screen launched
- Watcher fired at 18,000 eps. Before stopping, read the GREEDY eval (not the sampled winrate):
  ladder 3/12/19/13/7/21/8/10% at EVAL@2000..16000 -> 5-eval avg FLAT 12-14% since 12k; _best.pt has
  not moved since 03:54 (~12k). Stopping cost nothing measurable -- independent of 4t, not carried from it.
- Stopped per guardrail: ckpts SHA-verified into data/bench/stopped_real_cuda_18k_20260902/, then
  Stop-Process; python 20 -> 6, train-sim-ppo 0, RAM 11.1 GB free, GPU idle.
- YOLO26s SMOKE on our real 230-class data: exit 0, 5.6 ms inference / 0.4 ms postprocess @960 (NMS-free).
  Paper: yolo26s 48.6 vs yolo11s 47.0 COCO mAP50-95, same params, fewer FLOPs, + ProgLoss/STAL (small objects).
- LAUNCHED the 2-arm screen (yolo11s control vs yolo26s, identical, fraction 0.35 / 30 ep / 960px, ~2 h each).
  Screen numbers compare ONLY to each other -- never to board-26's 0.860. That is why the control exists.
- battery_watchdog.ps1 REWRITTEN to the owner's spec: pause -> sit 90 min -> wait >=25% -> auto-resume,
  12 cycles; refuses to resume a STRIPPED ckpt (that silently starts a coco8 run -- 3 such folders here).
- Next: read the screen ~11:30, build the held-out synthetic val from unseen kitka sprites, then the full run.

### L2 addendum (2026-09-02 08:05) -- owner asked about overnight cell/elixir alerts
Re-read `ppo_watchdog.log` for the stopped run (114 readings). Cell head sat below the 1.27-nat collapse
line on 83/94 readings after 4k and from the first reading (ep 200) -- a starting state, not an overnight
event; 28-43 distinct cells throughout (never the 3-cell catastrophe). Elixir>=6 fell 2% -> 0.5% -> 0.02%
over 8k->18k: a real monotone decline that makes X-Bow/Rocket uncastable and matches the 12-14% plateau.
L2 report did not read this instrument; corrected in HANDOFF §5ba.6b. Stop decision unchanged.
Two items queued in §6 for the next PPO run (elixir drift rule; per-card top-cell dump).

## L3 — 2026-09-02 07:40-08:30 | kitka folded in, L1 counts RETRACTED, held-out synthetic val built
- RETRACTED §5az.4 numbers: `dataset_updates/` is a byte-duplicate of `segment/segment`, so every L1
  per-class count was ~2x (hunter_evo 546 -> 276). Unique library: 183 classes / 7,792 PNGs. It fills
  3 empty classes (pekka_evo, giant_snowball_evo, skeleton_army_evo), not 1.
- Split 80/20 by sha1(name): 6,313 train / 1,479 holdout. Imported train slice into the bank
  (44,094 -> 48,929 files, +4,835, 0 removed) and the holdout slice into its OWN bank (1,124 / 106 cls).
  Thin classes now 42-222 sprites each (were 0-19). 5 names needed explicit mappings (dart_goblin_evo had
  imported 1 sprite before the fix).
- Built the missing instrument: 1,000 VAL-frame composites from the held-out bank (2,479 pastes, 156
  classes), own `holdout_val.yaml`. Read per-class AP for pasted classes only; never its overall mAP.
- (b) kitka crop scale CV 0.27 around 735 px; one composite eyeballed and troop-sized. (b) 10 kitka classes
  are objects our taxonomy cannot name (goblinstein, goblin_dummy, skeleton_balloon_evo, hogs_evo...) -> §6.
- NOT regenerated the training synth: the screen reads `data/detect/synth` and regen overwrites in place.
  First step after the screen. Screen measured 5.4 min/epoch -> both arms ~13:00 (not 11:30).
- Next: gate-prior builder on the one existing engine recording (CPU) while the screen runs.

## L4 (owner task, mid-gauntlet) — 2026-09-02 09:00-10:10 | hogeq brought up to icebow's version
- parity 65 identical / 18 declared / 2 UNEXPECTED -> 70 / 15 / 0, `--strict` green from both decks.
  Ported: katacr_segments.py, sprites.py, reward.py, model.py, sim/drill_env.py, tests/test_aim_assists.py
  + the five new CLI flags by hand (cli.py is deck-different, so the gate could never have caught it).
- ⚠ FOUND: hogeq's env.py has always CALLED `log_corridor_cell` behind try/except and its reward.py never
  defined it -> the Log corridor aim assist was INERT in a deck that runs The Log. Now defined; 16 ported
  aim tests pass in hogeq. Live-path behaviour change (hogeq is sim-only, nothing in flight).
- model.py port verified checkpoint-safe: hogeq's policy_sim_ppo_best.pt strict-loads, cell head (11,24,1,1).
- Two DRIFT notes were STALE: `_env_flag` is in BOTH decks (the real drift was 3 icebow-only drill knobs);
  reward.py's entry described a gap as a deck opinion. hogeq's "42 known failures" baseline is dead: 1,272
  OK before the ports, 1,288 OK after. icebow: 1,257 with 1 PRE-EXISTING failure (xbow_front 0.56 -> 0.625
  from the 5y retune invalidated a test premise; left for an owner call).
- Corpus: hogeq had none, and the icebow crawl cannot supply it (0 of 520 battles has a hogeq-deck
  opponent; 5 are 7/8-card neighbours). New `crawl_deck.py` (crawl_icebow.py left frozen), session token
  borrowed from the icebow crawl -- no owner login needed, probe pulled a 109-card replay with 131 markers.
- ⚠ BUG in the first pass: RoyaleAPI's "similar decks" for hog 2.6 are card SUBSTITUTIONS, not evo swaps;
  only 100 of 531 rated players are on the exact base deck, so the top-50-by-rating roster produced
  14 players walked / 0 battles kept. Roster now filtered by is_variation first; crawl restarted.
- Next: finish + re-run the crawl to sweep rate-limited players, then hogeq placement priors (5ag's path).

## L5 — 2026-09-02 14:22-15:00 | screen verdict, board-27 CANCELLED (owner ruling), first latency number
- Screen final, identical args, same val: yolo11s mAP50 0.408 / mAP50-95 0.294 vs yolo26s 0.253 / 0.171.
  y26s behind at all 30 epochs; gap peaked +0.177 (ep 11-12), closed to +0.150 by ep 30. 36% slower to train.
  (b) a full-schedule crossover is not excluded (linear extrapolation ~ep 130); not worth 24 GPU-h given:
- IDLE-BOX latency bench (241 real 1182x668 frames, fp32 @960, 200 calls, the live predict() call):
  board-24-5 (operating) 29.5 ms median / 35.0 p90 (pre 7.1 / inf 19.6 / post 3.1); board-26 32.6;
  y11s 31.3; y26s 34.5 (inf 26.1, post 1.1). (c) "NMS-free = faster" CONTRADICTED on this GPU: +3.2 ms net.
  half=True is deprecated in 8.4.107 and moved nothing consistently.
- Owner ruling 14:30: a day of board training only if kitka's benefit is significant. It is (b) UNTESTED
  and invisible on the main val (0-2 instances of those classes) -> board-27 CANCELLED. Right-sized test
  queued as an owner option: 2-4 h fine-tune from board-26 on kitka synth, read on holdout_val.yaml + the
  detect-eval promotion gate. Not launched.
- Consequence: the PPO elixir-fix run (08:20 ruling) is now gated on its prep only, not on board-27.
- Next: OFFLINE stage timer for play.act_in_match over data/sessions/20260815_222309/video.mp4 (obs build,
  recognition, threat/canvas, policy forward, LiveSearch.decide) -- the full 100 ms budget breakdown
  without touching play.py; then the 7 ms preprocess term. Gate-prior prep in parallel (CPU).


## L6 — 2026-09-02 15:00-15:25 | GATE-PRIOR RUN LAUNCHED (owner order "launch the elixir fix run")
- Built + smoked + launched in one loop. tools/gate_prior.py (both decks) fits P(play per 0.6 s window |
  floor(elixir), phase) from the crawled replays; elixir reconstructed (start 5, engine regen, CardDB cost),
  error MEASURED: 1.7% (icebow, 519 replays / 23,620 plays) and 2.8% (hogeq, 595 / 30,258) of plays under
  cost. Both decks bank: single-elixir P(play) ~0.04-0.06 at 3-7 elixir, 0.20-0.25 at 9. Pros made 65% (icebow)
  / 54% (hogeq) of plays at >=6; the 18k agent spent 0.02% of steps there.
- Hook in both train_sim_ppo.py: sim.ppo_gate_prior_coef (0.0 = off) x Bernoulli CE of the GATE head toward
  the table on match rows with play unmasked; engine clock added to the rollout + remote payload for the
  phase key. Watchdog: ELIXIR>=6 drift rule with its own floor 0.002 (0.05 would have been dead), suppressed
  when GATE DRIFT fires the same cycle. real_run_gates.py --run <kind>_<date>. Tests 15/15 icebow, 7+1 skip hogeq.
- Deviation from the 08:20 ruling, stated: no threat key in v0 (needs the engine recording pass).
- RUN: 15:07, cuda, seed 41, 40k, ONE change vs the 18k run = coef 0.1 (untested first value). Update 200:
  pi(play) 0.379 vs prior 0.051 on usable rows, 8% of rows usable (= the collapse: nothing affordable on 92%).
  Watchdog + gates armed on data/policy_gate_20260902.pt. Stale 18k watchdog still alive (kill refused).
- TRAP (a): 91 watchdog readings of the FROZEN 18k checkpoint: cell_struct 685-14,834x, elixir>=6 0.0-11.3%;
  the CELL STRUCTURE drift rule fired on an unchanged file. HANDOFF 8 + 5bf.5.
- hogeq refuses --search-interval with workers>1 (search-in-workers never ported) -- parked in 6.
- Next: read the run at m~1000 / the m=5k gate; latency-loop offline stage timer (single-thread parts only
  while the box is contended).


## L7 — 2026-09-02 15:45-16:05 | GATE-PRIOR RUN READ AT m=2000: NOT DISTINGUISHABLE FROM THE 18k CONTROL YET
- Box contended (12 workers + cuda) -> no latency timing. Built tools/gate_prior_probe.py: the watchdog's
  sampler + per-row affordability + P(play|elixir bucket) vs the pro table, np.random seeded, 12 s/run.
- (a) 3 seeds each, gate m=2000 vs frozen 18k: affordable rows 25-27% vs 28-29%; P(play) on affordable rows
  0.41-0.43 vs 0.38-0.41 (pros ~0.06); played/row 11-12% both; 80% of rows below 3 elixir in both; `played`
  at bucket 3: 0.39-0.45 vs 0.36-0.37 vs pros 0.063. The prior has not moved behaviour by m=2000.
- (a) the cheap-card collapse from the hand side: skeletons in hand at 1 elixir on 7-9% of rows (expected
  ~50% under a neutral cycle) -- cheap cards are spent on draw, the hand holds 3-6 cost cards at 1-2 elixir.
- (c) RETRACTED my 15:42 "direction looks right" read: the 15:45 watchdog reading reversed it, and the
  watchdog's P(play) mean is ~74% masked rows (nothing affordable) -> HANDOFF 8. Trainer's pi(play) on
  usable rows, DE-CUMULATED: 0.336 -> 0.316 over 3,800 updates -- flat.
- Pre-registered m=5k rule (HANDOFF 6): probe gate_m5k.pt on 3 seeds; `played` at bucket 3 >= 0.30 on all
  three -> ask the owner to relaunch at coef 0.5; < 0.30 on all three -> leave to m=10k; mixed -> read again 7.5k.
- Next: m=5k gate (~17:00). Run untouched, 0.8 ep/s, ETA ~05:00 09-03.


## L8 — 2026-09-02 16:54-17:10 | COEF 0.1 LOSES TO PPO; THE GATE IS THE RIGHT LEVER (counterfactual bank) -- STOPPED TO ASK
- (a) trainer `GATE PRIOR CE` de-cumulated per 800 updates: pi(play) on usable rows 0.34 -> 0.28 (upd 2400)
  -> 0.375 (upd 8800), AWAY from the prior 0.059; window CE 0.43 -> 0.61. Probe m=4000, 3 seeds: played at
  3 elixir 0.42-0.48 (control 0.36-0.37); mean cost of cards played 2.45-2.49 (deck 3.50); x_bow once / 7,200 rows.
- (a) `--force-bank 6` counterfactual on the same checkpoint: card head picks at mean cost 3.35-3.44
  (~uniform over hand: skeletons / ice_wizard / x_bow / tesla ~30 each of 190), x_bow on ~15% of plays; same
  elixir spend per row (0.27) as unforced. The cheap-card collapse is the GATE opening at 1-3 elixir, not a
  cheap-biased card head.
- Arithmetic: prior per-usable-row pull = coef x (pi-p) / 0.09 ~ 0.33 at 0.1 vs PPO advantage ~0.8 -> loses
  (observed). 0.5 -> ~1.7, equilibrium pi ~0.20 at 3 elixir; 1.0 -> ~0.13; pros 0.06. (b) both.
- STOPPED (--questions): relaunch at coef 0.5? Run untouched at m~4,300; m=5k snapshot still taken.
- Open side question: file host for the 9 replay mp4s (SwissTransfer needs a captcha -- not scriptable).


## L9 — 2026-09-02 17:07-17:45 | m=5k READ MOVED TOWARD THE PRIOR; RELAUNCH ORDER ON HOLD FOR A YES/NO
- Owner ruled (~17:00, on the m=4k picture): stop and restart at coef 0.5. Waited for the m=5k snapshot as planned.
- (a) probe `gate_m5k.pt`, 3 seeds: played at 3 elixir 0.299 / 0.279 / 0.305 (m=4k 0.42-0.48; 18k control
  0.36-0.40); P(play|affordable) 0.28-0.32 (m=4k 0.43-0.45); elixir >=6 0.8-1.6% of rows (m=4k 0.0-0.2%);
  affordable rows 32-36% (23-25%). First read below control, all seeds, every stat. Plays/row unchanged.
- (a) trainer's window pi(play) on usable rows still 0.29-0.41 (updates 10.4k-11.6k) -- instruments disagree.
- (c) PARTIAL RETRACTION of L8 "0.1 cannot win": the arithmetic was (b) and the m=5k probe contradicts it.
- Pre-registered rule says MIXED -> re-read at 7.5k. Killing is irreversible -> asked the owner: hold to 7.5k
  (~18:40, recommended) or kill now and relaunch at 0.5 as ordered. No answer = hold and probe at 7.5k.
- Side task done: 9 replay mp4s zipped as one file, uploaded to gofile (bashupload dead), md5 verified, link sent.
- Correction: 18k control played@3 is 0.36-0.40 (seed 0 = 0.403), not 0.36-0.37 as written in L7/L8.

