# Opponent human-likeness scorecard (plan1026 Pillar 2)

## Pre-registration log
| when | file | sha256 | note |
|---|---|---|---|
| 2026-10-27 | THRESHOLDS.json v1 | `5b9cd2faa46149a69bdf7d091ba2d21ef111fc9cf4ce474ad3d791b1a8f8803c` | written and committed BEFORE any scoring; numbers copied from PLAN.md / REPORT_opponents.md section 4 |
| 2026-10-27 | THRESHOLDS.json v2 | `0ba3aa32763dc3812d55fcaedd827f8fea482605945b2ca2a0cd364d6c5e2802` | before any model score. Two changes found by the human-vs-human control (see section Controls): B3 drops first_tick; A.ece_min_decisions = 200000 added. v1 is superseded |

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
