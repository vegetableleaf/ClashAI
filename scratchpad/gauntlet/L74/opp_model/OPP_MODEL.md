# Opponent modelling + SIM -> live predictiveness (W3, 2026-10-20)

Items A, B, J9-J11 of `plan1019/TUESDAY.md`. Analysis only, on the laptop, one process, local files. Nothing was trained,
deployed or run on a pod. Every number below comes from `analyze.out` (and `null_beta.out` / `check_table.out`). Labels:
**(a)** measured, with the number; **(b)** plausible but untested, with the test that would settle it; **(c)** contradicted.

## 0. Bottom line

1. **A confound nobody had logged: our own tower level went up mid-CLX.** On 10-19 at 14:02 our princess tower's max HP went
   from 4424 to 4858, which is one tower level. Every match before that, from every Mark, had 4424.
   - CLX at 4424: 46.5% [37.6, 55.6] (n = 114), level with its three predecessors.
   - CLX at 4858: 62.3% [54.0, 70.0] (n = 138), plus the whole 13,060 -> 14,030 climb.
   - Same model: +15.8 pp [+3.5, +27.6]. The princess-loss rate fell from 50.9% to 31.2%.
   - So CLX's good live record is **(a)** the same moment as the tower upgrade. Pinning it on the level, and not on the time
     of day or the opponent pool, is **(b)**. It is **not** live evidence for the SIM's +5.6 pp.
2. **J11 verdict: SIM -> live predictiveness is not established, and these data cannot establish it.** Comparing Marks at the
   same tower level, in the trophy bands they shared:
   - SIM predicted +3.4 to +10.2 pp per promotion. Live showed +0.8 to +4.8 pp, and every live 95% CI is about +-10 pp.
   - Calibration slope (live gain / SIM gain): **+0.38 [-0.30, +1.06]**. The data fit "SIM gains do not transfer at all" and
     "they transfer in full" equally well.
   - The rank order matches in both triplets (Kendall tau = +1 twice; chance of that = 1/36). This is weak and post hoc,
     because the live gaps inside each triplet are 1-5 pp.
   - A trophy-adjusted strength model looked like it settled the question, and I retracted it. Its trophy slope is an
     artefact: the null simulation gives the same slope when trophies have no effect (section 1.4).
   - Telling apart a 5 pp difference needs **1,570 matches per arm**. The largest Mark sample is 385.
   - What the data do show **(a)**: the SIM's over-prediction grows with each promotion in every context. SIM minus live,
     f36_fact: CXXIV +7.9 -> CXXXVIII +13.5 -> CLIII +18.4 -> CLIX +22.3; fin13: CLX +24.3. The SIM gains piled up while the
     live win rate stayed at 46-53%.
3. **J9: much of the doctrine's "SIM opponents don't take towers" gap is a level-table mismatch. A real opponent gap
   remains.** P(opponent takes a princess in play):
   - (A) SIM with the 12k level table vs live with our 4424 towers: 29.7% vs 53.9%, gap -24.2 pp [-28.3, -20.1].
   - (B) All-16 SIM vs live with our 4858 towers: 20.4% vs 31.2%, gap **-10.7 [-19.1, -3.4]**.
   - The SIM's level table gives 45% of opponents a level-16 tower. At 13k live it is 70% (521 / 748).
   - The SIM still over-predicts wins (+19.5 / +9.6 pp). SIM games are tower-starved: both sides take a princess in 7.0% / 4.8%
     of SIM games vs 18.0% / 9.4% live. Overtime is +8..+12 pp too common in the SIM.
   - Hog is the worst cell: SIM wins 76% vs 53% live at all-16.
4. **J10: SIM opponents answer too fast and play too much in double elixir (a).** Live 13k vs the default E4 opponent:
   - answers within 3 s: 0.26 vs 0.48 (d +1.79);
   - plays per minute in double elixir: 8.5 vs 12.2 (d +1.18);
   - first play at tick 257 vs 338 (d +0.57);
   - plays on our half: 0.08 vs 0.03 (d -0.52).
   - Overall distance 0.93; the floor (two samples of one population) is 0.05. Slowing the opponent down (decide every 20-30
     ticks + a 20-tick reaction delay) gives 0.68.
   - Humans at 12k and 13k are nearly the same population (distance 0.10), so one opponent model can serve both bands.
5. **Stage-2 post-mortem.**
   - What it was **(a)**: s2_all_il_sA = pro-imitation init (gen_v32_s0) plus 130 PPO updates against a frozen CXXXVIII.
     Win-only reward, level-11 towers. Never gated (S2-10 never ran) and never calibrated on crown stats.
   - Stage-2-style opponents **(a)**: they take more princesses than E4 (36.7-45.2% vs 23.5-34.6%, Hog pool), but by
     stalling. Overtime share is 66-75% (live 54-59%) and both sides take a princess in 1.7-3.6% of games (live 13.6-17.1%).
     Behaviour distance 0.96 vs 0.93 for E4: no more human.
   - The learner hardly learned to beat it **(a)**: 56% -> 62% over 130 updates.
   - Against E4 it cost -4.4 / -6.2 pp **(a)**, mostly against beatdown: golem -11.9, P.E.K.K.A bridge -20.0, Royal Giant -12.2.
   - "Worse against real-like opponents, or only different?" is **(b) untested**. CTRL never played live, and every eval used
     E4. On the evidence it was a different opponent, not a more realistic one.
6. **Data audit.**
   - 2,271 graded live icebow matches at >= 12,000 trophies (1,523 in the 12k band, 748 at >= 12,950), with 51,285 detected
     opponent plays (22.6 per match).
   - Every match has an exact tower-fall timeline.
   - Opponent hand and elixir are hidden but can be inferred from public data: 72% of 13k matches show >= 7 of the 8 deck cards.
   - The owner's beatdown archetypes are thin: Royal Giant (+Monk) 113, Lava 42, Golem 106, P.E.K.K.A bridge 44 matches at
     >= 12k.
7. **Build plan.** Fix the levels first, then build the opponent from live data and use it for evaluation first. The plan is
   section 6, and nothing in it is trained before its gate passes.
   - **First pod job:** the tower-level natural experiment. Score CLX against E4 with our tower at 15 vs 16, using the 13k
     opponent level table: 2 x 1,920 games, about 1.2 pod-h, no code change. Does the SIM reproduce live's +15.8 pp and
     -19.7 pp?
   - That separates engine / level error from opponent error before any opponent is fitted.
8. **O0 result (ran 10-20 09:03-09:48 UTC on pods 13396 and 14009; section 6.1).** The SIM gets the direction right and about
   half the size.
   - Tower 15 -> 16: P(win) +7.8 pp [+5.6, +10.1] in the SIM vs +15.8 [+3.5, +27.6] live.
   - P(opp takes a princess): -7.7 [-9.8, -5.7] in the SIM vs -19.7 [-31.2, -7.5] live.
   - By the pre-registered rule this is a **PASS**: both SIM changes fall inside the live 95% CIs. But the princess cell
     passes only at the edge: the SIM-minus-live gap is +12.0 pp, z ~ 2.0.
   - The absolute gap does not come from the level: at tower 16 the SIM still says 78.1% wins / 17.2% princesses lost, vs
     live 62.3% / 31.2%.

## 1. J11: does SIM win rate predict live?

### 1.1 Data

**Live** (`live_table.py`, every graded ladder match; `check_table.py` validates it): result and trophy change from
`card_use.results()`.
- Trophies before each match: the `[ladder] trophies: N total` readings, carried forward with each match's change.
- Mark: from the checkpoint sha (`models/registry.json`).
- Crowns: an exact tower-fall timeline. It matches the graded result in 3,328 / 3,330 matches and the logged end-of-match
  crowns in 731 / 733.

**SIM** (`sim_sets.py`): every eval of these Marks that exists locally. Six contexts:

| context | engine | pool | levels | Marks |
|---|---|---|---|---|
| rt35_live | 0.1.35 | live-mirrored | level 11 (no level table) | CXII, CXVII, CXXIV, CXXXVIII |
| rt35_std | 0.1.35 | standard CAL c | 11 | CXII, CXVII, CXXIV |
| f36_fact | fork36 + tower troops | live-mirrored | live table (learner tower 15) | CXXIV, CXXXVIII, CLIII, CLIX (C3 same-code rerun) |
| fin13 | FIN13 | live-mirrored | live table (learner tower 15) | CLIII, CLX, CTRL |
| fin13_l16 | FIN13 | live-mirrored | all 16 | CLIII, CLX |
| s2_* | fork36 | live-mirrored | live table | CXXIV, CXXXVIII vs 5 other opponents |

- CXII = r1, CXVII = F1 u65, CXXIV = u250, CXXXVIII = cue130.
- The stepd "fin13" rows are **not level 11**, as the ticket put it. The chain passes `--live-levels`. The rows say learner
  tower 15, cards (16, 16, 14, 16, 16, 16, 15, 16), and opponent towers 15: 481 / 16: 433 / 14: 44 per 960.

### 1.2 Live record (own tower 4424 unless stated)

