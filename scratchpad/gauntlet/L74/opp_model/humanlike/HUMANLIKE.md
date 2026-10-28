# Opponent human-likeness scorecard (plan1026 Pillar 2)

## Pre-registration log
| when | file | sha256 | note |
|---|---|---|---|
| 2026-10-27 | THRESHOLDS.json v1 | `5b9cd2faa46149a69bdf7d091ba2d21ef111fc9cf4ce474ad3d791b1a8f8803c` | written and committed BEFORE any scoring; numbers copied from PLAN.md / REPORT_opponents.md section 4 |
| 2026-10-27 | THRESHOLDS.json v2 | `0ba3aa32763dc3812d55fcaedd827f8fea482605945b2ca2a0cd364d6c5e2802` | before any model score. Two changes found by the human-vs-human control (see section Controls): B3 drops first_tick; A.ece_min_decisions = 200000 added. v1 is superseded |
| 2026-10-27 | THRESHOLDS.json v3 | `0c42e9142d70842b1c59623b7fbe71ea4da890192e55bb3c2f677916712ec703` | before any new model score; human controls only. B3 point band becomes a CI-overlap rule (see changelog in the file); TOST unchanged. v2 superseded |
| 2026-10-28 | THRESHOLDS.json v4 | `a5eb2c8fb232ccf94f3fee68617a297451dbcbd62287f3111e24fe9a5ad05695` | P2-SCORE, before any model score on the new items; human controls only: 25-stat closed-loop list, B-HF sufficiency 3,700 games per class, siege margins S (design-size 95% human pass), C built. B-live rule unchanged (decision owed). v3 superseded |
| 2026-10-28 | THRESHOLDS.json v5 | `438a7692d85bfe58127c23eb30bffae5b1d585407535727e26e64ef327ff31b9` | P2-SCORE (account 2), owner decision 10-28 (HANDOFF_1028 9.9): B-live + C-live from ALL recorded live matches, recency-weighted; human controls only, registered BEFORE any model score (section 9). v4 superseded |
| 2026-10-28 | THRESHOLDS.json v6 | `265681678b39907533182e9d9f499b267b97bc067635807ed2044dc45c20b309` | P2-SCORE, OWNER DECISION 10-28 16:10: calibrated to TODAY's humans (drift-aware newest-block null, half-life 2 d, SE-scaled per-stat margins, RMS 0.10, C-live human class = newest block); LF sha; registered before any model score (section 11). v5 superseded |

`scorecard.py` refuses to run if THRESHOLDS.json does not hash to the LAST sha in this table.

## Files
- `scorecard.py`: `repro` (reference table), `selftest` (instrument controls), `score NAME=PATH ...` (B, pooled D, H_B per model). PATH = a root with NAME_SEED/D3/matches.jsonl rows carrying `o3_plays`, or `ob:SIM` = `human/data/sim_SIM.json.gz` (positions available).
- `THRESHOLDS.json` (v2). `out/repro.txt`, `out/selftest.txt`, `out/baselines.txt|json` = the outputs quoted below.
- Reused, unmodified: `human/opp_behaviour.py` (features, Cohen d), `opp_model/o3_score.py` (SIM rows to plays), `w14/o4r_table.py` (Ranked rows, `style_dist`), `analyze.py` (live 13k set, `arch2`), `L67/agreement_ceiling3.out` (saved ceiling run).

## 1. Reproduction of the known reference values (all must match before the tool is trusted): REPRO OK
(a) measured, `out/repro.txt`. Style = RMS Cohen d of per-match opponent features, SIM minus live.

| quantity | reference | scorecard | independent path |
|---|---|---|---|
| human floor sqrt(2/748) | 0.05 | 0.052 | |
| 12k vs 13k humans, 13 stats | 0.10 | 0.106 | |
| E4 (`ECON_r1`, 960 games) vs live 13k, 13 stats | 0.93 | 0.935 | |
| O2b vs live 13k, 9 stats | 0.65 | 0.654 | `o4r_table.style_dist` 0.654 |
| gen_v32_s0 vs live 13k, 9 stats | 0.79 | 0.789 | 0.789 |
| I u40 (`w14F_Iu40`, 2880) vs Ranked-233 | 0.78 | 0.776 | 0.776 |
| B u20 (`w14O4_Bu20`, 1920) vs Ranked-233 | 0.53 | 0.525 | 0.525 |
| human-human card / cell agreement ceiling | 43.7 / 27.5 | 43.72 / 27.52 | read from the saved L67 run, NOT recomputed |

