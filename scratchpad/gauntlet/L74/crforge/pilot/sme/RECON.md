# RECON: one general reconstruction instead of the SME_* hand rules (ENGINE-RECON, 2026-10-30)

Code: `sme/recon/` (`recon.py` rules + hypothesis generator, `test_recon.py` planted checks, `offline.py` the hand-rule
cases, `field_census.py` the rules on every frozen fresh input, `recon_search.py` the engine-scored search for a pod).
Evidence: `results/live/recon/`. Labels: (a) measured, (b) plausible but untested, (c) contradicted.

## STATUS (keep current)
- **Restart point (10-30 ~14:30 UTC):** laptop part DONE and committed: rules + generator (`recon.py`), 35 planted
  checks (`python -I sme/recon/test_recon.py` -> `ok 35`), the general generator proposes the hand fix on all 6
  hand-rule cases tried (`offline.py`, output `results/live/recon/offline.txt`, section 5), field census of the rules on
  FRESH4-8 (`results/live/recon/field_census.txt`, section 4), the engine-scored beam search `recon_search.py` with a
  stub-engine loop test (`python -I sme/recon/test_search_dry.py` -> `ok 12`).
- **NOT done: no engine run.** No crforge on the laptop; the SME gate tree (32657 `/workspace/pilot/f1fix/sme11f`) is
  gone (32657 refuses SSH; TARGET_OBS.md M1c: SME pods stopped, /workspace wiped). 33903 has JDK + the 5e8089a4 tickprobe
  lib but no gate code and only tables 16.402.22 under crforge_cache (14:00 UTC load 5, quota 54.4 CPUs). Next: section 7.
- Codex dispatches: none. pyflakes not installed on the laptop (plain or icebow/.venv): `py_compile` + a manual
  unused-import pass only; run pyflakes on the pod before relying on it.

## 1. Why (the measured problem)
- (a) Pooled strict-fresh FRESH2-8 = 122 / 151 (0.808, CP lower 0.748), flat at ~81% across ~20 SME_* rules
  (SME.md STATUS). Of ~25 traced failures, ~1 was an engine rule; the rest were observation gaps: unseen Zaps,
  dropped bodies, same-tick order, spell dating (memory note engine-resume-approach-1029).
