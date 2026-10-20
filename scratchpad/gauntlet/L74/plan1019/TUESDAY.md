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
   - Card levels (owner ruling 10-19): model EVERY card at level 16, both sides (13k ~ 15-16, Ranked all 16). Check engine support for level-16 stats + towers, switch the SIM from 11 to 16, then re-baseline evals + parity.
D. RL arms on the CLX recipe, after A says which eval to trust:
   - R1 lead-protection penalty (~0.2 x the win reward);
   - C2 crown-state starts (check engine support);
   - R3 re-grade the Rocket arms on tower Rockets;
   - more seeds per arm (seed spread: -0.4..+5.7 pp).
E. Live: an A/B protocol at the same trophy level, >= 150 matches per arm. Bait: watch the bait_gae u65 record.
F. Ops: heavy agentic work on Codex with Claude-written decision trees; API key credits are empty (bz-northwestern).
G. Live ops (owner 10-19): add a --ranked flag to start_live.sh. With it, the supervisor never taps the end-of-match OK to check Trophy Road rewards or open chests; it loops back-to-back matches (Play Again) until the STOP file exists.
H. Investment cards (owner 10-19, part of the Rocket fix): offensive X-Bow / defensive X-Bow / Rocket per matchup, pros vs ours (share, lock + tower damage, elixir lost when answered, Rocket-cycle damage, result) -> learned matchup-adaptive aggression: turtle with defensive X-Bows + Rocket cycle vs hard counters (memory investment-cards-matchup-adaptation).
I. Owner 10-19 reward request (memory reward-redirect-to-king): while both own princesses are alive, penalise own-princess damage only (potential -w x princess hp lost), so redirecting attackers to the king (Tornado Hog -> king) pays. First verify the SIM's Tornado-to-king / king activation parity and that no live decode rule hoards Tornado. One arm on the L16 recipe.
   I2 (owner 10-19): also PUNISH Tornado pulls toward our king once >= 1 own princess has fallen (king already active; wastes elixir). Pull-to-king works only for units whose range / aggro radius / mass allow it: verify the SIM's mass-dependent pull + king activation vs live, give the model what it needs to learn which units qualify (identity; maybe range/sight/mass features), scenario curriculum over attacker types.
J. SIM PARITY METRIC SUITE (owner 10-19: fight parity is not enough; >= 95% on EVERY metric is the end goal).
   Each metric gets a definition, a live data source and a noise ceiling where chaos applies.
   J-ENGINE (replay-based; same state + same inputs -> same result; agreement within tolerance / noise ceiling):
     1. fight parity (existing, FIN13);
     2. spell mechanics per spell: Tornado displacement vs unit mass, Rocket / Log damage + knockback, IW slow, Freeze;
     3. tower mechanics: king activation (trigger + tick), tower targeting, tower damage per hit;
     4. elixir economy: our elixir at each decision, 2x / 3x / overtime transitions;
     5. deploy / spawn timing and card cycle order;
     6. macro pathing: bridge-crossing times, lane / retarget choices;
     7. WHOLE-MATCH open-loop replay: replay both sides' recorded plays from tick 0. Grade:
        - the tower-HP trajectory per minute;
        - the crown sequence;
        - king activation time.
        Normalise by SIM-vs-SIM perturbed replays (divergence compounds).
     8. match-end resolution: overtime, tiebreak, crown rules.
   J-BEHAVIOUR (distributional; parity = 1 - normalised gap or CI overlap; this is opponent modelling, not engine):
     9. crown-path stats: P(princess taken), 1-1 rate, give-back after 1-0, P(win | crown state);
     10. opponent play stats per archetype: elixir per minute, push size, response latency, card timing.
   J-PREDICTIVE:
     11. SIM eval vs live win rate across the models with live records: calibration / rank agreement.
   First: define all 11 with data sources, measure the current values, rank by gap. Then fix biggest-first.
