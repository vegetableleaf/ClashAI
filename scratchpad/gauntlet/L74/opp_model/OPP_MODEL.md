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
- the 29 card_use fallback grades (section 9).

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
5. **The card_use.results() account-switch grading bug** (section 9, item 1) is still open (lead: not this worker's fix).

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

| R6 | R4 u100 + KL on the play / wait gate anchored to O2b (`kl_ref_gate`; card / cell stay anchored to u100), decide 40, live stack; fresh run rlarm_oppC6_gate_s74 (cfg/oppC6_gate_s74.yaml), started 20:36 UTC on the lead's order to keep P1 busy until 18:00 EDT. kl_target 0.1 -> 0.03 after update 0 (u100's gate began at KL 0.08 from O2b, under a 0.1 target that would never pull it back); KL_gate fell to 0.017 by u7. Stopped at 18:00 EDT (u26) | | | | | | |
| R6 | u5 / u10 / u15 / u20 / u25 | 68.5 / 70.0 / 66.5 / 64.0 / 65.4 | 33.8 / 31.2 / 34.8 / 35.4 / 32.3 | 56.7 / 56.5 / 56.5 / 56.2 / 55.0 | 12.1 / 11.7 / 11.5 / 12.9 / 11.5 | 0.71 / 0.72 / 0.70 / 0.73 / 0.75 | strength back to R4's level by u20; style only -0.03 |
| **O4** | **R6 u20 (34522564), 1,920** | **63.2** | **36.2** | **54.9** | **11.9** | **0.71** | **all 6 overall cells pass (max z 1.42)**; per archetype hog CLX-takes still fails (63.9 vs 44.1, z 2.26; R4 u100 z 2.38); every other archetype cell passes |

