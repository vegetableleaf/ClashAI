
## L59 (2026-09-05 00:0x-05:0x) -- step 1 wired (arm G), worker config seam fixed, ARM G LAUNCHED 04:49
- Owner (04:2x): full autonomy overnight on the radii work; decisions on their behalf, recorded in §5cs.30.
- `geometry_reward.py`: P2 buildings-only, P7 off for swarm, PATH-based P1 (pull_ok), placement_credit in
  [-0.3, 1.0]; `sim/env.py` +131: graded credit w_time*P5 + w_geom*place*gate paid only when place > 0, X-Bow
  w_wincon*P6, geo_* record-only ledger; `env.geometry.enabled false` = HEAD reward to 1e-9 (2 matches). (a)
- Gate rerun: path P1 fires on 53.3% of pro Teslas (snapshot 40.9%, n=807); modal (9,21) 0.543 vs corner 0.143.
  Hog-vs-Tesla scenario: graded pays +2.85..+3.0 at hog tile 14.7-17.1, 0 at 18.3+; the old binary paid +1.0
  at 18.3/20.7 and 0 in the pull window -- DISJOINT windows. Pre-placed Tesla still unpaid (env sees no threat
  on the enemy half) -- parked doctrine change. (a)/(b)
- SEAM FIX: `remote_pool._worker` re-read config.yaml from disk -> every env-side `--config` key and
  `--drill-only` never reached the workers. Config records .source; workers load the parent's yaml; proven via
  the real CLI with --workers 1. c2r unaffected (its one env-side difference resolved equal). Commit 794d030.
- Found, not fixed: `_trade_reward` keyed by id(u) -> elixir_trade flips 1 step in 512 across processes. (a)
- ARM G launched 04:49 from c2r_best (sha verified), c2r's exact CLI + `env.geometry.enabled true` as the ONE
  change; rail guard x0.0430 (raw 105); early curve = c2r's resume shape (avg_rew -29/-34 vs -31/-31). Detached:
  trainer, ppo_watchdog, `L59/arm_gates.py` (m5k/10k/20k snapshot + place_probe x3 + geo_ledger_probe x2 +
  gate_prior_probe -> Discord). Baseline (c2r_best under the arm reward, seed 0): tesla scored 24 paid 2, mean
  P1 0.039; skeletons 53/0. (a)
- DECISION: G runs alone (9.7 GB RSS, 1.1 GB free); G+E / E queued, yamls + launchers ready. Read at m5k
  (~2.5 h at 0.6 ep/s), m10k. One seed = screen; three before any claim.