Two reference scales exist and the old notes mix them: the 13-stat form (positions + `opp_el`; only `ob:` sources have it) and the 9-stat form (what every `o3_plays` row set can give). E4 is 0.93 on 13 stats but 1.09 on the 9. Compare only within one scale.

## 2. Instrument controls (`out/selftest.txt`): SELFTEST OK
(a) measured. 20 random halves of the 12k live set (about 960 matches per side, 15 stats): RMS d <= 0.10 in 20/20; TOST all stats 18/20; B3 band 17/20; **full B pass 15/20**. Planted speed bug (ppm_2x x1.3, react_3s x1.5): RMS 0.46, fails. Planted spread collapse (push_mean SD x0.3): B3 fails. Level A: a calibrated model with Exp(1) gaps passes (ECE 0.20 pp, KS 0.010 at n=300k); a miscalibrated / constant-gap model fails.
Finding that led to v2: `first_tick` SD ratio between two human halves was 0.76-0.94, so humans failed the B3 band on it. Remaining concern: even without `first_tick`, humans fail the full B rule 25% of the time at this n (B3 band [0.9, 1.1] and the all-stats TOST are tight for n ~ 960; (b) a CI-based B3 rule would fix it, untested, needs the foreman's decision before v3).

## 3. Baseline scores (B and pooled D; thresholds v2; `out/baselines.txt`)
(a) measured. B = RMS d over the stats shown (13 for E4/ECON_r1, 9 otherwise) + 6 play-gap/card-mix stats in TOST and B3; pass needs RMS <= 0.10, all TOST < 0.20, B3 in [0.9, 1.1]. D here is the POOLED version on Ranked-233 (not the sealed block, n < 1500), so it can only fail by the sufficiency rule; the point difference is informative.

| model | rows used | n games | RMS d vs 13k | RMS d vs Ranked | B | D: SIM win vs live Ranked 48.1% (n 233) | H_B |
|---|---|---|---|---|---|---|---|
| E4 | `ob:ECON_r1` (r1 learner, CAL pool) | 960 | 0.93 (13 stats) / 1.09 (9) | 0.86 / 0.93 | FAIL | no outcome in these rows | 0 |
| E4, CLX learner | `tonight1020/clx_fin15` | 1920 with plays (3840 rows) | 0.70 | 0.58 | FAIL | 68.2%, +20.1 pp [+13.5, +26.6] | 0 |
| gen_v32_s0 | `o3/48148/o3_gen_s0_T0.1_d40_r0` | 480 | 0.79 | 0.65 | FAIL | 74.8%, +26.7 pp | 0 |
| O2b | `o3/48148/o3_liveoppB_T0.1_d40_r0` | 480 | 0.65 | 0.54 | FAIL | 83.8%, +35.7 pp | 0 |
| I u40 | `w14/o4/w14F_Iu40` | 2880 | 0.88 | 0.78 | FAIL | 48.8%, +0.8 pp [-5.9, +7.3] | 0 |
| B u20 | `w14/o4/w14O4_Bu20` | 1920 | 0.66 | 0.53 | FAIL | 57.0%, +9.0 pp [+2.2, +15.7] | 0 |
| D1 u60 | NO ROWS | - | - | - | - | - | - |

- Every model is 5x or more above the 0.10 line; nothing is close. The best (B u20 vs Ranked 0.53, O2b 0.54) are the weakest opponents (CLX wins 57-84%).
- Per-archetype CORE9 RMS d and signature stats (hog / hyperbait / golem / lava / pekka_bridge / royal_giant card rate and first-play time) are in `out/baselines.txt`; royal_giant (1.4-1.9) and pekka_bridge (0.7-1.5) are worst in every model, hog is best (0.5-1.0).
- **H = 0 for every model** (A and C not scored; H_B, the share of live opponents in archetype cells whose archetype passes B, is also 0.000 over 21 band x archetype cells, live n 2271 at >= 12k).
- I u40 matches the live Ranked win rate (+0.8 pp) while its style distance is 0.78: outcome parity without style, so D alone can be passed by a non-human opponent; this is why A-C stay in the definition.

### Rows missing (stated, not guessed)
- **D1 u60 (`oppD1_deny_s74`)**: no `matches.jsonl` with `o3_plays` on this laptop or in `pod_backup_weekend`; the LEDGER numbers (CLXIII wins 49.5%, lock 0.544) come from pod 33458's `q_xbD1`, which was not copied back. Needs a CLX-vs-D1 run with the o3 telemetry.
- **Level A for every baseline**: no model dumped per-decision probabilities; only cited numbers exist (O2b cell NLL 3.05, card 0.531; gate head flat at 0.685). `level_a()` is built and controlled but needs a prediction dump.
- **Level C**: later ticket. **Head-deck cells**: need HF side counts; folded into the 8 `arch2` archetypes (the plan's 10-archetype taxonomy is not implemented; `weekend/archetypes.py` has 7 + `hog`).
- Positions (own_half, bridge, our_half, opp_el, 4 of the 13 stats) exist only on `ob:` sources; the o3 / fin15 row sets carry no x, y.
- B-HF (model vs re-driven humans) needs the D1 engine replay; B here is B-live only.

## 4. Caveats
- (a) Live archetype is classified from cards SEEN, SIM from the full deck (known confound from `opp_behaviour`).
- (a) Live reference is icebow-vs-human at 12-14k; SIM opponents are not band-conditioned, so H cells take their archetype's pass (stated in `coverage()`).
- (a) Public-info rule held: live enters only through detected plays and the reader's public counter.

## 5. v3 update (coordinator decision on concern 1)
**Rule change (human controls only; v3 sha logged above before re-scoring).** B3 no longer uses the point ratio. It uses the kurtosis-aware 90% CI of SD_model / SD_live (SE of log SD = sqrt((kurt - 1) / (4 n))) and passes unless that CI lies wholly outside [0.9, 1.1]. TOST is unchanged. (a) measured, 50 random halves of the 12k live set (seeds 100-149, about 960 per side, 15 stats): RMS 50/50, TOST 48/50, B3 50/50, **full B 48/50 = 96%** (v2: 15/20). Two failures are TOST on single stats. Planted speed bug and planted spread collapse (ratio 0.31) still fail; the level A controls are unchanged. `repro` is still OK.
Caveat: the rule is an overlap test, so B3 can only reject a clear spread mismatch; it cannot certify a ratio of exactly 1.0 +- 0.1. (a) At n ~ 960 per side a rule that certified that would fail humans, which is the finding.

**Baselines re-scored under v3: all six still FAIL B** (`out/baselines.txt`). The margin is the RMS line, not the spread rule:

| model | RMS d vs 13k / Ranked | times the 0.10 limit | TOST (all stats < 0.20) | B3 vs 13k / Ranked |
|---|---|---|---|---|
| E4 (13 stats) | 0.93 / 0.86 | 9.3x / 8.6x | fail | fail / fail |
| E4, CLX learner | 0.70 / 0.58 | 7.0x / 5.8x | fail | pass / fail |
| gen_v32_s0 | 0.79 / 0.65 | 7.9x / 6.5x | fail | fail / fail |
| O2b | 0.65 / 0.54 | 6.5x / 5.4x | fail | pass / fail |
| I u40 | 0.88 / 0.78 | 8.8x / 7.8x | fail | pass / fail |
| B u20 | 0.66 / 0.53 | 6.6x / 5.3x | fail | fail / pass |

Closest to passing is B u20 vs Ranked at 0.53, still 5.3x over; the human 12k-vs-13k control is 0.07 (9 stats) / 0.106 (13 stats).

## 6. Owed
- **D1 u60**: skipped (pod 33458 is gone). Needs a CLX-vs-D1 run with `o3_plays` telemetry when a pod is available.
- **Level A baselines need a per-decision probability dump for every model: E4 (`rdef_e4_u0020`, graft 430faaee), gen_v32_s0 (61011b6c), O2b (`icebow/data/pipeline/o2/gen_live_b.pt`, 0882374c), I u40 (`pod_backup_weekend/w14/rlarm_oppW14I_otstartE_s74_u0040.pt`), B u20 (`.../rlarm_oppW14B_gatefree_s74_u0020.pt`), D1 u60 (checkpoint was on the pod; recover first).**
  No script that writes the dump exists yet (checked `pipeline/*.py` and `opp_model/pod/o2_finetune.py`; the latter only logs aggregate val NLL). The intended command, to write as `humanlike/dump_probs.py` (not built, outside this ticket's scope):
  `icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/opp_model/humanlike/dump_probs.py --ckpt CKPT --data scratchpad/gauntlet/L74/opp_model/out/o1_holdout_v32.npz --out humanlike/out/probs_NAME.npz`
  with outputs `p_true`, `top1`, `p_top`, `correct_top`, `gaps_rescaled` (the `level_a()` inputs). The holdout is the time-ordered 15,885 live opponent rows O2 used; E4 / RL checkpoints were not trained on it, O2 / O2b were fine-tuned on the earlier part only.

## 7. P2-SCORE STATUS (closed-loop levels; updated 2026-10-28 ~13:55 EDT)
- Done: `run_closed.sh` = pod runner (CLXIII vs one opponent on crforge, gap.py D3, G2 handicap, --record-board/--habit-log/--crown-log;
  writes OUTROOT/ENGINE.json with the crforge build, facade sha, tables, code head). Resumable: a 480-row seed block is skipped.
- Running: pod 32657, `/workspace/score/rows/e4` (E4 baseline, seeds 741200 742000 743000 744000, 40 workers), code copy
  `/workspace/score/cb` (git archive of b84b440 pipeline + tools + L74 tree; icebow/data -> /workspace/d2x/cb/icebow/data;
  research/ext copied with the LAPTOP catalogue 936cd3c4, the pod's 7b01d9ac is stale), crforge CF-MAIN a677e080 plain.
  Restart: `ssh -p 32657 root@157.157.221.29 'cd /workspace/score && WORKERS=40 setsid nohup bash run_closed.sh e4 /workspace/score/rows/e4 741200 742000 743000 744000 > e4.out 2>&1 < /dev/null &'`
  (I u40: `OPP_CKPT=icebow/data/pipeline/o2/w14opp_I.pt OPP_EXTRA="--opp-decide-every 20 --opp-tau 0.2" ... run_closed.sh iu40 /workspace/score/rows/iu40 ...`).
- Next: card.py (one command: refs live by time block / HF tier A, ~28 stats, B-live, B3, signatures, siege facts, C via disc.py, D sealed last),
  hf_ref.py (pod 33308), human controls, THRESHOLDS v4 from controls, then score E4 / I u40.
- 14:20 update. HF reference built (a): `hf_ref.py` on pod 33308 over `/workspace/redrive/full_bec5811a` tier A = 75,229 replays ->
  150,458 side records, `/workspace/score/hf_ref_bec5811a.json.gz` (copy at humanlike/data/, not committed, sha256 e981d634...;
  rebuild: `PYTHONPATH=/workspace/redrive/pylib python -s hf_ref.py --redrive /workspace/redrive/full_bec5811a --data /workspace/hf_il_replay/data --out X`).
- B-HF human control (a, `.foreman/scratch/p2score/hf_ctl.py`, 23 stats, TOST |d| < 0.10, 20 random match-level halves):
  1,000 matches/half 0/20 pass; 2,000/half (test split) 6/20; 3,700/half (splits 1+2) 18/20. So the plan's ">= 2,000 games per
  archetype" cannot certify humans (c); pooled B-HF needs ~3,700+ matches per class, per-archetype B-HF needs the same per cell.
  `repeat_rate` is undefined for humans in HF (a card can never be played twice in a row: zero variance) -> dropped in v4.
- Pod code copy needed (a): icebow/ tree minus data (clashrl), all tracked scratchpad .py/.json/.yaml/.txt (L68 live_reader),
  the L74 tree, fin16 manifest; jpype linked into the copy root (gap.py resets PYTHONPATH to the copy root). Push script used:
  git archive of HEAD in 150-path chunks (Windows argument limit).
- 14:35 update (all (a), human data only, no model scored yet):
  - Live reference = calibration block CLXIII: 856 matches (train block has 0 CLXIII matches: CLXIII went live 10-25).
  - B-live rule (25 stats, TOST |d| < 0.20 each, RMS <= 0.10, B3 CI) on human controls: calibration halves (428/side) RMS 47/50,
    TOST 0/50, full 0/50; HF humans at the DESIGN size (856 vs 1,920, 23 stats, 40 draws) full 31/40 = 78%. The all-stats TOST at
    0.20 does not reach the >= 95% human pass rate with 25 stats at n_live 856 (c). Needs the coordinator's decision (v4 rule
    shape or more live reference data); until then card.py reports B-live under the v3 margins on the 25-stat list, labelled unregistered.
  - Siege facts on live calibration: 3,108 reach X-Bows, lock 0.466, zero-lock share 0.118 (n 754 matches with >= 2), P(lock | prev
    failed) 0.356 (n 1,267) vs P(lock | prev locked) 0.511 (n 1,007), X-Bow again in 30 s after fail 0.653 / after lock 0.564 =
    persistence 1.16. Design-size margins for a 95% human pass (bootstrap SE x (1.645 + 1.96) x sqrt(1 + 856/1920)): lock 0.046,
    zero-lock 0.051, P(lock|fail) 0.064, cond gap 0.095; per archetype only hog (0.100), other (0.094), weak_other (0.072) are
    certifiable at +-0.10 (>= ~600 live X-Bows) -> arch_min_live_xbows 600. Halves control (428/side): 0/25 full (smaller n than the design).
  - Runs: pod 32657 `/workspace/score/rows/e4` and `/workspace/score/rows/iu40` (40 workers each, ~16 rows/min each, G2 OFF:
    e1_eval HEAD raises "tap_loss / tap_slow are not defined for follow_ups plays" with the live stack). Restart = same command (resumable per block).
- 14:45 update: THRESHOLDS v4 registered (a5eb2c8f, logged above) before any model score. card.py end to end on 146 partial E4
  rows (debug, --no-c --no-d; not a result): every level runs; SIM plays are filtered to live-visible cards (o3_score.visible).
  Pod 32657 has a 54-CPU cgroup quota (cpu.max 5440000/100000), shared: E4 + I u40 at 40 workers each give ~7 rows/min each
  (~4.5 h for 1,920). Plan: score each at 960 rows (2 seed blocks), let the other 2 blocks finish (resumable).
- NEXT (in order): (1) score E4 / I u40 with `card.py score --name e4 --sim humanlike/rows/e4` (fetch: `card.py card --name e4 --no-run`),
  (2) C controls (disc.py selftest), (3) split items below.
- SPLIT (not buildable inside this ticket; each needs a production-path change outside humanlike/**):
  a. timing-head SIM decode (`gate_decode='timing_head'` in decision_options / e1_eval; REPORT_opponents section 5): without it no
     P2-OPP1 checkpoint can play a closed-loop match, so card.py can score them on level A only;
  b. model-vs-model runner with BOTH decks + levels from HF deck pairs (search_s0 has no learner-deck option): B-HF and C-HF closed loop;
  c. persona fork test (SIM forks on crforge at post-failed-X-Bow states, X-Bow again vs wait, per opponent persona);
  d. predict_live.py: per-sealed-match P_hat (64 games per match, battle-log deck); card.py's D uses per-archetype P_hat meanwhile;
  e. G2 handicap with the live stack (e1_eval: tap_loss / tap_slow undefined for follow_ups plays).

## 8. P2-SCORE results (2026-10-28 ~16:00 EDT; THRESHOLDS v4 a5eb2c8f; crforge CF-MAIN a677e080 plain, tables 16.402.22, G2 OFF)
Command: `card.py score --name NAME --sim humanlike/rows/NAME` (rows from `run_closed.sh` on pod 32657; `card.py card` = launch + fetch + score).
Reports: `out/card_e4/report.txt|json`, `out/card_iu40/report.txt|json`. Both baselines FAIL, as before (a):

| item | live (calibration, 856) | E4 (1,913) | I u40 (1,913) |
|---|---|---|---|
| B-live RMS d, 25 stats | human halves 47/50 <= 0.10 | 0.57 | 0.67 |
| worst stats | | react_lift +1.52, react_3s +1.19, opp_el -1.07 | own_half -1.65, opp_el -1.47, react_s -1.12 |
| lock rate (reach X-Bows) | 0.466 (3,108) | 0.57, diff +0.100 [+0.081, +0.118] | 0.61, +0.142 [+0.121, +0.161] |
| zero-lock share | 0.118 | 0.03 | 0.04 |
| P(lock / prev failed) vs P(lock / prev locked) | 0.356 vs 0.511 | 0.48 vs 0.59 | 0.51 vs 0.63 |
| persistence (again in 30 s after fail / after lock) | 1.16 | 1.2 | 1.2 |
| C-live AUC (n < 5,000: FAIL by sufficiency anyway) | halves 0.549 [0.490, 0.610] | 0.979 [0.971, 0.986] | 0.985 [0.977, 0.991] |
| D (sealed block) | 0 graded CLXIII matches yet | FAIL (sufficiency) | FAIL (sufficiency) |

- The SIM zero-lock share 3-4% vs live 11.8% reproduces the plan's "SIM today 3-7% vs live 9-16%" on crforge (a); the SIM
  opponents also let a failed X-Bow lock again far more often (0.48-0.51 vs 0.36): an X-Bow failure predicts the next failure
  much less in SIM than live (the adaptation-value audit fails for both).
- Engine-limited (a): block 743000 lost 7 of 480 games per opponent to a crforge UnsupportedOperationException
  ("giantbuffer_enchanting_buff on LittlePrince ... not modelled"); the scorer reads the surviving per-worker rows (473).
  run_closed.sh treats a block with < 480 merged rows as unfinished and REDOES it on restart.
- Instrument caveats (b, untested): live opponent plays are detector sightings (lag after the engine runs a play; positions =
  first clean sighting), SIM plays = engine run tick (land + 20) at the deploy point; opp_el reads the SIM counter at the last 1-s
  board sample (up to 20 ticks earlier than live's last decision). C-live therefore mixes opponent and instrument differences;
  C-HF (both exact) is the clean form and needs split item b.

## 9. THRESHOLDS v5 (2026-10-28, account 2): B-live and C-live from all recorded live matches (owner decision, HANDOFF_1028 9.9)
All (a) measured on human data only, before any model score; outputs `out/v5_shift.txt|json`, `out/v5_bnull.json`,
`out/verify/v5_bnull.json`, `out/v5_cnull.json` (+ per-draw `out/v5_cnull/`), reference `data/allref_v5.json.gz` (local, sha256
109b37ce...; rebuild = `allref.py scan` on the laptop, `parse` + `build` on a pod: section 9.5).
(The sha is of the LF file, as scorecard.load_thresholds hashes it; commit 85d0269 logged c0c2feb4..., the hash of the same content with Windows CRLF line ends: corrected before any score. allref.register now writes LF.)
### 9.1 Reference
- Population rule: every non-sealed, non-dry live_play log of the ICEBOW deck (all Marks, both accounts) with public frames and
  >= 3 detected opponent plays = **4,752 matches** (10-07 .. 10-28 09:06; logs before 10-07 have no public frames). Bait-deck
  matches (306) are out by rule: same days, bait minus icebow humans differ by d -0.44 opp_el, +0.35 own_half, -0.33 react_s.
  The sealed block is never opened: every step name-tests the stem first. (The opp_model / humanlike caches DO hold 38
  sealed-block caches each, written by v4's level_d run; excluded by name from every copy and build.)
- Weights: w = 0.5 ** (age_days / 7), age from sealed_from; **Kish n_eff 3,417** (half-life 3.5 d: 1,945; 14 d: 4,337; none: 4,752).
  Why 7 d: the owner asked for recency (harder opponents later); one week = the newest Ranked week keeps >= 50% weight per match.
- Reader / Mark shift test (`allref.py shift`, 300 matches per side at each boundary, flag |d| > 1.96 sqrt(SE^2 + tau^2), tau =
  0.099 = the excess spread of 6 same-Mark placebo boundaries): **reader boundaries shift nothing**: v2 -> merged (10-17, + Mark
  CXXXVIII) 0 stats, game build 160635001 port (10-27 05:00) 0 stats, merged -> merged_sf (10-28 07:53) 0 stats but only 18
  matches after it (smallest flaggable |d| 0.51: (b) untested at useful power; the reader trial's "play metrics unchanged" is
  the other evidence). **Mark boundaries do**: CLIX -> CLX (10-19, also the Ranked start) react_s / react_3s / react_lift /
  gap_p10 / gap_p50 / own_half; CLX -> CLXIII (10-25) own_half / bridge / troop_depth. Rule extended to Mark changes (my call:
  the opponent reacts to OUR plays, so a stat that moves with the Mark is not comparable to CLXIII SIM rows): a flagged stat is
  NaN before its latest flagged boundary (dropped, not corrected). Masks: react_s, react_3s, react_lift, gap_p10, gap_p50 from
  10-19; own_half, bridge, troop_depth from 10-25 (per-stat n_eff 1,604 / 861).
### 9.2 B-live (human null at the scored n: n_eff draws ~ w vs 1,900 human "model" games ~ w, 1,000 draws)
- Plan margins (per-stat TOST 0.20, RMS 0.10, B3 CI): humans pass **92.4%** (RMS 100%, B3 99.9%, TOST 92.4%: the max over 25
  stats of |d| + 1.645 SE has q95 0.212). RMS q95 0.050.
- v5 = max(plan, human q95): **per-stat 0.22, RMS 0.10, >= 1,900 model games; humans pass 97.4% at these limits** (same null re-run).
### 9.3 C-live (40 fresh discriminators, weighted human half vs 1,900 humans drawn ~ w from the other half, match-level split)
- AUC mean 0.499, upper-CI q95 0.556 (max 0.576); 90% of draws pass the plan's 0.55 -> **v5 limit 0.56, >= 1,900 model games**
  (C.n_per_class_min 5,000 kept for C-HF). Conservative: the null's human class has n_eff ~1,708, the scored one 3,417.
### 9.4 CONCERN (a) measured: the null has no drift, and human behaviour drifts
- Same-Mark placebo halves (a day or two apart) differ by tau ~0.10 SD per stat; the newest humans (CLXIII 10-25 .. seal, 867)
  vs the weighted older reference: RMS d 0.134 (pocket_share -0.32, ppm_ot +0.22, lane_left +0.21).
- The weighted reference sits away from the newest block by bias RMS 0.015 / 0.043 / 0.077 / 0.096 at half-life 2 / 3.5 / 7 /
  14 d (worst pocket_share +0.22 at 7 d). A model EQUAL to the newest humans, at 1,900 games, would pass v5's B-live only ~2%
  at h 7 (per-stat 0.22; RMS median 0.084), 33% at h 3.5, 60% at h 2 (noise of the low-n stats then binds); the direct target
  control (1,900 draws from the newest 867) agrees (h 7: 3%). So the owner's implementation (bootstrap at n_eff, no drift)
  makes humans pass 97% of the time only if "human" means the weighted mix, not today's opponents.
- Not changed in v5 (the owner fixed the method; E4 / I u40 fail by 5x either way). Options for v6 (owner decision): (i) a
  drift-aware null (human draws from the newest block), which at h 7 needs a per-stat margin ~0.4; (ii) a shorter half-life
  (2 d: bias 0.015, n_eff 1,129) plus (i); (iii) drop the all-25-stats per-stat TOST (the low-n stats pocket_share / ppm_ot /
  spell_depth drive its max) for per-stat margins scaled to each stat's own SE, keeping RMS. C-live has the same caveat, plus
  (b) untested: its human class mixes Marks while the SIM class is CLXIII, and the discriminator sees our play ticks.
### 9.5 Rebuild
`allref.py scan` (laptop, 3 min) -> copy logs lacking `opp_model/cache` (data/parse_list.txt) + caches (< sealed_from by name) to a
pod -> `allref.py parse` (8 shards) -> `build` -> `shift` -> `bnull --unregistered` -> `cnull --unregistered --seeds ...` -> `csum`
-> `register --half-life 7 --n-sim 1900` (writes v5 from v4). Transfer script used: scratchpad copy of p2s_xfer.sh (tar with
`--no-same-owner`; root tar exits 2 on Windows uids otherwise).

## 10. P2-SCORE STATUS (re-dispatch, account 2; updated 2026-10-28 ~16:30 EDT)
### 10.1 Baselines re-scored under v5 (sha 438a7692; `card.py score --name N --sim rows/N --no-d`, pod 32657; reports `out/card_{e4,iu40}_v5/`)
| item | E4 (1,913, a677e080) | I u40 (1,913, a677e080) | v5 limit |
|---|---|---|---|
| B-live RMS d, 25 stats vs the weighted all-matches reference | 0.60 (19 stats fail TOST) | 0.68 (17 fail) | 0.10 |
| worst stats | react_lift +1.55, react_3s +1.25, react_s -1.06, opp_el -0.99 | own_half -1.65, opp_el -1.38, react_s -1.15, bridge +0.98 | per-stat 0.22 |
| C-live AUC (90% CI) | 0.985 [0.981, 0.988] | 0.986 [0.982, 0.990] | upper <= 0.56 |
| siege (S unchanged, calibration block) | lock +0.100 [+0.081, +0.118], zero-lock -0.090 | as v4 | FAIL |
Both FAIL by ~6x on B-live and by ~0.43 AUC on C-live, as under v4 (0.57 / 0.67; AUC .979 / .985). D not read (--no-d: the
sealed block stays untouched; D1 belongs to predict_live.py).
### 10.2 Split items
- (e) G2 with the live stack: DONE, f6c2ae0 (e1_eval hunk + 3 tests; smoke on 2205952+hunk = pure 2205952 7ddefc77 / cfb86766,
  SMOKE PASS; pytest 22 passed on the pod; pyflakes: 2 warnings that pre-exist on HEAD, none new). run_closed.sh G2_ON=on now works.
- (d) predict_live.py: BUILT + smoke (24 games: 6 calibration battles x 4, CLXIII D3 + G2 vs E4; follow_ups fired with tap
  losses in the same matches; P_hat + logged sha). Battle-log mapping: 578 / 590 calibration battles map (12 hold Minion Giant,
  no engine card). The battle log starts 10-26 (poller), so D1 covers 10-26 onward. Not run on the sealed block (level D, last).
  Open wording issue for the lead: "write + hash before the block is played" cannot hold per match (the deck is known only
  after); implemented = predictions from deck-only fields, sha logged before `grade` may read outcomes.
- (b) model-vs-model runner: BUILT + smoke (pairs.py --mvm, 24 HF test-split pairs, E4 in both seats, 24/24 games; card.sim_records
  mvm gives 2 seat records per game; level_b vs HF humans runs). Owed: a full B-HF run (>= 3,700 games per class; jobs:
  `hf_ref.py --jobs 4000` on 33308) and C-HF wiring in card.score (records exist, the call does not).
- (c) persona fork test: NOT BUILT. Proposed: an eval-only driver over pipeline/cf_credit.py's xbow_after_fail trigger
  (candidates X-Bow again / wait / Rocket, K CRN continuations) with the opponent seat = each persona; per persona mean A(again) -
  A(wait). cf_credit is P3-FORK's code; needs that worker or the lead to decide the driver's home (outside humanlike/**).
### 10.3 Running / restart
- Nothing of mine is running. Pod 33308 restarted at ~18:40 UTC (uptime reset) while my 10 C-null processes (~1.4 GB each,
  4 threads each) ran beside other workers; cause not established; the draws were finished on 32657.
- Pod files: 33308 /workspace/score/v5 (code copy, 5,178 caches; the 661 copied raw logs were deleted after parsing,
  6 GB freed); 32657 /workspace/score/cb (scoring copy; placeholder empty files for the 887
  calibration log names in scratchpad/gauntlet/L68/live_reader so live_records finds the cached records), /workspace/score/pylib
  (polars, private), /workspace/score/g2 (smoke trees), /workspace/score/pl (pairs smokes), /workspace/score/v5log.
- Re-score: `ssh -p 32657 ... 'bash /workspace/score/v5log/rescore.sh'`. New closed-loop rows: crforge fe364ceb (run_closed.sh default).
### 10.4 Codex dispatches
- p2score_1 (medium): G2 smoke pair + pyflakes + pytest on 32657 -> DONE (numbers above, checked against the logs).
- p2score_2 / 2b / 2c (medium): log copy + parse on 33308 -> BLOCKED three times (ssh array quoting; sealed caches in the cache dir,
  correctly refused; ssh consuming the piped script). Done by hand instead (p2s_xfer.sh).

## 11. THRESHOLDS v6 (owner decision 10-28 ~16:10 EDT: calibrate to TODAY's humans)
All (a) measured, human data only, registered (LF sha 26568167...) before any model score. Outputs `out/v6_bnull.json`,
`out/v6_cnull.json` (+ `out/v6_cnull/`); commands `allref.py bnull6 / cnull6 / csum6 / register6` (pod 32657, run_v6null.sh).
- Reference: the same 4,752 icebow matches, half-life **2 d** (Kish n_eff 1,129; the newest block holds 82% of the weight). Masks
  unchanged; the Mark-change extension of the reader rule is LEAD-APPROVED (10-28).
- Newest block = the current Mark: CLXIII since it went live (10-25 08:49 .. seal), 856 matches with >= 3 plays.
- **B-live** (drift-aware null, 1,000 draws: model = 1,900 draws from the newest block, reference = n_eff draws ~ w from the pool):
  per-stat rule |d_k| <= **3.2 x SE_k** (each stat's own SE at the scored n; replaces the flat 25-stat TOST), RMS <= 0.10, B3 CI,
  >= 1,900 model games. **Today's humans pass 95.4%** (RMS 100%, B3 99.8%; max z median 2.21, q95 3.17; RMS median 0.043,
  q95 0.060). The v5 rule on the same draws: 57.7%.
- **C-live**: human class in scoring = the newest block only (fixes the mixed-Mark part of the ticks caveat: both classes now
  face CLXIII). Null: 40 fresh discriminators, human class = a random half of the newest block (weighted, n_eff ~393), model =
  1,900 draws from the other half: AUC mean 0.500, upper-CI q95 0.597 (max 0.657); 47.5% pass at 0.55 -> **limit 0.60**.
  Conservative (the scored human class has about twice this n_eff). Remaining caveat (b): the discriminator still sees our
  play ticks (SIM CLXIII vs live CLXIII: an instrument / engine difference can separate them, not only the opponent).
- What v6 makes stricter / looser: per-stat checks are now "no detectable difference at this n" (z <= 3.2), so a stat with a large
  SE (pocket_share, ppm_ot) gets a wide margin and a well-measured stat a narrow one; RMS 0.10 is the substantive bound.