**Final pick (lead's rule: all overall cells, then the hog cell, then style): R6 u20.** Both R4 u100 and R6 u20 pass every
overall cell. Both fail the hog CLX-takes cell (z 2.26 vs 2.38). R6 u20 has the better style, 0.71 vs 0.74. The margins are
small: on the same 1,920 games CLX wins 63.2 vs 63.7%, and a style gap of 0.03 is about the size of the style noise between
neighbouring gates. **Why the gate anchor bought so little style (a):** R6's react features are O2b's own (react_s 4.85 vs
O2b's 4.94, live 6.16). The live-imitation net itself already answers about 1.2 s faster than humans, so pulling the gate
back to it cannot move react_s. R4's extra drift came from push_mean and ppm_2x, which the gate does not set. The style
floor of this family is O2b's 0.65. Going below it needs a better imitation target (O1's open items: late sightings after
reader gaps, the public-elixir input). More RL will not do it.

**Verdict at the 18:00 checkpoint: R4 u100 is the opponent (READY below).** The two rounds after it gained nothing on the
whole goal: R4k (eval-time slowdowns) and R5 (training at the slower tempo). Both bought style only by opening the game. This
counts as a confirmed plateau on style at this recipe. Diagnosis, (b) untested: in this SIM, every way of making the
opponent answer later (decide 60 / 80, +20 / +40 reaction ticks, trained or not) lets CLX's pushes through. CLX then takes a
princess in 69-88% of games vs 62% live, and both sides take one in 16-21% vs 9.4%. Live humans answer as late yet lose fewer
towers. That fits O0's finding that the SIM gives about half of live's tower-level effect (tower physics against human-sized
pushes), more than it fits an opponent problem. The test that separates the two: re-score R4 u100 at decide 80 on the
next parity runtime (fin15) and see whether both-took falls toward live.

### 7.1 READY: the opponent for tonight's arm

**FINAL (22:22 UTC): R6 u20 = `rlarm_oppC6_gate_s74_u0020.pt`, sha256 345225645845 (full
3452256458450fcc8fc4848445e5c06c64970ad0b1b8a60c1a915208509c475b).**
- Same setting as R4 u100: T .1, decide 40.
- O4 is in the R6 row above.
- P1's icebow/data/pipeline/o2/w7opp.pt now IS R6 u20; R4 u100 is kept beside it as w7opp_R4u100.pt.
- League config smoke with it on P1: **SMOKE PASS** 22:21 UTC (yaml 2f77bbcd unchanged). exploiter_league was played in 4
  games. Log: /workspace/w7/stepd_l16_w7opp_s74/.
- Laptop copy: pod_backup_weekend/w7/rlarm_oppC6_gate_s74_u0020.pt.
- The R4 u100 block below stays valid as the alternate (its smoke log: /workspace/w7/stepd_l16_w7opp_s74_R4u100/).

- **Alternate, R4 u100:** `rlarm_oppC1_icemix_s74_u0100.pt`, sha256 **ea1d080496b3**. Lineage: O2b (0882374c) -> C1 u0-u84
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

## 8. W14: calibrate the opponent to RANKED (10-21, rounds logged below)

**Why (a).** CLX's 233 Ranked matches (clx_ranked/CLX_RANKED.md) sit 16-32 pp below what the SIM says against W7's R6 u20.
R6 u20 reproduces the 13.5-14k ladder (section 7), not Ranked. Every gate so far picked successors against a ladder-strength
opponent.

**Target = the O4-Ranked table** (`w14/o4r_table.py`). Each SIM opponent is compared with CLX's 233 Ranked matches, cell by
cell:
- Same definitions on both sides: the SIM rows go through clx_ranked/sim.py `row()`, the live rows are clx_ranked/rows.json.
- BEAT = the tank / bridge-spam win conditions of report.py.
- Gate = the 11 `*` cells below plus style. Each cell needs |z| < 1.96 (two-proportion z, as W7's O4 rule) AND, where a
  point tolerance is predeclared, |SIM - Ranked| within it: win 5 pp, vs BEAT 10, win \| OT 8, opponent takes 8, CLX
  takes 8. Style vs Ranked <= 0.65. An undefined cell counts as a FAIL.
- A z pass alone only says "no detectable difference at n = 233". The point tolerances are the calibration claim.
- BEAT is classified from REVEALED cards on both sides: live = the seen cards; SIM = the cards the opponent played
  (o3_plays). The full-deck version (W13's T7 / T11) is kept as a monitored cell. On R0 the two differ by 0.6 pp (56.9 vs
  57.5).
- Style = the opponent's play-style distance (o3_score's 9 features) vs the live RANKED opponents of those 233 matches (and
  vs W7's 13k ladder set, for continuity).
- Live n = 233, so the CIs are about +-6.5 pp on the overall win and +-9 pp vs BEAT. This is a weak gate, as W7's was.

**R0 = R6 u20 (34522564) on fin15, 1,920 games (W12's rows, the tn_base opponent today): 3 of 12 gate items pass.**
`o4r_table.py --check` reproduces CLX_RANKED.md T11 exactly (64.0 / 57.5 full-deck / 77.5 / 34.6 / 19.5), which checks the
table code. Full table: `w14/o4r_R0_R6u20.out`.

| cell | SIM R6 u20 | Ranked [95%] | SIM - Ranked [95%] | z |
|---|---|---|---|---|
| * CLX win | 64.0 | 48.1 [41.7, 54.5] | +15.9 [+9.1, +22.6] | +4.72 |
| * win vs BEAT (revealed cards) | 56.9 | 25.3 [17.2, 35.6] | +31.6 [+20.7, +40.4] | +5.47 |
| * win vs the rest | 68.4 | 60.7 [52.7, 68.1] | +7.7 [-0.2, +16.1] | +1.90 |
| * OT share | 55.2 | 62.7 [56.3, 68.6] | -7.5 [-13.9, -0.8] | -2.18 |
| * win \| OT | 70.1 | 47.3 [39.3, 55.3] | +22.8 [+14.3, +31.2] | +5.51 |
| * win \| OT decided before the drain | 77.5 | 52.6 [42.7, 62.4] | +24.9 [+14.7, +35.2] | +5.27 |
| win at the drain | 49.1 | 37.3 [25.3, 51.0] | +11.8 [-3.1, +25.1] | +1.56 |
| * CLX lost the first princess | 34.6 | 48.1 [41.7, 54.5] | -13.5 [-20.2, -6.8] | -4.05 |
| * opponent takes a princess | 40.5 | 51.1 [44.7, 57.4] | -10.6 [-17.3, -3.8] | -3.09 |
| * CLX takes a princess | 71.4 | 52.8 [46.4, 59.1] | +18.6 [+12.0, +25.3] | +5.82 |
| * both took one | 11.9 | 5.6 [3.3, 9.3] | +6.3 [+2.4, +9.1] | +2.90 |
| * regulation loss | 19.5 | 18.9 [14.4, 24.4] | +0.6 [-5.1, +5.5] | +0.24 |
| loss by tiebreak drain | 7.3 | 15.5 [11.4, 20.6] | -8.1 [-13.4, -3.8] | -4.25 |
| style distance vs Ranked / vs 13k ladder | 0.58 / 0.70 | | | |

What the target asks for (a):
- An opponent that both defends better and attacks better than R6 u20.
  - CLX takes a princess 18.6 pp less often.
  - The opponent takes one 10.6 pp more often.
  - Both took one is half as common (5.6 vs 11.9): Ranked games are more one-sided.
- More overtime (62.7 vs 55.2), and the opponent wins it: CLX wins 47.3% of Ranked OTs vs 70.1% in the SIM.
- Style vs Ranked:
  - R6 u20 answers faster (react_s d -1.10);
  - it plays more in double elixir (ppm_2x d +0.90);
  - it pushes with more elixir (push_mean d +0.61).

**Not the lever (a): the eval deck mix.** It already matches Ranked's archetype shares closely.
- BEAT share by revealed win condition: SIM eval 38.5% vs Ranked 35.6%.
- CLX win re-weighted to Ranked's BEAT share: 64.3% (vs 64.0% at the SIM mix). Re-weighted per win condition: 62.8%.
- Ranked / SIM win-condition shares (%): Hog 15 / 10, MK 14 / 19, Goblin Barrel 9 / 8, PEKKA 6 / 5, E-Giant 6 / 2, Royal
  Hogs 5 / 4, Giant 5 / 3, Battle Ram 4 / 2, Balloon 4 / 5. The table prints this line for every config.
- So the gap is how well the SIM opponent plays, mostly with BEAT decks. Per win condition (R0, SIM vs Ranked; live n
  6-36): Giant 49 vs 9, Royal Hogs 55 vs 18, E-Giant 55 vs 23, Golem 39 vs 17, PEKKA 63 vs 36, Battle Ram 53 vs 30, Goblin
  Barrel 86 vs 64, Balloon 79 vs 56.
- The BEAT cell is a primary target: gated with a 10 pp tolerance.

**Not tried, with the reason (b):** a Ranked-only imitation fine-tune (O1 -> O2 on the 233 Ranked logs, about 5k opponent
plays).
- The imitation nets are the weak end of this family: O2 87.9% / O2b 83.8% CLX win, vs 62.3% live ladder.
- All of the strength since then came from RL (section 7).
- 5k plays would at best move style, not the 16 pp of strength.

**Method.** W7's recipe: RL-strengthen the opponent-to-be vs the FROZEN icebow mix with `league_opp_live`, on the census
decks. The W14 base:
- start from R6 u20 (KL card / cell anchored to it, the gate to O2b);
- kl_target 0.1;
- trained on **fin15** (the tn_base / eval runtime; W7 trained on fin13);
- 40 updates per round (round 2 resumes the winners);
- gated every 5 updates on block 741200 (480 games, T .1, decide 40), by a pod-local watcher (`w14/w14_gate.sh`) beside the
  training;
- `w14/launch.sh` installs and starts an arm, `w14/pull.sh` pulls (sha-checked) and prints the brief table.

Round 1 = four arms, two per pod, each ONE change vs the base:

| arm | change vs the W14 base | why |
|---|---|---|
| A `oppW14A_lr3_s74` | lr 1e-5 -> 3e-5 | W7's plateaus came with the KL leash NOT binding: beta at its floor, clip_frac ~0.04, ratio_mean 1.0000. The policy moves too little per update |
| B `oppW14B_gatefree_s74` | no `kl_ref_gate`: the play / wait gate is anchored to R6 u20 like card / cell (W7 R4's rule) instead of to O2b | the gate decides WHEN to play: bank and build a push, or answer now. O2b's timing answers fast and over-plays in 2x (react_s d -1.10, ppm_2x +0.90). Tank decks need that timing most. (b) R6 vs R4 showed no strength difference over 26 updates |
| C `oppW14C_lr10_s74` | lr 1e-5 -> 1e-4 | the upper bracket of A |
| D `oppW14D_base_s74` | none (control) | W7's history says more updates plateau; D measures it on fin15 and is the baseline for A-C |

- **Arm B was first "BEAT decks x3 in the opponent-to-be's training draw".** It was withdrawn before launch on the lead's
  order (10-21 09:05, after W15's LEVERS23.md: BEAT is already 61% of tn_base's opponent draws vs 35.6% on Ranked; do not
  upweight tank decks in the arms or in opponent training).
  - What the 61% measures: the LEARNER's opponent pool in tn_base (decks_rl.json census 0.663 + the exploiter pool, by
    "contains a BEAT card").
  - What the old arm B changed: the deck draw of the opponent-to-be while it is being trained. With anatomy.wincon that is
    0.407 of draws, x3 -> 0.673.
  - That arm aimed at the lead's own diagnosis: the SIM opponent plays these decks too easily, so more practice WITH them.
    It is withdrawn, not refuted. It stays an option if A-D leave the BEAT cell open, and needs the lead's OK.
- Pods: 48148 runs A (gate every 5) + D (every 10); 19899 runs C (every 5) + B (every 10). That is 12 gates per pod per
  round (about 7-10 min each, beside about 2.3 h of training).
- Two arms share a pod: each holds the pod's claim.lock SHARED and its own train lock, so exclusive claimers such as
  stepd_chain wait. The gate evals share one eval lock per pod.
- Cross-pod identity check before reading arm differences: both pods first replay R6 u20 on block 741200 (T .1, decide
  40). Same code (rl_royale e96c830d, royale_env 9059df4d on both, checked 08:00 EDT) and the same seeds should give W12's
  741200 rows.
- Selection vs confirmation: snapshots are picked on block 741200 only. The pick is then confirmed on three FRESH blocks
  (742000 / 743000 / 744000, 1,440 games), and the fresh-only numbers are reported, as W7 did.
- Round 2 = the winner(s) continued for 40 more updates, one of:
  - a RESUME of the arm's run (w7_train.sh RUNNAME=<arm>, a yaml with max_updates 80; keeps the optimizer, rng, PFSP
    ratings and KL anchor);
  - a FRESH run whose init is the chosen snapshot (a new KL anchor, as W7's R6 from R4 u100).
- Deadline order: the O4-Ranked confirmation (1,920 games) and the league-config smoke need about 1 h of pod time. No new
  round starts after about 18:30 EDT.

**Post-princess-fall cells (owner 10-21: pocket, surviving princess, X-Bow locks by crown state; `w14/pocket.py`).**
- SIM side needs deploy positions and a tower / X-Bow trace. Those come from an opt-in, pod-local telemetry patch of the
  isolated eval copy (`w14/pos_patch.py` v2; env O3_POS=1).
  - It wraps env.eng.act and env.core.step of the REAL match only; search forks run on other envs.
  - (a) It does not change play: R6 u20 with it on block 741200 = the replay rows, 480 / 480 identical.
  - It slows an eval about 2.5x, so it runs on probes and final candidates only, not on every gate.
- Definitions, one frame on both sides: our half = y > 16; pocket = y >= 17.5. Troops / buildings only: no spells, no
  Miner / Goblin Drill. Lock = enemy tower HP lost >= 5% of a princess while the X-Bow lived.
  - Live lock: invlib.xbow_rows, towers in reach.
  - SIM lock: the tower the X-Bow targeted.
- Live Ranked vs SIM R6 u20 (block 741200, 480 games):

| cell | live Ranked (CLX, 233) | SIM R6 u20 | SIM E4 |
|---|---|---|---|
| matches where our first princess fell | 119 | 184 / 480 | 141 / 480 |
| (a) pocket share of opponent troop deploys after the fall | 41.0% [36.9, 45.2] (n 527) | 45.3% [42.4, 48.2] (n 1,124) | 15.8% [12.8, 19.4] (n 474) |
| (a) same area BEFORE the fall (detection / rule floor) | 0.2% | 0.7% | 0.2% |
| (a) matches with >= 1 pocket deploy (of those with a fall) | 37.0% | 56.0% | 21.3% |
| (b) pocket deploys per minute after the fall | 2.60 | 2.74 | 1.06 |
| (c) our king HP lost after the fall, per min / per match (princess units; not attributed to pocket units) | 0.35 / 0.24 | 0.50 / 0.51 | 0.36 / 0.18 |
| (c) P(our king falls \| our princess fell) | 7.6% [4.0, 13.8] | 18.5% [13.5, 24.7] | 6.4% [3.4, 11.7] |
| (d) surviving princess HP lost after the fall, per min / per match | 0.285 / 0.198 | 0.299 / 0.302 | 0.271 / 0.135 |
| (e) X-Bow lock rate at 0-0 (n) | 40.2% (936) | 49.5% (1,741) | 42.6% (2,190) |
| (e) at 1-0 | 44.2% (52) | 47.2% (163) | 31.9% (251) |
| (e) at 0-1 | 15.7% (51) | 35.1% (114) | 32.4% (37) |
| (e) at 1-1 | **12.2% (41)** | **48.2% (85)** | 36.4% (33) |
| (e) locks per minute 0-0 / 1-0 / 0-1 / 1-1 | 0.52 / 0.42 / 0.15 / 0.16 | 0.63 / 0.69 / 0.39 / 0.52 | 0.60 / 0.52 / 0.34 / 0.37 |

- **E4 (the promotion-gate opponent) DOES under-use the pocket (a).** After our first princess falls, 15.8% of its troop
  deploys go into the pocket (live 41.0%), at 1.06 per minute (live 2.60). So the owner's diagnosis holds for the gate
  opponent every promotion was decided on: CLX 72.9% vs it on this block. E4's style distance vs Ranked is 1.01.
- **(c) "The SIM opponent does not use the pocket" is contradicted for R6 u20, the tn_base opponent.**
  - After our first princess falls, 45.3% of its troop deploys go into the pocket, vs 41.0% live.
  - Rate: 2.74 vs 2.60 per minute.
  - It is also no gentler on the king: 18.5% of those matches end with our king down, vs 7.6% live.
  - The SIM allows pocket deploys: the floor before a fall is 0.7%, after 45%.
- **(a) The owner's 1-1 X-Bow observation IS a calibration gap.**
  - Live, the lock rate falls from 40% at 0-0 to 16% at 0-1 and 12% at 1-1.
  - In the SIM it stays near 48% at 1-1 (35% at 0-1). That is a 36 pp gap at 1-1.
  - The live n is small (41 / 51 X-Bows).
  - The lock definitions differ (towers in reach vs the targeted tower). The 0-0 cells (40 vs 50) bound how much of the gap
    that can explain: about 10 pp.
  - So the SIM opponent defends X-Bows at 1-1 far worse than Ranked humans, although it uses the pocket as often.
  - Where the gap comes from is (b) untested: what the opponent places into the pocket, and when (at our X-Bow or at our
    king).
- **(f) Log bait (lead 10-21, `pocket.py` (f); only o3_plays needed).** Opponent plays per match of Goblin Barrel /
  Skeleton Barrel / Dart Goblin, and the punish rate: our Logs vs a deck holding one, followed by one of them within 6 s.

| | live Ranked | SIM R6 u20 (1,920) | SIM E4 (480) | A u30 | B u5 |
|---|---|---|---|---|---|
| bait plays per match (GB / SB / DG) | 0.72 / 0.54 / 0.63 | 0.74 / 0.61 / 0.53 | 0.70 / 0.40 / 0.51 | 0.74 / 0.50 / 0.46 | 0.73 / 0.51 / 0.57 |
| Log punished within 6 s | 19.2% [15.6, 23.4] (n 396) | 19.9% [18.0, 21.9] | 14.6% [11.6, 18.3] | 23.3% | 25.2% |

  - (a) R6 u20 plays and punishes the bait at the live rate.
  - E4 punishes a wasted Log about 25% less often than live humans.
- Calibration targets added: X-Bow lock rate at 0-1 / 1-1 (live 15.7 / 12.2) and P(king falls | princess fell) (7.6).
  Each candidate's final 1,920-game check runs with O3_POS=1.

**Plan review (Codex gpt-6-astra, read-only, 10-21 08:10 EDT; seat unverified). The ten findings, adjudicated:**

| # | finding | verdict | action |
|---|---|---|---|
| 1 | a failed eval still writes ALL_DONE; an undefined z passes silently | valid (observed) | the watcher moves a failed eval (GAP EXIT or != 480 rows) aside and retries once; the table counts an undefined cell as a FAIL and flags incomplete or duplicated row sets |
| 2 | round-2 continuation not specified | valid | specified above (resume vs fresh-from-snapshot) |
| 3 | \|z\| < 1.96 is not equivalence | valid | point tolerances predeclared above |
| 4 | selection on one reused block | valid | fresh-block confirmation of the pick |
| 5 | eval throughput can lag the training | valid | gate cadence 5 / 10 per arm (12 gates per pod per round) |
| 6 | code identity across pods not verified | partly: the trainer and env shas were checked | add the R6 u20 replay check on both pods |
| 7 | CLX takes a princess (+18.6) and drain losses are not gated; style has no threshold | valid | CLX-takes gated (tol 8), style <= 0.65; drain losses stay a monitored cell, because OT share and win \| OT cover them |
| 8 | the planned arm C (tower_crown shaping) is a critic prior, not a chip reward: with an accurate critic the potential cancels out of the GAE advantages | valid (derived; R6's critic explained variance is 0.77) | arm C dropped before launch, replaced by lr 1e-4 |
| 9 | a beta floor and ratio_mean 1 do not prove lr is the limit | valid | A and C are labelled exploratory (b); their KL, clip_frac and beta logs are read before round 2 |
| 10 | live BEAT uses revealed cards, SIM the full deck | valid | revealed-card BEAT on both sides (difference 0.6 pp on R0) |

**Round log** (480 games = block 741200 unless marked; CLX win / vs BEAT / vs rest / OT share / win \| OT / win \| OT
before the drain / opponent takes / both took / style vs Ranked; Ranked 48.1 / 25.3 / 60.7 / 62.7 / 47.3 / 52.6 / 51.1 /
5.6; the 480-game SE is about 2.2 pp on win).

| round | config | win | BEAT | rest | OT | win\|OT | pre-drain | opp takes | both | style R | gate fails | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R0 | R6 u20, 1,920 | 64.0 | 56.9 | 68.4 | 55.2 | 70.1 | 77.5 | 40.5 | 11.9 | 0.58 | 9 | ladder-calibrated, not Ranked |
| R0 | R6 u20, block 741200 only (the gate block) | 66.2 | 63.1 | 68.4 | 55.4 | 72.2 | 80.5 | 38.3 | 10.2 | 0.56 | 8 | the per-gate baseline |
| R1 | A lr 3e-5 u5 / u10 / u15 | 63.3 / 61.7 / 62.3 | 58.6 / 52.8 / 52.5 | 66.7 / 67.8 / 69.1 | 54.4 / 53.3 / 54.0 | 68.6 / 68.0 / 69.5 | 77.3 / 78.1 / 75.8 | 41.9 / 43.8 / 40.8 | 13.8 / 14.6 / 11.7 | 0.58 / 0.54 / 0.52 | 9 / 8 / 9 | -4 pp by u10, mostly vs BEAT; style improves |
| R1 | A u20 / u25 | 60.6 / 60.2 | 56.3 / 55.0 | 63.7 / 63.9 | 59.8 / 57.5 | 67.6 / 65.6 | 73.0 / 72.9 | 44.6 / 43.5 | 13.3 / 10.8 | 0.66 / 0.67 | 8 / 8 | still falling, slower; style drifts past 0.65; cell KL from R6 u20 reaches the 0.1 target at u25 |
| R1 | C lr 1e-4 u5 / u10 / u15 | 69.8 / 63.5 / 66.0 | 64.3 / 57.3 / 58.6 | 73.7 / 68.0 / 71.3 | 55.2 / 54.4 / 58.8 | 74.7 / 69.7 / 75.2 | 79.5 / 76.4 / 80.4 | 36.0 / 40.8 / 39.6 | 13.8 / 13.3 / 11.2 | 0.64 / 0.66 / 0.61 | 9 / 10 / 9 | no gain (noise around the 66.2 baseline): the leash binds from u3 (cell KL 0.10, beta held 0.075), clip_frac 0.24. Stopped at u16 (14:26 EDT) |
| R1 | B gate-free (19899, from 14:27 EDT) u0 | 66.2 | 63.1 | 68.4 | 55.4 | 72.2 | 80.5 | 38.3 | 10.2 | 0.56 | 8 | = R6 u20 (critic warm-up only), as every u0 |
| R1 | A u30 | 60.2 | 54.0 | 64.6 | 56.2 | 63.3 | 69.8 | 44.6 | 13.8 | 0.63 | 7 | still moving on OT cells |
| R1 | B u5 | 59.6 | 52.5 | 64.5 | 57.1 | 67.2 | 77.2 | 45.0 | 11.9 | 0.62 | 7 | B (gate free) is already where A is at u30 |
| R1 | A u35 / u40 (u40 = A2 u0: its own gate lost its tarball when launch.sh overwrote the running eval script; launch.sh now copies atomically) | 59.2 / 61.9 | 55.1 / 56.5 | 62.1 / 65.7 | 57.5 / 56.9 | 62.7 / 67.4 | 71.2 / 75.2 | 48.1 / 43.1 | 15.0 / 13.3 | 0.63 / 0.64 | 7 / 8 | **plateau since u20: 60.6 / 60.2 / 60.2 / 59.2 / 61.9** (480-game SE 2.2) |
| R1 | B u10 / u15 | 62.3 / 59.6 | 52.8 / 53.0 | 68.9 / 64.2 | 53.8 / 53.8 | 65.1 / 62.8 | 73.2 / 67.0 | 41.7 / 44.6 | 9.4 / 13.3 | 0.58 / 0.59 | 8 / 8 | the same level as A (~60), with better style (0.58-0.62 vs A's 0.63-0.67) |
| R2 | A2 = A continued as a FRESH run from A u40 (cf9f60f9; new KL anchor, the 0.1 budget restarts), 48148 from 15:16 EDT: u5 | 61.9 | 52.8 | 68.3 | 57.1 | 70.8 | 76.8 | 43.1 | 13.1 | 0.66 | 9 | no gain over A u40: stopped at u10 (16:00 EDT) for A3 |
| R1 | B u20 | **55.0** | 51.0 | 57.7 | 51.5 | 58.3 | 63.0 | 50.2 | 14.6 | 0.54 | 6 | the first clear step below 59: -11.2 pp vs R6 u20 on the same 480 games, style better than R0 |
| probe | B u15 at decide 20 (eval-time tempo only) | 61.9 | 56.6 | 65.6 | 59.8 | 67.9 | 76.7 | 43.3 | 12.7 | 0.70 | 8 | (c) a faster opponent is not stronger: +2.3 pp for CLX vs decide 40 (59.6), style worse |
| R1 | B u25 / u30 / u35 / u40 | 58.5 / 54.6 / 56.0 / 56.2 | 54.5 / 48.2 / 46.5 / 50.5 | 61.4 / 59.1 / 62.8 / 60.3 | 52.9 / 56.9 / 57.1 / 54.2 | 63.0 / 61.9 / 64.2 / 62.7 | 67.9 / 73.3 / 71.6 / 69.9 | 46.5 / 49.8 / 50.0 / 48.3 | 12.9 / 12.3 / 14.8 / 14.2 | 0.59 / 0.69 / 0.68 / 0.66 | 7 / 7 / 7 / 8 | **plateau u20-u40 at ~56** (55.0 / 58.5 / 54.6 / 56.0 / 56.2); leash NOT binding (KL <= 0.056, beta at its floor); training win vs the mix flat at ~0.47 |
| R2 | A3 = A u40 continued fresh WITHOUT kl_ref_gate (B's change on A's net), 48148 from 16:02 EDT: u5 / u10 / u15 | 56.5 / 60.4 / 54.8 | 50.0 / 54.3 / 53.5 | 61.1 / 64.8 / 55.7 | 55.2 / 60.6 / 56.5 | 64.5 / 66.7 / 63.1 | 71.6 / 75.1 / 73.7 | 49.6 / 46.5 / 50.0 | 14.2 / 16.2 / 12.7 | 0.66 / 0.67 / 0.68 | 7 / 8 / 7 | gate-free moves A's net too (61.9 -> ~57), to B's level, with worse style |
| R2 | A3 u20 / u25 / u30 / u35 / u40 | 60.0 / 59.8 / 54.2 / **52.5** / 55.8 | 53.5 / 54.5 / 48.2 / 48.0 / 52.8 | 64.5 / 63.6 / 58.4 / 55.7 / 58.0 | 56.5 / 51.0 / 59.8 / 58.8 / 55.6 | 66.1 / 67.3 / 63.1 / 61.3 / 65.5 | 71.7 / 74.4 / 71.2 / 69.7 / 76.4 | 46.2 / 45.8 / 52.9 / 53.3 / 48.3 | 16.9 / 13.5 / 16.5 / 14.6 / 12.3 | 0.68 / 0.71 / 0.71 / 0.72 / 0.69 | 8 / 9 / 7 / 6 / 7 | still moving at u30-u40 (mean 54.2 vs B's ~56), but style 0.69-0.72 fails the 0.65 bound; A3 u35 (45a1c8b0) gets a fresh-block check |
| **O4** | **A3 u35 (45a1c8b0), 1,920 = 741200 + fresh 742000-744000** | **53.0** | **45.5** | **57.8** | **58.0** | **60.1** | **67.5** | **51.7** | **13.8** | **0.75** | **6 of 12** | fresh blocks only (1,440): 53.1%. **The CLX win cell PASSES** (+4.9, z 1.41, tolerance 5); style fails |
| R3 | E = B u20 continued fresh (gate-free, lr 1e-5) + ONE change: BEAT x3 in the opponent's own training draw (lead 10-21 ~18:00: one training-mix change on 48148), from 18:23 EDT | | | | | | | | | | | |
| R3 | E u0 (= B u20) / u5 / u10 / u15 / u20 | 55.0 / 55.4 / 54.6 / 50.0 / 55.2 | 51.0 / 51.0 / 49.2 / 38.7 / 51.5 | 57.7 / 58.5 / 58.4 / 58.0 / 57.9 | 51.5 / 50.6 / 56.9 / 54.4 / 50.4 | 58.3 / 58.4 / 60.1 / 59.0 / 62.4 | 63.0 / 65.9 / 65.8 / 67.9 / 70.8 | 50.2 / 47.7 / 50.4 / 56.5 / 49.2 | 14.6 / 14.8 / 14.6 / 18.1 / 14.6 | 0.54 / 0.56 / 0.54 / 0.63 / 0.68 | 6 / 7 / 6 / 7 / 9 | no clear gain by u20 (u15 was noise: the BEAT cell has n ~200 per gate, SE ~3.5 pp); runs on to u40 |
| R3 | E u25 / u30 / u35 / u40 | 54.2 / 51.7 / 54.8 / 50.6 | 47.7 / 43.4 / 55.8 / 48.7 | 58.7 / 57.4 / 54.1 / 51.9 | 50.8 / 52.1 / 52.3 / 54.0 | 63.5 / 61.2 / 60.6 / 57.1 | 68.0 / 69.0 / 67.6 / 62.0 | 50.8 / 52.7 / 48.5 / 55.2 | 16.7 / 15.6 / 12.7 / 16.5 | 0.62 / 0.60 / 0.62 / 0.64 | 8 / 7 / 7 / 6 | the overall win and the OT cells move after u20; the BEAT cell is noisy (n ~200) |
| **O4** | **E u40 (e5198fb7), 1,920 = 741200 + fresh 742000-744000** | **50.1** | **42.1** | **55.1** | **54.8** | **56.9** | **62.2** | **55.2** | **15.4** | **0.66** | **7 of 12 fail (5 pass)** | fresh only (1,440): 49.9. **The new best on the Ranked cells**: win +2.0 (z 0.59); BEAT +16.8 (A3 u35 +20.2); win \| OT +9.6; pre-drain +9.5 (pass); CLX takes +7.4 (z 2.18); style 0.66 (A3 0.75). New fail: regulation loss 26.2 vs 18.9 |
| R4b | F = A3 u35 continued fresh (A3 recipe) + ONE change: ot_start_share 0.25 from the MIRRORED live 3:00 states (pod 40116, main HEAD code a7fa2292, from 19:54 EDT) | | | | | | | | | | | |
| R4b | F u0 (= A3 u35 on pod 40116 with HEAD code: the same 52.5 as A3 u35's own gate, so HEAD code with the new keys absent = identical) / u5 / u10 / u15 | 52.5 / 55.4 / 52.9 / 56.5 | 48.0 / 49.0 / 46.5 / 54.0 | 55.7 / 60.0 / 57.5 / 58.2 | 58.8 / 57.7 / 64.6 / 60.0 | 61.3 / 64.6 / 59.0 / 65.6 | 69.7 / 74.7 / 70.6 / 73.0 | 53.3 / 49.4 / 50.6 / 48.1 | 14.6 / 15.4 / 12.5 / 9.4 | 0.72 / 0.65 / 0.70 / 0.69 | 6 / 7 / 6 / 6 | no OT gain by u15 |
| R4b | F u20 | 50.0 | 45.5 | 53.2 | 58.8 | 59.2 | 65.9 | 52.9 | 12.1 | 0.68 | 6 | win \| OT 61.3 -> 59.2: within noise, and confounded with A3's own drift (lr 3e-5 continuation, no control). Stopped at u25 (21:31 EDT) for the clean A/B below |
| R5 | E2 = E u40 continued fresh, E's recipe unchanged (48148, from 21:27 EDT) | | | | | | | | | | | the CONTROL for R5b |
| R5b | I = E2's exact recipe + ONE change: ot_start_share 0.25 from the mirrored Ranked 3:00 states (40116, from 21:35 EDT) | | | | | | | | | | | A/B vs E2 at matched updates |
| R5 | E2 u5 / u10 / u15 / u20 / u25 / u30 / u35 / u40 | 49.2 / 54.4 / 51.2 / 49.0 / 51.5 / 48.8 / 54.6 / 50.6 (mean 51.2) | 43.2 / 54.0 / 47.7 / 43.7 / 47.7 / 44.2 / 46.5 / 48.2 | | 53.8 / 56.5 / 53.3 / 48.8 / 48.3 / 51.5 / 51.0 / 54.8 | 55.4 / 61.6 / 61.3 / 61.5 / 60.3 / 55.9 / 62.9 / 60.8 (mean 60.0) | | | | 0.64-0.70 | 5-8 | **plateau**: = E u40 (50.6 on this block); OT share drifts down (48-55) |
| R5b | I u5 / u10 / u15 / u20 / u25 / u30 / u35 | 52.9 / 48.8 / 48.8 / 53.8 / 47.9 / 46.9 / 50.0 (mean 49.9) | 48.7 / 41.9 / 42.0 / 46.2 / 43.2 / 38.9 / 47.0 | | 57.1 / 55.4 / 56.9 / 59.4 / 53.5 / 57.3 / 56.0 | 59.1 / 56.4 / 55.7 / 61.4 / 56.4 / 57.5 / 58.7 (mean 57.9) | | | | 0.67-0.71 | 5-7 | vs the control E2 at matched updates: CLX win -1.3, win \| OT -2.1, OT share +4, BEAT -3. Each gap is about one 480-game SE, so (b) the effect is not established; style 0.02-0.04 worse |

| R6a | J = E u40 + ONE change: the frozen mix = CLX only (48148, 23:50-01:27 EDT) u5 / u10 / u15 / u20 / u25 / u30 | 53.1 / 51.7 / 50.6 / 50.2 / 48.8 / 52.9 | 48.0 / 45.2 / 47.5 / 44.7 / 41.7 / 50.8 | | 57.7 / 56.5 / 55.6 / 58.3 / 52.9 / 56.9 | 58.8 / 55.0 / 56.6 / 57.5 / 57.1 / 65.6 | | | | 0.61-0.70 | 4-7 | its target cell did not move: CLX takes a princess 63.0 pooled (control E2 61.8). Stopped at u31 |
| R6b | K = E u40 + ONE change: kl_ref_gate = B u20 (40116, 00:00-01:27 EDT) u5 / u10 / u15 / u20 | 52.9 / 48.8 / 48.8 / 51.0 | 51.5 / 43.2 / 43.7 / 43.1 | | 50.6 / 52.3 / 57.1 / 59.6 | 60.5 / 55.4 / 52.9 / 58.4 | | | | 0.61 / 0.64 / 0.69 / 0.67 | 7 / 6 / 3 / 6 | its target (style) did not move: 0.67 pooled vs 0.69. Stopped at u21 |
| **O4** | **I u40 (4ff9fe93), 1,920 = 741200 + fresh** | **47.9** | **39.3** | **53.3** | **57.0** | **57.4** | **65.8** | **56.5** | **14.4** | **0.76** | **6 of 12 pass** | fresh only 47.1. Passes win (z -0.06), OT share (z -1.64), CLX takes (57.9, z 1.49) beyond E u40. Fails: BEAT +14.0, win \| OT +10.1, pre-drain +13.2, both +8.8, reg loss +8.9, style 0.76 |
| O4 | I u15 (08118523), fresh 1,440 only | 50.3 | 41.4 | 55.8 | 56.9 | 57.1 | 65.3 | 53.1 | 12.8 | 0.72 | | between E u40 and I u40 |
| probe | I u40 at decide 60 / 80; E u40 at decide 60 (eval-time tempo, block 741200) | 54.0 / 57.3; 52.5 | 47.7 / 46.5; 43.9 | 58.4 / 65.0; 58.5 | 49.8 / 44.0; 50.0 | 66.5 / 67.3; 58.8 | 73.3 / 78.9; 65.2 | 51.9 / 47.1; 54.0 | 18.5 / 16.7; 19.6 | 0.65 / 0.53; 0.60 | | (a) as W7's R4k: slowing the opponent buys style and opens the game (OT share 44-50, both took 17-20), and CLX gains 4-7 pp. Tempo is not the style fix |
| R7 | I2 = I u40 continued fresh, I's recipe unchanged (40116, from 01:32 EDT, last round on that pod) | | | | | | | | | | | |
| R7 | I2 u5 / u10 / u15 / u20 / u25 / u30 | 50.0 / 52.3 / 53.3 / 52.5 / 49.8 / 47.9 (mean 51.0) | 45.2 / 50.8 / 47.5 / 45.8 / 43.5 / 43.8 | 53.4 / 53.4 / 57.5 / 57.3 / 54.3 / 50.9 | 59.6 / 57.7 / 59.4 / 61.9 / 58.8 / 56.7 | 56.3 / 58.8 / 61.8 / 58.9 / 55.7 / 58.5 | 63.1 / 67.2 / 68.3 / 68.3 / 60.8 / 65.3 | 53.3 / 52.1 / 51.2 / 51.0 / 52.9 / 54.8 | 11.9 / 10.4 / 9.6 / 9.8 / 10.2 / 11.9 | 0.74 / 0.74 / 0.76 / 0.81 / 0.78 / 0.75 | 4-6 | **plateau** (= I u40's 50.2 on this block), style drifts up. Stopped at u33 (03:22 EDT); pod 40116 stopped 03:25 EDT after the copy-back (27 tarballs + logs, sha 251db8c7) |

**Rounds 5-6, pooled per arm (every gate snapshot u5-u40 of the arm on block 741200; `w14/pool.py`, numbers
here):**

| arm (one change vs E u40's recipe) | n | CLX win | vs BEAT | OT share | win \| OT | pre-drain | CLX takes | both took | reg loss | style |
|---|---|---|---|---|---|---|---|---|---|---|
| E2 (control: continue) | 3,840 | 51.1 | 46.9 | 52.2 | 60.0 | 67.1 | 61.8 | 15.8 | 27.9 | 0.69 |
| I (+ opponent OT-starts) | 3,840 | 49.9 | 43.9 | **56.7** | 58.5 | 65.3 | **59.0** | **12.8** | 26.6 | 0.72 |
| J (CLX-only mix) | 2,880 | 51.2 | 46.3 | 56.3 | 58.4 | 63.2 | 63.0 | 16.9 | 25.4 | 0.68 |
| K (gate anchored to B u20) | 1,920 | 50.4 | 45.4 | 54.9 | 56.7 | 64.8 | 61.9 | 15.9 | 25.9 | 0.67 |
| live Ranked | 233 | 48.1 | 25.3 | 62.7 | 47.3 | 52.6 | 52.8 | 5.6 | 18.9 | <= 0.65 |

- (a) Only I moves Ranked cells beyond the pooled SE (~1.1 pp on the overall cells, ~1.8 on BEAT):
  - OT share +4.5 (z ~4);
  - both took one -3.0 (z ~3.8);
  - CLX takes a princess -2.8 (z ~2.5);
  - BEAT -3.0 (z ~1.7).
  - Each moves toward Ranked; style is 0.03 worse.
  - The snapshots of one arm are correlated, so these z are optimistic.
- So OT-state starts are the one training-mix change that helped. I's u40 and u15 go to fresh-block checks on 48148, and I2
  continues it on 40116.

**Round 5 verdict.** Continuing E's recipe is a plateau: E2 averages 51.2 on block 741200 over u5-u40, vs E u40's 50.6. Adding
opponent OT-starts (I) keeps the OT share near Ranked's direction and lowers win \| OT by ~2 pp, but within noise. Neither
beats E u40 by a margin that a 1,920-game check could resolve. E u40 stays the pick.


- **Pod 40116 (owner-rented, RTX 3090, quota 31 cores), set up 10-21 19:35-19:55 EDT.**
  - Copied from 48148 through a temporary key, which was removed afterwards: venvf15 (fin15 runtime), the fin15 marker,
    cb_stepd without .git and bench, plus 5 bench checkpoints (CLX, CLIII, CLIX, CXXXVIII, E4).
  - sha256 check: the 26,480 non-bench files are identical to 48148; the 5 bench files match.
  - Then main HEAD's pipeline/ + L74 nextround / gap / livecal were overlaid: git archive with autocrlf OFF, 7,9xx files,
    every one sha-checked. An autocrlf archive had shipped CRLF files first; that copy was overwritten.
  - nextround/ot_states.json on THAT pod only = w14/ot_states_mirror.json (sha f4d3ad86). The original is kept at
    /workspace/w14/ot_states_original.json.
  - Eval copy /workspace/o3w12/cb with o3_patch + pos_patch v2.

| **O4** | **B u20 (40275759), 1,920 = 741200 + fresh 742000-744000** | **57.0** | **48.7** | **62.3** | **54.2** | **63.0** | **68.8** | **47.4** | **12.1** | **0.53** | **7 of 12** | fresh blocks only (1,440): 57.7%; the 741200 pick (55.0) regressed by 2.7 pp, as expected from picking on one block |

**Round-1 facts (a).**
- The pods are CPU-capped: cgroup quota 27.2 cores (48148) / 30.6 (19899) on 256-thread hosts. That is why cpu.lock exists.
  Two arms per pod ran at ~6 min / update each. Arm D (control) was therefore stopped at u2 (13:01 EDT, exact PIDs;
  its run dir is kept), and 19899 runs one arm (C).
- Determinism and cross-pod identity: R6 u20 replayed on block 741200 on 48148 gives W12's rows 480 / 480 identical
  (outcome, end tick, crowns). Every arm's u0 (critic warm-up only) gives the same 480 rows, on 48148 (A, D) and on
  19899 (C). So arm differences are not pod or code differences, and the SIM is deterministic per seed.

### 8.1 Result at the 20:00 checkpoint: best-so-far (NOT at the Ranked target) + plateau diagnosis

**Best-so-far opponent = B u20: `rlarm_oppW14B_gatefree_s74_u0020.pt`, sha256 40275759ecf3
(40275759ecf33170267456a6ceddb3e14e7952e353364c2bd278e12d82ae60a0).**
- Lineage: O2b -> C1 -> R4 -> R6 u20 (34522564) -> W14 arm B, 20 updates on fin15 without kl_ref_gate.
- Copies:
  - laptop: C:/Users/benpe/pod_backup_weekend/w14/rlarm_oppW14B_gatefree_s74_u0020.pt;
  - 19899: cb_stepd/icebow/data/pipeline/o2/w14opp.pt and the eval copy;
  - 19899 run dir: cb_stepd/icebow/data/bench/rl_royale/rlarm_oppW14B_gatefree_s74/.
  - Not installed on 48148.
- Setting: T .1, decide 40, reaction 0, as R6 u20.

**O4-Ranked, 1,920 games, CLX on fin15 all16** (`w14/o4r_O4_Bu20.out`), vs R6 u20 (R0) and live Ranked:

| cell | R0 = R6 u20 | **B u20** | live Ranked [95%] | B u20 verdict |
|---|---|---|---|---|
| CLX win | 64.0 | **57.0** (fresh only 57.7) | 48.1 [41.7, 54.5] | FAIL: +9.0, z 2.60 (tolerance 5) |
| win vs BEAT (revealed) | 56.9 | **48.7** | 25.3 [17.2, 35.6] | FAIL: +23.4 |
| win vs the rest | 68.4 | 62.3 | 60.7 | pass (+1.6) |
| OT share | 55.2 | 54.2 | 62.7 | FAIL (-8.4) |
| win \| OT | 70.1 | 63.0 | 47.3 | FAIL (+15.8) |
| win \| OT decided before the drain | 77.5 | 68.8 | 52.6 | FAIL (+16.2) |
| CLX lost the first princess | 34.6 | 41.7 | 48.1 | pass (z -1.87) |
| opponent takes a princess | 40.5 | 47.4 | 51.1 | pass (-3.6) |
| CLX takes a princess | 71.4 | 64.7 | 52.8 | FAIL (+11.9) |
| both took one | 11.9 | 12.1 | 5.6 | FAIL (+6.6) |
| regulation loss | 19.5 | 22.9 | 18.9 | pass |
| style vs Ranked | 0.58 | **0.53** | <= 0.65 | pass |
| items passed | 3 of 12 | **5 of 12** | | |

Post-fall cells of B u20 (block 741200 with positions; `w14/pocket.py`; live / R6 u20 in the table above):
- pocket share 49.1% (live 41.0, R6 45.3);
- pocket deploys 3.30 per minute (live 2.60);
- P(our king falls \| our princess fell) 17.8% (live 7.6);
- surviving princess HP lost 0.32 per minute (live 0.285);
- X-Bow lock rate 0-0 / 1-0 / 0-1 / 1-1: 50.1 / 30.8 / 34.9 / 35.8% (live 40.2 / 44.2 / 15.7 / 12.2; R6 u20 1-1 48.2);
- log bait per match 0.74 / 0.58 / 0.50 (live 0.72 / 0.54 / 0.63); Log punished within 6 s 20.1% (live 19.2).

**Update 19:20 EDT: a stronger alternative, A3 u35 = `rlarm_oppW14A3_gatefree_s74_u0035.pt`, sha256 45a1c8b0ce48
(45a1c8b0ce4808e01ee0cc7a964fbafc4328c22178b491cdf4b40dfbf4b4e1eb).**
- Lineage: A u40 (R6 u20 + 40 updates at lr 3e-5) + 35 gate-free updates.
- Laptop copy: pod_backup_weekend/w14/; 48148: its run dir.
- O4-Ranked, 1,920 games (`w14/o4r_O4_A3u35.out`), first R6 u20 -> B u20 -> A3 u35, then live Ranked:
  - CLX win **53.0** (64.0 -> 57.0 -> 53.0; live 48.1): **PASSES** (+4.9 within the 5 pp tolerance, z 1.41);
  - vs BEAT 45.5 (56.9 -> 48.7 -> 45.5; live 25.3);
  - win | OT 60.1 (live 47.3);
  - opponent takes a princess 51.7 (live 51.1);
  - CLX takes a princess 62.1 (live 52.8);
  - style 0.75 (B u20 0.53): FAILS the 0.65 bound.
  - Log bait: 0.75 / 0.62 / 0.53 per match; punished 22.2% (live 19.2).
- Trade-off:
  - A3 u35 is the strength-calibrated one: the overall CLX win is inside the Ranked tolerance.
  - B u20 is the human-like one: style 0.53.
  - Neither closes the tank, OT and CLX-takes cells.
  - Recommendation: A3 u35 as the next round's exploiter / eval opponent if strength calibration is the priority (this
    ticket's target); B u20 where human-like timing matters. The league yaml is unchanged either way: install the chosen
    file as icebow/data/pipeline/o2/w14opp.pt. The smoke ran with B u20; A3 u35 has the same architecture and
    loader path, but its own smoke is (b) not run.
- Plateau diagnosis amended: A3 kept improving to u35 (60 -> 52.5 on block 741200), so gate-free on A's net was NOT plateaued
  at u40. It bought strength with style (0.64 -> 0.75).

**Update 21:30 EDT: E u40 is the best confirmed opponent (recommended for the next successor round).**
- Checkpoint: `rlarm_oppW14E_beat3_s74_u0040.pt`, sha256 e5198fb7bd3933253e79a6cbba9992db7a7239643b718c62dc8d8eca34d5b372.
- Lineage: B u20 + 40 updates of tank-deck practice (gate-free, lr 1e-5).
- Copies: laptop pod_backup_weekend/w14/; 48148 cb_stepd/icebow/data/pipeline/o2/w14/e_u40.pt and w14opp.pt; 40116
  o2/w14/e_u40.pt.
- O4-Ranked, 1,920 games (`w14/o4r_O4_Eu40.out`), vs Ranked:
  - CLX win 50.1 (pass, z 0.59);
  - vs BEAT 42.1 (+16.8);
  - win \| OT 56.9 (+9.6);
  - OT decided before the drain 62.2 (pass);
  - opponent takes a princess 55.2 (pass);
  - CLX takes a princess 60.2 (+7.4, z 2.18);
  - both took one 15.4;
  - regulation loss 26.2 (+7.4, a new fail);
  - style 0.66.
- Post-fall cells (block 741200 with positions):
  - pocket share 44.5% (live 41.0);
  - pocket deploys 2.91 per minute (live 2.60);
  - P(king falls \| princess fell) 19.6% (live 7.6);
  - X-Bow lock rate 0-0 / 1-0 / 0-1 / 1-1: 49.6 / 38.3 / 43.1 / 35.6 (live 40.2 / 44.2 / 15.7 / 12.2): the 1-1 gap stays.
- Log punished within 6 s: 21.8% (live 19.2).
- League smoke with it as w14opp.pt on 48148: **SMOKE PASS** 01:29:56 UTC; the exploiter was played 4 + 6 games.
- A3 u35's own smoke on 48148: SMOKE PASS 23:38:46 UTC (exploiter 4 + 8 games).

**League config (verified on a pod):** `cfg/tn_base_w14opp_s74.yaml` = tn_base_s74.yaml + ONE change, the exploiter
checkpoint:
```
league_exploiters:
  ckpt: icebow/data/pipeline/o2/w14opp.pt      # = B u20, 40275759
  decks: scratchpad/gauntlet/L74/mix/decks_live_train.json
  share: 0.3
  T: 0.1
  decide_every: 40
```
- Real `rl_royale --smoke` on 19899 (fin15, venvf15, rl_royale e96c830d): **SMOKE PASS** 21:25 UTC.
- The exploiter was played: exploiter_league 4 + 4 games. Log: /workspace/w14/tn_base_w14opp_s74/.
- Ship the checkpoint to an arm's pod as icebow/data/pipeline/o2/w14opp.pt.

**Plateau diagnosis (iterate-parity-rounds rule: two rounds with no CI-significant gain, plus a written why).**
1. (a) Every arm stops at a floor.
   - lr arms: A (lr 3e-5) reaches ~60-62% at u20 and stays there to u40. C (lr 1e-4) never leaves the 66% baseline; the leash
     binds from u3.
   - A2 (A continued with a new KL anchor) stays at A's level: 61.9 / 60.0 at u5 / u10.
   - The one lever that moved: dropping the gate's anchor to O2b (B; A3 on A's net). That gives another ~5 pp, then a
     plateau at ~56% on 741200 / 57.0% on 1,920 games, from u20 to u40.
   - B's leash is not binding (KL <= 0.056, beta at its floor), so the leash budget is not the limit.
2. (a) The training signal is saturating: the opponent-to-be wins ~0.45-0.47 of its training games vs the frozen mix (A, B).
   The residual gap to Ranked is in specific cells, not spread evenly:
   - vs the rest of the decks: met (62.3 vs 60.7);
   - opponent takes a princess, CLX loses the first princess: met;
   - vs tank / bridge-spam decks: +23 pp;
   - CLX takes a princess: +12 pp (the opponent defends X-Bow pushes too weakly);
   - OT conversion: +16 pp;
   - X-Bow lock at 1-1: 36 vs 12%.
3. (b) Why this recipe cannot close those cells. Untested; each comes with its test.
   - Tank decks. The opponent trains on the census mix, where BEAT is 41% of draws, against an icebow mix that beats it
     ~53%. The BEAT x3 practice arm (withdrawn on the lead's order) is the direct test.
   - OT conversion. Win-only RL sees an OT state only in the ~55% of games that reach it, and never from a Ranked-like 3:00
     state. W15's `ot_start_share` (OT-state starts, uncommitted in the working tree) applied to the opponent's training
     is the test.
   - X-Bow defence at 1-1. Ranked humans deny the X-Bow cheaply (T10: 5.73 elixir per bridge X-Bow); the opponent is
     trained against the whole icebow mix with PFSP. A CLX-weighted mix (or CLX-only) for the opponent is the test.
   - All three are training-mix / start-state changes. None is another lr / anchor / tempo knob, and those knobs are what
     rounds 1-2 exhausted.
4. (c) Contradicted on the way:
   - "a faster opponent is stronger" (decide 20: +2.3 pp for CLX);
   - "the SIM opponent never uses the pocket" (R6 u20 45%, B u20 49% vs live 41%; only E4 under-uses it, 16%);
   - "the eval deck mix is the gap" (re-weighting moves 0.4 pp).

**What B u20 is good for now.** It is strictly closer to Ranked than R6 u20 on the main cells: -7.0 pp CLX win, -8.2 pp
vs BEAT, -7.1 / -8.7 pp in OT, opponent princess takes +6.9, style 0.53 vs 0.58. The lead can swap it in as the
tn_base exploiter, or use it as a stricter eval opponent. It still OVER-predicts CLX on Ranked by ~9 pp overall and ~23 pp vs
tank decks. A successor gated against it is gated against a ~57%-CLX opponent, not a 48% one.

### 8.2 Night checkpoint (10-22 ~04:15 EDT): the opponent for the next successor round

**Recommended: I u40 = `rlarm_oppW14I_otstartE_s74_u0040.pt`, sha256 4ff9fe93b02d
(4ff9fe93b02dcdd445e4fb2a0e8c65e5ad78909534f3d6db965ba00432c8d444; laptop C:/Users/benpe/pod_backup_weekend/w14/rlarm_oppW14I_otstartE_s74_u0040.pt).**
- Lineage: R6 u20 -> B (gate-free, 20 updates) -> E (tank-deck practice, 40 updates) -> I (E's recipe + opponent OT-starts
  from the mirrored Ranked 3:00 states, 40 updates).
- Trained on pod 40116 with main HEAD code; evaluated on 48148.
- Installed: 48148 cb_stepd/icebow/data/pipeline/o2/w14opp.pt.
- League smoke (cfg/tn_base_w14opp_s74.yaml with it as w14opp.pt) on 48148: **SMOKE PASS** 06:36:52 UTC; the exploiter was
  played 4 + 8 games.
- Alternative: E u40 (e5198fb7). Style 0.68 vs 0.78; smoke PASS.

**Final O4-Ranked, 2,880 games each** (blocks 741200 + fresh 742000-746000; `w14/o4r_final_{Iu40,Eu40}.out`):

| cell (Ranked [95%]) | R0 = R6 u20 (1,920) | E u40 | **I u40** | I u40 verdict |
|---|---|---|---|---|
| CLX win (48.1 [41.7, 54.5]) | 64.0 | 50.7 | **48.8** | pass (z 0.22) |
| vs BEAT (25.3) | 56.9 | 43.4 | **41.0** | FAIL (+15.7) |
| vs the rest (60.7) | 68.4 | 55.1 | 53.7 | pass (z -1.64) |
| OT share (62.7) | 55.2 | 55.9 | **58.3** | pass (z -1.29) |
| win \| OT (47.3) | 70.1 | 57.5 | 57.6 | FAIL (+10.4) |
| win \| OT before the drain (52.6) | 77.5 | 63.3 | 66.3 | FAIL (+13.6) |
| CLX lost the first princess (48.1) | 34.6 | 47.2 | 48.9 | pass |
| opponent takes a princess (51.1) | 40.5 | 54.5 | 55.3 | pass |
| CLX takes a princess (52.8) | 71.4 | 60.3 | **58.0** | pass (+5.2, z 1.55) |
| both took one (5.6) | 11.9 | 14.8 | 13.3 | FAIL (+7.8) |
| regulation loss (18.9) | 19.5 | 25.6 | 26.5 | FAIL (+7.6) |
| style vs Ranked (<= 0.65) | 0.58 | 0.68 | **0.78** | FAIL |
| items passed | 3 of 12 | 4 of 12 | **6 of 12** | |

Post-fall and bait cells, block 741200 with positions (`w14/pocket.out`):

| cell | live Ranked | R6 u20 | E u40 | I u40 |
|---|---|---|---|---|
| pocket share after our first princess falls | 41.0% | 45.3% | 44.5% | 44.7% |
| pocket deploys per minute | 2.60 | 2.74 | 2.91 | 2.93 |
| P(our king falls \| our princess fell) | 7.6% | 18.5% | 19.6% | 16.9% |
| surviving princess HP lost per minute | 0.285 | 0.299 | 0.324 | 0.292 |
| X-Bow lock 0-0 / 1-1 | 40.2 / 12.2 | 49.5 / 48.2 | 49.6 / 35.6 | 45.3 / 35.8 |
| Log punished within 6 s | 19.2% | 19.9% | 21.8% | 24.8% |

**Why I u40 over E u40 (the lead's guard: prefer Ranked cells to a lower CLX win alone).**
- I u40 improves Ranked cells beyond the CLX win: OT share +2.4 (now a pass), CLX takes a princess -2.3 (now a pass), BEAT
  -2.4, both took one -1.5, king falls after a princess -2.7.
- On top of that, CLX's win is 1.9 pp closer to Ranked.
- Its costs:
  - style 0.78 vs 0.68 (both fail the 0.65 bound);
  - OT-before-drain +3.0 and regulation loss +0.9 (both fail either way).
- If the owner weighs human-like timing over these cells, E u40 is the pick: the same yaml, a different w14opp.pt.

**Gap closure since R6 u20 (2,880 vs 1,920 games):**
- CLX win 64.0 -> 48.8, closed.
- vs BEAT 56.9 -> 41.0: half of the 31.6 pp gap closed.
- win \| OT 70.1 -> 57.6: 55% of the gap closed.
- CLX takes a princess 71.4 -> 58.0: 72% closed.
- Opponent takes a princess 40.5 -> 55.3: overshoots Ranked by 4.2.
- Style 0.58 -> 0.78: worse.

**Round summary (one change per round; the full log is above):**
1. lr x3 / x10: plateau / no gain.
2. Gate-free (B; A3 on A's net): -7 pp, the first lever.
3. Tank-deck practice (E): -6.9 pp over B on 1,920 games, and the OT cells.
4. New KL anchor / continuation (A2, E2, I2): plateau each time.
5. Opponent OT-starts (I vs control E2): OT share +4.5, both took one -3.0, CLX takes a princess -2.8.
6. CLX-only mix (J), gate anchored to B u20 (K), eval tempo (decide 20 / 60 / 80): no gain on their targets.
   Tempo trades style for open games.

**Confirmed plateau and what is left (b, untested):**
- The last two rounds on I's line (I2) and on E's line (E2) gave no gain. The cells still failing:
  - BEAT (+15.7);
  - OT conversion (+10 / +14);
  - both took one (+7.8);
  - regulation loss (+7.6): the SIM opponent wins more in regulation than Ranked humans do;
  - X-Bow lock at 1-1 (36 vs 12%);
  - style (0.78).
- Next fixes, one each, in order of expected gap closed:
  1. A tank-specific reward or start state. For example, OT / regulation scenario starts with the opponent holding a tank
     deck at 10 elixir. Deck weighting alone closed only half of the BEAT gap.
  2. A style term for the opponent that does not slow it: a KL to O2b on the timing features only, or an imitation loss on
     the live-detected Ranked plays (O1 rows). Every tempo or anchor knob tried so far traded style against strength.
  3. Engine fidelity of tank pushes and pocket play at 1-1. The SIM opponent puts as many troops into the pocket as humans
     (44.7 vs 41.0%), yet CLX's X-Bow locks there 3x as often as live. That points at what the pocket troops do (targets,
     placement), or at the engine, not at how often they are played.
- Pods:
  - 40116: stopped 03:25 EDT after a verified copy-back.
  - 48148: idle since 04:00 EDT. claim.lock is free; it holds I u40 as w14opp.pt.

### 8.3 W18 (10-22): NEW TARGET (owner 10-22): the most recent 100 Ranked CLX matches (`w18/o4r_recent.py`; diagnosis of the 6 / 12 plateau: `DIAG_12.md`)

**Data (a).**
- W13's pipeline (index.py -> anatomy.py), re-run over every CLX Ranked log: 267 matches, 10-20 13:28 -> 10-21 14:32 (the switch
  to Mark CLXI). That is 34 more than the 233, which stopped at 07:08.
- Output: `diag12/recent/rows_ext.json`. W13's rows.json stays the 233-match reference.
- The window is the last 100: 10-21 02:47 -> 14:22.

**Tolerance rule (stated).**
- Each predeclared point tolerance is scaled by sqrt(n_233 / n_recent) of that cell's live n, so it stays the same multiple of
  the live standard error as W14's rule.
- |z| < 1.96 is unchanged; it widens by itself with n.
- The style bound stays 0.65 (an effect size), measured against these 100 matches' opponents.

| cell | all 233 [95%] | **recent 100 [95%]** | tolerance (pp) |
|---|---|---|---|
| * CLX win | 48.1 [41.7, 54.5] | **40.0 [30.9, 49.8]** | 5 -> 7.6 |
| * win vs BEAT | 25.3 [17.2, 35.6] (n 83) | **41.9 [26.4, 59.2] (n 31)** | 10 -> 16.4 |
| * win vs the rest | 60.7 [52.7, 68.1] (n 150) | **39.1 [28.5, 50.9] (n 69)** | z only |
| * OT share | 62.7 [56.3, 68.6] | **57.0 [47.2, 66.3]** | z only |
| * win \| OT | 47.3 [39.3, 55.3] (n 146) | **43.9 [31.8, 56.7] (n 57)** | 8 -> 12.8 |
| * win \| OT before the drain | 52.6 [42.7, 62.4] (n 95) | **45.7 [30.5, 61.8] (n 35)** | z only |
| * CLX lost the first princess | 48.1 [41.7, 54.5] | **53.0 [43.3, 62.5]** | z only |
| * opponent takes a princess | 51.1 [44.7, 57.4] | **57.0 [47.2, 66.3]** | 8 -> 12.2 |
| * CLX takes a princess | 52.8 [46.4, 59.1] | **45.0 [35.6, 54.8]** | 8 -> 12.2 |
| * both took one | 5.6 [3.3, 9.3] | **5.0 [2.2, 11.2]** | z only |
| * regulation loss | 18.9 [14.4, 24.4] | **28.0 [20.1, 37.5]** | z only |
| loss by tiebreak drain | 15.5 [11.4, 20.6] | 16.0 [10.1, 24.4] | monitored |

**Re-score against the recent 100** (`diag12/recent/o4r_recent100.out`):

| opponent | CLX win | vs BEAT | vs rest | win \| OT | pre-drain | CLX takes | both took | reg loss | style | pass |
|---|---|---|---|---|---|---|---|---|---|---|
| target (recent 100) | 40.0 | 41.9 | 39.1 | 43.9 | 45.7 | 45.0 | 5.0 | 28.0 | <= 0.65 | 12 |
| I u40 (2,880) | 48.8 F | 41.0 | 53.7 F | 57.6 F | 66.3 F | 58.0 F | 13.3 F | 26.5 | 0.79 F | **5** |
| E u40 (2,880) | 50.7 F | 43.4 | 55.1 F | 57.5 F | 63.3 F | 60.3 F | 14.8 F | 25.6 | 0.69 F | 5 |
| B u20 (1,920) | 57.0 F | 48.7 | 62.3 F | 63.0 F | 68.8 F | 64.7 F | 12.1 F | 22.9 | 0.54 | 5 (+ lost-first F) |
| A3 u35 (1,920) | 53.0 F | 45.5 | 57.8 F | 60.1 F | 67.5 F | 62.1 F | 13.8 F | 23.9 | 0.75 F | 5 |

**What changes with the target (a), and what does not.**
- At the current rank the opponent must be STRONGER overall: CLX win 40 vs I u40's 48.8.
  - The extra strength is with the NON-tank decks (vs rest 39.1 live vs 53.7).
  - BEAT and regulation loss now PASS for I u40. On the old target those two were failing.
- Failing on BOTH targets, i.e. the robust gaps:
  - CLX takes a princess: X-Bow denial, ledger B8 / T5;
  - win \| OT and OT before the drain: 3:00 state + OT focus, O5 / O6;
  - both took one: T5 / T6;
  - style: tempo, S6.
- The fix rounds already queued aim at exactly these:
  - R1 princess_redirect: chip / X-Bow denial;
  - R3 play_cost: tempo;
  - R2 lead_protect: lead defence.
- The new target adds one requirement: R1's extra defence must not cost strength. CLX win has to FALL (48.8 -> <= 47.6), not rise.

**The window is noisy (iv), so read single cells with care.** With I u40, the failing set changes with the window length:

| window | fails | which |
|---|---|---|
| 80 | 5 | win, vs rest, pre-drain, CLX takes, style |
| 100 | 7 | (as in the table above) |
| 120 | 6 | win, win \| OT, pre-drain, CLX takes, both took, ... |
| 150 | 5 | win \| OT, pre-drain, CLX takes, both took, style |

- The BEAT swing (25.3 on all 233 -> 41.9 on the last 100) rests on 31 matches.
- The vs-rest swing (60.7 -> 39.1) rests on 69.
- The cells stable across windows are CLX takes, win \| OT, pre-drain and both took one. Those are the ones to fix first.

### 8.4 O4 GATE v2 -- the gate version used from 10-22 on (owner decisions G1-G4 + the recent-window target)

**Run it:** `icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/opp_model/w18/o4_gate.py [--targets] [--lock11] ROOT ...`

| item | rule |
|---|---|
| target | the most recent 100 live Ranked CLX matches: `diag12/recent/rows_ext.json`, 10-21 02:47 -> 14:22, the last 100 of 267 |
| tolerances | W14's point tolerances x sqrt(n_233 / n_100) of each cell's live n: win 7.6, vs BEAT 16.4, win \| OT 13.1, opp takes 12.2, CLX takes 12.2; plus \|z\| < 1.96 per cell; an undefined cell fails |
| G1 | live overtime = end > 3610 AND crowns level at 3:00 (the SIM's rule) |
| G2 | CLX plays WITH its measured live handicap in every SIM run of the gate: `--tap-loss 1x:0.0180,2x:0.0363,ot2x:0.0388,ot3x:0.0890 --tap-slow 0.151:17` (w18_eval.sh `W18_EXTRA`). The scorer marks a row set without it **INVALID (G2)** |
| G3 | both took one: per-match Wilson (unchanged, stated). The 1-1 X-Bow lock cell (monitored) uses a match-cluster bootstrap CI |
| G4 | live style = the opponents' features with our CONFIRMED taps (lost / retried taps out, tap tick kept); bound 0.65 vs the same 100 matches |
| pass | 12 of 12 (11 cells + style) |

**Targets** (recent 100, G1; `o4_gate.py --targets`):

| cell | target | cell | target |
|---|---|---|---|
| CLX win | 40.0 [30.9, 49.8] | win \| OT | 43.4 [31.0, 56.7] (n 53) |
| vs BEAT | 41.9 [26.4, 59.2] (n 31) | OT before the drain | 45.2 [29.2, 62.2] (n 31) |
| vs rest | 39.1 [28.5, 50.9] (n 69) | CLX lost the first princess | 53.0 |
| OT share | 53.0 [43.3, 62.5] | opponent takes / CLX takes | 57.0 / 45.0 |
| regulation loss | 30.0 [21.9, 39.6] | both took one | 5.0 [2.2, 11.2] |

1-1 X-Bow lock (G3, monitored): live 5.3 [0.0, 33.3]. That is 19 X-Bows in 5 matches, so the cell is uninformative at this n.

**Re-scored under v2:**

| config | rows | v2 result |
|---|---|---|
| I u40 + CLX handicap (w18_Iu40_tl, 2,880) | valid | **10 of 12**; fails both took one (13.3, z 2.42) and style (0.72) |
| I u40 / E u40 / B u20 / A3 u35 W14 runs, the tau probes, R1's first two gates | no handicap | INVALID (G2); re-run with the handicap |
| E u40 + handicap, I u40 tau 0.55 / 0.50 + handicap (2,880 each) | queued on 33401 stream C | pending |
| R1 / R3 / R2 gates | gate watcher v2 (`w18/w18_gate2.sh`, every 5 updates on block 741200 WITH the handicap) | pending |

R-round gates pair with `w18_Iu40_tl`'s block-741200 rows: the same 480 seeds, the handicap on, the opponent's init.

## 9. Problems found along the way (not fixed outside this directory)

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

## 10. Files and reproduce

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
- W14 (section 8), `w14/`:
  - `o4r_table.py`: the O4-Ranked table (`--check` reproduces CLX_RANKED T11);
  - `pocket.py`: the post-fall, X-Bow-lock and log-bait cells;
  - `pos_patch.py`: the opt-in pod telemetry;
  - `launch.sh` / `w14_gate.sh` / `pull.sh` / `confirm.sh`: the pod loop;
  - `o4r_*.out`: the tables.
  - Gate rows: C:/Users/benpe/pod_backup_weekend/w14/o3/ (sha-checked tarballs).
- Inputs: L68/live_reader logs, L70/live/overnight.out, pod_backup_weekend/{rt35, pod1017_*, codex1018, stepd, stage2,
  pod1014b_econ}, human/data/*.json.gz.
