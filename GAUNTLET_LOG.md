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
