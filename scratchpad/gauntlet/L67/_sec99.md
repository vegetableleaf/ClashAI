### §5cs.99 -- L67g (2026-09-08 18:00-20:00 UTC): **THE LIVE "FREEZE" IS REAL (~50 s stretches at 8-10 elixir with 0 plays, 4 owner matches) BUT MY FIRST DIAGNOSIS OF IT WAS MEASURED ON A CONDITIONED SAMPLE AND IS RETRACTED. On engine states the gate is CALIBRATED IN ELIXIR almost exactly (model 0.046 -> 0.472 across elixir 1 -> 10 vs a pro rate of 0.037 -> 0.490, and joint in units x elixir), so the head is not the defect. Two traps found on the way: the play.py log prints p only on WAIT frames, which truncates the sample at tau; and the training rows are sampled every 2.0 s (median) at a 27.2% play-row rate, so the gate's tau is calibrated to a 2 s window while the live loop asks it every 0.77 s. The owner's deck-veto rule for unknown-team cards was ALREADY LIVE and is measured to work (0 impossible-class detections survive as mine/unknown after TeamTracker, 2 sessions); it was missing only from the contract path, where it is now added deck-generally.**

**A. The freeze, from the owner's own run (a), `scratchpad/live_run3.log` (4 matches, 18:38-18:46, v6lat_s0 at tau 0.27).** It is NOT a hang: 600 decisions in ~472 s of match time (1.27/s) and WAIT lines keep printing straight through every frozen stretch. 70 plays / 600 decisions = 11.7%, which at that cadence is **9.1 plays/min against a pro's 8-10.5/min -- the RATE is right**. What is wrong is the distribution: match 2 ended on ~70 consecutive waits (~55 s) at 8-10 elixir, match 3's last ~50 waits were all at 10 elixir, match 4 the same. Overflowing at 10 elixir is wasted resource, so this is not patience.

**B. RETRACTION (c).** I reported to the owner that "the gate ignores elixir", from the log's WAIT lines (mean p 0.062 at elixir 10 vs 0.026-0.081 at elixir 2-6). **That sample is conditioned on the outcome being explained**: play.py prints p only when it WAITS, and WAIT is exactly `p < tau`. At high elixir the high-p frames leave the sample by becoming PLAYs, so a perfectly calibrated gate produces the same flat curve. The log cannot answer the question and the claim did not follow from it.

**C. What the gate actually does, against pro labels (a), `gate_vs_elixir.py`, v6lat_s0, 55,461 v6 VAL rows.**

| elixir | 1 | 3 | 5 | 7 | 9 | 10 |
|---|---|---|---|---|---|---|
| model p | 0.046 | 0.174 | 0.268 | 0.246 | 0.375 | 0.472 |
| pro rate | 0.037 | 0.181 | 0.259 | 0.248 | 0.352 | 0.490 |

Jointly too: units 0-1 x elixir 9-10 -> model 0.286 / pro 0.300 (n=3591); units 2-3 x 9-10 -> 0.428 / 0.427; units 4-6 x 4-6 -> 0.291 / 0.286; units 7+ x 0-3 -> 0.178 / 0.178. **The gate head has learned the pro's elixir response almost exactly**, which relocates the freeze to the live input or to the threshold, and removes "the gate is broken" from the table.

**D. A cadence trap that changes what tau MEANS (a).** v6 VAL rows sit a **median 2.0 s apart** (mean 1.415, p10 1.3, p90 5.35) with a **27.2% play-row rate** -- i.e. 8.1 plays/min, the pro rate. The live loop asks the student every **0.77 s**, ~2.6x more often. A gate calibrated to "is this 2 s window a play window" is being sampled 2.6x per window, so the live threshold is doing double duty as a cadence correction, and no tau can be read off the training boundary. Any future gate work must state which cadence its number belongs to.

**E. The owner's deck rule was already there, and works (a), `team_rule_scan.py`, 623 frames of 2 sessions.** Owner ruling: "if a goblin barrel is tagged 'unknown' auto assume it's the enemy cuz icebow doesn't run goblin barrel. this card check should always be in there no matter what deck the model runs." `TeamTracker._claim` (replay_mine.py:337, the 2026-08-16 deck veto) already does exactly this and play.py feeds it the deck.