- (a) Each hand rule is a detector that must decide FROM OBSERVATION ALONE whether something happened. SME_ZAP_DEAD
  needed three rounds of blocks (projectile 108, splash 48, targets-victim 32, area 32, opp play 15, body near 12, ...)
  to reach 1 firing in 297 records, and SME_ZD_SINGLE then lifted one of those blocks for another match. The blocks
  exist because the rule cannot simulate: it guesses whether a seen cause (a Mega Knight's splash, a Hog) explains the
  vanish. The engine knows: if the SIM's own Mega Knight kills the Skeletons, they are not SIM-only at the divergence.
- (a) The existing fitter (`sme_live.fit_match`) already IS a search, but a narrow one: at the first divergence d it
  moves ONE command's run tick inside its extractor window, or an opponent play's point by 500 units, and keeps the
  variant that moves d latest. It cannot add or drop a play, change same-tick order, or move two commands together.
  Every hand rule in the three classes below exists because of one of those four gaps.

## 2. The idea
Treat the extracted plays as a NOISY OBSERVATION of the true input stream. At each first divergence d, propose the
edits to the input stream that could explain the diff at d, drop every edit a hard game rule forbids, score the
survivors with the engine and the UNCHANGED comparator, keep the best, continue at the next divergence.
This is the existing fitter with (i) a larger move set and (ii) hard rules as the prior. The comparator is never
touched: a hypothesis only changes crforge's inputs (as every SME_* extractor rule already does).

## 3. Search space: the edits (`recon.hypotheses`)
| edit | what | generated from | replaces (hand rule) |
|---|---|---|---|
| shift | one command's run tick | each command run in [d-120, d]; ticks its observations allow (window, travel) | the fitter's move |
| joint | several commands' run ticks together | commands IMPLICATED by the diff (their card can make an object the diff names), cartesian product of their tick sets (cap 64) | SME_SPELL_KING (151109) |
| swap | order of two same-tick commands | every same-run pair near d | SME_SAMETICK_ORDER / _GEN (031310) |
| point | a play's point | the first listed body of the play (>= 300 units off); opponent plays also the +-500 grid | SME_OWN_BODYPT / BODYPT3, the fitter's grid |
| add (a) | an unseen spell of side o | VICTIMS of side 1-o in the diff (SIM-only bodies with no live body within 300; live bodies at the SIM point with less hp); every spell in o's deck whose radius covers all victims from the centroid or a +-500 grid point; run ticks [previous frame - flight, d - 1 - flight] | SME_ZAP_DEAD, ZD_SINGLE, ZD_BLDG, TOWER_ZAP, ZAP_CHAIN1, ZAP_ADD (021310, 235834, 024716 class) |
| add (b) | a play the extractor missed | a live body the SIM lacks (no SIM body within 300) of a deck card no near command plays; run [frame before its first listing - 1, first listing - 1] | SME_HIDDEN_GEN-type misses, 063025 bush, 004719 |
| drop | a play the extractor invented | an implicated opponent play | NEAR_BIGGER(2)-type false plays, 211745 duplicate Heal |
| press | an unseen ability press | the side's latest play of an implicated card with an ability row (hero / champion), R in [d-4, d-1] | IWGHOST10, TOMB_HERO, BB_RISE, OWN_PENDCAST, CHARGE8 |

## 4. Hard rules (`recon.legal` + the generator; planted checks in `test_recon.py`)
| rule | statement | field census on the frozen inputs of FRESH4-8 (139 records, 9,939 plays; `results/live/recon/field_census.txt`) |
|---|---|---|
| cycle | the side's play sequence admits a 4-card-cycle deal (ours: the known deal) | (a) opponent fits 113 / 139, own 137 / 139. A side that already fails is not tested (the rule cannot be a filter there; an edit that RESTORES it is the signal) |
| elixir | bank: start E0, +1/56 per tick at 1x, 2x from 2400, 3x from 4800, cap 10, card cost (and ability-press cost, `character_abilities.ManaCost`) at the run tick; never < -0.5 | (a) E0 from OUR first frame = 5.99 on all three cases. Own-side model vs the reader's own elixir, 3,791 frames >= 60 ticks from an own command: median error 0.052, p95 0.155 (max 6.0 = frames after the match end, t >= 6100). Opponent minimum over the match: median 0.48 (players run near 0), 5 / 135 below -0.5: 3 flagged opp_no_fitting_deal (211745 = Heal Spirit extracted twice per play, 953/975, 1658/1706, 2601/2625), 2 unflagged (223547 -1.66, 203126 -0.57; untraced, b: an extra extracted play). Elixir-making decks (Elixir Collector, Elixir Golem) skip the rule: 4 records |
| zone | a troop / building / territory-bound spell lands in its half, or the pocket (rows to 20 / from 11) of a lane whose enemy princess tower is down; CanDeployOnEnemySide cards anywhere | (a) 18 / 9,939 extracted points break it, all from point conventions: Suspicious Bush 9 (walking body), Heal Spirit 6 (the heal area's point), Barbarian Barrel 2, Hog Rider 1. Only RECON-proposed points are tested |
| travel | a flying / rolling spell: run = t1 - |p1 - origin| / speed when that is a whole tick (origin = the caster's king; SpellAsDeploy = the point moved back MinDistance) | (a) inside the extractor window for 1,423 / 1,425 extracted projectile-spell plays (Log 942, BarbLog 191 + 1 outside + 1 none, Fireball 168, Rocket 57, Goblin Barrel 42, Snowball 23) |
| visible | an ADDED, never-seen spell is on the board <= 2 ticks (Zap: area life 1 tick; a thrown spell's flight; rollers never) | (b) the reader's frame gap is 2 ticks; no census yet |

## 5. The hand-rule cases: does the general generator propose the hand fix? (a; `offline.py`, laptop, no engine)
Inputs: the FROZEN fresh inputs (scored before the fix) + the gate's first-divergence diff (`*_results.jsonl`
first_detail). "Legal" = after the hard rules; that count is the engine runs the round costs. Output `results/live/recon/offline.txt`.
| case | hand rule and its fix | general generator (rank among legal edits by prior cost) |
|---|---|---|
| FRESH5 021310@1986 | SME_ZAP_DEAD: opponent Zap (12864, 17261), R 1985, window [1984, 1985] | 19 legal (1 shift, 18 add); **#2 / #3: add Zap R 1984 / 1985 at the victims' centroid (12922, 17231)**, 66 units from the hand point (the hand probe at (12800, 17300) was also exact) |
| FRESH4 151109@925 | SME_SPELL_KING: Snowball and our Log both run 924 | 12 legal (1 refused by the cycle); the travel rule gives each 924; **#4: joint Log -> 924, Snowball -> 924** |
| FRESH6 031310@3954 | SME_SAMETICK_GEN: our Knight created before the Mega Knight on 3931 | 25 legal; **#1: swap MegaKnight <-> Knight @3931** |
| FRESH4 235834@4612 | TOWER_ZAP + TZ_REACH: opponent Zap on our 19-hp princess tower, R 4611 | 19 legal; **#3: add Zap R 4611 at (14500, 25500)** (R 4610 is proposed too; the hand probe: 4610 -> 40 div, so the engine must pick 4611) |
| FRESH4 220244@3374 | SME_OWN_BODYPT: our Knight at its first body point | 1 legal; **#1: point Knight (2499, 13500)** |
| FRESH4 222707@1653 | SME_OWN_BODYPT | 2 legal; **#2: point Knight (1499, 10500)** |
Prediction, no hand fix exists: **FRESH6 024716@1399** (SME.md: "our princess tower 77 below the SIM = exactly a
level-16 Zap's crown-tower damage; untraced"). The diff also has our Knight 306 below the SIM = the level-16 Zap's troop
damage (ZAP_DMG 16 = (306, 77)) (a). The generator's only proposals are 18 Zap adds; the cheapest = Zap R 1397 / 1398 at
the two victims' centroid (14479, 24739) (b until the engine scores it).
Out of scope (a): FRESH5 004719 (SME_BANNER_GIVEN) was an input-DELIVERY fix in SmeRun (the banner by object id), not an
input edit; RECON does not cover it.
Not shown yet: that the ENGINE keeps each fix (section 7, item 1).

### Hand rule -> RECON edit (b, except the 6 rows above)
| fresh_prep flag (20) | RECON edit that should cover it |
|---|---|
| ZAP_DEAD, ZD_SINGLE, ZD_BLDG, TOWER_ZAP, TZ_REACH, ZAP_CHAIN1, ZAP_DOT | add (a) unseen spell, victims from the diff |
| SPELL_KING | travel rule (+ joint) |
| SAMETICK_GEN | swap |
| OWN_BODYPT, OWN_SPAWN, RASCAL_EDGE2 | point (first listed body / formation centre) |
| NEAR_BIGGER2, OWN_NEARDEAD | drop / add (b) |
| HIDDEN_GEN, HIDDEN_CHILD | add (b) for missed plays; HIDDEN_CHILD's comparator side is not an input edit (not covered) |
| TOMB_HERO, BB_RISE, OWN_PENDCAST | press (add / its absence) |
| GK_WALK | drop of an ability cast (drop covers plays only today: owed) |

## 6. Scoring and search strategy (`recon_search.py`)
- Objective: `sme_live.objective` = (first div frame outside given-up episodes, - div frames), on the same window the
  fitter uses ([d-125, d+400]); the full comparator (analyse + reclassify) scores the final plan.
- Beam search, left to right: state = plan + edit list. Each round, for each beam member: its first divergence d ->
  legal edits -> one crforge run each (`sme.run_batch`) -> keep the top B (default 4) by (objective, - edit cost).
  Edit cost (Occam prior): shift 1, swap 1, joint 2, point 2 (grid 3), add 3, drop 3. Stop when no member's d moves
  (that episode is given up, as in fit_match) or after MAX_ROUNDS. B = 1 with only shift + point = fit_match's move set.
- Acceptance for structural edits (add / drop): the new first divergence must be >= d + HEAL (20) ticks later, so a
  phantom play cannot be kept for a one-frame gain.
- Cost: ~15-30 legal edits per round on the three cases (section 5) = the fitter's 10-24 variants per round. A crforge
  fork (snapshot at d - 125, run only the window) would cut each run ~5-20x; SmeRun has no snapshot entry (b).

## 7. Owed (next account), in order
0. **Gate rebuild (prerequisite, shared with TARGET_OBS.md M1c):** a pod with JDK 17 + `/workspace/crforge_main/
   5e8089a4/tickprobe/lib` + tables 16.635.3 (laptop copy `.foreman/scratch/reader_torn/sme/tables/16.635.3`, sha
   1243a2df... in each fresh `prep.txt`). Copy `crforge/pilot/sme` (tracked tree) to the pod, build `build/` (SmeRun) and
   `build_snap/` (SnapRun2) against that lib, env = `f1fix/runH.sh` with SME_LIB = the tickprobe lib and
   SME_BANNER_GIVEN=1. **Byte-identity check before anything else:** `sme_live.py one` on FRESH5 021310 (frozen inputs
   `engfix/fresh5/inputs_rngfree.jsonl`, frames `engfix/fresh5/frames`) must give F5_main's 1660 exact + 105 div, first
   1986; FRESH4 151109 2767 + 264, first 925; FRESH6 031310 2102 + 40, first 3954. A mismatch = the rebuild is not the gate.
1. Engine-score the 6 cases + 024716: `cd SME && <runH env> python3 recon/recon_search.py all --workers 4 --inputs
   <set>/inputs_rngfree.jsonl --frames <set>/frames --out OUT --only 021310,151109,...` (<= 8 threads on 33903, CPUs
   210-217, `taskset`, check load first). Pass = the beam keeps the hand fix and reaches the hand-rule result (021310
   1765 / 1765, 151109 3031 / 3031, 031310 2142 / 2142, 235834 2271 / 2271, 220244 3025 / 3025, 222707 1766 / 1766).
   Also `--ops shift,point --beam 1` on the same cases must equal F*_main (the fitter's move set).
2. Planted recall: in exact matches, delete one seen opponent Zap / one seen play / swap one same-tick pair; the
   search must restore it (and nothing else).
3. Precision: run the search on every failing record WITHOUT the 20 SME_* flags; count adds / drops kept on
   divergences whose cause is traced as non-observational (body position: 123045, 073232); the HEAL rule (20 ticks)
   and the edit cost are the knobs.
4. The gate question: RECON (flags off) vs fresh_prep's 20 flags on dev + FRESH1-8, then the first fresh set scored with
   RECON alone. Only then retire flags (each retirement = byte-identical scored outcome or better, planted checks kept).
5. Small owed rule work: drop for ability casts (GK_WALK); trace the 2 unflagged elixir breaks (223547 -1.66, 203126
   -0.57); a census of the visible rule.
