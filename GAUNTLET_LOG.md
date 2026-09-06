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


## L10 — 2026-09-02 18:54-19:10 | m=7.5k = OSCILLATION; coef-0.1 run killed at 7,575, coef-0.5 run launched 18:59
- Owner 17:50: hold to 18:40 to tell genuine improvement from oscillation. Rule: >=0.30 all seeds -> relaunch.
- (a) probe live ckpt at m=7,500, 3 seeds: played at 3 elixir 0.376 / 0.301 / 0.401 (m=5k 0.28-0.31; control
  0.36-0.40); P(play|affordable) 0.34-0.39 (m=5k 0.28-0.32); elixir >=6 0.5-1.0%. Bounced back -> oscillation.
- (a) trainer's window pi(play) on usable rows per 1,000 updates: flat 0.34-0.37 over 16,800 updates, CE never fell.
- Verdict: coef 0.1 exerted no sustained pull (L8 claim stands; L9's partial retraction was the oscillation).
- Killed PID 29460 tree at 18:57 (procs 2 -> 0, exit=1 logged), endpoint in HANDOFF §3. Launched
  gate05_run_launch.sh 18:59: `GATE PRIOR ON: coef 0.500`, ONE change vs the killed run. Watchdog + gates re-armed.
- Watch item: free RAM 0.6-1.1 GB at startup (workers 560 MB each). Re-check at m=2k.
- Next: coef-0.5 m=2k probe (~20:10 at 0.5 ep/s), pre-registered: <=0.25 all seeds = biting; >=0.35 all = ask.



## L11 — 2026-09-02 19:20-20:25 | coef 0.5 BITES at m=2k; PPO push climbing back in trainer windows; level-16 answered; stale watchdog killed
- (a) probe gate05_m2k.pt, 3 seeds: played at 3 elixir 0.271 / 0.227 / 0.239 (coef-0.1 m=2k 0.39-0.45; control
  0.36-0.40; pros 0.063). P(play|affordable) 0.227-0.233 (coef-0.1 0.43-0.45); elixir >=6 3.0-4.0% (0.0-0.2%).
  Rule: <=0.25 all seeds missed by 0.021 on seed 0; >=0.35 ask-branch far away. Verdict: biting (direction, 3 seeds).
- (a) trainer window pi(play) per 200 updates: 0.34 -> 0.22 by update 2,000, then back to 0.24-0.29 through 5,600,
  CE 0.35 -> 0.42-0.44. First coef that moved the trainer's own gate; PPO pushing back. m=5k decides equilibrium.
- (a) m=2k same seed: avg_rew -18.2 (coef 0.1 -15.2; 18k -13.4); EVAL@2000 5%/2% (n=150, noise). Coef 0.5 worst on
  reward, (b) banking cost vs simply worse -- unresolved.
- Side: level-16 sandbox writeup (scratchpad/gauntlet/L11/level16-research.md; (c) HANDOFF:5737 retracted); stale
  18k watchdog killed; owner's decision-time question answered with a counter-question (act_period vs latency).
- Trap: two-threshold rule (0.25/0.35) left a dead zone; probe spread at fixed ckpt is ~0.04-0.05. One threshold next.
- Box 20:08: run at 2,550 eps, 0.62 ep/s, 4.2 GB free. Next: m=5k read (~21:15-21:30), ask-branch = >=0.35 all seeds.


## L12 — 2026-09-02 20:30-20:55 | owner order: stage timer + agent_dt weighing. RETRACTION: decision path was measured all along
- (c) "act_in_match / decision path unmeasured" (§5be, §6, my 20:0x reply): env.py has timed every stage of every
  decision since 08-12 (`cadence` dict in data/reward_stats/live_*.jsonl, 904 matches; `[cadence]` print). Nobody read it.
- (a) act_period-0.6 era, 100 matches / 38 sessions since 08-20, per-match means: loop p10 0.664 p50 0.760 p90 0.898 s;
  wait 0.123; env sum 0.343 (reads 0.131, act 0.058, state 0.056, threat 0.053, grab 0.035, hand 0.012, obs 0.003);
  trainer residual p50 0.315 (p10 0.08, p90 0.45); pipeline (loop-wait) p50 0.646. 91/100 matches loop>0.66.
  => trained at 0.6, served at 0.76 (27% mismatch, the 08-12 bug class). Box load per session unrecorded (caveat on
  the split, not on ">0.6": the p10 match is already over).
- (a) pros: 43,205 consecutive same-side gaps, 519 replays: <0.6 s 1.4%, <1 s 3.6%, <2 s 18%, p50 4.15 s.
- Built icebow/tools/latency_stage_timer.py (offline, real Vision/trackers/detector/net, no live-path edits). Smoke
  on the CONTENDED box (40 frames, upper bounds): detect_state 86 ms, detector 80, threat colour 62, tower-HP OCR
  22 p50/348 p90, elixir 15, mass 10, hand 5, observe 4; net fwd b1 1.6 ms, DDQN learn step b64 21 ms (cuda).
  => the 0.3 s trainer residual is NOT the net; (b) live search (on since a410de6 08-29) / doctrine / contention.
- Weighing (owner delegated): lower agent_dt buys 1.4% of pro combos + (b) placement timing, nothing on reaction
  (event wake already exists; reaction is pipeline-bound ~0.5 s). Costs: sim retrain, gamma retune, gate prior
  tables per dt, halved sim throughput, and it cannot be served (pipeline 0.65 > 0.6 today).
  VERDICT: do not lower agent_dt; make serving honest at 0.6 first (residual split, detect_state at 2 Hz, OCR p90).
- Repro (cadence): python over live_*.jsonl, sessions >= 20260820_093600, matches with cadence.n>=50, per-match means
  of cad[k]/n, percentiles across matches. Repro (pros): plays_ext.csv, sort by (battle, side, t), diff t, drop abilities.
- Trap: an instrument that writes to a JSONL nobody greps does not exist (§8 entry added).
- Files: tools/latency_stage_timer.py; scratchpad/gauntlet/L12/stage_timer_smoke_{,net_}contended.json. HANDOFF §5bl.
- Box 20:25: run untouched (gate05, watchdog + gates alive). Next: 21:11 wakeup = m=5k read; idle-box timer run parked.


## L13 — 2026-09-02 20:30-20:55 | owner reports tested: X-Bow at dead tower; spell whiffs; ROCKET NEVER CAST in sim
- (c) "model doesn't know which cells target which tower": tower HP in obs since 08-10; live dead-lane assist since
  08-16 (reward.py:319); sim reward alive-only. (a) today: 6/6 bows at cell 243, raw==assisted; after took_tower
  `_defensive` flips and env.py:1823 SKIPS all bow assists -> unassisted constant cell, billed -1 for depth.
  (a) `_wincon_exec_live` ignores tower alive (sim checks). (c) crawl has no tower-death events.
- (a) sim probe, greedy no-mask, 36 matches/ckpt: m2k 168 spells, 0-dmg 11%, mask-whiff 11%, nado_bad 19%;
  18k 496 spells, 0-dmg 9%, mask-whiff 21%, nado_bad 13%. Rocket 0 casts on BOTH (pros 3.4%). Live today
  spell_waste 25/54 spell plays (other instrument). Mask at ~86% in training -> (b) policy never learned aim.
- Proposed (owner call): env.py:1823 run defensive bow snap when _defensive; env.py:1574 alive-only anchors.
- Files: scratchpad/gauntlet/L13/{spell_xbow_probe.py,probe_gate05_m2k.*,probe_18k.*}. HANDOFF §5bm.
- Run untouched. Next: 21:11 wakeup = m=5k read.


## L14 — 2026-09-02 20:55-21:10 | owner ruling on X-Bow defensive doctrine: verified vs pros, APPLIED to live env.py
- (a) pro blue bows n=1,029: front share 93% (0-30 s) / 82% / 63% (2x) / 54% (OT) / 48% (3x OT); 122/255 replays
  switch front->back, 70 of them in 2x. Late bows: 54% front when the pro took a crown vs 62% at 0 crowns ->
  time gate = real soft preference; tower gate = no support (and §5bm measured it harmful).
- (a) env.py edits (owner-authorised): tower-gated `_defensive` flip removed (OT+chip only); defensive bow snap
  also when `_defensive`; `_wincon_exec_live` anchors alive-only. 56/57 tests, the failure PRE-EXISTING (stash-verified).
- NOT done: sim twin (sim/env.py:3149, run live -> §6); OT snap hard vs soft = owner call (flag: overrides ~54% of pro OT bows).
- (b) edits unexercised live. Files: scratchpad/gauntlet/L14/pro_bow_timing.{py,txt}. HANDOFF §5bn.
- Run untouched. Next: 21:11 wakeup = m=5k read.


## L14b — 2026-09-02 21:10-21:30 | owner steering: OT flip -> SOFT RAMP; agent_dt verdict pinned in HANDOFF §6
- (a) live env: `_defensive_w` = clamp(s into OT / `env.xbow_defense_ramp_s` 60) while chip < success_frac, else 0;
  blends the bow reward, scales rocket-cycle credit, is the snap probability. `_defensive` = property (w>=1).
  `clock.overtime_s` added. 5 new tests; 130/131 (the 1 pre-existing). Unexercised live (b).
- HANDOFF §6 PRIORITY-C: agent_dt verdict (§5bl.6) with the order of work, so it is not lost.
- Run untouched. Next: 21:11 wakeup fired? -> m=5k read.


## L15 — 2026-09-02 21:15-21:20 | m=5k wakeup landed early (4,425 eps, 0.5 ep/s); no pre-registered read
- (a) watchdog @4000, both arms: same CELL-COLLAPSE (ent 1.07 vs 1.06 /5.08) and ELIXIR>=6 alerts -> recipe, not coef.
  P(play) 0.26 vs 0.48, card_ent 1.18 vs 1.82 (coef-0.5 vs 0.1): (b), single sampled readings, not the probe.
- Trainer EVAL @4000: coef-0.5 13%/10%, coef-0.1 8%/4% -- winrate, logged only.
- Trap: ETA from one rate reading; next wakeup paced on the snapshot file. Next: 21:41 = m=5k read (rule §3).


## L16 — 2026-09-02 21:20-22:10 | FINAL loop (owner order): spell niches; nado_retarget unreachable; m=5k read; gauntlet STOPPED
- (a) pro reference (6,804 icebow-side casts): log 87% own bridge side; rocket 81% enemy half/tower zone; tornado spread,
  19% own back/king zone. Class of the preceding enemy play only mildly separates the spells; the crawl has no unit
  positions, so "what the spell covered" is sim-only.
- (a) sim, 3 ckpts x 3 seeds x 12 matches, engine truth: LOG zone pro-like (72-85% own bridge) but covers nothing on
  18-26% of casts, kills on 25-37%; TORNADO king activation 0/1/4 per 36 matches (king asleep at 43-54% of casts),
  2-14% cast near our king vs pros 19%; clump set up 7-19x, rocket never cashes it; ROCKET 1 cast / 108 matches.
- (c) `nado_retarget` has NEVER been payable: gate centre-dist <= reach+1.0 (1.8 for hog) vs measured attack distance
  2.20 (hog) / 2.10 / 2.68 / 2.68 -- engine reach is a gap. Fix queued §6 (one change, after the run).
- Retracted before recording: my first pass read "0 clump/combo/king/retarget" from ledger keys that do not exist.
- (a) m=5k read: played@3 0.281/0.269/0.315 -> mixed, not the ask branch; == coef-0.1's own 5k (0.28-0.31). Run continues.
- HANDOFF §6: agent_dt DEFERRED, YOLOv26 NO-GO (owner). Gauntlet stopped on owner order; new gauntlet next.
- Files: scratchpad/gauntlet/L16/*. HANDOFF §5bq. Run untouched (2 trainer PIDs before and after).


## L17 — 2026-09-02 22:10-22:30 | AGGRO gauntlet loop 1: the obs predictor vs the engine's sticky lock
- Premise corrected: aggro IS modelled (interactions.predict_targets -> interaction vector + predictive canvas), memoryless.
- (a) vs engine Unit.target, m5k ckpt, 36 matches x 3 seeds, 60,599 unit-samples: walking 96/93% agree, LOCKED 81%
  (n=14,268; 1,041 = tower-hitter shown turning to a nearby troop), buildings 25/16%, deploying 0%. Engine target
  changes 14.4/unit-min, 47% with the old target alive.
- (a) wiki rules (KTA on damage only + 4 s; nado/log/stun retarget; X-Bow 3.5 s deploy, air can't distract) match the engine.
- Next: aggro ORACLE over an engine fork (new module + tests; unblocked). Run untouched (5,975 eps). HANDOFF §5br.


## L18 — 2026-09-02 22:20-22:30 | AGGRO gauntlet loop 2: engine-backed aggro oracle + tests
- Built `sim/aggro_oracle.py` (fork engine, advance, read Unit.target back; no re-derived rules) + 8 tests = the owner's questions.
- (a) X-Bow vs Valkyrie: knight steals the lock if placed <= 1.6 s, fails from 1.8 s = her first hit; valk kills bow then
  princess after 7.9 s; valk beats knight 26% HP, mini-PEKKA beats knight 56.5%. Hog on princess + reference tornado -> KING.
- (a) cost: fork 0.5 ms, question 2-3 ms, 31-fork window 83 ms (6-unit board).
- (b) flagged: engine resets a lock when a body spawns on the locked unit; no 4 s king aim delay. Run untouched (6,000 eps). HANDOFF §5bs.


## L19 — 2026-09-02 22:45-23:00 | AGGRO gauntlet loop 3: do the existing aggro drills grade aggro? (c) no
- (a) knight_guards_the_bow: success = bow alive AND knight played -> passes the step ANY knight lands (bow dies 7-8 s);
  cell/timing ungraded. Oracle: the knight takes the lock on 23/760 cell x delay combos (river line, <= 1.8 s).
- (a) nado_the_sneaky_lock, 40 reps ladder roll: reference 47.5%, knight-only 60%, nado-only 0%, knight-in-front-no-nado 80%.
  The bow never re-locks a tower after the reference pull (2 tiles vs 11.5 reach) -> notes (c). L16 enemies: 5% for every line.
- (a) trap: `cli drills --level 11` pins the ENEMY only; our bow is L16 -> "nothing 100%". Use ladder or pin 14-16.
- Next: `sim/aggro_drills.py` with lock-state predicates (tank_for_bow, bow_first_lock). Run untouched (6,950 eps). HANDOFF §5bt.


## L20 — 2026-09-02 23:05-23:45 | AGGRO gauntlet loop 4: `sim/aggro_drills.py` -- drills graded on the engine's lock state
- Built `tank_for_bow` (success = the valk's `target` becomes our knight; failure = her first hit on the bow) and `bow_lane_choice`
  (success = the bow's FIRST lock after deploy is a tower; failure = a troop) + 4 tests. Explicit `register_all()`, not auto-imported.
- (a) 40 reps ladder: nothing 0/0, scripted 92/95 (L16 pinned 98/98), knight @4.2 s 0%, far-lane knight 0%, same-lane bow 0%, doctrine 95/90.
  Knight BEHIND the bow still 88% (he walks past it) -> the drill grades lane + timing, not the row.
- (a) traps: first legal agent row is y 0.5625 (L19's river-line cells were unreachable -> scripted 0% until the bow moved to 0.60);
  drill noise lands in the answer's lane (reference 68% with noise) -> `setup` strips it; a Scenario `noise` field waits for the stop.
- (a) trained policies, greedy masked, 40 reps: gate05 m5k 12% / 0% (tank / lane), pre-run policy_sim_ppo 15% / 35%; doctrine 95 / 90.
  "No concept of aggro" is measured for these two questions. nado_king_activation 0% for every policy, doctrine 5%.
- Run untouched (7,825 eps). HANDOFF §5bu.


## L21 — 2026-09-03 00:55-01:15 | AGGRO gauntlet loop 5: m10k read TRIPS the owner's rule; coef-0.5 run STOPPED
- (a) greedy bucket probe, 3 seeds, m10k: elixir>=6 share 0.1 / 0.2 / 0.0% (m5k 1.2/1.3/1.0, m2k 4.0/3.5/3.0); P(play|affordable)
  0.36/0.35/0.38 (m5k 0.28-0.30); elixir mean 2.09; x-bow plays 1/2/0 per 2,400 rows; played cost still 2.50-2.53. Median 0.1% < 1% -> stop.
- (a) stopped per ruling: state recorded (10,000 eps, 356W-7653L-10D, best_wr 11.338, gate m10k regret 0.2418/0.2395), ckpt
  backed up cmp-verified, watchdog stopped first, procs 2 -> 0, ckpt unchanged. Box idle (7.6 GB free).
- (a) diagnosis cut 1, trainer's own instrument (237 blocks): post-clip gate pressure toward PLAY 199/237 (mean +0.25), unclipped
  zero-mean (-0.05, 124/237 positive); clip rate PLAY 0.77 vs WAIT 0.01. = the KNOWN clip sign-flip, present all run at coef 0.5.
  The gate drifted +0.04 P(play|choice); >=6 share is its geometric tail (b). clip_play_mult history = null on winrate/reward at
  700 matches, which cannot see a 2k->10k drift; repair (b) until graded on the bucket probe.
- Next: L22 pick the repair with one measurement, implement behind a flag, unit test; then TEST RUN; aggro wiring behind a flag; restart. HANDOFF §5bv.


## L22 — 2026-09-03 01:08-02:05 | AGGRO gauntlet loop 6: diagnosis cut 2 -- repair chosen (pressure-conditioned prior)
- RETRACTED L21's "unclipped gate pressure is zero-mean" (heavy-tailed block sums). ADV BY ACTION, 11.6M samples: play +0.211 vs
  wait -0.008 -- the PLAY bias is in the advantages.
- (a) per-term ledger, 24 matches x 3 seeds, m2k/m5k/m10k, two instruments: the 2k->10k reward gain is the wait-side penalty
  vanishing (sampled threat_miss_idle -2.20 -> -1.11; greedy wait-side -6.5 -> -0.26); x-bow terms flat (sampled) or falling
  (greedy exec 2.24 -> 0.62 m5k->m10k, total +2.96 -> +0.93). Greedy m2k is a HOARDER (>=6 29.9%, leak -3.8) -- instrument-dependent.
- (a) the shipped prior is board-blind; refit with "enemy troop played < 6 s ago" from plays_ext.csv: pro P(play) at 5/6/7
  elixir 0.024/0.030/0.029 quiet vs 0.086/0.068/0.066 pressured (2.3-3.6x, n 3k-10k/cell); pressure on 37% of pro windows.
- (a) sim opponent, same key, single elixir: pressure 46-52% of steps, quiet median 4.8-5.4 s, bank-length stretches 10-16%
  vs pros 37% / 9.0 s / 39%. ~1 bankable window per phase vs ~2.7. Bounds any gate repair (b for the size).
- Decision: repair = pressure-conditioned prior (schema 2 + sim key, flag OFF = today's table). Question posted on the opponent
  cadence (not blocking). Next: build + unit test, then TEST RUN from scratch graded at m2k/m5k. HANDOFF §5bw.


## L23 — 2026-09-03 01:31-01:55 | AGGRO gauntlet loop 7: the repair is BUILT + TEST RUN LAUNCHED (L22's stamps were ~35 min fast; box clock here)
- Built, one flag: `tools/gate_prior.py --pressure-s 6` (schema 2; blend byte-identical to the shipped table) ->
  `config/gate_prior_p6.json`; sim key `SimMatchEnv.enemy_troop_min_age()` carried raw as payload `eage`;
  `sim.ppo_gate_prior_pressure_s` in the trainer (0.0 = gate05 byte-for-byte; W must match the table's, asserted).
- (a) table W=6, single elixir 5/6/7 elixir: quiet 0.024/0.030/0.028 vs pressure 0.086/0.067/0.067; 38% of single
  windows pressured (CardDB kind; L22's hand list said 37%). No unknown red cards.
- (a) 5 new unit tests, 12/12 pass. CPU smoke run flag ON: reaches the loss, `PRESSURE on 57% of usable rows`
  (untrained policy, 8 matches -- not L22's number). Flag-OFF smoke (gate05_run.yaml, isolated --out): exit 0, original banner, no PRESSURE clause.
- Staged `data/bench/gatep6_run.yaml` (= gate05_run.yaml + the flag + isolated paths). NOT launched. Next: launch the
  TEST RUN -- DONE at 01:46: `data/bench/gatep6_run_launch.sh` (same CLI as gate05, cuda, seed 41, from scratch), ckpt
  `data/policy_gatep6_20260903.pt`, watchdog + gates monitors up; first update `PRESSURE on 44% of usable rows`. Next: m2k read
  (~1.1 h) with gate_prior_probe seeds 0/1/2 vs gate05's 4.0/3.5/3.0%. HANDOFF §5bx.5.


## L24 — 2026-09-03 02:45-02:55 | AGGRO gauntlet loop 8: m2k read of the conditioned-prior test run -- BELOW gate05
- (a) gate_prior_probe seeds 0/1/2 at m2,350: >=6 share 0.9/0.8/0.5% vs gate05 m2k 4.0/3.5/3.0 (L11) and m5k 1.2/1.3/1.0 (L16);
  elixir mean 2.2 vs 2.6; P(play|aff) 0.34 vs 0.23. Every seed below every gate05 seed.
- (a) trainer stat at 5,000 updates: conditioned target averages 0.066 vs blend 0.060 on sim rows because PRESSURE covers 50%
  of usable rows (pros 38%). (b) net pull-to-wait weaker; quiet windows (~5 s median) too short to bank; the split is a
  licence to spend under the sim's cadence -- the §5bw.4 caveat materialising.
- Run continues to the pre-registered m5k read (~03:50). Owner question re-posted with the mechanism: (A) opponent cadence arm
  (recommended), (B) restart on gate05's blend + aggro wiring, (C) stronger coef on the conditioned table (expect fail). HANDOFF §5by.


## L25 — 2026-09-03 03:52-04:25 | AGGRO gauntlet loop 9: gatep6 m5k read -- bar FAILED, tie with gate05; run stopped
- (a) probe s0/1/2 at m5,150: >=6 share 1.4/1.1/2.0% vs bar (above 4.0/3.5/3.0) -- FAILED; vs gate05 m5k 1.2/1.3/1.0 -- tie.
  L24's early "worse" closed by m5k; carry "does not help", not "hurts". Bucket P(play) flat 0.22-0.31.
- (b, strengthened) >=6 share bounded ~1-2% by the opponent model (two tables, same landing). Settled only by path A.
- Run stopped 04:16 at 5,175 eps (recorded §5bz.4); python 19 -> 1 (Nucleo). Box idle, 9.8 GB free. A/B/C question open.
- Next: aggro wiring behind a flag (owner-ordered, unblocked) while the question stands. HANDOFF §5bz.


## L26 — 2026-09-03 04:21-04:30 | AGGRO gauntlet loop 10: aggro wiring BUILT behind two flags, both OFF (39aa80b)
- `sim.aggro_drills` (tank_for_bow + bow_lane_choice in; knight_guards_the_bow + nado_the_sneaky_lock retired from the pool,
  still registered). OFF = the 29-drill gate05 pool exactly (a, verified; the new test caught a registry leak, fixed).
- `env.nado_retarget_reach_fix`: centre-to-centre -> engine `_gap`. (a) hog at 2.20 tiles is now a targeter and the reference
  pull earns the credit's predicate; OFF reproduces the never-fires behaviour. 3 new tests from the L16 script.
- `Scenario.noise` field replaces the `_no_distractors` hook. 83/83 tests across the touched modules. Box idle. A/B/C open.
- Next: lock-aware `predict_targets` graded by aggro_agreement.py (stopped-window job). HANDOFF §5ca.


## L27 — 2026-09-03 04:31-04:48 | AGGRO gauntlet loop 11: lock-aware predict_targets built (flag OFF) and graded
- Built: `interactions.Hint(engaged, deploying)` + optional `hints` on predict_targets/mover_forecast/interaction_vector/
  predictive_channels; `view.interaction_state(hints=True)` reads Unit.locked/target + deploy_left; `observation.lock_aware_targets`
  (default false) feeds it into the sim obs. 6 new tests, 45/45 across touched modules.
- (a) engine agreement, gate05 m5k, 12 matches x 3 seeds, SAME 60,599 samples as L17: memoryless 74.2% (unchanged), engine-truth
  hints 95.8% (locked 81.5/80.6 -> 97.8/96.7, deploying 0 -> 100, buildings 25/16 -> 95/95), live-style proxy 89.7%.
- (b) live has no track memory (per-frame detections), so the flag is a sim-to-real seam; proxy = ceiling with a perfect tracker.
- Trap: engine `deploy_left` float residue makes every 1.0 s deploy 1.1 s (one sub-tick). Not fixed (engine change).
- Three default-off changes now wait for the restart; recommended order aggro_drills -> reach fix -> lock-aware (after the live
  seam is decided). A/B/C still open. Nothing running. HANDOFF §5cb.


## L28 — 2026-09-03 05:48-05:52 | AGGRO gauntlet loop 12: HOLD -- produced nothing
- No owner ruling on A/B/C (L24), no steering, no new commits; box idle (python = Nucleo only, 9.4 GB free).
- Every aggro item is built default-off (aggro_drills, nado_retarget_reach_fix, lock_aware_targets). The only remaining step
  is the restart, blocked on the ruling. Checked whether the live-tracker seam could be probed cheaply: data/sessions are raw
  video + click events (no per-frame detections), so it is a detector-over-video job, not a hold-loop probe. Parked.


## L29 — 2026-09-03 06:50-07:05 | AGGRO gauntlet loop 13: Path A prepared -- opponent cadence knob built (default OFF) and screened
- Cause of §5bw.4's over-pressure found (a): the non-beatdown ScriptedBot has NO elixir rule on its attack branch -- it plays on
  the first step it can afford any offensive card. Added `sim.bot_attack_floor` (default 0), training-only via make_opponent's
  `adaptive` gate (eval bots untouched). Identity at 0: deploy-log sha equal on HEAD vs patched, eval- and training-style.
- Screen (a), m10k sampled policy, 12 matches x 2 seeds per floor, non-beatdown bots: floor 0 press 56% / median 4.8 s /
  bankable 0.62 per phase; 5-6 barely move; floor 7: 42% / 6.6 s / 2.2; floor 8: 42% / 7.8 s / 2.2; pros 37% / 9.0 s / 2.7.
  Instrument differs from L22 (training provider vs non-adaptive) -- compare within the table only. 2 seeds = a screen.
- (b) whether the floor lifts the policy's >=6 share is Path A itself (one change, `sim.bot_attack_floor: 7`, read at m5k).
- Tests 5/5 new, opponent regression 16/16. Nothing launched; A/B/C still open. HANDOFF §5cc.


## L30 — 2026-09-03 07:45-07:52 | AGGRO gauntlet loop 14: owner ruled; Path A LAUNCHED
- Owner ruling 07:4x: cadence toward pros YES; do A, then C with caution if A fails; aggro flags one at a time, aggro_drills ->
  reach fix -> lock-aware; "this floor is really good" (opponents that never play their RG / Recruits).
- Owner's observation CONFIRMED (a): floor 0, 7 of 17 decks holding a >=6 card never fielded it (RG x2, Pekka, E-Barbs x2, 3M,
  Boss Bandit); floor 7: 0 of 13. m10k policy, 12 matches x 2 seeds per floor.
- LAUNCHED 07:48 from scratch: floor7_run.yaml = gate05_run.yaml + sim.bot_attack_floor 7.0 (one change), seed 41, ckpt
  data/policy_floor7_20260903.pt, watchdog + gates up; 19 python after (1 before). Bar: m5k >=6 share > gate05's 1.2/1.3/1.0%.
- Next: m2k by hand (~09:00), m5k from the gates snapshot. HANDOFF §5cd.


## L31 — 2026-09-03 08:52-09:10 | AGGRO gauntlet loop 15: floor7_run m2k screen -- below gate05; Path A's premise fails a cross probe
- (a) pre-registered probe, floor7 ckpt @m2450, seeds 0/1/2: >=6 share 1.2/1.3/0.5% (gate05 m2k 4.0/3.5/3.0; gatep6 0.9/0.8/0.5;
  gate05 m5k 1.2/1.3/1.0). P(play|aff) 0.29 (gate05 m2k 0.23) -- more eager, not less.
- (c) cross probe, fixed ckpt vs floor-0 and floor-7 training bots: gate05 m2k 5.0/4.5/2.4 -> 4.5/3.5/4.3; floor7 1.5/1.8/0.9 ->
  1.8/1.4/1.0. The opponent's cadence does not move a fixed policy's >=6 share; P(play|aff) unchanged to 2 decimals. The
  "opponent bounds the bank" premise of Path A is contradicted at m2k; the policy spends at its own rate whatever the windows.
- Decision: pre-registered -- run to m5k (ETA 10:05-10:20), bar unchanged. Fail -> C with caution = floor 7 + gate_prior_p6 at a
  stronger coef (one change vs floor7_run). Box: 19 python, physical RAM ~0.6 GB free (paging), probes run one at a time.
- HANDOFF §5ce.


## L32 — 2026-09-03 10:38-10:52 | AGGRO gauntlet loop 16: PATH A FAILED the m5k bar; run stopped; question posted
- (a) BAR READ, pre-registered probe on data/bench/floor7_m5k.pt (snapshot 10:18), seeds 0/1/2: >=6 share 0.7/0.9/0.5% vs the
  bar (gate05 m5k) 1.2/1.3/1.0 -- below on 3/3 seeds, and DOWN from its own m2450 read of 1.2/1.3/0.5. FAILED.
- (a) same-count gates: regret oracle 0.271 vs 0.2291, belief 0.2483 vs 0.2045 (WORSE); x-bow DEFENSIVE 6% vs 28%; deploy rate
  14.7/min vs 13.3 (pro 11.7, so further away). RETRACTS §5ce.3's hopeful reading -- the higher training winrate (110W vs 58W at
  m2700) came from a WEAKER banking opponent, not a better policy.
- (a) mechanism: GATE PRIOR CE line stable over 12.6k updates -- prior wants pi(play) 0.057, policy sits at 0.283, coef 0.5 on
  10% of rows. The term is under-powered by construction; agrees with L31's cross probe from the other side.
- (a) only gatep6 (conditioned table) ROSE m2k->m5k (0.73 -> 1.50 mean). C builds on the one arm with a positive trend.
- Run STOPPED at m5950 (289W-4519L-6D, drills 45%, state recorded first; ckpt + m5k snapshot preserved, resumable). Procs 19 -> 2.
- STOPPED ON A QUESTION: does C keep bot_attack_floor 7 (owner's cadence preference, carries the regret regression) or run clean
  (gatep6 + coef only, my recommendation)? HANDOFF §5cf.


## L33 — 2026-09-03 10:55-11:30 | AGGRO gauntlet loop 17: owner ruled; Path C LAUNCHED (gatec2_run, coef 2.0, no floor)
- Ruling 10:5x: coef 2.0; strip bot_attack_floor for C; floor DEFERRED to after C (owner hesitant to drop it permanently --
  it changes what the bots do and therefore what the model learns).
- LAUNCHED 11:20 from scratch: gatec2_run.yaml = gatep6_run.yaml + ppo_gate_prior_coef 0.5 -> 2.0 (one change; p6 table,
  pressure_s 6.0, no floor), seed 41, ckpt data/policy_gatec2_20260903.pt; trainer prints GATE PRIOR ON coef 2.000; 19 python.
- Pre-registered: m2k screen ~12:25 (vs gatep6 0.9/0.8/0.5, gate05 4.0/3.5/3.0); m5k bar ~14:00: PASS > gatep6's 1.4/1.1/2.0
  per seed, STRONG > gate05 m2k 4.0/3.5/3.0; in-run: pi(play) on usable rows vs gatep6's 0.242 at 11k updates; caution
  guards = regret / drills / x-bow split / deploy rate / cell-head alerts. HANDOFF §5cg.


## L34 — 2026-09-03 12:24-12:30 | AGGRO gauntlet loop 18: gatec2 m2k screen -- gate05's level, 4-5x gatep6; coef bites on level not shape
- (a) ledger probe, gatec2 @m2450, seeds 0/1/2: >=6 share 3.5/4.4/3.4% (gate05 m2k 4.0/3.5/3.0; gatep6 0.9/0.8/0.5; floor7
  1.2/1.3/0.5). P(play|aff) 0.20 (gatep6 0.34). Elixir mean 2.62-2.80.
- (a) in-run: cumulative pi(play) on usable rows flat 0.150-0.162 from update 800 to 5400 (gatep6 0.242 @11.4k, floor7 0.283).
  The pre-registered tell is met. Per-bucket P(play) flat 0.17-0.22 across elixir 0-9: the LEVEL is suppressed uniformly,
  the pro SHAPE (hold at 3-7, spend at 9) is not learned.
- (a) drills pass-all at m2450: gatec2 39% vs gate05 38%, gatep6 31%, floor7 43% -- no collapse.
- (b) durability: gate05 stood here at m2k and fell to 1.17 by m5k. Bar unchanged, m5k ~13:55. HANDOFF §5ch.


## L35 — 2026-09-03 13:16-13:35 | AGGRO gauntlet loop 19: owner question (elixir/x-bow/spell trend); PYTHONHASHSEED trap found, own numbers retracted
- MY ERROR (a), against a rule already in this repo's standing rules ("export PYTHONHASHSEED=0 before any labelling run"):
  greedy EVAL tools need it too; real_run_gates.py:65 sets it, my ad-hoc runs did not. Not a new trap -- a violated one.
  Same ckpt: 68 vs 79 x-bows, DEFENSIVE 68% vs 49%, tower lock 40% vs 66%; continuation plays 401 (seeded, twice) vs 367/399
  (unseeded). My first x-bow/continuation runs this loop are RETRACTED. New standing rule.
- (a) MATCHED m2k card mix (new cardmix.py on continuation_report's exact rollout): SPELL share gatep6 29.4 > floor7 25.2 >
  gate05 21.6 > gatec2 14.0%, mirrored by x_bow share 3.3 < 5.3 < 8.0 < 13.2%. Total plays 520 -> 401. Support cards
  (skeletons/ice_wiz/knight) FLAT across all arms -- the coef removed spell plays specifically, not plays in general.
- (a, unmatched counts) x-bow at m2450: 2.83/match, DEFENSIVE 68% / OFFENSIVE 29% / dead 3% (gate05 m5k 28/48/25, floor7 m5k
  6/69/25). Directional only until gatec2's own m5k gate.
- (b) ELIXIR trend NOT callable: 3 non-monotone watchdog points (2.57/2.28/2.71) + one probe point (2.72 at m2450). Said so
  rather than drawing a line through noise. HANDOFF §5ci.


## L36 — 2026-09-03 14:04-14:15 | AGGRO gauntlet loop 20: gatec2 m5k -- bar PASSES, caution guards COLLAPSE = "not a pass"
- (a) BAR, ledger probe on data/bench/gatec2_m5k.pt (m5200), seeds 0/1/2: >=6 share 2.3/1.7/2.0%. vs gatep6 m5k 1.4/1.1/2.0
  -> above on 2 seeds, EQUAL on the third (not the clean seed-by-seed sweep the bar asked for); vs gate05 m5k 1.2/1.3/1.0 ->
  above on all 3. First arm to hold >2% at m5k; keeps 53% of its m2k share vs gate05's 33%.
- (a) GUARDS FAIL: regret oracle 0.2924 / belief 0.2880 -- WORST of every arm (gate05 0.2291/0.2045, floor7 0.271/0.2483).
  Cause is one column: waits 22 -> 60 of 203 states, 55%/50% of them wrong. Absolute errors 57/203 (28.2%) vs gate05's
  36 (17.7%); ALL the excess is wrong waits (33 vs 5) -- its plays are better (24 wrong vs 31). Enemy-troop regret 0.3013.
  Falsification: converted rates to counts to rule out a "waits more often" artifact; it is not an artifact.
- (a) causal chain complete: coef 2 lowers the gate LEVEL not SHAPE (L34) -> removes cheap SPELL plays (L35, 29.4->14.0%) ->
  those are the defensive answers -> declines to defend (L36). Each link measured before the next was known.
- Verdict per §5cg.2 pre-registration: NOT A PASS ("the prior won by breaking the policy").
- Not all bad (a): closest arm to pro deploy rate (10.4 vs 11.7), best after-bow L1-to-pro (0.304 vs 0.902), 4.79 bows/match
  with 16% dead vs 25%. §5ci's 3% dead at m2450 did NOT hold at m5k -- the matched-count caveat was right.
- QUESTION OPEN (next arm: coef 1.0 / fix coverage / go do the aggro work [my rec] / run to m10k first). Run LEFT RUNNING --
  m10k gate ~16:45 preserves that option free. HANDOFF §5cj.


## L37 — 2026-09-03 14:25-14:40 | AGGRO gauntlet loop 21: owner ruled -- wait for m10k, then aggro work regardless
- Ruling 14:2x: §5cj option (iv) then (iii). Owner: 5k is early, real chance of a rebound; after m10k move on to aggro
  regardless -- three direct arms did not budge the elixir share, so likely confounders; aggro flags may move it indirectly.
- No measurement this loop. gatec2_run untouched: m5900 at 14:25, 0.5 ep/s, drills 39%, 19 python; m10k gate ~16:45-17:00.
- PRE-REGISTERED (HANDOFF §5ck.2): REBOUND = m10k regret <= gate05 m10k 0.2418 AND wrong waits <= 15/203; HELD = >=6 share
  above gate05 m10k 0.1-0.2 on 3 seeds. First aggro arm = ONE change `sim.aggro_drills: true`; base = gatec2 m10k ckpt only
  on rebound+held, else gate05 recipe from scratch seed 41. Read on the ledger + the lock-state drill counters.


## L38 — 2026-09-03 14:55-15:15 | AGGRO gauntlet loop 22: owner question (spells) -- new engine-attributed spell probe; suppression is recovering in-run
- (a) The m5k gate report contains NO spell metrics (one incidental line: the_log = 16% of after-x_bow follow-ups).
- NEW INSTRUMENT `scratchpad/gauntlet/L38/spellprobe.py`: attributes damage on the ENGINE (wraps _resolve_spell/_resolve_roll/
  _tick_vortex/_tick_roll; whiff = 0 enemy bodies AND 0 tower damage). Validates EXACTLY against L35 cardmix on the same ckpt
  (401 plays, 14.0/8.7/4.5/0.7) -> one instrument. NOT comparable to L13's mask-whiff / spell_waste probe.
- TRAP (a): the Searcher deepcopies the engine and the forks cast spells too -- counting them gave 7 log casts vs 6 log plays.
  Fixed by an identity test on the live engine; casts == plays is now the probe's validity check.
- (a) matched m5000: gatec2 SPELL 11.6% vs gate05 28.3, floor7 27.4; log whiff 14% vs 24/32; tornado whiff 0% vs 9/4; tornado
  catches 5.33 bodies/cast vs 2.74/2.51. Fewer, better-aimed casts -- not loss of aim.
- (a) IN-RUN TREND gatec2 m2450/m5000/m6800: SPELL 14.0 -> 11.6 -> 19.8%; log 0.63 -> 0.87 -> 1.44/min; nado 0.34 -> 0.24 ->
  0.68/min; log whiff 73 -> 14 -> 24%. The suppression that caused the L36 regret failure is recovering -> first support for
  the owner's rebound hypothesis (b as a rebound claim; the m10k regret read decides it).
- RETRACTED IN-LOOP: my live claim that rocket usage "went up / first non-zero ever". Rocket is 3 casts/16 matches at m2450 AND
  m5000, 0 at m6800; L35 already had all four arms at 0.4-0.7% rocket share at m2k. Rocket did not go up. HANDOFF §5cl.


## L39 — 2026-09-03 16:16-16:30 | AGGRO gauntlet loop 23: 4th spell point + disjoint seed slices -- my own L38 "recovery" RETRACTED
- (a) NOISE BAND, new `--offset` (same ckpt, SEEDS[16:32]): spell share repeats to 0.4pp (m6800), 0.6pp (gate05 m5000),
  3.9pp (m8600). Cross-arm gaps (11.6 vs 28.3) are far outside it -> §5cl.2's cross-arm table stands.
- (c) RETRACTED: §5cl.3's "spell suppression is recovering". Series is 14.0 / 11.6 / 19.8+19.4 / 13.7+9.8 -- up then back
  down. The m6800 rise was real (both slices agree) and did not persist. No trend; oscillation in a 10-20% band.
- (a) ROCKET rose at m8600: 10 and 7 casts per 16 matches (2.3% / 1.1% of plays, 0.21 / 0.11 per min) vs 0 at m6800 and 0
  for gate05/floor7. Highest measured in the project; pros 3.4%. Partly reverses §5cl.4 ("rocket did not go up" -- true
  through m6800, wrong at m8600). BUT 30% / 14% of those rockets hit nothing (6 elixir each).
- (a) log whiff at m8600 8% / 15%, best of any ckpt (gate05 24/26%, floor7 32%).
- (b) matched trainer counters: gatec2 drills last-300 38 -> 42 -> 49% at m5900/6800/8600 while gate05 went 49 -> 47 -> 39;
  EVAL ladder 2/12/23/27 vs gate05 5/13/17/8/10. Both say "still improving"; neither is a discriminator.
- LOOP RULE ADDED (.claude/commands/gauntlet.md §2): repeat a headline number on a disjoint seed slice before reporting it.
- Run untouched, m8800 at 16:23; m10k gate ~17:05. HANDOFF §5cm.


## L40 — 2026-09-03 17:15-17:35 | AGGRO gauntlet loop 24: gatec2 m10k read = NO-REBOUND + HELD; gatec2 stopped; aggro arm 1 launched
- (a) pre-registered §5ck.2 read on `gatec2_m10k.pt`: regret 0.2824 / 0.2805 (bar <= 0.2418) FAIL; wrong waits 33/203
  (bar <= 15) FAIL -- the SAME 33 as m5k. >=6 share 2.7 / 3.8 / 2.4% on seeds 0/1/2 (gate05 m10k 0.1-0.2) HELD, up from
  m5k 2.3/1.7/2.0. Outcome 3 of 4: banks by refusing to defend, §5ck.3 chain confirmed at 2x the matches.
- (a) secondary at m10k vs own m5k: deploy 11.4/min (pro 11.7; m5k 10.4), gap 4.20 s (pro 3.85); x-bow dead 16 -> 35%,
  defensive 45 -> 23%, offensive dmg 1217 -> 1676; L1-to-pro after x-bow/tesla 0.30/0.39 -> 0.46/0.51 (worse).
  EVAL@10000 ladder 25% fair 20%; drills 42%/42%.
- Rule fired as written (base = gate05 recipe, NOT gatec2's ckpt). gatec2 STOPPED at m10150 (best_wr 17.77, 472W-7651L-8D);
  live+best ckpts backed up to scratchpad/gauntlet/L40, cmp-verified; python 19 -> 1 (Nucleo only) verified.
- AGGRO ARM 1 launched 17:22: `aggro1_20260903` = gate05_run.yaml + `sim.aggro_drills: true` (3-line diff), same CLI,
  seed 41, from scratch. Pool verified on the trainer's code path: 29 drills, tank_for_bow + bow_lane_choice in,
  knight_guards_the_bow + nado_the_sneaky_lock out. Watchdog + gates monitors up; 19 python, 2.1 GB free.
- Read plan pre-registered in §5cn.4: drill counters (direct) + ledger >=6 share 3 seeds at m2k/m5k (indirect) + regret
  at the m5k gate vs gate05 m5k. First look ~19:00 (m2000 EVAL), decisive ~20:10 (m5k gate). HANDOFF §5cn.


## L41 — 2026-09-03 17:25-17:45 | AGGRO gauntlet loop 25 (owner follow-up): gatec2 m10k stat sheet; "init from gatec2" arm parked
- Owner: future arm = aggro flag + init from gatec2 ckpt; "best results of any checkpoint" -> (a) on EVAL/crowns/x-bow,
  (c) on regret/defense. Parked as aggro arm 1b in HANDOFF §6, to run AFTER aggro1's m5k read.
- (a) gatec2 m10k vs gate05 m10k, both slices: spell share 11.0/9.0 vs 27.2/27.3; log 0.94/0.83 per min whiff 21/22%;
  tornado 0.20/0.09 per min whiff 27/20% (nearly gone); ROCKET 4/2 casts -- the m8600 rise (10/7) did NOT hold (c).
- (a) outcome on the greedy rollout 1/16 and 7/16 for the SAME policy on consecutive slices -- n=16 winrate not a
  discriminator, demonstrated again. Use EVAL@10000: gatec2 25%/20% vs gate05 10%/10%. Crowns 24-40 vs 8-45 per 32.
- (a) x-bow m10k: 4.33 vs 0.71 per match; tower lock 70% vs 50%; dmg 1676 vs 676; dead placements 35% vs 24%.
- spellprobe.py gained an OUTCOME line. aggro1 at 600 episodes, 0.7 ep/s, untouched. HANDOFF §5cn.7.


## L42 — 2026-09-03 17:50-19:05 | AGGRO gauntlet loop 26 (owner steering): LIVE SPELL AIM FIX (authorized) + aggro1 first look
- (c) owner's "mapping issue": the warp is shared by troops and spells; a log-only forward bias cannot be it. Owner's
  own third message (cast delay ~1 s) is the diagnosis the code supports.
- (a, in code) four defects: env.py gated on CURRENT positions before leading (lead never ran on the cast that needed
  it); tracks fetched without the base (KB speed fallback dead on fresh tracks); log_hits back-slop 1.73 tiles (x width
  on the y axis; sim uses 1.0); play.py never led log or tornado, rocket used the deprecated rate, no cast delay.
- FIX shipped (live only, sim untouched): env.spell_cast_delay_s 1.0 (b); lead-then-gate on led tracks for log/rocket/
  tornado in env.py AND play.py; back-slop 1 tile; drill_env.report registers aggro drills (report only).
  Offline: hog +2.0 tiles, knight +1.0, building 0; hog gate fails on led body -> cast 2.24 tiles back.
- aggro1 m2500: tank_for_bow 36% (gate05 m5k 12% same instrument; §5bt.4 12%), bow_lane 0, nado_king 0 (doctrine 8%);
  >=6 share 2.5/1.0/1.2; EVAL@2000 4/2%. One seed, 25 reps: a screen. m5k gate (~20:10) is the read.
- §6 queue += sim spell_delay 0.4 -> 1.0 parity arm after aggro1b (owner). Owner 19:1x: delay is 1.0 s for ALL spells
  (online sources) -- no measurement owed; the sim's 0.4 is the wrong one.
- Run untouched (12 trainer procs before/after). HANDOFF §5co.


## L43 — 2026-09-03 19:10-20:00 | AGGRO gauntlet loop 27 (owner steering): the CEILING measured; archetype-GA answered; opp-elixir obs mismatch found
- Owner: "too much scaffolding / GA like Trackmania?" -> answered (c on the analogy, right on entropy collapse ent=0.05-0.06);
  owner chose (1) measure the ceiling only. Ran it: gatec2_m10k, ladder, 48 paired seeds: policy alone 41.7% / tower -0.91;
  search teacher (H=12, cells 3) 77.1% / +0.11 (a). Ledger 08-27 said 37.0 -> 85.7 (m18000, n=300). Sim is not the ceiling;
  the learner is. Distillation (6-PRIORITY-B) is the case, privileged-teacher gap (reseed_opp) must be measured first.
- Per-archetype (a, screen): policy beatdown 8% / control 46 / cycle 60 / siege 33 (n 12/13/20/3); teacher 58/77/85/100.
- Owner's archetype-GA: obs already has OpponentMemory + measured detector noise; recommended ONE net + archetype-posterior
  input over six GA loops (fitness noise x6; nets cannot be averaged). Not started.
- FOUND (a, code): sim/env.py:643 puts OUR elixir in memory slot 5; live puts the opponent-elixir estimate there (3bc1d45,
  08-11). Sim policy has never seen opponent elixir. Parity-arm candidate; untouched while aggro1 runs. HANDOFF §5cp.

## L44 — 2026-09-03 20:23-21:00 | AGGRO gauntlet loop 28 -- CLOSE-OUT: aggro1 m5k FAILED all three halves; run stopped; reach fix ON
- Direct (a): tank_for_bow aggro1 m5k 0%/0% (seeds 5,6) vs gate05 m5k 12%/12%; m2500's 36% did not persist. bow_lane 0,
  king activation 0 (prior 4-8% = doctrine gap). Indirect (a): >=6 share 2.0/2.1/1.4 vs gate05 2.3/1.7/2.0 -- unchanged.
  Regret (a): 0.2621, 25 wrong waits vs gate05 0.2291 / 5. Verdict: FAILED; drill curriculum through PPO is not the lever
  (same message as L43's ceiling: learner-bound).
- aggro1 STOPPED at ~m5900 (state in §5cq.1/4; python 19 -> 1, Nucleo untouched). aggro1b NOT launched (same mechanism).
- Owner's reward bug fix switched on: env.nado_retarget_reach_fix true (tests pass). Every prior ckpt predates it.
- Four remaining aggro levers (king-activation doctrine line, opp-elixir obs slot, sim spell_delay 1.0, distillation)
  all belong to the next gauntlet's direction. GAUNTLET CLOSED per owner ruling 20:3x. HANDOFF §5cq.

## L45 — 2026-09-03 21:05-21:45 | NEW GAUNTLET: sim->live gap, loop 1 -- c2r launched; live harness built; first sample BLOCKED (display off)
- c2r PPO resume RUNNING 21:27 (gatec2_m10k best + reach fix, coef 2.0, 12 workers cuda, 0.8 ep/s). Traps: counter restarts
  at 0 (+10000 absolute), no optimizer state, RAIL GUARD cell-head x0.0556 on resume -- not a pure volume arm. HANDOFF §5cr.1.
- Live-obs harness: data/bench/live_obs.yaml (eps 0/0, learning off, isolated ckpt+replays) + L45/live_obs_session.py
  (idle>=15 min gate, foreground-verified, N-match clean stop, foreground-loss hard abort). §5cr.2.
- BLOCKED (a): display asleep -- foreground 0, CR frame mean 0.0, AC display timeout 20 min < owner idle 81 min. Wake nudge
  is input outside the game window (classifier blocked it too). Owner question posted. §5cr.3.
- Correction (a, code): epsilon branch = doctrine/counter-table/advisor/random, not uniform random; the owner's sessions were
  ~60% that branch, ~40% PPO. §5cr.4. Next: retry the live gate each loop; offline obs-assembly diff meanwhile.
- L45 cont. (22:0x-22:2x): owner set display timeout Never; waiter armed. FOUND (a): train-rl greedy rule = tau 0.5 vs sim/
  play.py tau 0.25; gatec2_m10k p(play) p99 0.358 -> 0.5 rule keeps 0.1% of plays (6 vs 581 in 16 sim matches). At eps 0
  the PPO never plays live; owner's sessions = exploration half + wait-till-9.5-then-bow half. Fix: train.rl_gate_tau 0.25
  (config.yaml), key absent = legacy (live_obs.yaml baseline / live_obs_tau.yaml). Base-block seam (sim 6 slots vs live 16)
  measured second-order (gate agree 0.93; detector-fed slots 16+ carry the decision: 0.83). Config-value correction:
  rl_epsilon_start 0.50 not 0.60. HANDOFF §5cr.7.
- L45 cont. (22:2x-23:2x): live obs sessions at eps 0. s1 BLIND (my venv error), s1b/s3/s3b FROZEN reads, s2 = the gap:
  3.3% plays, 69% of decisions at >=9 elixir, one burst then idle. Offline ablation on the live states: ONE slot -- threat
  31 (opp-memory 5) = opponent-elixir estimate live (mean 0.035) vs OUR elixir in sim; slot31 := own elixir -> p(play)>tau at
  >=9 elixir 1.7% -> 96.9%; obs image/hand/next/tower are not it. Fix env.opp_mem_slot5 (config, default legacy). s3c with
  own_elixir + working reads: 58/463 plays (12.5% vs sim 10.8%), elixir 5.2, plays all match long, still 2 losses.
  Frozen reads (a): fresh WindowCapture on the MATCH_END screen locks 38 px short (dark bottom band), never re-scans ->
  hand -1 / elixir 9.22 forever; launcher relocks at the first IN_MATCH frame inside reset(). Window drift (a): SW_RESTORE
  un-maximizes a maximized window (controller.py comment (c)); IsIconic guard. Next seam: live hand reads 2.9/4 slots,
  x_bow in hand 5% vs 56% sim. c2r m3725, watchdog >=6 share 0.005 (68% below rolling median) -- m5k gate ~23:50. §5cr.8.
- L46 (2026-09-04 07:2x-08:0x): OVERNIGHT NOTHING RAN -- the 23:46 wakeup never fired; told the owner plainly. Pre-registered
  c2r gate read (greedy probe, seeds 0/1/2, same instrument same morning): init gatec2_m10k 2.7/3.8/2.4 (reproduces L36),
  c2r_m5k 3.8/4.0/4.0, c2r_m10k 5.0/6.7/4.9 -- NOT collapsed; first arm whose >=6 share rose init->m5k->m10k on all seeds.
  Attribution arms not owed. Watchdog "CELL HEAD COLLAPSED" alerts = a threshold (ent<1.27) inside every run's normal
  band (0.6-1.6); uninformative. Trainer EVAL ladder 19..33%, best 29.9 saved 03:51 (winrate not a discriminator).
  Stop-path fix shipped (env.py Play Again tap skipped when stop requested; launcher arms stop on the Nth match) -- (b)
  until a live session runs it. Full drill suite init vs c2r_m10k running in background. HANDOFF §5cs.
- L46 cont. (2026-09-04 08:0x-08:5x): the owner watched s4 and called the model "blind". Tested, not agreed: TWO input
  seams, both live-path only, both (a) with before/after on one instrument. (1) tower anchors drawn at frame-detected
  positions, rows 2-8 px off the sim's: s4 frames re-rendered with the sim's exact tower cells -> gate share at >=9
  0.085 -> 0.681 (sim ceiling 0.695); shipped `_SIM_TOWERS_BOARD` + alive gating in env.py/replay_bc.py. s5 with that
  fix alone did NOT recover (4.7% plays) -> RETRACTED "tower anchor = the seam": s5's mechanism was (2) `hand.slots`
  centres 7-10 px left of the cards in the Play Games window -> x_bow scored 0.42 < 0.5 -> hand = three hoarded spells
  -> deadlock 67% of decisions (sim 0.0%). Recalibrated slots (unread 13/52 -> 2/52). s6 with both: 53/408 plays
  (13.0%), elixir 5.68, >=9 share 14%, deadlock 9%, evo cards read+played live for the first time; residual -1 reads are
  ~1-s deal gaps (0.32-s scan, all runs <= 3 s) -- my "70-s empty slot" reading retracted (10-s stride artefact).
  Left (b): image still costs ~1/3 of the gate on sim states (0.317 vs 0.483); play.py never renders canonically.
  c2r reached 20k episodes 08:41; m20k gate not yet posted; drill suite still running. HANDOFF §5cs.6-8.
- L46c (09:0x-09:2x): c2r m20k gate. Pre-registered 3-seed probe, all four ckpts same instrument same day: >=6 share
  init 3.0 -> m5k 3.9 -> m10k 5.5 -> best 2.2 -> m20k 1.2 (means). The run PEAKED at m10k and is now below init on all
  3 seeds; P(play) 0.151 -> 0.202, affordable rows 59% -> 45% (spends earlier, so it is poorer). Does NOT strictly trip
  the owner's collapse rule (<=1% on ALL 3 seeds; read 1.5/1.0/1.1) -- not restarting on a rule that did not trip;
  m30k (~14:00) pre-registered as the decisive read. Found (a): the live sessions were initialising from the EVAL-
  WINRATE-selected `best` ckpt, which reads 2.2 on the mechanism metric vs m10k's 5.5 -- s7 = s6 with the init changed
  to c2r_m10k, one change. Open-factor slate recorded in §5cs.9. HANDOFF §5cs.9.
- L46d (09:2x-09:4x): s7 = s6 with ONE change (init c2r_m10k, not the winrate-selected best). 36/365 plays (9.9% vs
  13.0%), elixir 7.10 vs 5.68, >=9 share 0.31 vs 0.14, play share at >=9 0.123 vs 0.281, zero spells played. Per-match
  discriminator (play share when rich AND holding a non-spell) s6 0.467/0.087 vs s7 0.333/0.050 -- the arms OVERLAP at
  2 matches each, so (b) not (a). Direction: the sim's >=6 banking metric points the WRONG WAY live; live init stays
  `best`. Instrument trap found: npz['elixir'] is capped at 9, elixir_vec*10 is the policy-facing value. HANDOFF §5cs.10.
- L46e (09:4x-10:2x): owner order -- "do the checkpoint, figure out why the model is so stupid". WHY (a): his train-rl
  sessions ran rl_epsilon_start 0.5 over 6000 steps (~30 matches) with an epsilon branch that is an explicit expert
  ("quiet board + >=6 elixir -> X-BOW" + counter table), and the tau-0.5 greedy rule vetoed ~99.9% of the net's plays --
  so ~40% of his decisions were doctrine plays and essentially every play he watched was the doctrine, not the network.
  Both masks came off today (eps 0 + tau 0.25): s4-s7 are the first sight of the raw policy, not a regression. Sim drill
  suite agrees: 9 of 29 drills at 0% vs doctrine 76-100%, incl. bank_to_six_then_bow 0% vs 100%. Checkpoint arm 6 v 6
  alternated: best 196/1439 plays (13.6%), commits when rich 0.222, bow 0.137; m10k 68/1022 (6.7%), 0.049, 0.019.
  Rank test on the 6-a-side arm alone U 26/36 (p~0.15) -- direction consistent, not significant; pooled 8-a-side
  (post-hoc) U 50/64 p<0.05. Live init stays `best`. Fix route proposed: distil the doctrine into the policy.
  HANDOFF §5cs.11.
- L47 (2026-09-04 10:3x-11:0x): reverse channel-group swap (sim states + live image, one group at a time), s6 AND
  s7, 3 pairings each: semantic canvas 3-8 is NOT the seam (0.455-0.524 vs sim 0.483); RGB carries the bulk
  (0.36-0.45 alone); predictive <=0.05. Then: the gate is PALETTE-SENSITIVE -- same live frames re-styled through
  DomainRand's own distribution (24 styles) read share>0.25 0.263-0.579 (s6) / 0.360-0.667 (s7); canonical = 12th /
  29th percentile; style-median 0.439/0.465 ~ sim 0.483. Most of the residual image gap = the canonical palette is
  a low-gate style; DR did not buy invariance. Fix candidates parked (RGB-off arm first choice) behind distillation.
  Trap: sim "as recorded" averages over styles, live is one draw. c2r ~23k, m30k read ~14:20. HANDOFF §5cs.13.
- L47b (2026-09-04 ~11:00-12:00): owner order "spec both distillation teachers and decide". Four legs on the L43
  ceiling instrument (c2r_best, 48 paired seeds, ladder, DR off): policy 37.5%; DOCTRINE whole-match 14.6% / tower
  -1.465 (plays 1.5% of rich decisions -- the ">=8 -> cheapest card" rule nominates the log with no cell and holds);
  SEARCH teacher 79.2% / +0.167; search with reseed-opp 72.9% -> privileged gap ~6pp. Decision: arm D1 = doctrine
  imitation on DRILL STATES ONLY via the existing search-imitation plumbing (DoctrineSearcher, coef 0.5, all three
  heads), init gatec2_m10k, 5k matches, pre-registered drill bar (>=3 of the six 0% drills >40% AND 29-mean +5pp).
  Search teacher rejected as a one-frame distillation target on the ledger's numbers (card distils, winrate +0;
  gate not one-frame learnable; DAgger co-existed with banking collapse). Nothing launched: c2r running, m30k ~14:20.
  HANDOFF 5cs.14.
- L48 (2026-09-04 ~11:30-12:00): owner order "work on the doctrine ... and test the search on the drills". (1)
  RETRACTION of scale: the stock doctrine reads 14.6% on seeds 5000000+ and 33.3% on 5000048+ (policy 37.5 / 43.8)
  -- pooled n=96: doctrine 24.0% / td -1.34, policy 40.6% / -0.94 (paired td +0.400 t=3.46), search 80.2% / +0.29.
  Sign stands, headline was one slice. (2) Search on the 29 drills: doctrine 71.4 / policy 34.2 / search 45.8;
  search 0% on six restraint drills (never_rocket_their_king 80->8) -- the 12-s scorer spends where the verdict
  holds; search-on-drills arm CLOSED. (3) Doctrine loses because it is elixir-starved (0-2 elixir at 82% of
  unanswered pushes), not because of the rich-state freeze (D-1 fixes the leak, td unchanged); hold-after-play is
  WORSE (-0.349 t=-2.58). (4) Search-regret oracle -> rules: tempo bodies on quiet boards + a generic knight/skeleton
  body on uncovered pushes = +0.213 tower t=2.14 pooled 96, same ordering on both slices; still 0.19 tower / 12.5pp
  below the policy. Doctrine not a plausible whole-match teacher; D1 (drill-states-only) spec unchanged. c2r at
  24.2k, EVAL@24k 31%/21%, m30k ~13:25. HANDOFF 5cs.15.
- L48b (2026-09-04 ~12:10-12:50): owner steer -- withdrew the "stop authoring" recommendation (cost judgement, not a
  finding); pre-registered stop = two consecutive rounds < +0.10 tower pooled (96 paired). R1: the tempo knight
  breaks skeletons_stop_the_wall_breakers 92->8 via the drill's spent>4 bar (pre-threat knight + skeletons = 5);
  dropped. R2: d6nok (D-1 + skel cycle + D-6) +0.133 t=1.39 vs stock, drills 70.3 (no hard regression); policy
  +0.268 t=2.46 ahead. R3: D-7 tesla-for-tank -0.024, tesla-for-xbow +0.001 (never fires) -> STOP fires. OWNER
  REPORT CONFIRMED IN ENGINE: crowns() = dead towers; king kill with a princess standing = 2 not 3. Outcomes
  right; crown_delta understated (policy -0.354 read / -0.521 real-CR, 8 of 12 king losses undercounted); reward
  pays per tower. Fix post-c2r; reward semantics (A fix crowns / B report-only) is the owner's call -- report sent
  with --questions. HANDOFF 5cs.16 + bug-ledger row.
- L48c (2026-09-04 ~12:20-12:40): owner ruling (A) -- crowns() fixed in engine.py: enemy king dead -> 3, else
  dead-tower count. Reporting AND reward (take_enemy_tower/lose_own_tower pay x2 on a king-fall with a princess
  up). Landed while c2r runs: workers/eval envs spawned once at start (remote_pool 289-307, train_sim_ppo 156/1117),
  so c2r trained wholly on the OLD count; trap = a --resume after this commit splits the run into two reward
  regimes. Checks: state test 0/1/2/3/3, outcome unchanged, crown_undercount doctrine n=12 engine -0.917 == real
  -0.917, 165 unittests OK. Post-fix crown_delta is a NEW instrument -- never compare against pre-fix tables.
  c2r 25.8k at 12:28, 0.64 ep/s -> m30k ~14:15 (13:25 carried earlier was wrong). Compound drills: never enabled
  or measured (frac 0.0); answer = instrument read next loop, training arm only post-c2r / on a collapsed m30k.
- L48d (2026-09-04 ~12:40-13:15): owner order -- hogeq re-synced to icebow (2f9cd8e..6cca0a0): 12 shared files
  byte-copied (crown fix included), 7 declared-different files hand-ported (lock-aware targets, bot attack floor,
  eage/schema-2 gate prior, cast-delay leads, slot-5 switch, rl_gate_tau, tower anchors, play-again guard, and a
  NEW play.py Log corridor assist = live behaviour change for hogeq, untested on a screen), config keys at icebow's
  values, tools (schema-2 gate_prior, probe, latency timer, watchdog drift detector, real_run_gates), 4 deck-neutral
  tests. NOT ported: nado reach fix, xbow ramp (no bow/nado). Parity strict OK both decks; hogeq suite 1,322 OK /
  64 skip (3 bow-only tests removed). hogeq's OWN schema-2 table fitted (595 replays): quiet 4.6/4.3/5.5% vs
  pressure 8.8/8.8/9.7% at 5/6/7 elixir. "CHEAP CARDS" MEASURED on hogeq best (m2000, 3 seeds, sampled probe):
  mean play cost 2.02-2.05 vs pros 2.61, elixir mean 1.83, >=6 share 0.2%, hog in NO bucket's top-4, P(play) at
  1-3 elixir 0.5-0.56 vs pros 0.05-0.075. --force-bank 4 (1 seed): same card head picks mm 36 / hog 31 / tesla
  30, cost 2.96 -> the GATE is the cause, not the card head; same mechanism as icebow 18k. HANDOFF 5cs.18.
- L49 (2026-09-04 ~13:00-13:35): COMPOUND-DRILL instrument read (drill_compound_frac forced 1.0 in-process; never
  enabled on disk). Verdict fires on every board (0 timeouts), ~12-13 s, 2-3 components. Pass pooled n=96: nothing
  ~1%, doctrine 35.4%, c2r_m20k 26.0%, gatec2_m10k 29.2%; seed band 4-6pp -> checkpoints indistinguishable, doctrine
  6-12pp above. Doctrine's spell/log components 0/N; full-elixir override does not recover them (scarcity
  contradicted). ROOT CAUSE = GRADING: 12 success predicates in drills_icebow.py read e.units board-globally, so
  compound_verdict's per-component tag is dead code -- AND the same unused helper is the only thing hiding the
  drill_noise distractor, which is ON (0.5) in the running c2r and in hogeq (identical pattern, drills_hogeq.py:29).
  Measured on 10 affected drills, doctrine, n=250/arm: noise 0 78.0%, noise 0.5 66.8%, noise 0.5 + grader hides the
  distractor 70.4% -> grading bug ~3.6pp (small, real in sign), behavioural ~7.6pp (bow_defends 72->44,
  bridge_spam 48->20 not recovered). Learner impact untested. Fix (swap to all_enemies_dead/enemy_units, both decks)
  NOT landed: c2r depends on the drill files; its own experiment after m30k. c2r 27,325 eps at 13:20, 0.5 ep/s,
  m30k ~14:50; last-epoch gate drift on PLAY -1.08 (largest of 12) -- watch only. HANDOFF 5cs.19.
- L50 (2026-09-04 14:23-15:3x): THE m30k READ. Snapshot c2r_m30k.pt at 14:56 (log 30050). Sampled-gate probe, same
  instrument as L44/L46: c2r_m30k >=6 share 3.3/5.2/2.3 (seeds 0/1/2) + 3.2/2.5/3.1 (disjoint 3/4/5) = mean 3.3%,
  band 2.3-5.2; reference gatec2_m10k 2.7/3.8/2.4 (mean 3.0, reproduces L46 exactly -- deterministic probe). NOT
  COLLAPSED: no seed <=1%; P(play) 0.16 vs 0.17; play cost 2.7 both. Trajectory m5k 4.0 -> m10k 5.5 -> m20k 1.2 ->
  m30k 3.3: the m20k dip reversed. EVAL@30k ladder 31% / fair 24% (n=150, context only). Decision: no restart, c2r
  runs to 40k (~20:30). Owner Q answered: sandbox engine = measuring instrument, not training env; sim-parity oracle
  step 1 (our sim's crowns-match on the engine's 211 replays) queued next by owner ruling. HANDOFF 5cs.20.
- L51 (2026-09-04 15:2x-15:5x): SIM-PARITY ORACLE STEP 1 (owner-queued). `scratchpad/gauntlet/L51/sim_replay_drive.py`
  drives the crawl's real 20 Hz timelines through OUR sim with the engine's conversion (both sides L11 incl. towers
  3052/4824 = engine, abilities skipped, 40-tick slack). Same 211 tags, same 19,488 plays. Crowns match RoyaleAPI
  sim 55/211 = 26.1% (winner 44.1%) vs the real engine 77.7% / 80.1%; sim==engine crowns 28.9%; engine-clean 135:
  28.1%. ONE-DIRECTIONAL: real winners s1 129 / s0 82, engine 111/100, sim 23/188; side 1 = the X-Bow player in
  211/211. Mirror run (sides swapped) 28.4% with the bias following the deck -> sim symmetric, deck mechanics.
  Not the cause: heroes (no-ability subset 23%), elixir (1.2% of plays needed slack), tower HP, play counts. Sim
  games end earlier (median 180 s vs engine 276 s), 3-crown 58 vs real 20. Caveat: open-loop replay penalises the
  reactive deck first -- but the engine held the real board on the same inputs. Step 2 (engine per-tick diff,
  emulator, after c2r) now warranted. 31 s wall for the set. c2r 31,325 eps, 17 procs. HANDOFF 5cs.21.
- L52 (2026-09-04 15:57-16:3x): ORACLE STEP 1b -- tick-level diff of the two engine-recorded clips (`L52/tick_diff.py`)
  vs a sim per-0.1 s dump. Hog hit 317 = sim 316.8, rocket 1484/342, fireball 172: (c) the L51 hog-damage candidate is
  contradicted. Three measured divergences, each patched in the DRIVER only (`sim_replay_drive.py --patch`): spells
  measure blast to the collision edge (rocket 2.24 tiles kills the X-Bow 1561->71; sim untouched), Tesla/Drill sit on
  tile corners (0.71-tile snap error), hidden Tesla pulls building-targeters on its placement tick. Each fixes its clip
  (both now 0-1 = real). Population, 211 matches: base 26.1% -> spell_edge 26.5, corner 26.5, edge+corner 28.0,
  hidden_pull 26.5 (9 changed), all three 26.5% -- NULL. Damage rate: sim on icebow towers 32.2 HP/s vs engine 16.2,
  on opponent towers 4.2 vs 15.2. 20 sim matches end 3-0 for the opponent before 120 s (real: 20 three-crown matches
  total); skeleton-army in 8/20 (2.6x), skeleton-king 5/9, witch 5/10, goblin-gang 5/17, minion-horde 4/13. Evo skarmy
  clip 08QPVCPC9QQU: sim ghosts pile up while Gerry is never hit, 3-0 at 39.6 s. Priority list for oracle step 2
  written into §6. c2r 32,675 eps, 17 procs, 4 GB free. HANDOFF 5cs.22.
- L53 (2026-09-04 17:25-17:4x): SIM-ONLY SWARM PROBE (`L53/skarmy_probe.py`). Unanswered evo Skeleton Army vs the L11
  princess tower: tower dead at 10 s, 3947 total damage (non-evo 2279, tower survives at 773). Knight in front of the
  tower: evo 3947 -> 3947 (changes nothing), non-evo 2279 -> 407. Ice Wizard: evo -> 0 (splash kills Gerry at 3.1 s,
  ghosts vanish). Gerry trails 2-4 tiles behind, first shot by the tower at 12.2 s after the last live skeleton dies.
  `shadow_skeleton_speed_tiles: 1.0` in cards.yaml is read by nothing -- ghosts run at 1.5 t/s (wiki Medium = 1.0);
  driver patch `--patch shadow_speed`: 3947 -> 3785, population 55/211 -> 55/211 NULL. Clip 08QPVCPC9QQU: the pro's
  Ice Wizard lands inside 10 live + 5 ghost skeletons and dies in 0.7 s in the sim; the real one stopped the push --
  the real pack's position at 25.3 s is the first thing oracle step 2 must read. Crowns-match by opponent deck: any
  skeleton-army 3/32 = 9.4% vs 29.1% rest; other swarm 20.5%; none 31.4% -- side-0 bias in every subset (112/140
  sim side-0 wins vs real 55/140 even with no swarm card). c2r 35,000 eps, 17 procs, 4 GB free. HANDOFF 5cs.23.
- L54 (2026-09-04 18:07-18:2x, OWNER ASK: early stop?): m35k read, same instrument as m30k (`gate_prior_probe.py`,
  seeds 0-5): >=6 share 1.1/1.6/1.4/1.4/0.9/1.2 mean 1.3% (m30k 3.3%, m20k 1.2%, gatec2_m10k 3.0%); P(play) 0.20 and
  elixir mean 2.5 = the m20k signature (spend mode, visited twice; hold mode m10k/m30k visited twice). Collapse rule
  NOT met. Internal EVAL flat 12k-36k (ladder avg-5 28-31, fair 19-21), new BEST at 36k is 30 -> 31 = noise; per-4k
  training winrate 10.2/9.7/8.9%; drill pass-all 45-47% since 8k; entropy 0.05-0.08. Verdict: early stop justifiable,
  recommended (banked _best.pt at 36k, ~2 h of box for oracle step 2); irreversible, so put to the owner. State
  recorded: 36,100 eps 18:11, 17 procs, 4.2 GB free. HANDOFF 5cs.24.
- L55 (2026-09-04 18:18-18:4x, OWNER: stop c2r + "why oscillating" + "tesla in one tile"): c2r killed at 36,375 eps
  (17 -> 1 python procs, Nucleo untouched, 6.8 GB free; _best.pt = 36k ladder avg-5 31%, backed up to
  data/bench/c2r_best_36k_backup.pt). Live play_logs (36 matches, 1 W): tesla cell 235 x39/101, x_bow 235 x63/85.
  `policy_rl.pt` == c2r_best (max |diff| 0.0). Sim placement probe (`L55/place_probe.py`, greedy card+cell as
  play.py), c2r_best seeds 0-2: tesla -> cell 234 (row 13, col 0, left riverside corner) 52/82 = 63%, x_bow 21/34,
  tesla_evo 19/27, skeletons -> 423 (front of king) 153/154. LEARNED IN THE SIM, deployed unchanged; the 30% ladder
  was earned with it (scripted bots do not punish it). Oscillation: >=6 share 3.9/5.5/1.2/3.3/1.3 at m5k..m35k, all
  else flat 8k-36k, entropy 0.06, cell_struct 3350-5235x, gate PLAY drift negative in every batch on 5-20 play
  samples -- cause (b): no exploration left + gate updated from a handful of plays. Next: sim Tesla-outcome probe
  (corner vs centre), then an exploration arm from c2r_best. HANDOFF 5cs.25.


## L56 (2026-09-04) -- Tesla-outcome probe: the sim does not reward the corner (nor punish it)
- Ran `L56/tesla_probe.py` on c2r_best (play.py greedy rule, tau 0.25, no search): 4 arms x 24 matches x
  2 seeds, only the Tesla cell forced. Per-Tesla damage (upper bound), pooled: own 954 / corner(234) 1040 /
  lane(274) 690 / centre(314) 1157; per seed corner vs centre 1014 vs 1225 and 1070 vs 1067 (95% CIs +-170,
  overlapping both seeds); lane below both on both seeds (CIs disjoint). Kills/Tesla 1.64/1.75/1.26/1.64.
  Match level all noise (W 14/16/10/10 of 48). (a)
- Scripted bots cross RIGHT 55-64% of the time (8/8 arm-seeds); corner Tesla covers the left bridge only. (a)
- Placement history (place_probe seed 0): gatec2 m5k 14 distinct Tesla cells -> m10k 234 at 23/29, x_bow 234
  9/9; c2r resumed that lineage (cell head saturated raw |81|, RAIL GUARD rescale) and kept it 13/30 -> 27/31
  -> 63%. aggro1 locks 347/233, gate05 327: one cell per card in every arm; skeletons@423 in every checkpoint. (a)
- Verdict: the placement landscape is flat between corner and centre in the sim; 234 is a drift-and-stick of
  a coupled cell head (one `cell_conv` for all cards), not a sim payoff. Exploration alone cannot fix it. (b)
  Hypothesis for why 234 specifically: X-Bow reaches the left princess tower from there (10.4 <= 11.5). (b)
- Retract L55 (b) "the sim rewards the corner"; lane cell 274 is worse, not better. (c)
- Next: read the human Tesla/X-Bow cell distribution from the replay corpus (tools/replay_priors.py) -- how
  far off is 234 from what players do -- then spec a placement-prior arm (one change). Exploration arm parked.
- Box idle throughout (1 python proc = Nucleo). HANDOFF §5cs.26.


## L57 (2026-09-04) -- pro placements vs the locked cells; hidden_pull does not un-flatten the sim
- Pro corpus (12,220 blue plays, §5ag): X-Bow modal (15,19)/(2,19) = 48% lane bows; the policy's corner
  X-Bow tile (1.5,18.5) has 24% of pro bows within 1.5 tiles (50% lane-mirrored) -> the X-Bow cell is
  pro-correct to ~1 tile. Tesla: pros x=9 centre 48%, x 6-11 81%, y 18-22; policy tile = 2.0% of pro
  Teslas. Skeletons 4.9%, Knight 2.2%. (a)
- L56 probe rerun with the L52 `hidden_pull` mechanic: pooled dmg/Tesla own 1033 / corner 935 / lane 966 /
  centre 1029, all CIs overlap; lane rises 690 -> 966, corner = centre unchanged. (a) Missing pull is not
  why the sim is flat. (c)
- Decision to owner (STOP): fitted pro placement prior as a KL term on the cell head from c2r_best (mechanism
  stated: direct gradient, no reward difference needed -- unlike the 3 failed rollout-sampling priors), or
  opponent-model work, or neither. HANDOFF §5cs.27. Box idle.


## L58 (2026-09-04) -- radius-graded reward step 0 built + validation gate; two retractions
- Built `geometry_reward.py` (P1-P7, bridge block, tornado away/king), 19 tests OK, `sim-view --radii`
  overlay (flag off byte-identical). Commit c642a73. Nothing wired into env.py yet.
- RETRACTED (c): the corner X-Bow (1.5,18.5) DOES reach the enemy princess (`_gap` 10.67 < 11.5; a
  deployed bow damages it 4858->4568 in 6 s). L57/§5cs.27 and doc rev 1-3 said it does not (stale
  engine comment). RETRACTED (c): the locked troop cells are (9.5,31.3)/(12.5,31.3) behind the king,
  not (9.3,24.1)/(11.8,24.1) (cell_center mis-conversion); pro skeletons within 1.5 tiles = 8.9%, not 4.9%.
- Gate on 211 pro replays (5,825 blue plays): pro tile beats the locked tile on the equal-weight SUM for
  tesla 63/19, tornado 69/29, knight 51/9, ice-wiz 44/22, skeletons 40/22, log 34/32, rocket 16/65, x-bow
  11/83. Doc §3 rule drops nothing (modal Tesla vs corner on 350 Hog/Giant/PEKKA boards: SUM 88%/6%).
  Against the pros: P2 on troops (2/23) and spells (rocket 1/71), P7 on skeletons (0.1/7.6); building P5
  has no placement gradient; snapshot P1 fires on 41% of pro Teslas only. (a)
- Policy (c2r_best, 3 seeds x 24, 2,485 placements): SUM mean 0.828 -> w 1.21 raw; restricted sum 0.430
  -> w_geom 2.0 (cap). Rocket never played at tau 0.25. Linear probe: trunk holds ROLE-level enemy
  identity (39% vs 26%), not card (12% vs 6%) -> no obs change in run 1 stands. (a)
- Next: step 1 = restrict terms (P2 buildings only, P7 not swarm, building P5 = timing term), path-based
  P1, wire into sim/env.py with w_geom 2.0, then arms G / G+E. HANDOFF §5cs.29. Box idle.
- Flag: `config.yaml rl_epsilon_start 0.50 -> 0.85` is modified on disk (18:32 today, not by this
  session, not committed) -- left untouched.

## L59 (2026-09-05 00:0x-05:0x) -- step 1 wired (arm G), worker config seam fixed, ARM G LAUNCHED 04:49
- Owner (04:2x): full autonomy overnight on the radii work; decisions on their behalf, recorded in §5cs.30.
- `geometry_reward.py`: P2 buildings-only, P7 off for swarm, PATH-based P1 (pull_ok), placement_credit in
  [-0.3, 1.0]; `sim/env.py` +131: graded credit w_time*P5 + w_geom*place*gate paid only when place > 0, X-Bow
  w_wincon*P6, geo_* record-only ledger; `env.geometry.enabled false` = HEAD reward to 1e-9 (2 matches). (a)
- Gate rerun: path P1 fires on 53.3% of pro Teslas (snapshot 40.9%, n=807); modal (9,21) 0.543 vs corner 0.143.
  Hog-vs-Tesla scenario: graded pays +2.85..+3.0 at hog tile 14.7-17.1, 0 at 18.3+; the old binary paid +1.0
  at 18.3/20.7 and 0 in the pull window -- DISJOINT windows. Pre-placed Tesla still unpaid (env sees no threat
  on the enemy half) -- parked doctrine change. (a)/(b)
- SEAM FIX: `remote_pool._worker` re-read config.yaml from disk -> every env-side `--config` key and
  `--drill-only` never reached the workers. Config records .source; workers load the parent's yaml; proven via
  the real CLI with --workers 1. c2r unaffected (its one env-side difference resolved equal). Commit 794d030.
- Found, not fixed: `_trade_reward` keyed by id(u) -> elixir_trade flips 1 step in 512 across processes. (a)
- ARM G launched 04:49 from c2r_best (sha verified), c2r's exact CLI + `env.geometry.enabled true` as the ONE
  change; rail guard x0.0430 (raw 105); early curve = c2r's resume shape (avg_rew -29/-34 vs -31/-31). Detached:
  trainer, ppo_watchdog, `L59/arm_gates.py` (m5k/10k/20k snapshot + place_probe x3 + geo_ledger_probe x2 +
  gate_prior_probe -> Discord). Baseline (c2r_best under the arm reward, seed 0): tesla scored 24 paid 2, mean
  P1 0.039; skeletons 53/0. (a)
- DECISION: G runs alone (9.7 GB RSS, 1.1 GB free); G+E / E queued, yamls + launchers ready. Read at m5k
  (~2.5 h at 0.6 ep/s), m10k. One seed = screen; three before any claim.

## L59b (2026-09-05 05:1x-05:4x UTC) -- owner: credit is an AND gate; armG v1 stopped, v2 relaunched 05:13 UTC
- Owner (05:0x): "timing + placement payment should be 2-way ... basically an AND gate, but with some nuance";
  Chrome may be closed. `_geo_credit` -> `(w_time + w_geom) * place * P5 * gate` when place > 0 (v1 was
  `w_time*P5 + w_geom*place*gate`, which paid a perfect placement at P5 0.07 +2.07). +5 unit tests, 34 OK,
  disabled path still byte-identical. Scenario: +2.54/+3.0/+3.0 at hog tile 14.7/15.9/17.1, 0 elsewhere --
  same window, early row scaled. Baseline c2r_best s0: same 23 fires, credit sum +38.5 (v1 +47.9); tesla
  paid mean +0.84 (v1 +1.56), P1 0.039 unchanged. (a)
- armG v1 stopped at 725 eps (10%, avg_rew -15.9), procs 19 -> 1; checkpoint re-seeded from c2r_best (sha
  d209b41e verified x3). v2 relaunched 05:13 UTC, same CLI, rail guard x0.0430 identical; 125 eps -21.6, 0.7 ep/s.
- Chrome closed (30 -> 0): available 11.0 GB idle -> 3.6 GB with G running = one arm costs 7.4 GB. G+E still
  does not fit; half-size arms rejected (--envs sets the PPO batch = a second change vs c2r). DECISION: G alone.
- m5k ETA ~07:1x UTC via detached arm_gates.py (posts to Discord). Next: read m5k vs the AND baseline.

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

## L60 (2026-09-05 13:4x-14:4x UTC) -- owner pivot to IL: audit, crawl wave 3 (+88), BC dataset v1 (6,922 pro placements), c2r_best pro-cell agreement 3.3% / 10.9%
- Owner: "going in circles ... give imitation learning a chance ... sim gradient toward pro play case by
  case ... crawl players you haven't mined". Answered with labels (HANDOFF §5cs.33): flatness measured
  (10 days, 25-39% band, cell head re-collapses every arm), circle diagnosis (b): saturated start + a sim
  where pro play loses (26.1% vs 77.7%). IL yes; "case by case" needs a similarity rule = a model;
  kNN over a learned embedding vs a BC net, both to be scored on held-out replays. Sandbox engine already
  runs here (§5ax) -> route 1 = engine states for BC v2.
- Killed hung stt.ps1 PID 22200 (avail RAM 1.31 -> 3.40 GB). Crawl wave 3: +88 replays (608 total, 46
  players done, 4 rate-limited for retry), plays_ext 52,587 rows. (a)
- BC dataset v1 `icebow/data/bc_pro/` (L60/build_bc_dataset.py): 6,922 samples / 268 replays, blue only
  (icebow is blue in 268/268), split 228/40 replays. Baseline c2r_best top-1 3.26% / top-5 10.92% (chance
  0.63/3.1); the_log 11.4/37.6, tesla 0.7/2.8, x_bow 0.0/0.3; top-1 on cell 235 27% of the time. (a)
  Caveat: sim-reconstructed boards, 43.5% of pro plays fall after the sim's own end.
- Arm E running (2,200 eps, m5k ~15:1x UTC). Question open: stop E after m5k for the engine work?

## L60b (2026-09-05 14:5x-15:3x UTC) -- kNN vs BC vs baseline on 1,004 held-out pro placements: board-blind card prior 13.65/40.04 is the bar; c2r_best 3.49/11.75; trunk embedding near-constant; cell head at the tanh rails
- Same val rows, pro card's masked map. Card prior (no board) 13.65 / 40.04. kNN raw-PCA-256 k=15 gauss
  16.24 / 36.16 (+2.6 pt top-1 ~2 SE, marginal; never beats the prior on top-5 below k=150). Trunk
  embedding z is the WORST key (12.15) and near-constant: pro-to-pro NN cosine median 0.991 vs raw 0.562.
  BC head-only 8.27/8.27/8.37 (3 seeds), trunk ft 8.47 -- below the static prior; x_bow 0/91. (a)
- MECHANISM: c2r_best cell head at the tanh rails, 92.4% of masked raw logits |raw| > 8 (mean -23.6),
  gradient 1e-2..1e-6 -> PPO cannot move it; head-only BC without repair returned the untouched checkpoint.
  Shipped BC ckpts rescale cell_conv.4 /10.36. (a) Prior nulls §5ae/5am/5ao may be dead-gradient artefacts (b).
- Unresolved: uninformative boards (26% sim) vs stereotyped deck -- separators: real-record-feature
  conditioning (cheap), engine dataset v2. Also untested: coordinate channels / prior-initialised bias.
- Owner: stop E after m5k (E at ~2.6k eps, m5k ~15:5x UTC); then engine work.

## L60c (2026-09-05 14:1x-14:2x UTC) -- arm E read at m3.85k and STOPPED (owner order): entropy floor did not resist the collapse
- E snapshot m3,850: knight@426 35/39, 35/37, 35/40; tesla distinct 8/6/4; pro-cell agreement 2.59/9.36
  (baseline 3.49/11.75); cell head 82.4% at the tanh rails 3,850 matches after the guard's x0.043 rescale.
  (a, one training seed) Worse than the baseline and than G at m5k on every placement metric -> stopped
  at 3,975 episodes (14:19 UTC), python 21 -> 3, 9.8 GB available. No winrate eval (wrong instrument, wrong sim).
- New instrument: `L60/rails_read.py <ckpt>` = fraction of masked raw cell logits |raw| > 8 on the val split.
- Next: sandbox engine per-tick state -> obs renderer -> BC dataset v2; engine throughput measurement.

## L60d (2026-09-05 14:3x-14:5x UTC) -- board-value separators: real context adds <= +1.9/+4.7 over the card prior; prior-initialised bias map is the first BC above the prior
- M1 real-record context vs prior 13.65/40.04: time 12.95/38.94, engine elixir 14.54/41.93, opp last card
  13.45/37.85, opp last tile 15.54/44.72 (best), NB combo 15.44/42.13, real-vector kNN k=50 15.84/43.53.
  (a) Same size as the sim-board kNN gain (+2.6) -> the small board gain is not "wrong boards"; for this
  deck's placements the per-card prior is nearly everything; opponent's last lane/row is the one live feature.
  Card choice / timing NOT measured -- the "case by case" claim is untested for those heads.
- M2 head-only BC: coord channels 9.76/28.29 (x_bow 0/91 still); per-card bias map [10,432] init from the
  prior 15.44/46.61 (s1 16.24/46.41, s2 15.14/46.51), val CE 3.52 vs prior 3.88; coord+bias 15.54/46.91;
  bias only (convs frozen) 12.75/40.94. Source head's logits at epoch 0 DEGRADE the prior (9.16/32.47).
- Consequence: the policy needs `cells + cell_bias_map[None]` (4,320 floats) before the tanh cap -- a
  model.py change (not env.py), owner's call. Checkpoints carry it as `bc_pro_extra`.
- Next: L61 engine dataset v2 (running) -> re-score on engine boards; then the model change + BC init.

## L61 (2026-09-05 14:2x-15:0x UTC) -- BC dataset v2 from the REAL engine; checkpoint equally bad on real boards; sim-trained bias-map heads transfer; engine throughput measured
- 211/211 replays re-driven with full observe before every play: hashes identical to 5ay, 17,901 play frames, 2.34 s/match
  median with recording. Adapter (FakeEngine into SimMatchEnv._update_vectors) -> icebow/data/bc_pro_v2/: 9,444 samples,
  101/101 names mapped, 0 dropped; train 8,111 / val 1,333 (v1 split restricted). Sim vs engine at the same play:
  enemy bodies -0.74 (sim keeps more alive), towers-alive agree 70.7%, elixir +0.16.
- v2 val: c2r_best 2.78/11.10 (paired same-play: 3.12/10.75 engine vs 3.35/11.33 sim -> NOT a sim-board artefact);
  prior 12.08/37.66; kNN k15 14.03/37.28, k50 15.38/44.49. Sim-trained bias-map heads on engine boards 15.00/43.51,
  14.63/44.11, 14.93/43.44 (+2.6-2.9 top-1 ~3 SE, +5.8-6.5 top-5 ~4.5 SE over the v2 prior); trained map alone 10.58 ->
  the convs add +4.4 on real boards. x_bow 31-34% top-1 (c2r_best 0).
- Throughput: plays-only 2,800/h/slot; every-10-tick observe 920/h; every-2 260/h; 2 slots one VM 1,516/h (4.26 GB);
  direct RPC observe ~2 ms (5ay's "~20 ms" was adb -- retracted). Sim trainer ~2,880 matches/h on 16 cores (5cs.35).
  Opponent for an engine environment is unsolved (ghost / self-play / script) -> owner question.
- VM stopped. Next (after owner): model.py bias map + BC init + PPO with control; wave-4 crawl roster meanwhile.

## L61b (2026-09-05 15:2x-15:5x UTC) -- owner rulings applied: bias map in model.py; bcA (PPO from the BC init, control) LAUNCHED; crawl wins-first
- Q1 yes -> `PolicyNet.cell_bias_map` (78e14aa): old checkpoints bit-identical, native BC heads reproduce v1/v2 numbers exactly,
  suite 1,336/1,337 (1 pre-existing). Rail guard cell criterion max -> p99 (would have shrunk the BC init's convs x0.2).
- bcA launched 15:5x UTC: init bc_bias_native_s0 (15.44/46.61 sim, 15.00/43.51 engine), c2r config, one change = the init.
  Guard: "raw p99 9.5 within 2x cap -- left as loaded". Reads at m2k/m5k: does PPO keep or erode the pro agreement?
- Q2 (owner): mine ~10k icebow replays 10k trophies -> top, wins first; IL + 10k-deck pool + trophy-range ghosts + self-play
  opponent. Pushbacks: pro-weighted IL teachers; general-deck opponent needs a card-identity head; league not pure
  alternation; losses are the opponent-side signal; supply/rate unmeasured (~2 replays/min this wave).
- Wave 4: roster 50 -> 150, 1,445 battles, 834 replays queued, relaunched wins-first.

## L61c (2026-09-05 16:2x-16:4x UTC) -- bcA m2k: PPO erodes the BC init and re-saturates a HEALTHY head in 2,000 matches
- Pro agreement 15.44/46.61 -> 6.47/21.12 (v1) and 15.00/43.51 -> 6.98/20.11 (v2); rails 83.8% (p99 72.7) from p99 9.5 at load.
- Mechanism: bias map untouched (corr 0.9995, |d| mean 0.012); cell_conv.4 grows |d|/|w0| 0.777 -> the board-conditioned
  residual swamps a prior whose max entry is 5.32. Retracts 5cs.34's reading that the frozen head was the CAUSE of the
  circling: it is the consequence of this gradient. (a, one seed)
- Leading hypothesis (b): the sim reward prefers non-pro placement (pro play loses in our sim), so any PPO here erodes any
  pro-like init. Settled by bcB (same init + per-board KL-to-pro-prior) vs bcA at the same m.
- bcA continues to m5k as the control. New instrument L61/read_ckpt.py (both val sets + rails in one call).

## L62 (2026-09-05 17:0x UTC) -- owner: "kill bcA now and start the engine training". Sim PPO retired from the training path
- bcA killed at 2,550 eps (4% wr, state in L61/bcA_stop_state.txt), python 17 -> 3, 11.06 GB free. bcB (KL on the sim)
  NOT built -- the KL term moves to the engine env.
- Engine env v0 under construction in scratchpad/gauntlet/L62/: EngineMatchEnv (SimMatchEnv interface, ghost opponent,
  0.5 s decision cadence, engine-only unshaped reward) + ghost pool from the mined battles. Key v0 diagnostics:
  s/match with a policy in the loop, ghost rejection rate as the match diverges, deck/rating coverage.
- The sim survives as the obs RENDERER (the adapter drives _update_vectors) and as the fast smoke env; its reward and
  opponent are what is retired.

## L62b -- 2026-09-05 17:3x UTC -- ghost pool built; owner's Q2 targets measured against the corpus
- Pool: 447/1,148 battles convert (337 W / 110 L), 314 distinct opponent decks (259 once), 437 humans, 45 ghost plays/match.
- (c) 10,000 distinct decks NOT reachable by mining: whole corpus 715 decks, 0.56 new/battle and falling (~20-30k battles, extrapolated).
- (c) No trophy-range coverage: 434/447 Path of Legend (no trophy number), no opponent rating column at all, 81% in one 500-pt band.
- Cheapest 2x: crawler x/y backfill -> +473 battles, +273 decks (574 replays carry no positions at all).
- Ghost reactivity: 59.4% of ghost plays within 3 s of an icebow play vs 51.5% null -> ~1 in 12 is a reaction replay destroys.
- Holes: 5.0% of ghost actions are ability presses the driver drops; 0/447 timelines reach overtime; hand never unique (median 256 deals).
- Collision: env agent's 202-row pool overwritten at pool.jsonl -> env builder moved to pool_env_v0.jsonl. Trap: disjoint OUTPUT paths per agent.
- Owner ask: sim_view debugger -> engine. Yes, one renderer two feeds; radii/P1/term readout carry over via the L61 adapter; agent dispatched (L62/engine_view).
- Outlook: env agent still running (s/match, rejection-vs-time, determinism); then PPO-on-engine + KL control pair. Supply probe for trophy-road players is now mandatory before any "10k replays" promise.

## L62c -- 2026-09-05 17:5x UTC -- EngineMatchEnv v0 built and measured
- SimMatchEnv-interface env on the real engine; obs = L61 adapter; ghost = recorded human commands; unshaped engine-only reward.
- (a) inverse cell<->(x,y) exact 9,368/9,368; determinism 3/3; 1,159 matches/h one slot, 1,847/h two slots (BC policy in loop, CPU; cuda not faster).
- (c) RETRACTED the "rejection rate = divergence" diagnostic: all rejections are the end-of-battle gate; 0 game-state refusals in 799. Ghosts go STALE and RUN OUT: 50% of ghost commands never fire.
- Engine rule: no deploys before tick 90 (4.5 s countdown); episodes start at tick 90.
- Sanity 40 matches greedy BC: 4W/36L, 168.6 s mean; humans went 26W/14L on the same battles. Baseline.
- Limits: fixed seed 424242, levels 11, no ghost reaction, PPO-on-unshaped-reward untested.
- Next: standalone engine PPO driver; pair control vs KL-to-prior, one slot each, same init/seed; grade by pro agreement.

## L62d -- 2026-09-05 18:1x UTC -- sim_view debugger on the engine (owner ask)
- One renderer, two feeds: L62/engine_view.py builds an EngineView the unchanged render_frame accepts; radii/P1/term readout intact; 52/52 sim_view tests.
- (a) pixel checks: tower px error 0 vs SimMatchEnv, mirror exact, radii +5,197 px, P1 band +42,603 px; 1.74 ms/frame; 0 unmapped over 211 recordings.
- (a) FIRST GROUND-TRUTH READ OF THE RADIUS TABLE: engine reach is centre-to-target-EDGE; table right to 0.1-0.35 for cannon/x_bow/tesla/ice_wiz, but drawn rings + reward P-terms use bare reach -> 0.5-1.0 tiles short. Princess tower first shot 8.48 edge (>= acquisition), table 8.0, wiki 7.5.
- (c) lingering zones NOT in the bridge's effects (23,169/23,169 frames effects==projectiles). (a) recorder dropped target/timers/ability/level -- one-line recorder change + re-record recovers them.
- (b) kind 14 = "cannot act" (also flips on frozen/knocked bodies), not only deploying -- the policy obs deploying channel inherits this.
- Not wired to the live env yet (next: one render call per decision on EngineMatchEnv; ghost staleness marker).

## L62e -- 2026-09-05 18:0x UTC -- first PPO on the real engine launched (owner order)
- Pair live 17:49:44 UTC: control kl 0 (PID 31628, port 38031) vs KL-to-frozen-init 0.3 (PID 54320, 38032), seed 41, same tag sequence, from bc_bias_native_s0 (m0 checkpoint reproduces the init exactly 15.44/46.61, 15.00/43.51).
- (a) FINDING: bcA-style critic warm-up on the SHARED trunk moved both arms ~1.15 nats cell-KL from the init before any policy gradient (control raw p99 13.6 vs init 6.3 at m=48); the KL arm recovers to 0.08 within 3 updates. Kept running (shared drift, coef still the only difference). --kl_in_warmup added for re-runs; trunk-frozen warm-up parked.
- (a, contended) ~12 s/match/arm -> m250 ~18:40 UTC, m500 ~19:30, m2000 ~00:30-01:30 UTC Sep 6. Free RAM 2.2-2.5 GB with both trainers.
- Owner (18:2x UTC): "reverse engineer the remaining features [buffs/zones], you have my permission" -> RE agent dispatched, host-only phase (static on the 5ax dump + bridge patch + build), VM phase after the pair; generic buffs[] / area_effects[] export is the target, not 7 separate hunts.

## L62f -- 2026-09-05 18:4x UTC -- m250 grade separates the arms; bridge RE done
- (a) m250 pro agreement (read_ckpt, both val sets): control kl 0 = 11.25/32.97 (v1), 10.95/33.53 (v2) -- DOWN 4.2 top1 / 13.6 top5 from the init, bcA's collapse on schedule. KL 0.3 = 16.73/44.02 (v1), 16.28/42.69 (v2) -- top1 ABOVE the init (+1.29/+1.28), top5 held, rails lower (p99 8.9 vs 9.6). Arm gap +5.48 top1 / +11.05 top5. Not pinned, not collapsed.
- (a) The control loses the low-frequency cards first: rocket 1.9/18.9 vs KL 13.2/32.1, tornado 1.4/5.6 vs 2.8/22.2.
- Limits: one checkpoint, one seed, one coef; the across-seed band is unmeasured; the arm gap is far outside any plausible band, the +1.3 top1 rise is not. m500 ~19:30 UTC.
- (a/c) Bridge RE (owner-authorised, static only, sandbox commit 81e5dff): area effects are the 3M global-id series, NOT 4M -- the v1 gate was listing projectiles twice, which is exactly §5cs.43's effects==projectiles measurement, reached independently. No freeze/stun flag exists: "frozen" is a buff with -100 HitSpeedMultiplier, so a generic buffs[] export is the only faithful one. Buff manager = component[3], instance 0x70 B with remaining/total ms; AEO vtable 0x19691f8 with side/x/y/elapsed/life/radius.
- v2 bridge built (9b63a7a0) but artifacts/ deliberately restored to v1 (82887463, verified) -- the worker pool redeploys by hash on service start and would restart the live trainers. Verification runbook re_verify_bridge.py written, NOT run.

## L62g -- 2026-09-05 19:1x UTC -- RETRACTION: the play gate collapsed; pair killed and relaunched with the pro gate prior
- Owner watched engA_kl_m253 in sim-view and said it rarely plays. (a) Measured, same instrument (sim, greedy, tau 0.25), 16 matches: init 36.2 plays/match, p(play) max 0.63, crosses tau 22% of decisions; ctrl_m250 1.12 plays/match, max 0.34, 3.6%; kl_m253 **0.12 plays/match, p90 0.2325 max 0.2326, crosses tau 0.0%** -- the gate is a near-constant parked under the threshold. Not masking: 4.0 affordable cards at 100% of decisions (init 1.11 at 59%), plays at 9.5 elixir. 9 of 10 cards never played.
- (c) RETRACTION of L62f's reading: read_ckpt scores the per-card CELL map conditional on a play and never touches the gate, so it graded the aiming of a policy that does not shoot. The arm gap stands for the cell heads; "KL arm beats the init" does not stand as a claim about play. TRAP: every conditional metric needs an unconditional companion.
- (b) Cause, and it is my design error: engine_ppo.py dropped ppo_gate_prior_coef 2.0 as "doctrine/scaffold". It is not doctrine -- it is a Bernoulli CE on the GATE HEAD ONLY toward the pro P(play | elixir, phase) table fit from 519 replays / 23,620 plays. bcA had it. The engine run changed environment AND removed the scaffold: two changes.
- Kill (owner ruling): both arms at m=422, taskkill on 4 PIDs, python procs 7->3, crawler/Nucleo/qemu untouched, free RAM 2.4->8.6 GB, engA checkpoints kept as evidence.
- Relaunch engB: gate prior 2.0 in BOTH arms (kl_coef 0 vs 0.3 still the only variable), new prefixes/logs, new p_gate / frac_gt_tau / gp_ce readouts in the update line so a collapse is visible next time. Not bundled: explore floors, warm-up fix, kl retune.

## L62h -- 2026-09-05 19:5x UTC -- engB relaunched with the pro gate prior; the gate is alive
- (a) Update 1, BOTH arms identical (determinism check: same init/seed/ghosts, only kl_coef differs): p_gate 0.2157, p90 0.3815, frac_gt_tau 0.3208, gp_ce 0.5050, gp_target 0.0784. Killed engA KL arm was frac_gt_tau 0.0000.
- Patch verified offline by the agent: gate-head-only gradient (gate |grad| 33.93, card_head/cell_conv grads None), lookup unit check 27/27, coef 0.0 byte-for-byte equal to the pre-patch file, m0 reproduces the init exactly (all 27 model + gate tensors torch.equal).
- (a) Calibration: a gate MATCHING the prior sits at frac_gt_tau ~0.05-0.10 (only 8.14% of the table's 212,265 windows exceed tau; the largest single-elixir entry is 0.2033 < 0.25). So the number should FALL and settle there; alarm stays "heading to <=0.02". The prior's real job is restoring STATE DEPENDENCE (targets span 0.010-0.459).
- (b) Unfixed by design: the table is fitted at dt 0.6 s, engine_ppo decides every 0.5 s (~20% more plays/s than pros). Same in both arms, does not confound. Parked.
- THREE launch failures, all recorded as traps: (1) my taskkill /T on the engA trainers killed the in-guest WORKER SERVICES too -- restart them before any launch; (2) a multi-line `python -c` preflight mangled by Windows arg passing; (3) that preflight then reported a FALSE death (observe() with no battle -> IndexError) while the service was healthy -- a liveness probe must exercise the caller's own path.

## L62i -- 2026-09-05 20:1x UTC -- owner's 432->576 grid claim TESTED: contradicted, and 576 would cause the failure
- (c) 432 does NOT snap x-bows back a tile. Measured on all 2,617 real pro x-bow placements through the trainer's own ActionSpace: row pitch 0.499 tiles (NOT 1.333 -- the grid spans 19.7 tiles, not 32; actions.py's "one cell per board tile" docstring is stale), mean |dy| 0.097, p99 backward 0.304.
- (c) 576 would NOT fix it and makes things worse: pitch 0.374, mean |dy| 0.289 (3x worse), mean backward -0.155.
- (a) FUNCTIONAL test, 240 pro x-bows within 13.0 tiles of an enemy princess tower: 432 puts 0 out of reach (worst distance added +0.000); 576 puts 132 of 240 = 55.0% OUT of reach. Cause is PHASE not resolution -- pros place on the half-tile lattice, 0.499 aligns with it, 0.374 does not, and an offensive x-bow sits AT the range boundary.
- (b) The observation is real but the cause is elsewhere: it was seen on engA_kl_m253, the COLLAPSED checkpoint (0.12 plays/match, cell head 1+ nat off the pro prior). At 0.499 tiles/row a ONE-CELL policy error is ~0.5 tiles = exactly the symptom.
- (b) Phase-preserving alternative if finer control is ever wanted: 48 rows = 0.25 tiles (864 cells), still on the half-tile lattice. Not now -- n_cells is baked into the BC init, both val sets and every checkpoint, so a grid change is a full IL re-fit, not a flag.

## L62j -- 2026-09-05 20:1x-20:4x UTC -- engB m250 graded on three instruments (HANDOFF §5cs.49)
- read_ckpt: engB control 7.47/26.79 (v1) 6.83/26.86 (v2) -- collapsed FASTER than engA's control (11.25/32.97); engB KL 16.33/44.02 / 14.25/42.76 -- at the init (15.44/46.61, 15.00/43.51), not above it. Arm gap +8.9/+17.2 (v1), driven by the control's fall.
- Gate ALIVE both arms: engine p_gate 0.058-0.085 vs gp_target 0.09-0.11, p90 0.10-0.16, gp_ce flat 0.30-0.35; sim probe p50/p90/max 0.152/0.201/0.245 (ctrl) 0.194/0.241/0.318 (KL) -- state-dependent, unlike engA's constant 0.2325.
- Under the deploy rule tau 0.25: control 0 plays/710 decisions, policy-stats 0.1 plays/match; KL 1.5/match (policy-stats, 16 m) vs 21/match (gate_probe, 3 m) -- same rule, 20x swing = tau sits at the gate's p92-95, threshold decides, not policy.
- RETRACTION: the §5cs.47 alarm "frac_gt_tau < 0.02 = prior failed" was wrong -- only 8.14% of pro windows exceed 0.25, a working prior produces exactly that. Diagnostic = p_gate vs gp_target + p50/p90/max spread.
- BC init on engine boards (live_view selftest, agent): p(play) mean 0.47, 87% > 0.25 -- 4x the pro rate; it looked active because it was miscalibrated.
- Owner question posted: deploy rule -- sample the gate (rec.), calibrated tau ~0.10, or keep 0.25. Not changed.
- Visualizer agent restarted (accidental stop) -- resuming from live_view.py + template + payload; artifact not yet published.
- Next: m500 grade ~21:15 UTC (same three instruments); publish the live artifact when the agent returns.

## L62k -- 2026-09-05 20:4x-21:1x UTC -- deploy-rule ruling applied + live engine visualizer published (HANDOFF §5cs.50)
- Owner: "(1) sample the gate; if that doesn't work try (2) tau ~0.10". New src/clashrl/gate_rule.py (ONE GateRule for sim_view, policy_stats, cli drill helper, gate_probe); config sim.ppo_gate_rule: sample; play.py + sim trainer greedy bench untouched. 15/15 sim_view tests; threshold path reproduces §5cs.49 exactly (63 plays).
- Under SAMPLE (sim, 16 m, seed 4242): init 36.6 plays/match, engB control m250 17.2, engB KL m250 24.5 (were 0.1 / 1.5 under tau 0.25). Only rocket never played (was 9 of 10 cards). Sampled p(play) lower (0.12 vs 0.19) because the policy spends -- gate is elixir-conditioned.
- Visualizer agent restarted from disk, finished: artifact https://claude.ai/code/artifact/3aca72fa-8f09-40e9-9d59-65c0dc2e03d2 (3.74 MB, 5,268 frames, 527 decisions, radii/fire ring/P1 band/terms/gate/ghosts); live_view.md §1-6 STATUS complete. (c) sim_view HUD says 3x from 180 s; engine says 240 s (display-only).
- Next: m500 grade under SAMPLE (threshold column kept for comparison to §5cs.49).

## L62l -- 2026-09-05 21:2x-21:5x UTC -- engB KILLED; engine-PPO closed; HANDOFF split (HANDOFF §5cs.51)
- m500 grade: control 6.87/22.21 (rails frac>8 0.262, p99 18.0 -> 31.25 in the train log at m602) -- degenerating and accelerating. KL 15.64/45.12 v1, 14.03/42.69 v2 -- flat vs init 15.44/46.61 across m0/m250/m500.
- VERDICT: 4 arms, ~1,500 engine matches, the unshaped engine reward has produced NO measured gain in pro agreement. The leash defends the init; nothing improves it.
- Owner live-play report tested: "hasn't changed" (a) TRUE + expected; "sloppy/wastes cards" (a) expected at 15.6% top-1; "throwing on purpose" (c) contradicted, no mechanism. Caveats (b): live obs comes from the screen detector, and play.py still uses the tau-0.25 rule. UNRESOLVED: which checkpoint file was loaded.
- KILL (owner ruling): taskkill shims 40540/72932 + children 56708/71976, 45856/46364. python 7 -> 3, guarded survivors alive (29444/53824 crawler, 63608 uvicorn), qemu 54304 UP with both slots FREE, free RAM 2.4 -> 5.0 GB.
- NEW TRAP: `_latest.pt` is written only at save_every crossings -- engB_*_latest are byte-identical to m500/m502 and the weights from m500->m609 are gone.
- HANDOFF.md 12,879 -> 2,325 lines (1.1 MB -> 269 KB), LOSSLESS: old §3 run state, the §5a..§5cs.42 narrative and 270 lines of stale header stack moved verbatim to HANDOFF_ARCHIVE.md (10,800 lines) with a 150-entry index; new compact header + §6 top-of-queue block. Backup scratchpad/gauntlet/L62/HANDOFF_prespllit_backup.md.
- Next: awaiting the owner's new gauntlet; box idle.

## L63 -- 2026-09-05 22:0x-22:3x UTC -- NEW GAUNTLET (square one, research, propose); owner's "BC overfits" premise tested (HANDOFF §5cs.52)
- (c) "BC / IL overfits": bc_bias_native_s0 scores 17.62/48.85 on its OWN TRAIN rows vs 15.44/46.61 val (v1; CE 3.26 vs 3.52, H 3.47 nats over ~188 legal cells); on v2 val 15.00 > train 14.09. It underfits: misses the pro cell on 82% of the boards it was fit on, +1.8 over the board-blind histogram (13.65).
- (a) The legal-placement mask forbids the pro's cell on 3.0-5.1% of rows (train higher than val); cause untested (b). New pipeline must validate its mask against the corpus first.
- Research fan-out: 5 background agents -> scratchpad/gauntlet/L63/{lit_game_ai,cr_prior_art,recent_2025_2026,assets_audit,lessons}.md, incremental, STATUS line marks done.
- Five owner questions posted with --questions (live-path guardrail, engine in/out, which ckpt was played live, budget/cloud, grading ladder). Proposal next loop after answers + agent files.
- Box: nothing training; python 3 (crawler x2 + uvicorn), qemu UP, free RAM 3.9 GB.

## L63b -- 2026-09-05 23:1x UTC -- proposal posted, STOPPED for approval
- Artifact: https://claude.ai/code/artifact/0e57cffe-d199-46c2-b39c-5922032b6821 (src scratchpad/gauntlet/L63/proposal.html); HANDOFF §5cs.53.
- Five stages, pre-registered gates: S0 obs contract + corpus rebuild (613 x/y replays, ~3x) + mask <0.5% + scripted bot in engine; S1 imitation v3 (token transformer, full-res head; gate train>17.6, val>15.44+band, 3 seeds); S2 corpus x3->x10 (crawler + detector-as-IDM); S3 engine search teacher + DAgger supervised distillation (no PG); S4 live layer (reranked top-k, live matches re-driven for the teacher). Owner grades live.
- Diagnosis carried forward (a): underfit board-blind model (17.6/15.4, cos 0.991), PG no gain in 4 arms, sim 26% vs engine 78%, live 1.3%/957.
- Questions: approve; live-grading mode + block size; crawler stalled on Cloudflare clearance since 17:16 UTC (restart?); cloud for S3.
- Box: nothing training; python 3; qemu UP, guest services dead.

## L62m -- 2026-09-05 22:0x UTC -- wave-4 crawl finished unattended; corpus measured (HANDOFF §5cs.54)
*(out of order: written by the L62 close-out session while the new session was already on L63/L63b; renumbered from §5cs.52 after the collision -- see the trap in §5cs.54)*
- Crawl DONE: 565 new replays in 478 min, exit 0; both crawler PIDs exited. Box now has ONE python (owner's uvicorn). Nothing training, nothing crawling.
- Corpus: 1,253 battles, 1,237 with plays, **625 (49.9%) with x/y**; 109,963 play rows, 54,148 (49.2%) with x/y; opponent decks 781 raw but **435 usable**. Owner's bar is >1,000 decks -> the real gap is 435->1,000, not 781->1,000.
- Reading: the x/y-less half is the binding constraint on both board count and deck pool, and has been ~50% across waves. Cheapest next measurement is WHY (untested), not another wave.
- No experiment run; no re-fit attempted; BC init on disk unchanged.

## L63c -- 2026-09-06 01:5x UTC -- APPROVED; rulings recorded; S0 step 1 done (engine services back, verified)
- Rulings (§6): approved as written, hogeq inherits everything; live grading = ladder 10,000 trophies, 20-match blocks, EMA, no learning; crawler login when a session is re-opened (wave 4 actually finished 00:44 UTC -- "stalled" was (c)); Hetzner AX162 is $1.16/h or $700+/mo live (my $283/mo was stale, (c)).
- S3 compute estimate (b, §5cs.55): ~400 slot-hours incl. margin; box alone ~9 days of engine time; GCP $300 trial covers it at any density -> recommend GCP, sign up at S3 start.
- Engine: services were [false,false]; boot from Bash fails 6/6 (GNU tar reads C:\ as a host) -- TRAP; native PowerShell attempt 1 ok. Liveness via replay_drive on both slots == L61 reference (hash d0874ff2026fa69e, 121/121, 4.4 s).
- Concurrent-session trap: old L62 gauntlet session wrote §5cs.54 during L63b; owner should close it.
- Next: S0 step 2, the shared observation contract (engine schema + detector schema -> one obs_builder), then corpus rebuild for both decks.

## L63d -- 2026-09-06 03:0x UTC -- S0 step 2 done: shared obs contract (new pipeline/ package), 19 tests OK
- Audits: engine obs schema + live path (obs_audit_engine.md, obs_audit_live.md). NO live recording has ground truth; nothing logs tag/battle time -> engine re-drive of live matches impossible from disk (a). Live gate: deployed policy_rl.pt has no algo key -> legacy Q(wait)>=Q(play), the sampled rule never applied live (a, new). Two live gaps new to HANDOFF (no warp on Vision; rl_gate_tau ignored).
- pipeline/: vocab 232 (230 detector + 2 engine-only), 122/122 cards mapped, sub-spawn thresholds measured (mother_witch hog (b)); BoardState + from_engine/from_live/degrade(0.855/0.886)/to_tokens; 19 unittest OK; independent sweep 161,336 conversions 0 unmapped 0 out-of-range.
- (c) building kind 12 != deploying: 22% of kind-12 building rows damaged.
- Stale sessions messaged (ruling 5); clashbot-c9 idle-confirmed. Owner ruling 6: cleanup loop before S1.
- Next: S0 step 3 corpus rebuild both decks (needs --crawl on replay_drive), step 2b own-click test in parallel.

## L63e -- 2026-09-06 02:5x UTC -- S0 step 3 LAUNCHED: corpus rebuild both decks through the engine, per-play recording
- replay_drive.py: L61 per-play recording promoted in (--record-plays), --crawl <deck>; replay_batch.py: --crawl/--out/--record-every/--record-plays. Smoke: icebow 000YLY0JCPGL hash == batch_v2 (d0874ff2026fa69e), 121 play_frames; hogeq first tag drives.
- Tag lists: icebow 619/1,253 fully positioned (54,142 plays), hogeq 296/598 (24,668 plays). EB-evo replays included (engine refuses cleanly).
- Running: corpus_v3/icebow (37031, ~13 s/replay, ETA ~2 h), corpus_v3/hogeq (37032, ~8 s/replay, ETA ~40 min). Step 2b own-click agent dispatched.
- (c) machine sleep as the cause of the 3 lost nights: 0 sleep/wake/boot events in 4 days of the System log. Cron :23/:53 added as second trigger.
- Owner rulings: CR_ENGINE_EXTRACTION_REVIEW.md deleted; README rewritten (74a3e80).

## L63f -- 2026-09-06 03:1x UTC -- S0 step 2b DONE: own-click contract test on 276 real human plays (4 sessions, 17,336 detections)
- Recall of the placed unit within 1.5 s: same class 0.81 (hogeq 0.55 = class confusion on icebow's detector), any new detection 0.97. x error 0.29 tiles median (unbiased); troop y biased -0.73 tiles (box centre != feet) -> FIXED in from_live (fy = gy + 0.25 h). Conf p50 0.835 (uniform(0.35,1) contradicted); unknown-team 0.25; own units tagged enemy 30%, own spells 42%.
- degrade() recalibrated: conf mixture, sigma 0.45, unknown 0.25, wrong_team_rate {troop/building 0.15 (b), spell 0.40}. 20 tests OK.
- label.py defects (not fixed, old path): 9.1% of "plays" are tray taps; select-time stamp; river-line snapping.
- Batches: icebow 132/619, hogeq 150/296 at 03:07 UTC; icebow background task survived the 10-min mark.

## L63g -- 2026-09-06 04:1x UTC -- first hogeq engine numbers; icebow batch 528/619; scheduled triggers did not fire
- hogeq: 241/296 converted (52 EB-evo, 3 deal-inference), 98.7% plays accepted, det 27/27 SAME, crowns match 56.4% (65.3% even with zero rejections; icebow 80.8%), engine ends early in 36.5% (median 1,008 ticks). (b) level-11 uniform levels vs level-sensitive hog breakpoints.
- icebow partial: 421/528 converted (103 EB-evo, 4 duplicated-row tags -- TRAP), 99.2% accepted, crowns 76.2%, 211/211 batch_v2 hashes reproduced.
- (a) wakeup 23:39 + cron 23:53 local did NOT fire while idle; CronList still showed the one-shot at 00:11. Owner's message was the check.

## L63h -- 2026-09-06 04:2x UTC -- Overnight trigger FIXED: timer tasks replace ScheduleWakeup
- (a) ScheduleWakeup + CronCreate do not fire while idle (3 nights). (a) A background `sleep 60; echo WAKE` task's exit re-invoked the loop within seconds (task b4t2fo0uo, exit 0).
- Rule written into .claude/commands/gauntlet.md §4 and HANDOFF §7: end every loop on a timer task (N<=570 s under the Bash cap, chain for longer); long batches stay background tasks. ScheduleWakeup allowed only as a free second trigger.
- Icebow batch 592/619 at 04:19 UTC; 8-min fallback timer armed (bhlc02vvv).
- Icebow batch DONE (exit 0): 493/619 converted (120 EB-evo, 6 dup-row tags), 41,015/41,338 accepted 99.2%, crowns 76.9%, early-end 22.9%, det 49/49, 177.6 MB. S1 corpus = 734 replays. Next: cleanup loop (ruling 6), then S1 dataset build.

## L64a -- 2026-09-06 05:1x UTC -- cleanup loop done + S1 dataset builder
- Cleanup (ruling 6): scratchpad 1.1G -> 557M, 3,297 files deleted after zip backup (ClashBot_archive/scratch_2026-09-06.zip, verified); data/ untouched. TRAP: agent-staged deletions rode inside commit 9adc967 (lead's commit sweeps the index) -- subagents never stage.
- pipeline/dataset.py: icebow 21,687 play + 56,590 wait rows / 493 replays; hogeq 9,797 + 23,421 / 241. Hand on wait rows reconstructed exactly from hand_before of the next accepted play. 24 tests OK.
- Next: S1 model + trainer, board-blind baseline on the same val rows first.

## L64b -- 2026-09-06 05:0x UTC -- S1 first run DISCARDED (row-format leak), datasets rebuilt, 6 seeds relaunched
- Leak (a): gate bal-acc 0.98 came from play frames carrying kind->deploying + effects that compact wait frames lack. Fix `_as_compact`; after it token cols 8-13 identical (0.000) across row types, both decks. Leaked log kept as LEAKED_train_icebow_s0.log (tile 16.8% best -- NOT an S1 number).
- Rebuilt: same row counts (icebow 21,687/56,590; hogeq 9,797/23,421); 24 tests OK; baselines identical (icebow tile 8.90%, hogeq 11.45%).
- TRAP: TaskStop on a bash chain leaves the script's bash + python alive (advanced to seed 1) -- kill the PID tree and verify.
- Running: run_seeds.sh (icebow s0-2, hogeq s0-2, 20 ep) ETA ~1h45. Next: icebow finals, gate sanity (<0.98 expected), then re-score old trunk on new rows.

## L64c -- 2026-09-06 05:2x UTC -- RETRACTION of 5cs.48 (grid pitch), old init re-scored on S1 val, S1 seed 0
- RETRACTED (a): L62i measured the LIVE ActionSpace (frame fractions x32) -> phantom 0.499 pitch. Trainer grid (_board_action_space): 432 = 1.333 tiles/row (owner was right), 576 = 1.000 with ZERO snap error on 2,657 pro x-bows; 432 max backward snap 0.5 tiles, 0/242 in-reach x-bows lost at either grid (owner's "one tile back / out of reach" still contradicted in magnitude).
- Old init on the same 3,796 S1 val plays (a): 432 grid 13.70/41.73 (clean 2,072 rows 13.13/41.51; 37/85 val replays were in its train split); 1-tile bins 6.69%.
- S1 icebow s0 (a, one seed): val tile 18.1% / half 15.4% (baseline 8.9/8.5), card 59.2%, gate bal-acc 0.715 (leak gone), emb cos 0.20. Matched grid: 1-tile new 17.3 vs old 6.7; old's 432 grid new 12.5 vs old 13.7 (clean 13.6 vs 13.1); miss distance mean 4.07 vs 5.28 tiles.
- Monitor events also re-invoke the loop (a). Next: 3-seed bands per deck (~06:45 UTC).

## L64d -- 2026-09-06 05:5x UTC -- seed 1 agrees; engine play harness for the S1 model
- icebow s1 (a): val tile 18.34 / half 16.15 (s0: 18.12 / 15.36); old's 432 grid 13.28 vs old 13.70 (clean 14.29 vs 13.13). Band waits on s2.
- pipeline/engine_play.py (a): S1 model on the real engine vs L62 ghosts; 2-match smoke 1W-1L, 45/47 plays accepted, 8.8 plays/min (pool humans 10.9), deterministic. 3 offline tests OK.
- Traps: engine refuse code 13 = no elixir (engine_env retry keys on 1050 only); pool entry 02GY9R09LU8J 3-crowns us by t=70 s even with no plays -> 500-match run needs a no-plays control per tag.

## L64e -- 2026-09-06 06:2x UTC -- icebow band closed; no-plays control; L64d trap (2) withdrawn
- icebow 3 seeds (a): val tile 18.12/18.34/18.20 = 18.22 +/- 0.11 (baseline 8.90); half 15.99 +/- 0.57; card 59.26; gate bal-acc 0.70. Seed 2 best at epoch 20 (schedule maybe short, untested).
- Old init on its 432 grid (a): ahead of all 3 seeds on all rows (13.70 vs 12.54-13.28) but 37/85 val replays were in its train split; on the 2,072 clean rows all 3 seeds ahead (13.61-14.29 vs 13.13). Miss distance 4.07 vs 5.28 tiles every seed.
- `--gate none` control (a): passive icebow loses 0-3 at 61 s (099P9CL8L2QJ, the entry the model beat 2-1) and 70 s (02GY9R09LU8J). WITHDRAWN: L64d's "pathological entry" -- undefended = dead in a minute, any entry. Engine reads must be deltas vs the per-tag control. engine_env ghost retry now also keys on code 13.
- hogeq s0-2 running, ETA ~07:00 UTC.

## L64f -- 2026-09-06 07:5x UTC -- hogeq band closed; first engine read with controls
- hogeq 3 seeds (a): val tile 21.30/20.58/21.08 = 20.99 +/- 0.36 (baseline 11.45), half 19.26, card 54.91 (42.32); value acc 53.7 (icebow 69.8; crowns mismatch suspected, untested). Best epochs 20/11/18.
- Engine, icebow s0 ckpt, 100 paired pool entries (a): threshold 75W-25L, sampled 68-32; no-plays control 0-100 (91 s), rate-matched random policy 0-100 (130 s). Model survives +115 +/- 5.5 s on 100/100 entries, crowns against 0.86 vs 3.00. Model win rate identical on entries the pro won (75%) and lost (76%); all 100 engine-terminated.
- Not established: reactive opponents; old init on this instrument; checkpoint variance (s1 ckpt in flight). Harness: --policy random added.
