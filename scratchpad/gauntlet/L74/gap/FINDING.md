# GAP_r1: train/deploy gap for live A/B arm A (newsim r1), 2026-10-13

One checkpoint (`newsim_r1/newsim_base_r1_final_grafted.pt`), 480 paired games per setup, CAL set c (E4 at T .1),
evo + lad censuses, seeds 741200.., runtime 0.1.33 with Hero IW + live press rule in every arm (`gap.py`, pod C;
copy `pod_backup_weekend/pod1013c_gap/x_GAP_r1`, sha-verified).

| Setup | Win | evo / lad | Plays/game | Tower HP diff/game |
|---|---|---|---|---|
| D0 RL rollout sampler (T .5, tau .27), no rules | 16.67% (80/480) | 15.8 / 17.5 | 39.7 | -4,049 |
| D1 greedy tau .35, no rules | 42.08% | 40.4 / 43.8 | 40.2 | -1,478 |
| D2 D1 + timing rules | 38.96% | 34.6 / 43.3 | 42.2 | -1,424 |
| D3 D2 + card/cell overrides (SIM gate stack) | 41.46% | 34.6 / 48.3 | 42.8 | -1,297 |

Paired deltas (10,000 bootstrap draws within census/side):
- D1 - D0, decoding only: **+25.42 pp [+20.42, +30.42]**
- D2 - D1, timing rules: -3.12 [-8.54, +2.29]
- D3 - D2, overrides: +2.50 [-1.88, +6.88]
- D3 - D0, whole: +24.79 [+19.79, +29.79]

## Reading
- **Measured:** almost the whole train/deploy gap is the decoder. The player RL optimises (sampled, as in rollouts)
  wins 17% here; the same weights played greedily win 42%. Play counts are equal (39.7 vs 40.2), so the loss is in
  WHAT/WHERE is sampled, not how often it plays. Plausible, untested: cell sampling at T .5 over 2,304 cells is the
  main cause. Test next: sample one head at a time (gate / card / cell).
- **Measured:** in the SIM the live rule stack is neutral for r1 (D3 - D1 = -0.6 pp; both steps inside noise).
  The rules were built from LIVE-only failures (e.g. elixir at big-push start live 2.2-2.7 vs SIM 5.2), which the SIM
  does not reproduce, so the SIM cannot credit them. Consequence for the owner's goal (the model learns the rules,
  then they are removed): the SIM can only teach a rule once it reproduces the condition the rule fixes.
- Limits: one checkpoint, one opponent pool, 480 pairs (+-5 pp).

## Head decomposition (GAP_r1_heads, same seeds, vs D1 copied from GAP_r1)
One head drawn as in RL rollouts (T .5), the other two greedy as D1:

| Arm | Win | Delta vs D1 (95% CI) |
|---|---|---|
| G gate sampled (tau .27) | 21.67% | **-20.42 pp [-26.04, -14.79]** |
| C card sampled | 36.04% | -6.04 [-11.04, -1.04] |
| X cell sampled | 39.79% | -2.29 [-7.50, +2.92] |

**Contradicted:** "cell sampling is the main cause" (my guess). The gate is: plays/game are unchanged (40.2), so the
cost is play TIMING, the same number of cards at random moments. Consistent with the economy/timing loss mechanism.
Next (running, GAP_r1_sweep): gate centre vs temperature (Gc tau .35; G2 T_gate .2; G1 T_gate .1) and two rollout
candidates (R1: T_gate .1 + card/cell T .5; R2: all heads T .2).

## Rollout-decoder sweep (GAP_r1_sweep, vs the same D1)

| Arm | Setting | Win | Delta vs greedy D1 (95% CI) |
|---|---|---|---|
| G (above) | gate only, tau .27, T .5 | 21.67% | -20.42 [-26.04, -14.79] |
| Gc | gate only, tau .35, T .5 | 29.58% | -12.50 [-17.92, -6.88] |
| G2 | gate only, tau .27, T_gate .2 | 35.62% | -6.46 [-11.88, -1.04] |
| G1 | gate only, tau .27, T_gate .1 | 41.67% | **-0.42 [-5.62, +5.00]** |
| R1 | all heads; T_gate .1, card/cell T .5 | 28.54% | -13.54 [-18.96, -7.92] |
| R2 | all heads; T .2 | 33.96% | -8.12 [-13.75, -2.50] |

- **Measured:** the gate's temperature is the main knob: at T_gate .1 the sampled gate is indistinguishable from
  greedy (-0.4). Centring on the deploy tau (.35) recovers ~8 of the 20 pp at T .5.
- Card + cell sampling at T .5 still costs ~13 pp together (R1), more than the single-head arms suggest (-6.0, -2.3);
  at T .2 everything together costs -8.1 (R2).
- Plausible, untested: a rollout decoder of gate T .1 + card/cell T ~.2 lands within a few pp of greedy while keeping
  card/cell exploration. RL exploration needs SOME action variance across the 4 rollouts per matchup, so the colder
  the decoder, the weaker the learning signal: that trade-off can only be measured in an RL run.
