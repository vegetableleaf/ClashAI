

### §5cs.26 -- TESLA-OUTCOME PROBE (2026-09-04, L56, sim only): the sim does NOT reward the corner Tesla over a centre one -- per-Tesla damage (upper bound) corner 1040 vs centre 1157 vs the policy's own mix 954 (n~280-300 each, 2 seeds, CIs +-170), and it does not punish it either; the left-lane cell 274 IS worse (690, both seeds, CIs disjoint). Cell 234 was found by the gatec2 lineage between 5k and 10k from a 14-cell spread (c2r resumed it, cell head saturated at raw |81|); every arm locks on ONE cell per card, and Skeletons in front of the king (423) is universal. Landscape flat between corner and centre -> a training/exploration artefact on a sim that cannot tell them apart, not a sim payoff

**What ran.** `scratchpad/gauntlet/L56/tesla_probe.py` on `policy_c2r_20260903_best.pt`: play.py's greedy rule
(argmax card, argmax cell of the card's own map, own-half mask, WAIT iff sigmoid(Q_play-Q_wait) <= tau with the
CONFIG value `rl_gate_tau: 0.25`, no search), 4 arms x 24 matches x seeds 1234/5678, the TESLA cell forced per arm
and nothing else: own (policy's cell) / corner (234 = row 13, col 0) / lane (274 = row 15, col 4) / centre (314 =
row 17, col 8). Damage attribution as in tools/xbow_probe.py (HP drop of the locked target, sampled at agent_dt
0.6 s: an UPPER BOUND). Results `L56/tesla_probe.txt`, `.json`. Then `L55/place_probe.py` (seed 0) on the run
history and sibling arms: `L56/place_history.txt`. Box idle (1 python proc, 5.7 GB free) throughout; ~14 min.

**(a) measured -- in the sim.**
- Per-Tesla unit damage (upper bound), mean [bootstrap 95%]: own 1086 [924,1259] / 857 [717,995] (s1234/s5678);
  corner 1014 [834,1219] / 1070 [860,1295]; lane 731 [600,870] / 644 [515,777]; centre 1225 [1044,1407] /
  1067 [868,1258]. Pooled: own 954 (n=299), corner 1040 (274), lane 690 (298), centre 1157 (294). Kills per
  Tesla 1.64 / 1.75 / 1.26 / 1.64. Corner vs centre: overlapping on both seeds (1014 vs 1225, 1070 vs 1067).
  Lane vs either: disjoint on both seeds. The corner is as good as the centre and better than the lane cell.
- Match level (48 per arm): wins 14 / 16 / 10 / 10; crowns 35-68 / 44-69 / 40-74 / 37-72; enemy tower HP lost
  per match 5176 / 5752 / 5358 / 5324; ours 10484 / 10566 / 11375 / 10495. Noise-level differences (winrate is
  not a discriminator, §7); no arm changes the match.
- The policy plays a Tesla 5.3-7.2 times per match in every arm (a 4-elixir building every ~30 s of a ~200 s
  match); time-with-target 19-38%; mean lifetime 17-23 s of 30.
- Enemy river crossings left/right: 189/268, 235/351, 202/311, 265/268, 200/350, 224/257, 170/304, 226/260 --
  the scripted bots go RIGHT 55-64% of the time. The corner Tesla (reach 5.5) covers only the left bridge.
- History of the corner (place_probe, seed 0, tesla@234 share): c2r m5k 13/30 -> m10k 27/31 -> m20k 19/25 ->
  m30k 23/30 -> best 52/82 (L55, 3 seeds). gatec2 m5k: 14 distinct cells, top 266 at 5/21, x_bow 10 distinct
  -> gatec2 m10k: 234 at 23/29, x_bow 234 at 9/9. c2r was `--resume`d from that lineage (log line 1: "resumed
  policy_c2r_20260903.pt", and "RAIL GUARD: cell head saturated beyond the tanh cap -- raw absmax 81, rescaled
  x0.0556"). Other arms lock elsewhere: aggro1_m5k tesla 347/233, gate05_m5k tesla 327 (13/20). Skeletons -> 423
  in EVERY checkpoint probed (aggro1: 424), 47-54 of 47-54 plays. Knight -> 426 in the c2r/gatec2 line.

**(b) plausible, untested.** (1) Why 234 and not the centre, given a flat landscape: an X-Bow at 234 reaches the
enemy left princess tower (11.9 tiles centre-to-centre - 1.5 radius = 10.4 <= 11.5 reach) from outside the tower's
range -- a real "lane bow" spot -- and x_bow@234 rewarded by the wincon/lock terms could have dragged the other
cards' maps with it: the per-card maps are ONE `cell_conv` over the shared trunk + a card-context vector
(model.py 158-170), so they are structurally coupled. Measurement: tools/xbow_probe.py lock rate at 234 vs the
band, and the correlation of the per-card maps on the same states. (2) The gatec2 5k -> 10k move to 234 is
selection by the reward, but of what the reward could see -- the per-Tesla read says the sim cannot separate
corner from centre, so whichever cell the coupled head drifted to first would have stuck. (3) Skeletons@423 =
a 1-elixir cycle play in the safest spot: the reward's cycle/elixir terms pay it regardless of the board
(untested; the drill suite's skeleton drills would say).

**(c) contradicted.** "The sim specifically rewards a riverside-corner Tesla" (my L55 (b)) -- no: corner = centre
on per-Tesla damage on both seeds. "The lane cell would be the sensible fix" -- no: 274 is the worst of the four
in the sim (690).

**What this changes.** Exploration alone will not fix placement: a policy that explores on a sim whose payoff
is flat between the corner and the centre has nothing to learn from. The fix has to bring in what the sim does
not know -- either (i) a human placement prior per card from the 268-replay corpus (tools/replay_priors.py
exists; a KL term on the cell head toward the human cell distribution, one training change), or (ii) an
opponent that punishes out-of-position buildings (lane-switching / Rocket on buildings), which is opponent-model
work. (i) is cheaper and measurable with place_probe. Next loop: read the human Tesla/X-Bow cell distribution
from the replay corpus (cheap, decisive about how far off 234 is), then spec the prior arm. The exploration arm
(§5cs.25) is parked. The oscillation question stays (b).

**Traps found.** (1) A Tesla's last observed HP cannot separate "killed" from "expired": the sim drains building
HP over the lifetime (hp_end < 400 for 83-86% of Teslas in every arm, while 22-47% reached full life) --
`died 0/N` in the probe's summary line is an artefact of reading HP after removal. (2) Forcing one card's cell
diverges the whole match after the first play (Teslas per match 5.3-7.2 across arms on the same seed), so
per-Tesla numbers are the comparison, not per-match. (3) gate tau: the live/sim rule is `rl_gate_tau: 0.25`
(config line 911); the probe's first smoke used 0.5 and played half as often.
