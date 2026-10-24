# succ48 -- the 48-hour successor (owner 2026-10-23 ~20:45 EDT; deadline ~20:45 EDT 10-25 = 00:45Z 10-26)

Goal (owner): a successor that spends elixir well WITHOUT the forced (hazard) play, performs better live than CLX, and holds
50%+ climbing Ranked. No live runs without the owner. Reward design is the lead's call; every experiment goes in EXPERIMENTS.md.

## Why the leak exists
Live / eval gate every decision at tau_phase 0.35 / 0.45 / 0.55 (1x / 2x / OT); the forced play (stripped 10-23) covered the
cases the gate blocks. Training sampled the gate at 0.35 everywhere, so the policy never learned to clear the stricter 2x / OT
thresholds. No-hazard eval of the drift init: E4 win 0.700 -> 0.615, seconds at >= 9.9 elixir 18 -> 62 per match.

## Recipe (succ48_*)
cal30 (drift_tg + calibrated I u40 exploiter decode, share 0.3) + rollout tau_phase [0.35, 0.45, 0.55] + habit terms
(idle penalty, penalty-only trade) + habit_leak_w (penalty per elixir regenerated while full; cap 0.3 / match).
Init = the drift-test init (CLIII raw u65); KL to its own init on the card head only (beta 0.03), no CLX leash.

| arm | idle_w | trade_w | leak_w | seed | pod |
|---|---|---|---|---|---|
| a_s74 | 0.05 | 0.02 | 0.005 | 74 | 32525 |
| a_s75 | 0.05 | 0.02 | 0.005 | 75 | 33591 |
| b_s74 | 0.05 | 0.02 | 0.01 | 74 | 33572 |
| c_s74 | 0.1 | 0.01 | 0.005 | 74 | 33401 |

Why these weights: habc_s74 (idle 0.1, trade 0.01) over-defended (trade -0.31 at u75) -- avoiding one idle threat was worth up
to 10 elixir of over-pay; 0.05 / 0.02 caps that at 2.5. Leak 0.005: the init wastes ~30 elixir / match -> -0.15 (cap 0.3),
so the gradient survives until the leak is mostly gone; b doubles it.

## Schedule
- Each arm: drift_test.sh ARM 300 (checks every 25: E4 960 board-recorded, NO-HAZARD eval, drift_check vs its own u0 at 99%,
  tripwire = 2 consecutive gate FAILs or proagree < init - 5 pp).
- u50 / u75 (~6-9 h in): rank arms on (1) seconds at full elixir, (2) E4 win, (3) habits. Stop the clear losers; restart their
  pods with the leader's recipe on a new seed, or as a branch initialised from the leader's checkpoint.
- ~h36-42: candidates (best checkpoints by leak + win) -> promotion gate vs CLX WITH the hazard play (the live-proven
  baseline): pooled E4 1,920 (4 seed blocks) + calibrated I u40 (decide 20, tau 0.2) 1,920, paired; behaviour (leak,
  idle / ignored threats, trade, Log use, Rocket use).
- Report to the owner by the deadline: the best successor, its gate numbers, its leak, and the remaining risks. Owner starts
  live. Stop all 4 pods at the deadline unless the owner says otherwise.

## Success bar (SIM)
1. No-hazard leak: seconds at >= 9.9 elixir <= 12.5 / match (CLX WITH the hazard play, E11; CLX without it: 52.6; init: 62); first play <= ~13 s.
2. Win vs CLX-with-hazard: pooled E4 CI low > 0 (owner's promotion gate), and not worse vs calibrated I u40.
3. Habit checks clean vs its own u0 (idle / ignored / trade).
