
### 16. DOCTRINE AUTHORING, ROUNDS 1-3 UNDER A PRE-REGISTERED STOPPING RULE (owner steer, 2026-09-04 ~12:10-12:50, L48b): the tempo knight breaks a drill (wall_breakers 92 -> 8, the drill's SPEND bar), the next two oracle buckets are nulls -> stopping rule fires; and OWNER-REPORTED, ENGINE-CONFIRMED: `crowns()` counts dead towers, so a king kill with a princess standing is 2 crowns not 3 -- `crown_delta` in every ledger table is understated (policy -0.354 read vs -0.521 real-CR)

**Owner steer (verbatim):** "just to be clear, you are suggesting to stop oracle-guided authoring, even though it could
have a genuine significant effect over time, and it already performing the best on drills?" -- the L48 recommendation
to stop was WITHDRAWN as a cost judgement dressed as a finding; drill strength is not an argument either way (the
counter table, not the oracle rules, earns it). Replaced by a pre-registered rule: one bucket -> one rule -> 96 paired
seeds per round; STOP after two consecutive rounds adding < +0.10 tower pooled. Same instrument as 5cs.15.

**Round 1 -- do the L48 rules cost drills? (`doctrine_drills.py`, DrillEnv seed 5, 25 reps, first verdict; stock
71.4% mean).** (a) d6body (D-1 + tempo knight + skeleton cycle + D-6): 68.6%, `skeletons_stop_the_wall_breakers`
**92 -> 8**, bow_defends_from_the_centre 44 -> 32. Isolated per layer on that drill (`_r1b.sh`): D-1 alone 72, D-6
alone 72, either D-4 variant 8 -> the TEMPO KNIGHT. Traced (`_wb_trace.py`): the drill opens on a quiet board at
8-10 elixir, the knight (4) goes down at t=0 as tempo, the skeletons (1) answer the breakers, and the drill's
`failure` fires on `spent_more_than 4.0` (`success` needs spent <= 2.5) -- the drill charges pre-threat spending
to the answer. Drill accounting, not a lost fight; but the tempo knight's own whole-match value was never
significant (D-4 +0.109 t=0.75), so it is dropped. (a) Regret oracle under d6body: total 508 -> 290, mean 0.140 ->
0.078; residual empty-board bucket (n=249) is now HOLD -> ice_wizard/tesla, and the ice_wizard rules were already
measured null (5cs.15) -> the residual is read as the board-value artifact; next real buckets goblins (n=33),
bomber+pekka (n=13), x_bow (n=18), all HOLD -> tesla(_evo) at 4-6 elixir.

**Round 2 -- "d6nok" = D-1 + skeleton cycle + D-6, no tempo knight (`_r2.sh`, both slices + drills).**
(a) vs stock: **+0.133 tower t=1.39** pooled (slices +0.049 / +0.216), wins -1.0pp; vs d6body: -0.080 t=-1.04
(the knight is worth ~0.08 whole-match, not significant); drills 70.3% mean, wall_breakers back to 76, no hard
regression left. Policy still ahead of d6nok: **+0.268 t=2.46, +17.7pp t=3.45**.

**Round 3 -- D-7 (`doctrine_v7.py`, two arms, on d6nok).** Mechanisms (a): `pekka` is profiled `tank` but not
`win_condition`, so the "tesla for their wincon" rule (doctrine.py ~981) never fires on it; an enemy `x_bow` IS a
wincon but the tesla cell rule (~470) only accepts troop/building-targeting `movers`, so it nominates with no cell
-> HOLD. D7_TANK (tank at y > 0.30 -> tesla 5.0 + skeletons 3.0): **-0.024 t=-0.47** (slices -0.076 / +0.028).
D7_XBOW (enemy bow alive -> tesla 5.0 at the centre pull spot): **+0.001 t=0.13** -- fires so rarely on the ladder
pool that 95 of 96 matches are identical. Goblins -> tesla_evo skipped by design (4-for-2 is the measured
tesla-waste shape; the evo body is the board-value artifact). **Stopping rule fires** (rounds 2 and 3 both
< +0.10 over the previous best).

