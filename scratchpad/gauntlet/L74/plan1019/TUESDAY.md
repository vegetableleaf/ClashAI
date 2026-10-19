# Tuesday 10-20 kickoff (owner 10-19: start at 04:00 EDT when usage resets)

Owner's four items:
1. sim parity;
2. more RL levers -- discard proven nulls, rethink the route to 14k, with OPPONENT MODELLING as a lever equal to parity;
3. everything in PLAN.md;
4. anything else.

Read with: PLAN.md (this dir), ../doctrine/DOCTRINE_MEASURED.md, ../overnight1018/LOG.md, ../parity/diag_night/R7_SUMMARY.md.

## Facts the plan rests on (measured 10-18/19)
- Live at 13k, all about the same: CLX 46.0% (113), CLIII 47.8% (46), cue_ab2 47.6% (103), CXXXVIII ~45% at 13k.
  SIM gains of +5 pp did not show live. No live-predictive SIM yet.
- CLX recipe (CLIII init, current RL, NO Stage-2 opponents) vs CLIII pooled, by seed: base +5.62, s75 -0.36, s76 +5.68;
  s77/s78 due ~15:00 10-19.
- SIM opponents take a princess in 31.6% of games (live 47-55%); 1-1 costs -8 pp in SIM vs -28..-39 live.
- Our gap: giving a 1-0 lead back 15-20% vs pros <= 5%.

## DISCARD (measured null or negative; do not re-run without a new reason)
- Stage-2 deck-conditioned opponents as built: -4..-6 pp, 2 seeds.
- REB pro-imitation anchor: -7.1.
- Exploiter league: null.
- Fast plays: -6.8.
- Standalone learned press: -5.0. As part of the recipe it is fine; keep it in.
- Combo reward: n.s.
- Cue inputs: blinding them = no change.
- Critic context C2/F2: null.
- The 15/16 factorial factors: finish its analysis first, then drop what is null.

## Work, in order (one change per experiment; Codex runs mapped steps only, Claude decides)
A. SIM -> live predictiveness. FIRST, because without it no candidate can be trusted.
   - Correlate SIM eval vs live win rate for the 5 models with live records (CXXIV, CXXXVIII, CLIII, CLIX, CLX).
   - Add crown-path realism metrics (princess-take rate, 1-1 rate, give-back) to every SIM eval.
B. Opponent modelling (the new main lever).
   - Fit an opponent policy to OUR live opponents (2,000+ logged 12-13k matches, public info only), deck-conditioned.
   - Calibrate on the crown stats: P(take a princess) ~0.5, conversion after a lead.
   - Use it for eval FIRST (does it make the SIM predict live?), then as the training league.
   - Why Stage 2 failed: it was trained on pro replays and never calibrated to the crown stats; check this before building.
C. Sim parity (biggest lever first).
   - FIN13 raw 0.926 [0.920, 0.932] on 403 matches; tier-B coverage 0.278; goal: lower CI >= 0.975, tier B >= 0.90.
   - Gap map: timing 162 / movement 86 / target picks 61 / setup 43.
   - Explain why the 139 new captures score lower.
   - Land H-PREROLL with more data; the H-NEGHP reader fix.
   - Add the doctrine's tower-loss parity metric.
   - Card levels: icebow is all level 16 from 10-19; the SIM plays every card at 11 -- check the SIM level model vs live (relative levels vs 12-13k opponents).
D. RL arms on the CLX recipe, after A says which eval to trust:
   - R1 lead-protection penalty (~0.2 x the win reward);
   - C2 crown-state starts (check engine support);
   - R3 re-grade the Rocket arms on tower Rockets;
   - more seeds per arm (seed spread: -0.4..+5.7 pp).
E. Live: an A/B protocol at the same trophy level, >= 150 matches per arm. Bait: watch the bait_gae u65 record.
F. Ops: heavy agentic work on Codex with Claude-written decision trees; API key credits are empty (bz-northwestern).