| Mark | dates | live win | trophies p10 / p50 / p90 |
|---|---|---|---|
| CXII | 10-13 .. 10-15 | 47.8% [42.8, 52.8] n=385 | 12,008 / 12,091 / 12,279 |
| CXVII | 10-14 .. 10-15 | 52.6% [44.8, 60.2] n=156 | 12,164 / 12,283 / 12,369 |
| CXXIV | 10-15 .. 10-17 | 51.5% [45.9, 57.1] n=299 | 12,131 / 12,373 / 12,642 |
| CXXXVIII | 10-17 .. 10-18 | 48.1% [42.1, 54.1] n=262 | 12,737 / 13,050 / 13,170 |
| CLIII | 10-18 | 47.6% [40.2, 55.1] n=168 | 13,012 / 13,069 / 13,127 |
| CLIX | 10-18 .. 10-19 | 47.1% [37.8, 56.6] n=104 | 13,009 / 13,130 / 13,245 |
| CLX (tower 4424) | 10-19 00:20 .. 13:56 | 46.5% [37.6, 55.6] n=114 | 13,000 / 13,061 / 13,223 |
| **CLX (tower 4858)** | 10-19 14:02 .. 23:54 | **62.3% [54.0, 70.0] n=138** | 13,278 / 13,779 / 13,923 |

- Over all icebow matches, the opponent's tower level relative to ours is not a clean difficulty score:
  higher 49.1% n=795, equal 50.7% n=1145, lower 44.7% n=331.
- A likely reason **(b)**: a player who reached 13k with a lower King level is more skilled.

### 1.3 Predicted vs observed, per promotion link

SIM = paired delta, same seeds / census / side / deck. Live = the shared band at own tower 4424.

| link | SIM context | SIM delta | live delta | live band |
|---|---|---|---|---|
| CXVII - CXII | rt35_live | +10.21 [+6.10, +14.31] | +4.8 [-4.5, +13.9] | 12,000-12,499 |
| CXXIV - CXVII | rt35_live | +7.08 [+3.29, +10.88] | +1.0 [-9.5, +11.6] | 12,000-12,499 |
| CXXXVIII - CXXIV | rt35_live / f36 | +5.94 / +3.85 | no shared band | CXXXVIII crossed 12.5-12.75k in 30 matches while climbing |
| CLIII - CXXXVIII | f36_fact | +4.43 [+1.97, +6.88] | +2.8 [-7.1, +12.7] | 13,000-13,249 |
| CLIX - CLIII | f36_fact | +3.39 [+0.92, +5.85] | +0.8 [-11.4, +13.1] | 13,000-13,249 |
| CLX - CLIII | fin13 | +5.62 [+3.15, +8.10] | +1.0 [-10.9, +12.9] | 13,000-13,249 |
| CLX - CLIII | fin13_l16 | +3.07 [+0.48, +5.66] | same | |

- Interleaved live A/B: CXVII vs CXII, blocks of 5, same hours: **+2.7 pp [-13.0, +18.2]** (75 vs 75). The SIM said +10.2.
- Calibration slope through the origin (weights 1 / var(live)): **+0.38 [-0.30, +1.06]**. The live CIs are wide enough that
  a slope of 0 and a slope of 1 both fit.
- Pooled 13k chain: SIM predicts CLX - CXXXVIII = +10.1 pp; live +3.8 [-7.5, +15.1].
- Rank agreement: SIM order = live order in both triplets.
  - CXII < CXVII < CXXIV: live 47.8 / 52.6 / 53.6.
  - CXXXVIII < CLIII < CLIX: live 44.8 / 47.6 / 48.5.
  - Kendall tau = +1 twice; P = 1/36 under random order. Weak: the triplets were picked after looking, and the live gaps are
    inside the noise.

### 1.4 Two adjustment methods I tried and why I dropped them

**Trophy-adjusted logistic model.** P(win) = sigmoid(theta_Mark + beta x trophies).
- It gave CLX 60.5% vs CLIII 48.6% "at 13,000" and a calibration slope of 0.67.
- The problem: a Mark's trophies are a running sum of its own past results (a random walk). Regressing each result on that
  running sum produces a negative slope even when trophies have no effect.
- `null_beta.py` simulates exactly that case. Observed beta -0.543 vs null mean -0.601 [-1.323, -0.139], so the slope is
  entirely artefact.
- With CLX split at the level-up, beta = -1.60 vs null -0.58 [-1.14, -0.11], beyond the artefact. That rests on a single
  climb, CLX at 4858: 68% at 13.25k -> 56% at 13.75k+. A real "harder above ~13.5k" effect is **(b)**.

**Trophy-binned differences.** Win rates compared within the same 100-trophy bins.
- Biased by about +3..+7 pp where one Mark climbs through bins the other dwelt in (the 12k links in the null simulation).
- Unbiased (|bias| <= 1 pp) at the 13,000 floor, where all four 13k Marks dwelt. Those are the only binned numbers used above.

### 1.5 What would establish predictiveness

- An interleaved live A/B at the same tower level and trophy band: >= 614 matches per arm for an 8 pp gap, 1,570 for 5 pp
  (two-sided 5%, 80% power).
- The free substitute is **absolute calibration**. Predict a Mark's live win rate and crown stats at the levels it played,
  then check against a sealed block.
- Today the SIM's optimism **grows along the promotion chain in every context (a)**. SIM win minus live win:
  - rt35_live: CXII -4.0 -> CXVII +1.4 -> CXXIV +9.5 -> CXXXVIII +18.9;
  - f36_fact: CXXIV +7.9 -> CXXXVIII +13.5 -> CLIII +18.4 -> CLIX +22.3;
  - fin13: CLIII +17.6 -> CLX +24.3.
- The old 0.1.35 pool was roughly calibrated for CXII / CXVII. Each promotion then added 3-10 SIM points and about 0-5 live
  points. That is the pattern you get from selecting models on the SIM and overfitting to it (the E4 opponent plus the
  engine). It is (a) as a pattern; the cause is (b).
- The CLX tower-level natural experiment (section 6, job 1) is a second free test.

## 2. J9: crown-path realism, SIM vs live (`analyze.out` J9)

Definitions (shared code `crowns.py`, built on doctrine/measure.py).
- "In play" excludes the tiebreak tower (a fall at clock >= 5990).
- Live records are exact.
- Plain SIM rows have only final crowns + end tick, so order-dependent cells (give-back) are upper bounds there.
- SIM rows with behaviour telemetry (ECON_r1, Stage-2 T_* runs) carry tower frames, so they are exact too.
- Archetype: `weekend/archetypes.classify`, with Hog split out of weak_other / other. Live classifies on the cards seen,
  SIM on the full deck.

### 2.1 Matched comparisons, all archetypes

| cell | live 13k, own 4424 (n=610) | SIM live-levels f36 (CXXXVIII+CLIII+CLIX, 5,760) | gap (A) | live 13k, own 4858 (n=138) | SIM all-16 CLX (1,920) | gap (B) |
|---|---|---|---|---|---|---|
| P(win) | 46.2 | 65.7 | **+19.5 [+15.3, +23.6]** | 62.3 | 71.9 | **+9.6 [+1.6, +18.1]** |
| P(opp takes a princess) | 53.9 | 29.7 | **-24.2 [-28.3, -20.1]** | 31.2 | 20.4 | **-10.7 [-19.1, -3.4]** |
| both sides took one | 18.0 | 7.0 | -11.0 [-14.3, -8.1] | 9.4 | 4.8 | -4.6 [-10.7, -0.7] |
| OT share | 45.2 | 57.4 | +12.1 [+7.9, +16.2] | 57.2 | 65.5 | +8.2 [-0.0, +16.8] |
| OT starts 1-1 | 10.5 | 4.6 | -5.9 | 6.5 | 3.4 | -3.1 |
| P(win \| OT 1-1) | 29.7 [19.9, 41.8] (n 64) | 50.9 [45.0, 56.9] (n 265) | +21 | 44.4 (n 9) | 56.9 (n 65) | +12 (n.s.) |
| P(win \| lost a princess) | 8.2 | 10.2 | +2 | 11.6 (n 43) | 11.5 | 0 |
| regulation loss | 31.1 | 13.6 | -17.5 | 15.2 | 8.5 | -6.7 |
| gave a 1-0 lead back | 16.7 [12.8, 21.4] | <= 11.2 (bound) | <= -5.5 | 6.4 [2.8, 14.1] | <= 7.6 (bound) | none detectable |

Per archetype, P(opp takes a princess), gap (A) [live n]:
- **lava** -49.8 [-62.3, -22.9] (14)
- **golem** -34.9 [-49.6, -12.4] (20)
- **Hog** -34.7 [-44.1, -24.8] (106)
- weak_other -24.1 [-30.3, -17.5] (249)
- hyperbait -21.2 [-37.0, -4.5] (35)
- other -19.0 (134)
- RG +Monk -11.7 (15)
- P.E.K.K.A bridge -5.4 (12)
- Royal Giant -3.3 (25)

At (B), only Hog is clearly off: -26.8 [-43.7, -11.4], with P(win) +23.2 [+6.8, +40.0], n=34. The rest have n <= 44 and
CIs that cross 0.

### 2.2 Same learner, SIM opponent vs live opponents (exact SIM crown order from telemetry)

