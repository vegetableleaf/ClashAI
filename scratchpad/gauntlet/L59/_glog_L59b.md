
## L59b (2026-09-05 05:1x-05:4x UTC) -- owner: credit is an AND gate; armG v1 stopped, v2 relaunched 05:13 UTC
- Owner (05:0x): "timing + placement payment should be 2-way ... basically an AND gate, but with some nuance";
  Chrome may be closed. `_geo_credit` -> `(w_time + w_geom) * place * P5 * gate` when place > 0 (v1 was
  `w_time*P5 + w_geom*place*gate`, which paid a perfect placement at P5 0.07 +2.07). +5 unit tests, 34 OK,
  disabled path still byte-identical. Scenario: +2.54/+3.0/+3.0 at hog tile 14.7/15.9/17.1, 0 elsewhere --
  same window, early row scaled. Baseline c2r_best s0: same 23 fires, credit sum +38.5 (v1 +47.9); tesla
  paid mean +0.84 (v1 +1.56), P1 0.039 unchanged. (a)
- armG v1 stopped at 725 eps (10%, avg_rew -15.9), procs 19 -> 1; checkpoint re-seeded from c2r_best (sha
  d209b41e verified x3). v2 relaunched 05:13 UTC, same CLI, rail guard x0.0430 identical; 125 eps -21.6, 0.7 ep/s.
- Chrome closed (30 -> 0): available 11.0 GB idle -> 3.6 GB with G running = one arm costs 7.4 GB. G+E still
  does not fit; half-size arms rejected (--envs sets the PPO batch = a second change vs c2r). DECISION: G alone.
- m5k ETA ~07:1x UTC via detached arm_gates.py (posts to Discord). Next: read m5k vs the AND baseline.
