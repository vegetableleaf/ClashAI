
### 15. OWNER ORDER "work on the doctrine ... and test the search on the drills" (2026-09-04 ~11:30-12:00, L48): the search is NOT a drill teacher (45.8% mean, 0% on six restraint drills), regret-guided doctrine rules buy +0.21 tower over 96 paired seeds but the doctrine stays ~12pp / 0.19 tower BELOW the policy -- and a RETRACTION of the L47b "14.6%" headline: the same doctrine reads 33.3% on the next 48 seeds, pooled 24.0% (n=96)

**Instrument, unchanged from 5cs.14** (L43 ceiling: ladder pool, DR off, `c2r_best`, root `.venv`, 1 thread, run
beside c2r): slice 1 = seeds 5000000-47 (L47), slice 2 = 5000048-95 (today, `_slice2.sh`, `_slice2b.sh`). All
doctrine arms are IN-PROCESS overrides (`scratchpad/gauntlet/L48/doctrine_v{2,3,4,6}.py`, `--override` on
`doctrine_teacher.py`); `icebow/src/clashrl/sim/doctrine.py` is untouched because c2r imports it (7 standing rule).

**(1) RETRACTION of scale, not of sign.** 5cs.14 reported the doctrine as "a 14.6% whole-match player" vs the
policy's 37.5%. That was ONE 48-seed slice. On the disjoint slice the same stock doctrine reads **33.3%** and the
same policy **43.8%** -- a 19pp swing for an identical deterministic player between two seed slices. The instrument's
winrate is unusable at n=48 (as 7 says); tower delta paired per seed is the discriminator. Pooled over 96 seeds:

| player (c2r_best) | slice 1 wr / td | slice 2 wr / td | pooled wr | paired vs stock doctrine, n=96 |
|---|---|---|---|---|
| stock doctrine (whole match) | 14.6% / -1.465 | 33.3% / -1.214 | **24.0%** | -- |
| doctrine + D-1 + D-4skel + D-6 ("d6body") | 22.9% / -1.175 | 33.3% / -1.079 | 28.1% | td **+0.213 t=+2.14**, wr +4.2pp t=+1.00 |
| policy alone (H=0) | 37.5% / -1.124 | 43.8% / -0.755 | **40.6%** | td **+0.400 t=+3.46**, wr +16.7pp t=+3.30 |
| search teacher (H12 N1 K4 cells3) | 79.2% / +0.167 | 81.2% / +0.409 | **80.2%** | vs policy: td +1.29 t=8.2 (s1), +1.16 t=6.6 (s2) |

(a) The sign of 5cs.14 stands -- the doctrine is a worse whole-match player than the policy (paired td +0.400,
t=3.46 over 96 seeds; wins +16.7pp t=3.30) -- but the gap is 17pp, not 23, and the best doctrine arm closes it to
td +0.188 t=1.67 / wr +12.5pp t=2.32 (policy minus d6body, n=96). The search teacher's +40pp / +1.2 tower over the
policy reproduces on the second slice (a).

**(2) Search on the drills (`search_drills.py`, 3 shards, 25 reps each, play-out ON, first verdict decides).**
Doctrine **71.4%** mean / greedy policy **34.2%** / search (H12 N1 K4 cells3 on c2r_best) **45.8%** over the 29
drills. Search beats the policy on 15 drills (rocket_the_pump_on_sight 4->96, nado_the_sneaky_lock 8->84,
matchup_bridge_spam 20->76, knight_blocks_the_charge 28->88, log_the_ground_swarm 24->72) and is WORSE on 9 -- and
the 9 are the restraint drills: never_rocket_their_king 80->**8**, skeletons_kill_the_miner 100->40,
hold_the_tesla_for_their_wincon 20->**0**, bow_punishes_the_pump 24->**0**, nado_pull_the_flock_back 96->64.
Search is 0% on six drills (hold_the_tesla, nado_king_activation, bow_defends_from_the_centre,
bow_punishes_the_pump, ignore_the_ignorable, skeletons_stop_the_wall_breakers). (a) Mechanism: the 12-s
tower/board scorer rewards spending now (a rocket on a king tower scores tower damage; a held tesla scores
nothing inside 12 s), so the search plays the move the drill verdict forbids. The search teacher and the drill
verdicts encode different doctrines; on the drills the doctrine dominates both (71.4 vs 45.8 vs 34.2). The
"search-on-drills arm" left open in 5cs.14 is closed: NOT a candidate. Trap: this instrument is not L46's
`report()` (no play-out there -> different RNG stream per rep); compare only within this table. Full table in
`search_drills_{0,1,2}.txt`.

**(3) Why the doctrine loses whole matches -- ledgers (`doctrine_diag.py`, `doctrine_diag2.py`, 12 matches).**
(a) The rich-state freeze of 5cs.14 (`the_log` nominated, no cell -> HOLD) is a LEAK, not the cause: D-1 fixes it
(at-10-elixir share 0.098 -> 0.003) and wins/tower do not move (td -0.066 t=-1.23 vs stock, slice 1). (a) The
doctrine is elixir-STARVED: at 0-2 elixir in 1695 of 2068 decisions (82%) where a non-ignorable push is on our
side and nothing is nominated -- it answers every push with everything nominated (the wincon rule nominates
tesla + skeletons + ice_wizard and the policy plays them on consecutive decisions), then has nothing for the next.
(c) "Hold after answering so the answer can work" (D-2/v3, HOLD 4 s unless committed enemy elixir grows by 3):
td **-0.349 t=-2.58** -- WORSE. Holding elixir does not help a player that spends it badly.