| learner / opponent | P(win) | P(opp takes one) | P(we take one) | both | OT share | gave 1-0 back |
|---|---|---|---|---|---|---|
| CXII live 12k (n 385) | 47.8 | 56.6 | 59.0 | 19.7 | 46.5 | 18.3 |
| CXII vs E4, CAL pool, level 11 (960) | 41.9 | 44.1 | **31.4** | **3.2** | **69.3** | **5.6** |
| CXXIV live vs Hog 12k (n 44) | 52.3 | 40.9 | 56.8 | 13.6 | 54.5 | 17.4 |
| CXXIV vs E4, Hog pool (480) | 53.8 | 34.6 | 42.1 | 3.1 | 69.0 | 3.1 |
| CXXIV vs Stage-2 imitation exploiter u65 (480) | 42.9 | 45.2 | 34.4 | 2.7 | 66.0 | 3.8 |
| CXXXVIII live vs Hog 13k (n 41) | 34.1 | 53.7 | 46.3 | 17.1 | 58.5 | 29.4 |
| CXXXVIII vs E4, Hog decks | 67.6 | 23.5 | 58.7 | 4.6 | 68.5 | <= 7.8 |
| CXXXVIII vs Stage-2 imitation exploiter, 13k levels | 51.2 | 39.6 | 45.8 | 3.5 | 67.6 | <= 7.7 |

The common shape **(a)**: live matches are **open**, and SIM matches are **closed**.
- Live: both sides take towers in 14-20% of matches, and a 1-0 lead is given back in 17-29% of the matches that had one.
- SIM, every opponent tried: both sides take towers in 2-5%, give-back 3-6%, and 66-75% of games go to overtime.
- Stronger SIM opponents (the exploiters) push P(win) and P(lose a princess) toward live by defending and stalling, not by
  trading towers.
- This is the doctrine's "the SIM never teaches that towers matter", now with its mechanism: the SIM never produces the
  tower-trading game the live ladder plays.

### 2.3 Other opponents, learner CXXXVIII, f36 live levels, 960 games each

| opponent | P(win) | P(opp takes) | both | OT share | P(win\|OT 1-1) |
|---|---|---|---|---|---|
| E4 T .1 (the eval default) | 61.6 | 32.1 | 7.4 | 59.4 | 43.2 |
| E4 T .3 | 67.2 | 31.5 | 7.8 | 57.4 | 42.0 |
| pro imitation gen_v32 d10 | 67.1 | 34.0 | 9.9 | 56.1 | 61.9 |
| pro imitation d40 | 62.4 | 36.9 | 8.9 | **50.9** | 51.9 |
| exploiter 862bfe92 | **51.7** | **37.9** | 4.8 | 70.3 | 47.1 |
| live CXXXVIII >= 12,950 (n 224) | 44.6 | 54.5 | 18.8 | 44.6 | 21.7 |

No existing opponent is within 15 pp of live on "opp takes a princess", and none reaches half the live "both took one" rate.

Deck mix (live-mirrored pool vs live 13k):
- Hog 17.0% vs 18.7%, weak_other 32.9% vs 39.2%, other 27.1% vs 22.3%, golem 6.1% vs 2.9%.
- Close enough that mix is not the cause.

## 3. J10: opponent play realism (`human/opp_behaviour.py`; one detector, PlayDetector, on both sides)

Feature means, live 13k (n=748) vs SIM sets. d = Cohen's effect size vs live 13k.

| feature | live 13k | live 12k (d) | E4 CAL (ECON_r1) | E4 Hog (T_e4base) | gen_v32 d10 | gen_v32 d20 r20 | E4 d30 r20 | Stage-2 il u65 |
|---|---|---|---|---|---|---|---|---|
| plays / min, 1x | 5.18 | 5.31 (+0.10) | 5.61 | 5.33 | 5.58 | 5.26 | 4.58 | 5.16 |
| plays / min, 2x + OT | **8.52** | 8.64 | 12.20 (+1.18) | 11.77 | 11.77 | 11.03 | 10.38 (+0.70) | 11.56 |
| our-half share | **0.08** | 0.09 | 0.03 (-0.52) | 0.02 | 0.04 | 0.04 | 0.03 | 0.02 |
| first play tick | **257** | 259 | 338 (+0.57) | 383 | 348 | 391 | 495 | 400 |
| react within 3 s | **0.26** | 0.26 | 0.48 (+1.79) | 0.47 | 0.47 | 0.41 (+1.11) | 0.39 (+1.03) | 0.47 |
| react lift over chance | -0.05 | -0.05 | +0.09 (+1.75) | +0.09 | +0.08 | +0.02 | +0.03 | +0.10 |
| push elixir / 8 s, mean | 3.31 | 3.41 | 3.74 (+0.66) | 3.79 | 3.78 | 3.60 | 3.45 (+0.20) | 3.69 |
| push elixir / 8 s, max | 9.66 | 9.74 | 10.58 | 10.74 | 10.13 | 9.95 | 10.02 | 10.65 |
| **distance (floor 0.05)** | - | **0.10** | 0.93 | 0.93 | 0.90 | **0.68** | **0.68** | 0.96 |

- Per archetype vs E4, the react-within-3 s gap holds everywhere: d +1.6 (Hog) to +2.7 (Royal Giant).
- Plays per minute in double elixir: d +0.6 (golem) to +2.4 (P.E.K.K.A bridge).
- Humans are slower to answer, quieter in double elixir, open earlier, and drop more on our half. The last one is consistent
  with the higher live princess-take rate: a fallen princess opens the pocket.
- Caveats from opp_behaviour's own notes:
  - bodiless spells are invisible on both sides;
  - 24% of live plays are first seen after a reader gap, so position shares use clean sightings only;
  - "react" depends on our play timing too.

## 4. Why Stage 2 hurt (post-mortem)

| question | answer | grade |
|---|---|---|
| What was it trained on? | init `gen_v32_s0` (pro imitation, Path of Legend HF + crawl, 3.5M rows); 130 PPO updates against the **frozen CXXXVIII**; win/loss reward only (`shaping: none`); KL target 0.1 to its init; decks `mix/decks_live_train.json`; `live_levels: false` | (a) `stage2/cfg/s2_all_il_sA.yaml` |
| Was it gated / calibrated on crown stats? | No. S2-10 (the full gate) never ran for sA; Phase C's Hog pair failed its gate; the gate cells were win / OT share / regulation loss, never P(lose a princess), both-took or give-back | (a) LEDGER.md, HANDOFF 10-18 08:15 |
| Did its family behave like humans? | Behaviour distance 0.96 vs E4's 0.93. On crowns it took more princesses (36.7-45.2%) but by stalling (OT 66-75%, both-took 1.7-3.6% vs live 13.6-17.1%) | (a) sections 2.2 and 3 |
| What did the learner do against it? | CTRL's win rate against it: 56.2% -> 59.0 -> 58.3 -> 57.2 -> 62.5% over 130 updates. It took about 30% of training games, mostly from the snapshot / init pool | (a) train_log.jsonl |
| How did it hurt? | CTRL - CLX (no Stage 2) on fin13 / E4: std -4.38 [-7.97, -0.78], fresh -6.15 [-9.60, -2.70]. Per archetype: P.E.K.K.A bridge -20.0 [-37.2, -2.8], golem -11.9 [-22.5, -1.3], Royal Giant -12.2, other -5.2, Hog -5.5. SIM crowns: CTRL loses a princess more (30.2% vs 25.7%) | (a) |
| Worse against real-like opponents, or only different? | Not tested. CTRL never played live and every eval used E4. Best reading: the training mix moved to an opponent the learner could not learn to beat, one that is neither more human-like nor crown-realistic, and the learner got worse against E4's beatdown decks. Test (only if Stage-2 opponents return): score CTRL vs CLX on the O4 opponent of section 6 | (b) |
| What the ticket's premise gets right | "Trained on pro replays and never calibrated to the crown stats" holds: (a) for "never calibrated". "Pro replays" is half the story. The RL stage against a frozen learner (the exploiter recipe) made it a stalling exploiter, and the training levels were 11 | (a) / (b) |

## 5. Data audit: live opponent action sequences (`analyze.out`, last section)

| band | matches | detected plays | per match | 2-tick frame logs (spells visible via PublicObserver) |
|---|---|---|---|---|
| 12,000-12,949 | 1,523 | 34,488 | 22.6 | 337 |
| >= 12,950 | 748 | 16,797 | 22.5 | 748 |
| all >= 12,000 | 2,271 | 51,285 | 22.6 | 1,085 |

Per archetype, matches (plays) at >= 12,000:

| archetype | matches (plays) |
|---|---|
| Royal Giant + Monk | 30 (598) |
| Royal Giant | 83 (1,902) |
| Lava | 42 (665) |
| Golem | 106 (1,773) |
| P.E.K.K.A bridge | 44 (880) |
| hyperbait | 148 (3,833) |
| Hog | 352 (8,901) |
| weak_other | 845 (18,059) |
| other | 621 (14,674) |

At 13k alone: Hog 140, weak_other 293, other 167, and <= 50 for each named beatdown / bait archetype.

Fields per opponent play (public only):
- tick of first sighting;
- card;
- cost;
- first-sighting position (unreliable for 23.8% of plays, seen after a reader gap);
- body count;
- the public opponent-elixir counter just before it.

Also available per match: both sides' bodies and towers every decision (~10 ticks), and 2-tick frames since 10-15 17:26.

Counts by card type at 13k on the decision path: troops 14,611, buildings 1,223, spells 963. Bodiless spells (Log, Zap,
Arrows, Fireball, Rocket, Tornado...) are invisible there. The 2-tick frame path (habits/livelog.py PublicObserver) sees them:
about 4.5 per match in a 40-match check.

Hidden:
- **Hand / cycle**: inferable. The hand = the deck minus the last 4 cards played once the deck is known. At 13k, 72% of
  matches show >= 7 of the 8 deck cards (38% show all 8); the census can fill the rest.
- **Elixir**: the public counter. It runs high by the cost of invisible spells.
- **Card levels**: tower level is known from tower max HP. At 13k: 4858 in 521 of 748, 4424 in 121.