| | raw colour vote | after TeamTracker |
|---|---|---|
| 20260815: unknown / mine / enemy | 194 / 501 / 410 | 42 / 507 / 556 |
| 20260804: unknown / mine / enemy | 140 / 215 / 305 | 30 / 281 / 349 |
| impossible class still not enemy | 89 (72 + 17 tagged MINE) | **0 / 0** |

The "20/42 goblin barrels tagged unknown" of the previous loop was measured on the RAW detector and is **not a live-path number** -- the live path never sees a raw tag. What genuinely lacked the rule was `obs_contract.from_live`, which every offline harness (dry-run, ablation, this scan) uses with raw detections. Added there as `mine_classes(deck)`: the deck's 8 base keys plus the transitive closure of what they spawn, from the card DB's own `spawns.unit` plus vocab's measured spell-body table (verified: witch/golem/elixir_golem/goblin_barrel/graveyard/night_witch/lava_hound/tombstone all close correctly), so it holds for any deck. 20/20 `test_obs_contract` pass.

**F. The freeze's mechanism, three probes (a).** The live gate is NOT elixir-blind either -- `live_gate_elixir.py`, 835 real detector frames, p scored on EVERY frame (no WAIT conditioning): p 0.109 (elixir 0-3) -> 0.198 (4-6) -> 0.313 (7-8) -> **0.567** (9-10, n=58). What suppresses it is what the live path SENDS:

| live input variant | frac of frames over tau 0.27 | p at 9-10 elixir |
|---|---|---|
| live as-is (opp elixir absent) | **0.278** | 0.567 |
| + `my_elixir_exact` forced on | 0.214 | 0.517 |
| + opponent elixir 0.0 | 0.236 | 0.533 |
| + opponent elixir 5.0 | 0.156 | 0.408 |
| + opponent elixir 7.5 | 0.113 | 0.347 |
| + opponent elixir **10.0** | **0.087** | 0.289 |

**Supplying the opponent-elixir estimate cuts the live play rate monotonically, by up to 3.2x** -- and note that even opp=0.0 suppresses (0.236 vs 0.278), so it is the `opp_known` FLAG as much as the value. This matters because `OpponentElixirEstimator._est = my_elixir + my_spent - opp_spent`, clipped to [0, 10]: every enemy play the detector misses pushes it UP and it never comes back down, so a long match drifts toward the pinned 10 that costs the most gate. **I wired that estimate into the live path last loop (L67f, 5cs.98 F) on the strength of an ENGINE-label measurement where the opponent's elixir is ground truth, and the owner reported the freezing after it shipped.**

**G. `past` (a), `gate_vs_past.py`, 6,000 VAL rows.** An OLD history does not suppress the gate -- it raises it (mean p 0.263 at 3 s -> 0.432 at 30 s -> 0.448 at 60 s). An EMPTY history nearly kills it: **0.069 vs 0.276 as-recorded** (frac over 0.27: 8.2% vs 39.4%). The live student starts every match with `_past` empty and fills it only on an accepted tap, so the opening is the model's weakest gate state by construction. Caveat (b): "no past" correlates with match start in training (5.2% of rows, low elixir), so part of the drop may be the model reading it as "first ten seconds" rather than responding to the field.

**H. THE CEILING ON PRO AGREEMENT -- 27.8%, and the model is at 21.0% of it (a), `agreement_ceiling.py`.** Every S1 number in this project grades the model against ONE pro's tile as if it were the unique right answer. It is not. 40,000 pro PLAY rows, 2,238 replays; pairs blocked on same hand + same card + same integer elixir, drawn from DIFFERENT replays, binned by coarse board distance (6x8 occupancy per side + tower HP):

| board distance | 0-0.25 | 0.25-0.5 | 1-2 | 2-3 | 3-5 | 5-8 | >8 |
|---|---|---|---|---|---|---|---|
| two pros, same cell | **27.84%** | 26.14% | 18.54% | 13.99% | 14.08% | 9.66% | 5.18% |
| within 1 tile | **31.62%** | 37.50% | 22.21% | 17.61% | 19.21% | 14.98% | 9.55% |
| same card | **43.81%** | 50.57% | 35.68% | 37.74% | 38.91% | 37.55% | 39.29% |

