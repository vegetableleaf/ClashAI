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