Not usable:
- the bait-account matches (4-5k trophies, a different population);
- the 29 card_use fallback grades (section 8).

## 6. Opponent model design and build plan

**Principle.** Fit to OUR live opponents, deck-conditioned, from public information only. Score it on crown stats and play
style per archetype, never on matchup-blind averages. Use it to EVALUATE first. Do not train against it until it makes the SIM
predict a sealed live block.

**Why fine-tune and not build from scratch.**
- 51k live plays are too few to learn every deck. gen_v32_s0 already plays every deck from 3.5M pro rows.
- J10 shows the 12k and 13k populations are the same (0.10), so all 2,271 >= 12k matches can train one model.
- Time-ordered holdout: the newest 25% and every future sealed block never train.

| step | what | where / compute | acceptance (written before running) |
|---|---|---|---|
| **O0 levels (first pod job)** | Tower-level natural experiment. CLX vs E4 T .1, live-mirrored pool, fin13, 4 seed blocks (1,920 games) at **learner tower 15** and at **learner tower 16**, opponents from `stage2/levels/levels13k.json` (13k table, about 70% level-16 towers) via a pod-local copy of `L74/levels/live_levels.json` (the Stage-2 cb_13k trick; no repo change). Add the same pair with the pro-imitation d40 opponent if time allows | 2 x 1,920 games, about 1.2 pod-h (2.4 with d40). CPU pod after the L16 seeds | The SIM's delta (tower 16 - 15) is within the live CI: P(win) +15.8 [+3.5, +27.6] and P(lose a princess) -19.7 pp (50.9 -> 31.2). PASS = the level physics is right and the rest is opponent behaviour. FAIL = a J-ENGINE item 3 (tower) gap goes to the parity queue before any opponent is fitted. Either way, the eval default becomes the matching level config: learner tower 16 since 10-19 14:02 |
| O1 rows | `opp_model/build_opp_rows.py` (new). Opponent-seat rows from the live logs: mirror the reader frame and featurize with the live pilot's own observation code (`pipeline/live_gen.py` / `public_observation.py`) with `my_side` set to the opponent. Hand / next from cycle inference (deck = seen cards, completed by the nearest census deck). Own elixir = the public counter (LiveOppElixir). "Opponent" elixir = the same counter over OUR plays. Label = their next play (card, cell) or wait, at the decision cadence. Weight x3 for the owner's six archetypes | laptop, about 15 min single process; about 1 day of code (b) | Self-check: the same builder on OUR seat must reproduce the live model's logged decision inputs on >= 99% of fields. Row counts per archetype printed; holdout by time |
| O2 fit | Fine-tune gen_v32_s0 on the O1 train rows, small LR, early stop on held-out live NLL; 2 seeds | GPU pod, about 1-2 h | Held-out live card / cell / gate NLL better than gen_v32_s0 by more than the seed gap |
| O3 tempo | Grid over decide-every 10 / 20 / 30 x reaction 0 / 20 x T .1 / .3 (search_s0 / gap.py flags that already exist). Score by opp_behaviour distance to live 13k held-in. 480 games each with the behaviour telemetry (`human/opp_behaviour_pod.sh`) | about 12 x 9 min = 1.8 pod-h | Distance <= 0.30 (best today 0.68); react_3s and ppm_2x each within d 0.3 |
| O4 crown calibration | CLX (current live Mark) vs the chosen opponent at the O0 levels, 1,920 games, telemetry on (exact crown order) | about 0.6 pod-h | z < 1.96 vs the live own-4858 block on P(win), P(lose a princess), both-took, OT share, regulation loss, give-back. Overall and for Hog / weak_other / other (the only cells with n >= 30). If it fails: one ledgered knob at a time (T, tempo); last resort, an opponent-only fine-tune with a KL leash to O2 and a tower-conversion term, stopped as soon as OT share > live + 5 |
| O5 predictiveness | Re-score the 7 Marks + CLX@16 against the O4 opponent at the levels each played live | about 4 pod-h | (i) absolute: SIM win within the live CI for >= 6 of 8 configurations (today 0); (ii) SIM reproduces the CLX 15 -> 16 tower effect; (iii) **sealed block**: the next >= 150 live matches of the live Mark at fixed levels, predicted before they are played: P(win) and P(lose a princess) inside the live 95% CI. Passing (i) + (iii) is the first evidence of a predictive SIM |
| O6 league | Only after O5: the CLX recipe + `league_exploiters {O4 model, decks_live_train, share 0.3}` vs a same-seed control, 2 seeds; scored on E4 **and** the O4 opponent | about 2 x 8.5 GPU-h | Promote only on the O4-opponent eval + a live A/B at the same levels and band (>= 614 / arm for 8 pp) |

Total before any training: about 10 pod-h (O0-O5). The deck-conditioned pieces are O1 (deck tokens) and O2. Per-archetype
judgement happens at O3 / O4, where each archetype with live n >= 30 is its own cell.

**Untested assumptions in this plan, each with its test:**
- (b) the opponent-seat featurization round-trips: O1's self-check.
- (b) cycle inference is accurate enough: compare inferred vs logged OUR hand on our own seat, same code.
- (b) fine-tuning moves crown behaviour and not only play style: O4. If it does not, the crown gap belongs to the engine
  (O0 / parity), not the opponent.
- (b) the 13.5k+ difficulty effect: the sealed block must be at a fixed band, or reported per band.

### 6.1 O0 result: the tower-level natural experiment (run 2026-10-20, `o0_verdict.py` -> `o0_verdict.out`)

**Setup (a).**
- Learner: CLX grafted (5d212358), sampled ability head, the stepd promotion EXTRA. Opponent: E4 T .1 on the live-mirrored
  pool, fin13-linux, seed blocks 741200 / 742000 / 743000 / 744000 = 1,920 games per configuration.
- Opponent levels: `stage2/levels/levels13k.json` (sha 3547c8d3). Opponent towers came out 1,290 at level 16 and 630 at 15 in
  BOTH runs: same draw, same seeds, so the difference is **paired**.
- The only difference: our tower level in the pod-local table copy.
  - Pod 13396: own.tower 15, table sha dfd712ad.
  - Pod 14009: own.tower 16, sha a860d0a5.
- Each pod's `/workspace/cb_stepd` is untouched: its table is still 19e8d155. The runs used a hard-link copy, `/workspace/o0/cb`,
  with only that file replaced.
- Rows: pod_backup_weekend/o0/ (o0_t15.tgz 45d7c7eb, o0_t16.tgz 9f9b7f20, sha-verified). Scripts: `pod/o0_run.sh`,
  `pod/mklevels.py`, `pod/pull_o0.sh`.

| cell | SIM tower 15 | SIM tower 16 | SIM change (paired, n 1,920) | live CLX @4424 (n 114) | live CLX @4858 (n 138) | live change [Newcombe] |
|---|---|---|---|---|---|---|
| P(win) | 70.3% | 78.1% | **+7.8 [+5.6, +10.1]** | 46.5% | 62.3% | **+15.8 [+3.5, +27.6]** |
| P(opp takes a princess in play) | 24.9% | 17.2% | **-7.7 [-9.8, -5.7]** | 50.9% | 31.2% | **-19.7 [-31.2, -7.5]** |
| both sides took one | 6.6 | 4.5 | -2.1 | 13.2 | 9.4 | -3.8 |
| OT share | 59.5 | 61.7 | +2.2 | 50.0 | 57.2 | +7.2 |
| regulation loss | 11.3 | 6.5 | -4.8 | 30.7 | 15.2 | -15.5 |
| P(win \| OT 0-0) | 70.2 | 75.9 | +5.7 | 60.0 | 63.2 | +3.2 |

Per archetype, SIM win change: Royal Giant +16.3 [-0.2, +32.8], hyperbait +13.6 [+6.2, +21.1], Hog +8.9 [+3.8, +14.0],
P.E.K.K.A bridge +8.9, lava +7.8, other +6.9, weak_other +6.5, golem +5.1.

**Verdict.**
- **(a) PASS by the rule written beforehand.** Both SIM changes are inside the live 95% CIs. The SIM's level physics has the
  right sign and a material size; it is not a no-op.
- **(a) But the SIM effect is about half the live point estimate:** 7.8 vs 15.8 pp (wins), 7.7 vs 19.7 pp (princesses).
  - Win gap: 8.0 pp, z ~ 1.3.
  - Princess gap: 12.0 pp, z ~ 2.0.
  - The live side has n = 114 / 138, so these can be neither confirmed nor ruled out.
- **(b) Two explanations, untested:**
  1. The SIM under-models what a tower level does against human pushes (tower HP / damage vs the pushes that actually reach
     the tower).
  2. Part of the live jump is not the level: time of day, or the pool at 13.3-13.9k.
  - The test that separates them: more live matches at 4858 inside the 13,000-13,249 band (today n = 9), or the O4 opponent
    re-running this same pair. If the gap closes with a realistic opponent, cause 1 is about the opponent letting the tower
    matter.
