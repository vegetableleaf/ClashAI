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
