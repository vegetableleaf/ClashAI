### §5cs.98 -- L67e+f (2026-09-08 06:00-18:00 UTC): **OPTION B GRADED (3 seeds: clean 21.56 +- 0.07, degraded 19.45 +- 0.05) BUT ITS GAIN IS AGAINST A CORRUPTION MODEL WE NOW KNOW IS WRONG. Three label-free live measurements instead: the GATE survives real detector input (live .248-.325 vs engine .294-.298), PLACEMENT COLLAPSES toward the prior (top-1 cell share 0.25 vs 0.07 at matched unit counts), and nothing JITTERS (same-cell 61.4% live vs 38.7% engine -- the collapse seen twice, not a second defect). Ablation names the cause: MISSING VALUES (unit HP, exact/opponent elixir, king HP), not noisy ones -- spell tokens, unknown team tags and low confidence each do NOTHING. Against pro labels, SUPPLYING beats FLAGGING (blank_both 18.78 exact cell / 52.11 card -> fill_both 20.15 / 63.25), so the fill is now wired live and verified (live top-1 share 0.411 -> 0.322)**

**A. Option B, the 3-seed result (a), `s1_v6aug/eval_v3val_icebow_v6aug.out` + `eval_v3degraded_*`.** Augmented set = 622,923 rows (339,192 clean + 283,731 degraded TRAIN rows; val rows clean, so checkpoint selection is v6lat's own rule).

| metric | v6lat | v6aug | delta |
|---|---|---|---|
| exact cell, clean v3 VAL | 21.04 +- 0.22 | **21.56 +- 0.07** | +0.52 |
| exact cell, degraded VAL | 16.35 +- 0.56 | **19.45 +- 0.05** | +3.10 |
| card top-1, degraded | 49.3 +- 1.2 | **60.4 +- 0.6** | +11.1 |

Caveats (both material): seed 0 is a **13-epoch crashed run** (CUDA error under two trainers + the detector on one 8 GB GPU), so it is best-of-13, not best-of-20; and the degraded-VAL gain is **partly circular** -- trained on `degrade()`, graded on `degrade()`. Live, both v6aug seeds are near-catatonic at the training threshold (play rate 0.7-1.3% vs v6lat's 15% on the same 300 frames) -- NOT a broken gate but a shifted one: the tau reproducing v6lat's live rate is 0.16 (s0) / 0.083 (s1), not 0.5. **RETRACTION of the L67e chat claim that the augmented arm "loses on the thing we care about": it is a calibration difference, and its live placement quality is unmeasured.**

**B. Placement collapses live; the gate does not (a).** Same model, same rule, two input pipelines, matched on information content (>= 3 units, elixir >= 5) and on sample size (n=159 both sides):

| top-1 cell share | engine v3 VAL | real live frames |
|---|---|---|
| all rows | 0.07-0.11 | 0.25 (matched) / 0.40-0.62 (raw, per session) |
| units 2-3 | **0.10** | **0.33** |
| units 4-6 | **0.07** | **0.24** |
| units 0-1 | 0.33 | 0.53 |

Both halves matter: **sparsity alone collapses the head** (engine at 0-1 units is 0.33, and live frames carry a median of 2-3 units), *and* at matched sparsity live is still ~3x more concentrated. Detector recall would fix the first half only. The cells live collapses onto (1267, 1289 = lattice row 35, cols 7 and 29) are the model's own #2/#3 engine cells, so this is a fallback to its prior, not a coordinate bug -- the mirrored x-medians across sessions (0.194 / 0.806) were the first suspicion and are explained by the two mirrored favourites, not by a warp fault.

**C. No jitter (a), `place_stability.py`, decision gaps matched (live pairs 1.0 s, engine 0.5-2.5 s).** Same-cell fraction live **61.4%** vs engine **38.7%**; median move when it changes 6.00 vs 6.04 tiles, p90 13.1 vs 13.9, moves > 5 tiles 53.7% vs 57.7%. Detector noise is NOT shaking the placement head -- live is *more* repetitive, which is B's collapse seen through a second instrument and must not be reported as an independent finding. Note the 6-tile median move is large on BOTH sides: a property of the model, not of the live path, so it belongs to the pro-agreement problem.

**D. What causes the collapse (a), `ablate_live.py` -- one detector pass over 300 live frames, every variant re-scored on the same cached BoardStates.**

| live input variant | top-1 share | distinct |
|---|---|---|
| baseline | 0.400 | 43 |
| spell tokens removed | 0.417 | 39 |
| `side=-1` resolved | 0.390 | 42 |
| `conf` forced to 1.0 | 0.403 | 41 |
| **unit HP supplied** | **0.303** | 57 |
| **scalars supplied** (exact elixir, opp elixir, king HP) | **0.287** | 46 |
| all of the above | **0.243** | 54 |

**CONTRADICTED (c): the spell-token hypothesis.** §5cs.95 A and §5cs.97 both flagged the 29-78 live spell tokens per run (training rows contain zero) as a likely cause; removing them makes concentration marginally WORSE (0.417 vs 0.400). Same for `side=-1` (training: zero unknown sides) and for detector confidence. The head is not confused by unfamiliar or noisy values -- it degrades on **absent** ones. Residual after supplying everything is 0.243, still ~2x the matched engine baseline, so missing values are a large part but NOT all of it (b: the unit-count-matched version of the "all" variant is the next measurement).

**E. Supplying beats flagging, measured against PRO LABELS (a), `fill_vs_blank.py`, v3 VAL, v6lat_s0.** Dispersion is label-free, and filling a missing field with a plausible constant is a lie that could disperse the output while making it worse -- so the same manipulation was run where the labels are pro placements:

| input | exact cell | card top-1 | mean dist | gate acc |
|---|---|---|---|---|
| clean | 20.97 | 65.46 | 3.513 | .826 |
| blank HP / fill HP | 19.47 / **20.26** | 58.77 / **64.01** | 3.991 / **3.652** | .799 / .813 |
| blank scalars / fill scalars | 20.42 / **20.71** | 60.99 / **64.83** | 3.576 / **3.532** | .682 / .810 |
| blank both / fill both | 18.78 / **20.15** | 52.11 / **63.25** | 4.085 / **3.638** | .738 / .790 |

Fill beats blank on every metric. Also: **blank_both (18.78) is the closest labelled analogue of today's live input and sits 2.19 pp below clean, not the 4.2 pp `degrade()` predicted** -- the third independent sign (after the gate distribution and the live play rate) that the corruption model overstates the live penalty.

**F. Wired and verified (a).** `obs_contract.LiveReads` gains `opp_elixir` (default None, so training is untouched) and `from_live` gains `unit_hp_default`; `student_live.live_reads` sends the king's alive-proxy HP instead of None; `play.py` hands over the `OpponentElixirEstimator` reading it already computes and was discarding. One bug caught in review before it shipped: a `<= 1.0` rescale heuristic would have turned a genuine 0.8-elixir estimate into 8 (`_est` is already 0-10; `update()` is what normalises). 20/20 `test_obs_contract` tests pass. Verified on the same 292 live frames: **top-1 share 0.411 -> 0.322, distinct cells 43 -> 51, play rate 0.150 -> 0.170** -- and that is with unit HP + king HP only, because the dry-run harness has no opponent-elixir estimator; the live path supplies all three.

**G. State.** Live path: student OFF unless `--student <ckpt>` / `play.student_ckpt`. Owner has run it live twice (L67e): first run did nothing because the override sat behind the CNN's own gate (fixed, 1c29e4b); second played but its log captured nothing because Python block-buffers a piped stdout (fixed with flush, f9b9d2c). Open: rerun v6aug seed 0 to 20 epochs for a clean 3-seed number; the unit-matched "all" ablation; and a live A/B judged on the label-free instruments plus pro agreement -- **NOT on the owner's own clicks, which he ruled out as a quality standard (his skill is not pro); his sessions are used only as real detector INPUT.**