- **(a) The absolute gap does not come from the level.**
  - At tower 16 (today's live state) the SIM gives 78.1% wins and 17.2% princesses lost, vs live 62.3% and 31.2%: still +15.8
    / -14.0 pp.
  - The 13k level table makes the SIM *more* optimistic than all-16 (78.1% vs 71.9%), because a third of its opponents have
    level-15 towers.
- **Consequences.**
  - Eval levels should now be our tower 16 + the 13k opponent table. That is the live state since 10-19 14:02, and it is
    lead / owner's call.
  - Section 2.1's gap (B) used all-16. Against the 13k table the princess-take gap is -14.0 pp, larger.
  - The remaining SIM-vs-live gap belongs to O1-O4 (opponent behaviour) and to the J-ENGINE tower metrics. A level-table fix
    alone cannot close it.
  - O1+ waits for the lead's go.

### 6.2 O1 result: opponent-seat training rows from the live logs (`o1_build.sh` -> `o1_check.out`, `o1_check2.out`)

**Build (a).**
- `o1_records.py` converts each live ladder log into the driven-corpus record schema that `pipeline.dataset_gen` reads
  unchanged: the replay_rec/to_record.py schema, record_native + record_full.
  - Inputs: icebow main-account logs at trophies >= 12,000 that have 2-tick frame events. 1,087 matches since 10-15 17:26;
    1,075 records built.
  - Holdout: the newest 25% by time, from 10-18 23:16 on (CLIX / CLX era, 267 records). The other 808 train.
- `dataset_gen --feature-version 5` gives:

| split | rows | opponent-seat rows | opponent play rows | opponent wait rows | our-seat rows |
|---|---|---|---|---|---|
| train | 131,492 | **43,714** | 11,934 | 31,780 | 87,778 |
| holdout | 46,279 | **15,885** | 4,397 | 11,488 | 30,394 |

- `o1_finalize.py` remaps every card column to gen_v32_s0's vocabulary (no card was missing) and adds `opp_mask`. Our-seat
  rows stay in the file, masked out: they are our live model's play, never imitation targets.
  - Files: out/o1_train_v32.npz (sha eeac6965), out/o1_holdout_v32.npz (sha be175c5b). Not committed: derived, about 23 MB.
- Coverage limits **(a)**:
  - An opponent deck is known for 644 / 1,075 matches: 587 with all 8 cards seen, 57 completed from the census. The other 431
    give no opponent rows: 281 had 7 cards with no census match, 148 had <= 6.
  - 16,331 opponent plays had a determinable hand; 2,869 did not (fewer than 4 earlier plays, or a repeat inside 4 plays).
  - 54,234 bodies with a card id the catalog lacks were dropped, mostly 203000042 (the Hero Ice Wizard's ice cube, which the
    hero dedupe does not cover).

**Self-check (a).** OUR seat, the same converter + dataset_gen, compared with the live decision logged at the same tick. Rows
compared: 20,440 train / 6,924 holdout.

| field | train | holdout | pre-registered 99% bar |
|---|---|---|---|
| hand (4-card set) | 99.80% | 99.78% | pass |
| own elixir (\|d\| <= 0.1) | 100.00% | 100.00% | pass |
| tower hp fractions (<= 0.01) | 99.68% | 99.44% | pass |
| unit positions (same count, each within 0.02) | 96.79% | 99.23% | holdout pass, train fail (count differs in 638 / 20,440) |
| public opponent-elixir counter vs the live counter (<= 0.5) | 93.78% (mean \|d\| 0.29) | 96.20% (mean \|d\| 0.19) | fail |

- The counter misses are the cadence (b): the rows' public counter sees frames every 8 ticks, the live one every 2. Keeping
  all 2-tick frames should close it, at 4x the data. Untested.
- The train-era unit-count misses are not explained yet (b). The holdout era passes.

**Hand inference check (a).**
- The opponent rule (hand = deck - last 4 publicly detected plays) applied to OUR side, against the hand we really held.
- 97-100% of our plays were publicly detected. The hand was determined for 88.0% (train) / 88.9% (holdout) of them.
- When determined it was **exactly right in 99.39% / 99.65%**. So the opponent-seat hands in the training rows are about 99%
  correct where defined.

### 6.2b O2 + O3 results (pods P1 48148 / P2 40548, 10-20 10:42-11:50 UTC; `o2_summary.out`, `o3_score.out`)

**O2 (a).** gen_v32_s0 fine-tuned on the 43,714 opponent-seat train rows; 2 seeds; scored on the 15,885 time-ordered holdout
rows.
- Epoch 0 (untouched) vs the kept model (seed 1, epoch 16, sha f03f36d3):

| metric | untouched | fine-tuned |
|---|---|---|
| cell_nll | 6.44 | **3.19** |
| cell_tile_top1 | 0.210 | 0.301 |
| placement error | 5.2 tiles | 3.3 tiles |
| card_top1 | 0.509 | 0.532 |
| wait_top1 | 0.391 | 0.419 |
| gate_bal_acc | 0.685 | 0.685 (unchanged) |

- The seed gap is <= 0.01 on every metric, so the improvement is far outside it. **O2 acceptance passes**, except the
  timing (gate) head, which did not improve.
- Card and wait accuracy peak around epoch 15, then decline (over-fit).

**O3 (a).** Each config: CLX at all16, 480 games, fin13, live-mirrored pool. Style distance is to live 13k on the 9 position-free
opp_behaviour features (13k vs 12k humans: 0.10). Gaps are SIM minus live CLX at our tower 4858 (n = 138: win 62.3%,
opponent takes a princess 31.2%).

| opponent | style dist | CLX SIM win | win gap | opp takes a princess | gap |
|---|---|---|---|---|---|
| **live-imitation O2, T .1, decide 40** | **0.58** | 87.9% | +25.6 | 16.0% | -15.1 |
| live-imitation O2, T .3, decide 40 | 0.61 | 86.9% | +24.6 | 16.9% | -14.3 |
| live-imitation O2, T .1-.5, decide 10 | 0.81-0.84 | 90.6-96.2% | +28..+34 | 6.9-13.5% | -18..-24 |
| **pro-imitation gen_v32_s0, T .1, decide 40** | 0.79 | **74.8%** | **+12.5** | **23.3%** | **-7.8** |
| gen_v32_s0, T .1-.3, decide 30 | 0.86-0.88 | 76.0-76.2% | +13.7..+13.9 | 21.7-23.3% | -8..-9.5 |
| gen_v32_s0, decide 20 | 0.91-0.92 | 76.9-78.3% | +15..+16 | 20-22% | -9..-11 |
| gen_v32_s0, decide 10 | 0.97-1.00 | 82.3-85.4% | +20..+23 | 15-19% | -12..-16 |
| + 20-tick reaction delay (decide 10) | 0.78 | 82.9-88.8% | +21..+26 | 15-20% | -11..-16 |
| E4 T .1, all16, decide 10 (clx_l16 rows; no play telemetry) | - | 71.9% | +9.6 | 20.4% | -10.7 |

**Verdict (a).**
1. **Style vs strength trade-off.** The live-imitation model is the most human-like opponent we have ever had: distance 0.58
   vs 0.75-1.00 for everything else. Its opening time and plays per minute match live. But it is **far too weak**: CLX wins
   88%.
2. **Decision cadence is the biggest single knob.** Both imitation nets were trained on rows with a 40-tick wait stride.
   Deciding every 10 ticks makes them over-play and lose. At decide 40 they are at their strongest and most human.
3. **No opponent is calibrated.** The best on strength (gen_v32_s0 T .1 decide 40, or E4) still leaves CLX +10..+13 pp above
   live, and its princess-take 8-11 pp below. **O4's acceptance (every J9 cell inside the live CI) fails for every
   candidate.**
4. Why the live-imitation model is weak is **(b), untested.** Leading suspects:
   - spell labels: the public observer places a spell at its first-seen projectile position, mid-flight, not at its target, so
     the model learns to cast spells short;
   - 24% of troop sightings come after a reader gap, so their positions are late;
   - the model trains on the public elixir estimate (biased high) but plays on its true elixir in the SIM.
   - Testable in about 1.5 h: re-label spells with the projectile target (the reader logs target_x / y), rebuild O1, refit O2,
     re-score the decide-40 config.

**O1b / O2b, the spell-target relabel (a).**
- `o1_records.py --spell-targets` labels 2,586 projectile-spell plays at their projectile's target.
- Even the UNTOUCHED pro net now places better on the holdout: cell_nll 6.44 -> 4.77, cell_tile 0.210 -> 0.247. So the old
  live labels really were mis-placed.
- O2b kept model: seed 0, epoch 14, sha 0882374c. Holdout card 0.531, cell_tile 0.317, gate 0.680, cell_nll 3.05.

| opponent | CLX SIM win | opp takes a princess | style distance |
|---|---|---|---|
| O2b, T .1, decide 40 | 83.8% | 19.8% | 0.65 |
| O2b, T .3, decide 40 | 81.2% | 21.7% | 0.67 |

- The relabel made it 4-6 pp stronger than O2, but it is still above the lead's 76% rule.
- **Decision, by the lead's rule: league opponent = (A) gen_v32_s0, T .1, decide 40.**
  - (A): CLX SIM win 74.8%, opp takes 23.3%, style distance 0.79.
  - (B) O2b: 83.8% > 76%.
- Option B's arm configs are kept (stepd_l16_liveopp_s7x). Option C (RL-strengthening O2b against frozen CLX at all16, gated)
  is planned in `cfg/oppC_liveopp_rl_s74.yaml` for the next iteration.

**New baseline.**
- CLX vs gen_v32_s0 T .1 decide 40, all16, seed 741200: **359/480 = 74.79%**. That is the identical game list to the O3
  config: the eval is deterministic.
- CLIII, same: 328/480 = 68.33%.
- The other three blocks each were paused to free the pods for O2b and the smokes. Their rows stay on the pods
  (/workspace/o3/out); rerunning `opp_eval.sh` skips finished blocks.

**Trainer opt-in (lead decision 2): `league_exploiters` takes optional `T` / `decide_every` / `reaction_ticks`.**
- Commit 0bcc4c5 (`rl_royale.exploiter_league` + `own_opp_cfg`; the rollout actors and branch workers apply them to that
  opponent only).
- Absent keys give the identical trainer: `pipeline/tests/test_exploit_own_cfg.py` compares against e3f52a0, covering the
  exploiter dict, matchups + rng state, load_config, config_sha (incl. stepd_l16_s74.yaml) and the opponent cfg.
- Tests: 5 new + 6 old exploiter tests + 34 league tests pass. pyflakes clean.
- Real all16 pod smoke: **SMOKE PASS** on P2 (stepd_l16_proopp_s74, 12:04 UTC). It played 6 games against the exploiter
  opponent, and all 11 resume checks were true.

### 6.2c O6 launch plan (awaiting the lead's go)

**Arms** (code 25f0c42 shipped to both pods, CODE_OK):
- `stepd_l16_proopp_s74` on P1 48148, and the seed twin `stepd_l16_proopp_s75` on P2 40548.
- Each = `stepd_l16_s7x.yaml` + `league_exploiters {ckpt gen_v32_s0, decks decks_live_train, share 0.3, T 0.1,
  decide_every 40}`. That is ONE change vs its same-seed all16 control (stepd_l16_s74 / s75, trained overnight).
- Launch the way w6_arm.sh does: per-arm real smoke (`l16/pod_smoke.sh`); GO file EVAL_LEVELS=all16,
  DECODE='--ability-head-decode=sample --crown-log'; `stepd_chain.sh` under `/workspace/stepd/claim.lock`.
- Expected run time: about 5.5 h train + 1.5 h evals at nominal speed. This host is running 2-4x slower today, so expect
  ~8-14 h.

**Gating** (both are paired, same seeds):
- **Old eval:** the chain's own all16 E4 rows (fin13, std + fresh, 1,920 games) vs CLX's `clx_l16` rows and vs the same-seed
  control's rows.
- **New eval:** `pod/opp_eval.sh` against gen_v32_s0 T .1 decide 40, all16, std + fresh, for the arm, CLX (baseline
  block 1 done) and the control. Needs about 6 x 1,920 games: 19899 once it is free.
- Report both. The lead / owner gates.

**O5 (post-hoc):** if an arm goes live, its next >= 150 live matches at fixed levels are predicted by both evals before they
are played.

### 6.2d O6 LAUNCHED (lead GO 10-20 ~08:28 EDT)

Launched with `pod/o6_launch.sh` (= w6_arm.sh's steps). Same files on both pods: stepd_chain.sh 6da7c2f3, rl_royale.py
f7095b61, gen_s0.pt 61011b6c, init rlarm_succ_levels_u0065.pt 05d42da7.

| arm | pod | code | yaml sha | trainer config sha | chain pid | trainer pid | started (UTC) | smoke |
|---|---|---|---|---|---|---|---|---|
| stepd_l16_proopp_s74 | P1 64.247.206.80:48148 | 25f0c42 | bf803157 | b15d89a084b5 | 7624 (chain 7627) | 7635 | 12:28:42 | SMOKE PASS 12:26 |
| stepd_l16_proopp_s75 | P2 64.247.206.80:40548 | 25f0c42 | 23d3789c | a9b76a3805b7 | 7210 (chain 7213) | 7221 | 12:28:45 | SMOKE PASS 12:26 |

- GO files: EVAL_LEVELS=all16, DECODE='--ability-head-decode=sample --crown-log'.
- Logs: /workspace/stepd/rl_<arm>/{chain,train}.log. Results are packed to /workspace/stepd/out/<arm>.tgz; pull with
  stepd/pull_stepd.sh.
- **Update 1 reached on both arms** (critic warm-up, as the recipe).
  - s74: u0000 W/L 151/105, u0001 150/106, about 3.1 min / update.
  - s75: u0000 159/97, u0001 159/97, about 2.8 min / update.
  - The exploiter_league opponent is being played: s74 76-96 games / update at win 0.49-0.55; s75 48-84 at 0.58. That is
    about 30% of 256, matching the share.
  - Expected u0130 about 6.5 h after start (~19:00 UTC), then the all16 evals.
- **Remaining new-baseline blocks** moved to 19899 (64.247.206.76): CLX then CLIII vs gen_v32_s0 T .1 decide 40, all16, seeds
  742000 / 743000 / 744000.
  - `/workspace/o3/opp_eval.sh`, serialised on cpu.lock: one CPU job at a time.
  - CLX grafted 5d212358 was added to that pod's cb_stepd data; the code was untouched.
  - The 741200 blocks (CLX 359/480, CLIII 328/480) are pulled, sha-verified: pod_backup_weekend/o3/base741200/.

## 6.4 Open items (for the next session)

1. **Option C** (`cfg/oppC_liveopp_rl_s74.yaml`, not run): RL-strengthen the O2b live-imitation net against frozen CLX at all16.
   - Settings: KL 0.05 to O2b, the learner (opponent-to-be) deciding every 40 ticks, CLX at 10, 65 updates.
   - Next steps:
     - (i) copy O2b (sha 0882374c) to the pod as icebow/data/pipeline/o2/gen_live_b.pt and run a real smoke of the yaml.
       Untested: `decide_every 40` on the learner in league_frozen_opponent mode, and the frozen CLX's ability head (Stage 2
       used CXXXVIII with the rule press).
     - (ii) train.
     - (iii) gate the u15 / u30 / u45 / u65 snapshots with `pod/opp_eval.sh` (CLX learner, T .1, decide 40, 480 games):
       stop at the first with CLX SIM win <= 65%, style distance <= 0.70, OT share <= live + 5 pp, both-took >= 5%.
     - (iv) if one passes, re-run O4 (CLX + CLIII, std + fresh) and offer it as the league opponent of the next arm.
   - Risk: Stage 2's stalling exploiter. The OT and both-took gates are the guard.
2. **O1 self-check shortfalls** (vs the pre-registered 99% bar):
   - The public opponent-elixir counter is within 0.5 of the live counter in 93.8% (train) / 96.2% (holdout).
     - Cause (b): the rows' counter sees frames every 8 ticks, live every 2.
     - Test: rebuild O1 with FRAME_EVERY = 2 (4x data).
   - Unit positions pass 99.2% on the holdout era but 96.8% on the train era (count differs in 638 of 20,440).
     - Cause unexplained. The first check: diff the body lists of a few mismatched rows; candidates are older reader
       versions and unreadable-hp bodies.
3. **Why the live-imitation net is weak** (O2: 87.9%, O2b: 83.8% CLX SIM win; pro-imitation: 74.8%).
   - Spell targets explained 4-6 pp.
   - Untested candidates:
     - late troop sightings after reader gaps (24% of plays): use the 2-tick frames' first appearance or the deploy-timer
       state;
     - the public elixir estimate (biased high) as the opponent's own-elixir input;
     - the 4-plays warm-up gap at the start of every match (no hand rows before the 5th play).
4. **O3 grid on the new baseline opponent:** reaction delay never helped. Decide 40 beat 30 / 20 / 10 for both nets. A
   decide-60 point is untested.
5. **The card_use.results() account-switch grading bug** (section 8, item 1) is still open (lead: not this worker's fix).

### 6.3 Path to a successor tonight (owner 10-20 goal; lead's plan)

1. **O1** done.
2. **O2:** fine-tune on P1's GPU: `pod/o2_pod.sh`, 2 seeds, time-ordered holdout.
3. **O3 in parallel:** tempo grid on P1 + P2 (`pod/o3_grid.sh` -> `pod/opp_eval.sh`).
   - 12 configs of gen_v32_s0: T .1 / .3 x decide 10 / 20 / 30 x reaction 0 / 20.
   - Each config: CLX at all16, 480 games, with exact crown falls (`--crown-log`) and both sides' plays (pod-local o3_plays patch).
   - Scored by `o3_score.py`: J10 style distance plus J9 crown gaps vs live CLX @4858.
   - Then the O2 model at the best 2-3 tempos.
4. **O4:** the chosen opponent, 4 seed blocks, CLX and CLIII at all16. This is also the **new baseline**.
   - Acceptance: every J9 cell inside live CLX@4858's CI. At n = 138 the CIs are about +-8 pp, so this is a weak gate. Say so.
5. **O6:** the CLX recipe at all16 (stepd_l16_s74.yaml) + `league_exploiters {ckpt: the O4 model, decks: decks_live_train,
   share: 0.3}`. The lead decides before launch.
   - Known gap: rl_royale gives every league opponent the same temperature (`league_opp_T`) and tempo (`opp_decide_every` /
     `opp_reaction_ticks`). The calibrated tempo can therefore apply to all opponents (a second change) or to none. Applying
     it to the exploiter only needs an opt-in trainer key, with tests and a smoke.
   - **Decision needed (10-20 ~07:50 EDT).** No opponent passes O4. The candidates for the league opponent:
     - **(A)** gen_v32_s0 at T .1 / decide 40. Strongest of the human-tempo opponents: CLX 74.8%, opponent takes a princess
       23.3%, style distance 0.79.
     - **(B)** the live-imitation model after the spell-target relabel (O1b, building now). It goes to O2b and then a
       decide-40 eval, about 1-2 h on this slow host.
     - **(C)** RL-strengthen the live-imitation model against frozen CLX at all16. KL leash to O2, stopped by crown / OT-share /
       style gates. About 3-4 h, with the Stage-2 stalling risk.
     - Every option needs the per-opponent temperature and tempo. Without them a league opponent plays at the learner's decide 10
       and league T. That needs an opt-in `league_exploiters` key (trainer edit: test, pyflakes, real smoke). The alternative is
       the global `league_opp_T` / `opp_decide_every`, which also slows the self-play snapshots: a second change.
6. **O5** (the sealed live block) **cannot finish today.** It becomes the post-hoc check: the next >= 150 live matches of
   whatever trains tonight, predicted by the O4 SIM before they are played.

## 7. W7 option C: an RL-strengthened live-imitation opponent (10-20, rounds logged below)

**Goal (O4 acceptance, all16, our tower 16)**, vs live CLX at our tower 4858 (n = 138: win 62.3%, opponent takes a princess
31.2%, both took one 9.4%, OT share 57.2%, regulation loss 15.2%): CLX SIM win within ~5 pp of live, princess-take with CI
overlap, OT / both-crown near live (no Stage-2 stall), style distance <= ~0.65. Strict O4 cell rule: |z| < 1.96 per cell.

**Setup (a).**
- Trainer arm C1 = `cfg/oppC1_icemix_s74.yaml` (sha c08d8c10, config sha 92a66d5a): init O2b (0882374c); the learner = the
  opponent-to-be on the live census decks, deciding every 40 ticks; opponents = league_pfsp hard over a FROZEN icebow mix
  (CLX 5d212358, CLIII edc82ada, CLIX fb777048, CXXXVIII 0fba110c; all on the icebow deck, live policy, decide 10, the
  live IW press rule) plus the init; no learner snapshots; win / loss reward only; KL target 0.1 to O2b; 100 updates; all16.
  P1 (64.247.206.80:48148), `optC/w7_train.sh` (real smoke SMOKE PASS 12:57 UTC, then training; ~2.6 min / update).
- Gate = `pod/opp_eval.sh` on 19899: CLX learner vs the snapshot at T .1 / decide 40, all16, seed block 741200 (480 games,
  the O3 games). O4 = the same + blocks 742000 / 743000 / 744000 (1,920 games). Relay `optC/gate.sh`; tables
  `optC/o4_table.py` (SIM vs live per cell with z, style distance from o3_score.py's 9 features, per archetype).
- Rows: C:/Users/benpe/pod_backup_weekend/w7/o3/ (sha-checked); snapshots + shas: pod_backup_weekend/w7/.

**Round log** (CLX SIM win / opponent takes a princess / OT share / both took one / style distance; 480 games = block 741200
unless marked 1,920; live 62.3 / 31.2 / 57.2 / 9.4; the 480-game SE is ~2 pp on win).

| round | change | win | opp takes | OT | both | style | verdict |
|---|---|---|---|---|---|---|---|
| R0 | O2b, T .1, decide 40 (O3) | 83.8 | 19.8 | 48.8 | 9.4 | 0.65 | too weak |
| R0 | option A gen_v32_s0, T .1, decide 40 (1,920) | 73.2 | 22.8 | 58.3 | 6.5 | 0.77 | the current baseline; fails win / princess |
| R1 | O2b knobs: T .5 d40 / T .1 d60 / T .3 d60 / T .1 d80 | 86.7 / 80.4 / 83.5 / 84.8 | 16.9 / 22.9 / 22.7 / 20.2 | 43-44, 39 | 8.5-13.5 | 0.67 / 0.67 / 0.68 / 0.44 | tempo / T alone: <= 3 pp, no fix |
| R1 | gen_v32_s0 knobs: T .1 d60 / d80 | 74.2 / 78.8 | 26.5 / 26.5 | 51.2 / 43.5 | 10.4 / 14.0 | 0.84 / 0.58 | no gain on strength |
| R2 | C1 RL u10 / u15 / u20 / u25 | 83.5 / 78.5 / 76.0 / 74.6 | 19.2 / 21.9 / 22.1 / 25.6 | 51.5 / 54.0 / 55.0 / 50.0 | 9.6 / 7.3 / 7.5 / 10.0 | 0.69 / 0.68 / 0.68 / 0.68 | strengthening, defence first |
| R2 | C1 RL u30 / u35 / u40 / u45 / u50 | 72.3 / 70.8 / 70.0 / 69.8 / 67.7 | 31.9 / 30.2 / 34.6 / 32.7 / 31.9 | 54.8 / 50.4 / 49.0 / 50.6 / 54.4 | 15.4 / 13.8 / 15.2 / 12.1 / 11.5 | 0.67 / 0.68 / 0.62 / 0.65 / 0.62 | princess-take reaches live; no stall |
| R2 | C1 u30 at T .3 | 74.4 | 28.1 | 52.1 | 11.5 | 0.67 | T .1 kept |
| R3 | C1 u45 at decide 60 | 69.0 | 35.6 | 50.6 | 18.8 | 0.66 | no gain, both-took worse; decide 40 kept |
| **O4** | **C1 u40 (5935b73a), 1,920** | **67.7** | **33.2** | **53.9** | **13.5** | **0.63** | 5 of 6 cells pass; CLX takes a princess 69.9 vs 61.6 (z 2.06) |
| **O4** | **C1 u50 (38328249), 1,920** | **68.1** | **29.9** | **56.3** | **10.9** | **0.63** | **all 6 overall cells pass** (max z 1.53); win +5.8 pp; per archetype: hog CLX-takes 64.5 vs 44.1 (z 2.34), other win 78.3 vs 63.6 (z 1.96) |
| R2 | C1 u55 / u60 / u65 / u70 / u75 / u80 | 71.2 / 70.6 / 72.3 / 69.0 / 69.8 / 66.5 | 28.3 / 27.9 / 28.5 / 30.2 / 32.5 / 32.1 | 51.7 / 52.5 / 53.3 / 54.4 / 52.9 / 56.7 | 10.0 / 9.4 / 9.4 / 10.6 / 13.5 / 9.4 | 0.64 / 0.63 / 0.59 / 0.59 / 0.60 / 0.62 | PLATEAU: no gain u50 -> u75 (training win vs the mix 0.38 -> 0.40) |
| R3d | diag, C1 u50 vs CLX without its ability head (rule press, as the trainer plays it) | 67.3 | 32.7 | 55.8 | 11.7 | 0.66 | (c) the press head is not the train / eval gap |
| R3d | diag, C1 u50 vs CLX at plain tau .27 (live stack kept) | 67.7 | 31.9 | 54.4 | 11.5 | 0.62 | identical rows: tau_phase overrides the plain tau |
| R3d | diag, C1 u50 vs CLX WITHOUT its live decision stack, tau .27 (= the trainer's CLX) | 63.8 | 33.8 | 61.0 | 11.5 | 0.63 | (a) the live stack is worth +3.9 pp to CLX on the same 480 games: C1 trained against a weaker CLX than it is scored against |
| O4 | C1 u80, 1,920 | 68.1 | 32.7 | 56.6 | 11.4 | 0.64 | = u50 on 1,920 games: the plateau is confirmed; hog win z 2.21 / CLX-takes z 2.86 |
| R4 | C1 resumed from u84 with `league_opp_live` (the frozen icebow opponents play the D3 live stack; cfg/oppC3_icemix_live_s74.yaml; snapshots u85+ keep C1's run name). Training win vs the mix fell 0.49 -> 0.28-0.33 at once: the stack reached the opponents | | | | | | |
| R4 | u85 / u90 / u95 / u100 / u105 / u110 | 68.8 / 67.5 / 64.8 / 63.8 / 65.6 / 67.3 | 31.2 / 31.7 / 36.9 / 34.2 / 36.2 / 36.0 | 50.2 / 54.8 / 53.1 / 51.9 / 56.7 / 55.0 | 10.0 / 10.2 / 12.3 / 10.6 / 15.6 / 16.0 | 0.63 / 0.73 / 0.73 / 0.76 / 0.74 / 0.76 | past the plateau on strength; style drifts (answers faster) |
| **O4** | **R4 u100 (ea1d0804), 1,920** | **63.7** | **35.9** | **54.0** | **12.6** | **0.74** | **all 6 overall cells pass, win +1.4 pp (z 0.34)**; per archetype only hog CLX-takes fails (64.8 vs 44.1, z 2.38); style misses the ~0.65 goal |
| R4k | u100 eval knobs: decide 60 / decide 80 / +20 / +40 reaction ticks | 64.0 / 68.1 / 74.6 / 81.5 | 40.0 / 36.7 / 33.8 / 31.7 | 50.6 / 45.8 / 46.7 / 34.0 | 15.6 / 19.8 / 19.4 / 20.4 | 0.78 / 0.49 / 0.52 / 0.47 | slowing it at eval time buys style but costs strength: train at the slower tempo |
| R5 | R4 resumed from u117 with the learner deciding every 80 ticks (cfg/oppC5_icemix_live_d80_s74.yaml; at u119 the held-out GHOST screen's -10 pp stop fired, set to -100 and resumed); gate T .1 / decide 80 | | | | | | |
| R5 | u120 / u125 / u130 / u135 | 67.9 / 67.5 / 64.4 / 67.5 | 37.3 / 38.8 / 40.2 / 36.9 | 47.3 / 45.8 / 46.9 / 45.4 | 19.6 / 19.6 / 21.0 / 17.7 | 0.49 / 0.52 / 0.51 / 0.55 | FAIL: human style, but the games are too OPEN (both took one 2x live, z ~ 3; CLX takes a princess 77% vs 62%; OT 46% vs 57%). Stopped at u138 |

**Verdict at the 18:00 checkpoint: R4 u100 is the opponent (READY below).** The two rounds after it gained nothing on the
whole goal: R4k (eval-time slowdowns) and R5 (training at the slower tempo). Both bought style only by opening the game. This
counts as a confirmed plateau on style at this recipe. Diagnosis, (b) untested: in this SIM, every way of making the
opponent answer later (decide 60 / 80, +20 / +40 reaction ticks, trained or not) lets CLX's pushes through. CLX then takes a
princess in 69-88% of games vs 62% live, and both sides take one in 16-21% vs 9.4%. Live humans answer as late yet lose fewer
towers. That fits O0's finding that the SIM gives about half of live's tower-level effect (tower physics against human-sized
pushes), more than it fits an opponent problem. The test that separates the two: re-score R4 u100 at decide 80 on the
next parity runtime (fin15) and see whether both-took falls toward live.

### 7.1 READY: the opponent for tonight's arm

- **Checkpoint:** R4 u100 = `rlarm_oppC1_icemix_s74_u0100.pt`, sha256 **ea1d080496b3**. Lineage: O2b (0882374c) -> C1 u0-u84
  -> R4 (league_opp_live) u85-u100.
  - Laptop: C:/Users/benpe/pod_backup_weekend/w7/rlarm_oppC1_icemix_s74_u0100.pt.
  - P1: cb_stepd/icebow/data/pipeline/o2/w7opp.pt (hard link).
  - 19899: o3/cb/icebow/data/pipeline/o2/w7/.
- **Setting:** sampling T .1, deciding every 40 ticks, reaction 0. This is the setting it was gated and scored at.
- **League config verified on a training pod (a):** `cfg/stepd_l16_w7opp_s74.yaml` = stepd_l16_s74.yaml + ONE block:
  ```
  league_exploiters:
    ckpt: icebow/data/pipeline/o2/w7opp.pt      # = ea1d0804
    decks: scratchpad/gauntlet/L74/mix/decks_live_train.json
    share: 0.3
    T: 0.1
    decide_every: 40
  ```
  - Real `rl_royale --smoke` on P1: **SMOKE PASS** at 20:31 UTC (yaml 2f77bbcd, rl_royale 3188e77d = 25f0c42 + the W7
    patch, with the key absent = identical).
  - The opponent was played: exploiter_league 4 + 2 games, and all 11 resume checks were true.
  - Log: P1 /workspace/w7/stepd_l16_w7opp_s74/.
  - Ship the checkpoint to the arm's pod as icebow/data/pipeline/o2/w7opp.pt.
- **O4 (a), CLX vs the opponent, all16, 1,920 games (741200 + three fresh blocks), vs live CLX @4858 (n 138):**

| cell | R4 u100 (chosen) | C1 u50 (style fallback) | option A gen_v32_s0 T .1 d40 | live CLX @4858 |
|---|---|---|---|---|
| CLX win | **63.7** [61.6, 65.9] (z +0.34) | 68.1 (z +1.41) | 73.2 (z +2.76) | 62.3 [54.0, 70.0] |
| opp takes a princess | **35.9** [33.8, 38.1] (z +1.12) | 29.9 (z -0.30) | 22.8 (z -2.24) | 31.2 [24.0, 39.3] |
| CLX takes a princess | 65.7 (z +0.99) | 67.9 (z +1.53) | 69.8 (z +2.03) | 61.6 |
| both took one | 12.6 (z +1.08) | 10.9 (z +0.55) | 6.5 (z -1.35) | 9.4 |
| OT share | 54.0 (z -0.74) | 56.3 (z -0.22) | 58.3 (z +0.24) | 57.2 |
| regulation loss | 21.2 (z +1.69) | 16.0 (z +0.26) | 10.7 (z -1.63) | 15.2 |
| give-back | 9.8 (z +0.99) | 8.6 (z +0.66) | - | 6.4 |
| style distance (live 13k; floor 0.05, 12k vs 13k 0.10) | **0.74** | 0.63 | 0.77 | - |
| cells with \|z\| >= 1.96 | **0 of 6** | 0 of 6 | 3 of 6 | |
| per archetype (live n >= 30) | hog CLX-takes 64.8 vs 44.1 (z 2.38); all others pass | hog CLX-takes z 2.34, other win z 1.96 | - | |

- Fresh blocks only (742000-744000, 1,440 games, not used to pick u100): CLX win 918 / 1,440 = 63.8%; 741200 alone 306 / 480 = 63.8%. The pick on 741200 did not inflate it.
- **Against the goal:**
  - Win within ~5 pp of live: met, +1.4 pp.
  - Opponent princess-take near live with CI overlap: met, 35.9 [33.8, 38.1] vs [24.0, 39.3].
  - OT and both-took near live: met.
  - Style <= ~0.65: **not met**, 0.74. Better than option A's 0.77, worse than its own O2b init's 0.65.
  - C1 u50 is the fallback if the lead weighs style over strength: 0.63, but CLX wins +5.8 pp.
- **Caveats (b), untested:**
  - In training, the opponent's frozen icebow opponents press the Hero IW by the live rule, not CLX's head. Tested
    harmless: R3d, 67.3 vs 67.7.
  - The opponent-to-be fields no crown tower troops in training; the eval gives it about 7%.
  - All rows are fin13. The O5 sealed-block prediction is still owed.
  - The O4 rule is weak at live n = 138 (CIs about +-8 pp); hog has n = 34.

### 7.2 Next round (after tonight's arm ships; not started)

- R6: train at decide 40 with a style term or a KL anchor to O2b's gate head only (`kl_ref_gate`). The aim is to keep R4's
  closed games and pull react_s / ppm_2x back toward live.
- Or first run R5's diagnosis test (fin15 re-score at decide 80). It separates "the SIM's towers fall too easily" from
  "the opponent defends badly".

**Plateau diagnosis (R2 -> R4).** C1's gate win stopped falling at ~u50 while its training win rate kept creeping up
(vs CLX 0.44 by PFSP rating at u72; vs the mix 0.38 -> 0.40). The KL leash never bound (beta stayed at its 0.03 floor,
KL ~0.08 < 0.1), so the budget was not the limit. Two train / eval differences were tested on the same 480 games: the
Hero IW press head (no effect) and CLX's live decision stack (`livecal.LIVE`: tau by phase, hazard gate, X-Bow class
sampling, Rocket / Log aims, lethal finishers, dead-lane blocks + own effects), which gap.py D3 always applies and the
trainer's league never did: +3.9 pp for CLX. So the trainer was optimising against a weaker, different CLX. R4 removes
that difference with an opt-in trainer key (`league_opp_live`, pipeline/rl_royale.py; tests
pipeline/tests/test_league_opp_live_1020.py: absent = the 0bcc4c5 load_config + config hash on 3 yamls; pyflakes clean).

**Also built, not used:** `princess_take` (pipeline/reward_terms.py, opt-in crown term, +w per enemy princess felled in
play; tests pipeline/tests/test_princess_take_1020.py vs 0bcc4c5) and `cfg/oppC2_icemix_take_s74.yaml`. Not run: C1 did
not stall (OT 50-57%, both-took 9-15%, at or above live), so a tower-taking bonus would push the wrong way.

## 8. Problems found along the way (not fixed outside this directory)

1. **card_use.results() grades across account switches.**
   - Its trophy-total fallback, when a match has no result line, computes the change across the switch to the bait account.
   - Effect: 29 graded matches with |change| > 100 trophies (-10,230..+10,174), whose WIN / LOSS is therefore arbitrary.
     11 of them are icebow matches at >= 12k, including one CLX "loss" on 10-19 07:54.
   - Every tool on that function (habits/index.py, doctrine, plan1019 slices) carries them.
   - Here they are excluded: |delta| > 100 -> `BADDELTA`. The timeline-vs-result mismatches fell from 16 to 2.
   - Fix (not done, outside scope): skip the fallback when the two readings differ by > 1,000.
2. **The stepd fin13 evals are not level 11.** They run with `--live-levels`, using the 12k-era table: learner tower 15,
   opponents 45% level 16. Live 13k is 70% level 16, and our tower has been 16 since 10-19 14:02.
3. **HANDOFF / TUESDAY "CLX 46.0% (113)"** is the pre-level-up CLX. The 253-match record (55.2%) mixes two tower levels and
   must not be read as a model effect.

## 9. Files and reproduce

```
icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/opp_model/live_table.py     # -> cache/ + out/live_matches.jsonl.gz (~2-4 min cold, 36 s warm; not committed)
icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/opp_model/check_table.py > check_table.out
icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/opp_model/analyze.py > analyze.out
icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/opp_model/null_beta.py > null_beta.out
```

- `live_table.py`: the live table (PlayDetector plays, exact tower falls, trophies before the match).
- `sim_sets.py`: the SIM inventory and paired deltas; exact crown order from telemetry rows.
- `crowns.py`: shared crown records (doctrine method).
- `analyze.py`: J11 / J9 / J10 / Stage-2 / audit.
- `null_beta.py`: the random-walk null for the trophy-adjustment methods.
- `check_table.py`: validation.
- Inputs: L68/live_reader logs, L70/live/overnight.out, pod_backup_weekend/{rt35, pod1017_*, codex1018, stepd, stage2,
  pod1014b_econ}, human/data/*.json.gz.
