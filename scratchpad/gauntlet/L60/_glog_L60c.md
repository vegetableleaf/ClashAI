
## L60c (2026-09-05 14:1x-14:2x UTC) -- arm E read at m3.85k and STOPPED (owner order): entropy floor did not resist the collapse
- E snapshot m3,850: knight@426 35/39, 35/37, 35/40; tesla distinct 8/6/4; pro-cell agreement 2.59/9.36
  (baseline 3.49/11.75); cell head 82.4% at the tanh rails 3,850 matches after the guard's x0.043 rescale.
  (a, one training seed) Worse than the baseline and than G at m5k on every placement metric -> stopped
  at 3,975 episodes (14:19 UTC), python 21 -> 3, 9.8 GB available. No winrate eval (wrong instrument, wrong sim).
- New instrument: `L60/rails_read.py <ckpt>` = fraction of masked raw cell logits |raw| > 8 on the val split.
- Next: sandbox engine per-tick state -> obs renderer -> BC dataset v2; engine throughput measurement.