**(4) Regret oracle (`doctrine_regret.py`: at every doctrine decision the search scores the doctrine's move and the
best alternative; regret = best - doctrine).** 12 matches, 3633 decisions under D-1: mean regret 0.140, 30.5% of
decisions with regret > 0.05. Biggest buckets: HOLD -> knight (n=385, mean 0.45), HOLD -> skeletons (n=215),
HOLD -> tesla/tesla_evo (111), HOLD -> ice_wizard (57); by board: the EMPTY board (n=341, regret 134 of 508),
then archer_queen, skeletons, dark_prince, x_bow, goblins, elite_barbarians, inferno_dragon, giant. (b) CAVEAT
on the oracle: `Scorer.board_value` pays `bodies_ignore_frac` for a surviving own unit, so an idle knight on an
empty board earns scorer value without earning sim value -- some of the empty-board "regret" may be this
artifact. The arms below test that directly: if the oracle's advice were artifact, playing on empty boards should
not help.

**(5) Arms, all stacked on D-1, paired td vs stock doctrine, slice 1 unless noted (`_d5.sh`, `_d6.sh`):**

| arm | rule | paired td (t) | wr |
|---|---|---|---|
| D-1 `v2` cycle-with-a-cell | >=8 & quiet: drop the cell-less log nomination, cycle the cheapest card that HAS a cell (knight centre-back, ice_wizard corner, log at the weaker princess) | -0.066 (-1.23) | 14.6 |
| D-2 `v3` hold-after-play | HOLD 4 s after answering a push | **-0.349 (-2.58)** (c) | 8.3 |
| D-4 `v4` tempo knight | quiet & >=4: knight 2.0 centre-back | +0.109 (+0.75) | 18.8 |
| D-4 min 6 | same at >=6 | -0.106 (-1.56) | 18.8 |
| D-4skel | + skeletons 1.2 at corners from >=3 | +0.145 (+0.90) s1; +0.076 (+0.54) s2; pooled +0.110 (+1.04) | 27.1 / 27.1 |
| D-5 spam | knight >=3, skeletons >=1 | **+0.306 (+2.36)** | 18.8 |
| D-5 spam + ice_wizard >=3 | | +0.204 (+1.33) | 14.6 |
| D-4skel + ice_wizard >=5 | | +0.120 (+0.86) | 12.5 |
| **D-6 body** (on D-4skel) | non-quiet board, nothing nominated, deepest ground threat past y 0.42: knight 2.5 else skeletons 1.5 | **+0.291 (+1.90)** s1; **+0.134 (+1.06)** s2; **pooled +0.213 (+2.14)** | 22.9 / 33.3 |
| D-6 body + spam | | +0.194 (+1.37) | 20.8 |

(a) Playing cheap bodies on quiet boards helps (D-4/D-5 positive at >=3-4 elixir, negative at >=6 -- the value
is TEMPO, not banking), so the oracle's empty-board advice is at least partly real sim value, not only the
board-value artifact; the ordering d6body > d4skel > stock holds on BOTH slices. (a) Each rule is worth ~0.1-0.3
tower; the ice_wizard rules add nothing. (b) Whether more regret buckets (goblins+ice_spirit n=19, bomber+pekka
n=13 under D-4skel; HOLD -> tesla on quiet boards, which the measured tesla-on-empty waste forbids) would close
the remaining 0.19 tower to the policy is untested; at the observed rate it needs several more rules and each is
~48-96 matches (~1-2 min) to read, so it is cheap, but it is authoring, not measurement.

**Verdict for the owner's criterion ("if the doctrine can't perform it cannot be a plausible teacher"; owner rule:
a hand-written line must win 50%+):** (a) the doctrine is at 24.0% stock / 28.1% with today's three rules, the
policy at 40.6%, the search at 80.2%, n=96 each, one instrument. The doctrine is NOT a plausible whole-match
teacher and three regret-guided rules did not make it one. It remains the best player on the drills by 25pp
over the search and 37pp over the policy, which is exactly what arm D1 (drill-states-only imitation, 5cs.14)
uses it for -- that spec is unchanged by today.

**Does NOT establish:** that no rule set reaches 50% (b -- the oracle points at the next buckets; expected yield
~0.1-0.3 tower per rule); that the board-value artifact is zero (b -- a scorer variant with bodies_ignore_frac
removed on the same 12 regret matches would measure it); anything about the rules' effect on the DRILLS (not
run -- D-4/D-6 fire only with nothing nominated, so the counter table is untouched, but untested); that
`search_drills` numbers compare to L46's table (different instrument). Nothing in `doctrine.py` changed; landing
D-1 + D-4skel + D-6 there is a post-c2r edit (7).

**Files:** `scratchpad/gauntlet/L48/{search_drills.py, search_drills_{0,1,2}.{txt,json}, doctrine_teacher.py,
doctrine_diag.py, doctrine_diag2.py, doctrine_regret.py, regret_{v2,v4skel}.{txt,json}, doctrine_v{2,3,4,6}.py,
doctrine_none.py, _d5.sh, _d6.sh, _slice2.sh, _slice2b.sh, doctrine_*_48.json, doctrine_*_s2.json,
policy_s2.json, teacher_s2.json}`.
