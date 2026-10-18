# Combo reward versus its control

Supplementary paired comparison using the existing `mix/live_cmp.py` / `paired_drift` method on SHA-verified backups. Each row contains 960 paired games; 95% intervals use 10,000 paired bootstrap draws within census and learner side. Standard seeds: 741200 + 742000. Fresh seeds: 743000 + 744000. The standard comparisons were also checked with the unchanged live_cmp CLI and `--base combo_ctl_c3`.

| Existing evaluation setting | Seeds | Control wins | Reward wins | Reward minus control, pp [95% CI] |
|---|---|---:|---:|---|
| off | std | 624/960 | 637/960 | +1.35 [-2.08, +4.69] |
| off | fresh | 619/960 | 613/960 | -0.62 [-4.17, +2.92] |
| offc | std | 625/960 | 636/960 | +1.15 [-2.29, +4.58] |
| offc | fresh | 616/960 | 610/960 | -0.62 [-4.06, +2.81] |

These attribution comparisons do not replace the required standard **and** fresh comparisons against CLIII in [CANDIDATE_RESULTS.md](CANDIDATE_RESULTS.md). Intervals are nominal, with no correction for correlated arms. No live conclusion follows from a SIM interval.