**Where the doctrine stands, n=96 paired, one instrument:** stock 24.0% / -1.34; best drill-safe stack d6nok 23.0% /
-1.21 (+0.133 t=1.39 over stock); best any-stack d6body 28.1% / -1.13 (+0.213 t=2.14, costs one drill); policy 40.6%
/ -0.94; search 80.2% / +0.29. Yield per round: +0.21, -0.08, 0.00. (a) The oracle's remaining regret is
concentrated on tesla plays the measured tesla-waste term forbids and on the board-value artifact. (b) Untested
and the honest next lever if the owner wants to continue: a scorer without the idle-body credit (removes the
artifact) and per-bucket rules on `archer_queen` / `dark_prince` / `elite_barbarians` boards (regret_v2: 31 / 21 /
12) -- each needs its own counter entry, i.e. domain authoring rather than an oracle read.

**CROWN COUNT (owner report, verbatim: "if the opponent takes the allied princess tower followed by the king tower,
the sim view counts it as a 0-2 crown loss and not a 0-3 crown loss ... If the king tower falls at all for either
side, the other side gets 3 crowns").** (a) CONFIRMED IN THE ENGINE, not only the view: `engine.py:5970`
`crowns(team) = sum(1 for t in self.towers[1-team] if not t.alive)`. Match OUTCOME is right (`_check_end`: a
king down ends the match with the correct winner), so every winrate stands. Consumers of the count:
`env.py:3207` `take_enemy_tower` / `lose_own_tower` (w_take / w_lose x delta -- pays per TOWER, so a king-fall with a
princess standing paid 1 tower + the terminal, real CR = 3 crowns), `rollout_search.py:172` (search scorer
`crown_w x d_crowns`), every `crown_delta` / "crowns taken" / "crowns lost" figure in the ledgers and the
c2r_run.yaml comments (per-tower counts), and `sim_view.py` (what the owner saw). Measured (`crown_undercount.py`,
48 ceiling matches each): doctrine leg -- their king kills 12, **5 with one of our princesses standing**,
crown_delta -1.000 read vs **-1.104** real-CR; policy leg -- 12 king kills, **8 undercounted**, -0.354 read vs
**-0.521** real-CR. Our own king kills: 0 of 48 on either leg, so the undercount is one-sided against us in
these reads. **Fix (post-c2r, engine import): `crowns()` returns 3 when the enemy king is dead.** OWNER DECISION
NEEDED (reward semantics, one change per experiment): (A) fix `crowns()` itself -- reporting AND reward change:
losing the king with a princess up pays `w_lose x 2` in one step, taking theirs pays `w_take x 2` (real-CR
incentive; magnitude only differs at match end, ~0.25 matches in 48 here); (B) add `crowns_real()` for
sim_view / records / crown_delta only, leave the reward per-tower. Recommendation: (A), as its own line in the
next run's change list, because the reward should price the game the bot plays; but it is a reward change and
the owner sets those.

**Does NOT establish:** that the tempo knight is wrong in real play (b; the drill's SPEND bar charges it); that D-7
tank is null on a pekka-heavy pool (b; ladder-pool frequency limits it); anything about the crown undercount's
effect on TRAINING (b; the terminal reward already separates win/loss, so the affected term is the per-tower
shaping at match end). Files: `scratchpad/gauntlet/L48/{doctrine_drills.py, drills_doc_{stock,d6body,d6nok}.*,
_r1.sh, _r1b.sh, _r2.sh, _r3.sh, _wb_trace.py, regret_d6body.*, doctrine_v7.py, doctrine_d6nok_*.json,
doctrine_d7{tank,xbow}_*.json, crown_undercount.py, crown_undercount_policy.txt}`.