The curve PLATEAUS at the closest two bins (27.84 / 26.14), so this is a ceiling and not a truncated ramp, and the far bin (5.18%) is the coincidence floor. Against it: the student is **21.04% exact cell = 76% of the ceiling**, **31.87% within-1-tile against a pro-pair 31.62% (AT the human number)**, and **65.0% card top-1 against a pro-pair 43.8% -- the model matches the pro's card more often than a second pro does**. Two caveats, in opposite directions: the coarse board summary means "distance 0" is not literally the same state (biases the ceiling DOWN), and a pro can appear in several replays and agree with himself (biases it UP -- a re-run excluding same-player pairs via crawl2/battles.csv is the check). **What this changes: the imitation objective is close to exhausted, and no amount of corpus growth reaches a number pros do not reach with each other. Placement gains must come from an objective that evaluates outcomes, not from more labels.**

**I. Headroom for a RERANKER over the student's own ranking (a), `topk_headroom.py`, 12,000 VAL play rows, cell head teacher-forced on the true card.**

| K | 1 | 2 | 3 | 5 | 8 | 16 |
|---|---|---|---|---|---|---|
| pro's exact cell in top-K | 21.13 | 35.79 | **44.24** | **55.50** | 65.70 | 78.28 |
| within 1 tile of the pro | 32.70 | 48.33 | 57.38 | 67.58 | 75.78 | 85.23 |
| pro's card in top-K | 63.16 | 88.07 | 97.58 | (K=4) 100.0 | | |

The pro's tile is in the student's **top-3 44.2% / top-5 55.5%** of the time -- both far above the 27.5% pro-pair ceiling of H. So the answer is already inside this policy's shortlist and the argmax is not picking it, which is the same shape of claim that licensed the rollout-search work for the OLD CNN (`research/sim_parity/ledger/rollout_search.md`) -- now established for THIS model instead of inherited. Card top-3 97.6% confirms the spec's K=4 covers essentially every real option. **What it does NOT establish (b): that a search can actually FIND the right one. Ranking headroom is necessary, not sufficient.**

**J. Two live repairs shipped this loop; neither needs a retrain.**
1. `play.py` no longer sends the opponent-elixir estimate to the student (`play.student_opp_elixir`, default **false**; set true to restore L67f). Justification in F.
2. `opponent_elixir.py` RE-BASELINES on saturation instead of clipping the output and keeping the inflated books. The accounting `opp = my_elixir + my_spent - opp_spent` is exact only if every enemy play is seen; each missed one pushed `est` up permanently, and the clip hid it in the returned value while the next update recomputed from the same base -- so it ratcheted to a pinned 10 and stayed. Nobody holds more than 10 elixir, so an overflow IS evidence of a missed play: it is now charged to `_opp_spent` (and a sub-zero estimate credited back). Unit-checked: pinned at 10 after six unanswered own plays, then a single detected enemy Giant drops it to 5.0 -- pre-fix it stayed at 10.0 for the rest of the match. **This changes every consumer of the estimate, not only the student** (play.py:472 and the obs canvas), which is a deliberate bug fix, not a student-only tweak.
3. `student_live.decide()` now records `self.last` on the `no_mappable_card` path, and play.py's WAIT line prints `opp~<est>` and a `NO-TRAY-MATCH` flag. Before this a run of tray-read failures printed a STALE p and was indistinguishable in the log from genuine low-gate waits -- the exact evidence needed to read a freeze.

**K. RETRACTED within the loop (c): the barrel-landing probe.** The first version matched a barrel to the CENTROID OF LATER GOBLIN DETECTIONS and reported median 12.52 tiles. It is wrong: those goblins sit at board y 0.512 (the river) with only 38% within 3 tiles of my princess row, i.e. it was associating Goblin Gang / spear goblins with a barrel they never came from. (Its predecessor found 0 pairs at all, because it looked for detector class `goblin` when the detector names bodies after the CARD -- `goblins`.) Replaced by `barrel_track.py`, which tracks the barrel itself across frames and needs no cross-class association: the landing estimate is the track's LAST sighting and the owner's question -- how wrong is the CURRENT position -- is the distance from each earlier sighting to it.
