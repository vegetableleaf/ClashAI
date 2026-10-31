# RECON: one general reconstruction instead of the SME_* hand rules (ENGINE-RECON, 2026-10-30)

Code: `sme/recon/` (`recon.py` rules + hypothesis generator, `test_recon.py` planted checks, `offline.py` the hand-rule
cases, `field_census.py` the rules on every frozen fresh input, `recon_search.py` the engine-scored search for a pod).
Evidence: `results/live/recon/`. Labels: (a) measured, (b) plausible but untested, (c) contradicted.

## STATUS (keep current)
- **RECON-5 (10-31 ~00:45 EDT, section 12) -- IN PROGRESS.** Step 1 DONE (a): the 8 flagged-but-exact FRESH9 records (012313, 014530, 024332, 030902, 040421, 053225, 091421, 102101) ablated edit by edit
  (`recon/ablate_edits.py`, evidence `results/live/recon/r5/f9_ablate_edits.jsonl`): every structural edit NEEDED (8 / 8 restored plays: add own Knight / Tesla / IceWizard x3, add opponent Zap x2, re-dated Zap), 0 unneeded,
  0 harmful; FRESH9 v3 with the 8 counted: **128 / 177 pass (0.723, CP low 0.662), 125 strict (0.706, CP low 0.645)** vs as extracted 120 / 117; gate unchanged 122 / 117 (4 of the 8 are gate-exact already).
  Step 2: the battle-log deck is ALREADY the extractor's deck (section 12.2); the open class is the opponent's play sequence (12.3). Mechanism = `recon/cyc.py` (deck-constrained cycle repair, shortest path over the 1680 cycle states) + `RECON_CYC=1` in
  `recon_search.py`; planted checks `test_recon.py` ok 70, `r5_planted.py`. Dev / FRESH9 runs: section 12.5 (pod 33903, tree `/workspace/smeR4`, CPUs 226-237). Codex dispatches: none.
- **RECON-4 (10-30 ~16:20 EDT, section 11) -- STOPPED at the owner's priority change; committed, resumable.** Built and committed (code frozen, `ok 56`): generator v3 operators
  + `cls_ticks` in recon results + `recon/r4_report.py` + `recon/r4_prep.sh`; FRESH9 frozen (list sha 88059ea5, commit 7ec0921, BEFORE any generator change). Measured:
  dev 151 (IN-SAMPLE): gate 142 / 132 strict; v2 126 / 119; **v3 136 pass / 129 strict (138 / 131 with 155249 + 000242 counted)**; 0 matches lost v2 -> v3;
  paired v3 vs gate 7 : 1 (p 0.07; with the two counted 5 : 1, p 0.22). Held-out FRESH9: the 20-flag GATE is done: 122 / 177 pass, 117 strict (177 unique matches of 179 records; 35 flagged
  by the extractor: 27 opp_no_fitting_deal + 8 own_cycle_fail; 122 / 142 of the unflagged pass). **RECON v3 on FRESH9 was still running unattended when I stopped
  (f9_v3 ~60 / 179, then f9_gate_a0, f9_v3_a0, the ASSIGN pair on the 8 reader-hidden records); NOT measured: v3 on FRESH9, the FRESH9 ASSIGN guard.**
  Restart (pod 33903, tree `/workspace/smeR3`, CPUs 226-237; driver `drive_f9.sh` PID 600144 ends by itself with F9_DONE in `runs/f9_drive.log`):
  `cd /workspace/smeR3 && (nohup bash drive_f9.sh > drive_f9.out 2>&1 < /dev/null &)` (skips steps whose log says done; delete a half-done `runs/<step>` first).
  Then pull `runs/f9_gate/results.jsonl`, `runs/f9_v3/recon_results.jsonl`, `runs/f9_gate_a0/results.jsonl`, `runs/f9_v3_a0/recon_results.jsonl` and run
  `python3 recon/r4_report.py gate=f9_gate.jsonl v3=f9_v3.jsonl --a0 gate=f9_gate_a0.jsonl v3=f9_v3_a0.jsonl --unflag 155249,000242` (the --unflag ids are DEV ids; FRESH9 has none
  to un-flag, report as extracted). Dev rerun: `drive_v3.sh` (v3_dev on `data/off_all151.jsonl` + `v3_a0`). Known v3 dev gaps (11.3). Codex dispatches: none.
- **RECON-3 (10-30 ~13:40 EDT, earlier; superseded by the RECON-4 line above), section 10): the missing comparison is MEASURED. Nothing of mine is running.** Both pod drivers
  ended (R2_DONE, R2B_DONE). Hand-rule gate (20 flags, same raw logs, same lib 5e8089a4): **142 / 151 pass apart from torn
  (0.940, CP low 0.898), 132 strict**; RECON v1 123 / 116; RECON v2 126 / 119 (0.834, CP low 0.777). The gate wins 16 matches,
  RECON wins 0 (paired sign p < 0.0001). **The gate number is IN-SAMPLE (every hand rule was written on these records): not a
  gate number; a held-out FRESH9 is the real test.** ASSIGN guard (gate, per frame) PASS. The 16 gate-only matches map to named
  generator gaps (10.3). Diagnostic (patched input, a): the Tombstone press with unit index 2 lets repress fix 5 of the 6
  hero-Tombstone matches (the 6th needs a re-bind). Report: `python3 recon/r3_report.py` (usage in the file). Evidence
  `results/live/recon/r3/`. Next round: 10.5. Codex dispatches: none. Earlier close-out (11:50 EDT) is superseded.
- **RECON-2 (10-30, section 9). Restart point:** item 2 planted recall DONE (a): 49 plants on the 8 exact recon plans;
  in the move set's classes 22 / 25 restored exactly, inverse edit rank 1 of the first round every time it was listed,
  0 wrong fixes; outside it by design: drop of a visible spell 0 / 7, own point 1 / 5 (+ 4 equivalent body-point fixes).
  Bug fixed: sticky ability skip in recon_search (43f23fe). Items 3-4 RUNNING (10-30 ~11:10 EDT): laptop re-extraction
  of the 196 RNG-free FRESH2-8 records DONE (`recon/r2_regen.sh` -> `.foreman/scratch/recon2/{off,on}/`, 27 min at 2
  workers; flags-on FRESH7 11 / 11 and FRESH8 19 / 20 plays identical to the frozen inputs, the 1 = ZD_SINGLE, a), sets
  by `recon/r2_sets.py` on the pod in `/workspace/smeR/data/r2/` (shas `results/live/recon/r2/sets_sha.txt`), queue
  `/workspace/smeR/sme/recon/r2_drive.sh` running (log `runs/r2_drive.log`; restart = `cd /workspace/smeR && nohup bash
  sme/recon/r2_drive.sh > runs/r2_drive.log 2>&1 &`, skips steps whose log says done; a half-done step restarts from
  scratch: delete its `runs/<step>` dir first). Then `python3 recon/r2_prec.py runs/r2_fail/recon_results.jsonl
  runs/r2_abl/ablate.jsonl data/r2/strict_ref.jsonl` (9.2) and `python3 recon/r2_tally.py runs/r2_gate/results.jsonl
  runs/r2_fail/recon_results.jsonl,runs/r2_rest/recon_results.jsonl` (9.3). Codex dispatches: none.
  **Second pass queued:** generator v2 (spell grid + repress, section 9.2b) in `/workspace/smeR2` (`recon/r2b_drive.sh`, PID
  on the pod `ps ... r2b_drive`; waits for r2_drive's R2_DONE; log `/workspace/smeR2/runs/r2v2_*.log`). Restart: `cd
  /workspace/smeR2 && (nohup bash sme/recon/r2b_drive.sh > r2b.out 2>&1 < /dev/null &)`. Do not edit a running driver.
- **Restart point (10-30 ~14:30 UTC):** laptop part DONE and committed: rules + generator (`recon.py`), 35 planted
  checks (`python -I sme/recon/test_recon.py` -> `ok 35`), the general generator proposes the hand fix on all 6
  hand-rule cases tried (`offline.py`, output `results/live/recon/offline.txt`, section 5), field census of the rules on
  FRESH4-8 (`results/live/recon/field_census.txt`, section 4), the engine-scored beam search `recon_search.py` with a
  stub-engine loop test (`python -I sme/recon/test_search_dry.py` -> `ok 12`).
- **SME-REBUILD (10-30 ~14:25 UTC): gate rebuilt on 33903 and ENGINE-SCORED (section 8).** Gate tree
  `/workspace/smeR/sme` from tracked 18f614a reproduces F4_fe / F5_main / F6_main byte-identically (a). RECON search
  (beam 4, all ops) on the flags-off frozen inputs: **8 / 9 hand-rule cases reach the hand-rule result with the hand
  edit at rank 1 of its round (the 6 of section 5 + 024716 ZAP_DOT + 201103 RASCAL_EDGE2); 001856 (OWN_PENDCAST) not:
  an elixir-only diff generates no edit (a).** 165155 ends 20 ticks before the gate (zone rule vs the fitter's off-zone
  Hog grid move, a). Fitter move set (`--ops shift,point --beam 1`) = F*_main on 3 / 3 (a). Restart: section 8.
- Previous: no engine run (the SME gate tree on 32657 `/workspace/pilot/f1fix/sme11f` was lost with /workspace).
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

## 8. SME-REBUILD: the gate rebuilt on 33903 and the search engine-scored (10-30, evidence `results/live/recon/rebuild/`)
### Recipe (a: run as written)
1. Laptop: `git -c core.autocrlf=false archive <commit>:scratchpad/gauntlet/L74/crforge/pilot/sme | ssh ... 'tar -x -C
   /workspace/smeR/sme'` (LF; plain `git archive` is CRLF here). sme_live.py md5 86cd7fab = the ENG-FIX4 gate copy.
   `sme.py` reads `SME_TABLES` since 18f614a (absent = the old 16.402.22 default; this was the one sme11f-only line).
2. Laptop: `cd sme/engfix && tar -c freshN/{inputs_rngfree.jsonl,frames,prep.txt} | ssh ... 'tar -x -C /workspace/smeR/data'`
   (ownership warnings only). Check: `sha256sum inputs_rngfree.jsonl` and `cat $(ls frames) | sha256sum` = prep.txt
   (FRESH4 4ef8ce16 / b50dd9e5, FRESH5 00ea1059 / 0835bc29, FRESH6 20ac8e69 / 0c01b4c4: all equal).
3. Pod: `bash /workspace/smeR/sme/recon/rebuild_gate.sh` = copy tables 16.635.3 from /workspace/oplm/tables to
   /workspace/crforge_cache/tables (sha 1243a2df = prep.txt), sha-check the 5e8089a4 tickprobe lib, javac `build/`
   (SmeRun.java) + `build_snap/` (bp/SnapRun2.java), `sme.py selftest` ok.
4. Pod: `CPUS=226-237 WORKERS=n SME_THREADS=m ONLY=a,b bash sme/recon/runR.sh RUN gate|recon INPUTS FRAMES [VAR=val]`
   = f1fix/runH.sh's env + SME_BANNER_GIVEN=1 (ASSIGN on; trailing `SME_HIDDEN_ASSIGN=0` = off); recon extra args in
   `RARGS`. Output `/workspace/smeR/runs/RUN{,.log}`.
### Byte identity (a; `id{4,5,6}_results.jsonl`, `recon/idcmp.py`), ASSIGN off as the references
| match | rebuilt gate | reference | shared fields equal |
|---|---|---|---|
| FRESH4 151109 | 2767 + 264 div, first 925 | F4_fe same | 24 / 24 (only the newer `cls_ticks` differs) |
| FRESH5 021310 | 1660 + 105, first 1986 | F5_main same | 24 / 24 |
| FRESH6 031310 | 2102 + 40, first 3954 | F6_main same | 24 / 24 |
Includes first_detail, the fitter's repair log, plants (0 missed), overfit and deal checks. Wall 41-68 s per match (4 threads).
### Engine-scored RECON search (a; `rs1_*`, `op*_f4_*`, `fp_*`; summaries `recon/recon_sum.py`, `recon/recon_rank.py`)
Flags-off frozen inputs, beam 4, all ops, 3 threads per match. "Round" = the search round at the hand rule's divergence.
| case (hand rule) | RECON result | hand-rule result | hand edit rank 1 in its round? | legal / beat d there | window runs + full runs (whole match) | wall |
|---|---|---|---|---|---|---|
| FRESH5 021310 (ZAP_DEAD) | 1765 / 1765 | 1765 | yes: add Zap R1984 (12922, 17231) | 18 / 14 | 173 + <= 19 | 94 s |
| FRESH4 151109 (SPELL_KING) | 3031 / 3031 | 3031 | yes: joint Log, Snowball -> 924 | 12 / 1 | 107 + <= 8 | 65 s |
| FRESH6 031310 (SAMETICK_GEN) | 2142 / 2142 | 2142 | yes: swap MegaKnight <-> Knight @3931 | 25 / 1 | 53 + <= 6 | 48 s |
| FRESH4 235834 (TOWER_ZAP + TZ_REACH) | 2271 / 2271 | 2271 | yes: add Zap R4611 (14500, 25500) | 19 / 7 | 72 + <= 10 | 67 s |
| FRESH4 220244 (OWN_BODYPT) | 3025 / 3025 | 3025 | yes: point Knight (2499, 13500) | 1 / 1 | 194 + <= 19 | 141 s |
| FRESH4 222707 (OWN_BODYPT) | 1766 / 1766 | 1766 | yes: point Knight (1499, 10500) | 2 / 1 | 57 + <= 8 | 47 s |
| FRESH6 024716 (ZAP_DOT; section 5 called it "no hand fix": stale (c), SME.md ENG-FIX5 built ZAP_DOT, probe Zap (14480, 24740) R 1397 / 1398) | 1764 / 1764 | 1764 | yes: add Zap R1397 (14479, 24739) | 18 / 18 | 71 + <= 14 | 87 s |
| FRESH4 201103 (RASCAL_EDGE2) | 1702 / 1702 | 1702 | yes: point Rascals (9527, 31131) | 9 / 1 | 118 + <= 8 | 51 s |
| FRESH4 001856 (OWN_PENDCAST) | 1503 + 126, first 3159 (= gate) | 1629 | **no: 0 edits generated** | 0 / 0 | 33 + <= 7 | 30 s |
- (a) **8 / 9 hand-rule cases reproduced by the general search, hand edit at rank 1 every time.** The other edits in each
  final plan are shifts the gate's fitter also makes (base plan = sme_live.plan_from without the fitter).
- (a) **Gap: an elixir-only divergence generates nothing.** 001856's diff at 3159 is `S0_elixir` alone (no body), so no
  command is implicated and the press op (OWN_PENDCAST's class: an unresolved own press) never fires. Owed: implicate the
  side's ability-card plays (and their presses) from an elixir diff.
- (a) **Discrimination is weak on adds:** 14 / 18 (021310) and 18 / 18 (024716) of the legal Zap adds beat d in the
  window; the cheapest-cost tie-break picked the hand point. The full-match result confirms the pick, but precision
  (section 7 item 3) is still untested.
- (a) Fitter move set `--ops shift,point --beam 1` = F*_main counts on 021310 (1660 + 105 @1986), 024716 (623 + 1141 @1399),
  031310 (2102 + 40 @3954).
- Other open FRESH4 failures (no hand rule): 210016 1953 + 44 @2068 and 230352 379 + 1383 @914 = the gate (no edit kept;
  230352 = the owner's no-rule listing lag: no phantom fix, a). **165155 is 20 ticks WORSE than the gate (c for "RECON >=
  fitter")**: 2309 + 719 @4791 vs 2319 + 706 @4811. The gate's fitter moved the opponent Hog Rider (extracted from its
  first-seen body, (15332, 14889), on OUR half, no tower down) +500 / +500; RECON's zone rule refuses that point (and the
  extracted one), so only a drop is proposed (refused by the cycle). The real fix is to re-date a first_seen play to a
  legal tap (b, owed).
- (c) 223547 / 203126 are not failures: exact in F4_fe (3014 / 3014, 1764 / 1764); they are only the two unflagged
  opponent-elixir breaks of section 4. Not searched.
- Bug fixed in scope: `recon.victims` crashed (TypeError) on `S*_elixir` diff rows (201103, 001856); planted check, ok 36.
- Cost (a): 33-194 window runs + <= 6-19 full runs per match; wall 47-141 s per match at 3 threads = ~1-2.5x the gate's
  41-68 s at 4 threads. No snapshot fork needed at this scale.
### Restart
Pod 33903 `/workspace/smeR` (code `sme/`, data `data/fresh{4,5,6}`, runs `runs/`). Nothing of mine is running.
If /workspace is wiped: redo the recipe (steps 1-4, ~5 min). Next, in order: section 7 item 2 (planted recall), item 3
(precision on every failing record, flags off), the elixir-diff implication gap (001856), the first_seen re-dating (165155).

## 9. RECON-2: planted recall, precision, pooled exactness (10-30, evidence `results/live/recon/r2/`)
### 9.1 Planted recall (section 7 item 2; a). `recon/plant_recall.py`, pod runs `pr2_f{4,5,6}`, 6.0 min wall at 12 CPUs
Start = the 8 EXACT final plans of section 8 (rs1_f4 x4, rs1_f5, rs1_f6 x2, op2_f4 201103). One plant per type per match
(sha-seeded pick, run in [300, end - 500]), search (beam 4, all ops) from the planted plan. invisible = the planted plan
is still exact; restored = the planted command is back (drop: same card + side re-added within 2 ticks / 300 units) AND
the match exact; alt_fix = exact with a different edit. `plant_summary.txt`, rows `plant_results.jsonl`.
| plant | n | invisible | restored | alt_fix | not fixed | inverse edit rank 1 when listed |
|---|---|---|---|---|---|---|
| shift (another tick of the window) | 8 | 1 | 7 | 0 | 0 | 7 / 7 |
| point_opp (+-500 x) | 8 | 3 | 5 | 0 | 0 | 5 / 5 |
| swap (same-tick pair) | 5 | 4 | 1 | 0 | 0 | 1 / 1 |
| drop_troop (opponent troop) | 8 | 0 | 6 | 0 | 2 | 6 / 6 |
| drop_zap (spell on board <= 2 ticks) | 4 | 0 | 3 | 0 | 1 | 3 / 3 (one at R -1, 40 units: still exact) |
| drop_spell (Log, Fireball, Snowball, BarbLog, GoblinBarrel, GoblinCurse) | 7 | 0 | 0 | 0 | 7 | never generated (by design) |
| point_own (+700 x) | 8 | 3 | 1 | 4 | 0 | 1 / 1 |
- (a) **Inside the move set: 22 / 25 visible plants restored, all exact, the inverse edit rank 1 in the first round each
  time; 0 plants "fixed" by a different edit.** The 3 misses generate the inverse but nothing beats d by HEAL:
  235834 Zap R662 (8900, 21500) on our X-Bow: victim centroid +-500 grid misses the truth by >= 510 units (34 legal,
  0 better); 220244 Bats R5238 (5 reader-only Bats; 44 legal, 0 better); 024716 Barbarians R468. Cause of the 3 (b).
- (a) Outside the move set by design: a dropped VISIBLE spell is never re-added (the visible rule admits only spells on
  the board <= 2 ticks; add (b) adds bodies only): 0 / 7. A missed visible spell is a reader failure the extractor has
  not shown so far (b); an add (c) "spell the reader saw but no play explains" is owed only if a census finds one.
- (a) Own point: 4 / 5 are fixed with the first-listed BODY point, 1-32 units from the planted tap (7499 vs 7500, ...):
  equivalent placements, exact. Own taps are not on the +-500 grid by design.
- (a) **Bug found and fixed in scope (43f23fe):** `sme_live.base_run` turns the press of a refused play into a skip IN
  PLACE; recon_search's children inherited it, so a drop that broke the opponent's cycle (hero play refused) and was
  re-added still ran without the hero press. `recon_search.full_run` retries such presses. Red -> green: 031310
  drop_troop / drop_zap first div 3624 -> exact, 222707 drop_troop 3391 -> exact; every other plant identical
  (`plant_summary_prefix.txt` = the run before the fix).

### 9.2 Precision on the failing records, flags OFF (section 7 item 3; a). Pod run `r2_fail` (37 records, ~15 min at 12 CPUs)
Inputs = the CURRENT extractor with none of the 20 fresh_prep SME_* flags (regen_fresh.sh's v29 set only; `recon/r2_regen.sh`),
on the 37 strict-fresh records of FRESH2-8 that are not strictly exact (29 with div frames + 8 torn-only). Reference =
the strict fresh results (F2_fe .. F8_main). Table `prec_vs_strict.txt`, rows `r2_recon_base_results.jsonl.gz`, ablation
`ablate_fail.jsonl` (`recon/ablate.py`: remove each kept add from the final plan, re-score the whole match).
- (a) **vs strict: 10 made exact, 1 improved, 23 same, 3 worse.** Made exact: 110715 (own X-Bow point (1500, 19500), the
  open FRESH2 "X-Bow 1 tile off" failure: no hand rule), 142334 (add own IceWizard R1691), 151109, 201103, 220244, 222707,
  235834, 021310, 080149 (add Zap R514 = SME_ZD_SINGLE's fix, 184 + 1582 -> 1766 / 1766), 004719 (no input edit: the gate's
  SME_BANNER_GIVEN, so not a RECON win). Improved: 024716 (623 -> 1326 exact, first 1399 -> 2805).
- (a) **Kept adds: 5, and the full-match ablation says all 5 are needed** (without each: 021310 1660 + 105, 024716 /
  235834 / 142334 / 080149 likewise back to the failing count). **0 phantom adds kept.** No add / drop was kept on a
  record the search did not improve. So no tightening of the add scoring was needed on this set (the HEAL 20 rule +
  the full-match ranking already reject them). Kept POINT edits without a gain: 063025 Rascals, 074143 BattleRam
  (counts = the reference; their need is untested, b).
- (a) **The 3 worse are hand rules RECON does not cover yet** (diff of flags-off vs frozen inputs, `.foreman/scratch/recon2/diffm.py`):
  031310: the v29 extractor adds a phantom opponent Zap at 3680 (15000, 24568) that one of the 20 flags removes; it breaks
  the cycle fit (flag opp_no_fitting_deal), crforge runs a wrong deal, first div 246 (48 exact vs 2102). RECON's drop
  only targets plays implicated at d. Owed: a cycle-repair edit (when a side fails the cycle at base, propose dropping /
  re-dating the play whose removal restores the fit). 075729: own Knight at the tap (2500, 14500) vs the hand rule's
  (8499, 500) (OWN_SPAWN / OWN_BODYPT); the own-point op looks for a body only within 3000 units (1378 vs 1460 exact).
  165155: the zone rule (section 8; 2309 vs 2319). And 024716's remaining gap (2805): the hero Tombstone press at 3056
  vs TOMB_HERO's 2803, outside the ability's window, so shift never proposes it. Owed: re-date an ability outside its window.
- (a) 083923: 1814 + 39 torn_hidden + 2 div (first 935) vs the reference 1814 + 41 torn_hidden: 2 frames move torn -> div
  on the flags-off input (strict class unchanged: both fail strict; "exact apart from torn" lost). Cause untested (b).
### 9.2b Two more generator gaps found on the records the hand rules fix (a; generator v2, 39 planted checks)
Baseline r2_* runs use the generator before this change; v2 runs are `r2v2_*` in `/workspace/smeR2`.
- (c for "RECON's point op includes the fitter's"): the fitter also moves OPPONENT SPELL points on the +-500 grid; RECON's point op
  skipped spells. 172955 (strict exact): gate cmd 4 Zap (3475, 8700) -> (2975, 9200), first div 313 -> 938; RECON base run
  stays 1093 + 1352 @313, 8 legal, 0 better. Fixed: the grid now covers opponent spells (fitter parity; planted check).
- (a) **Press re-date, new edit (`repress`, a shift of an ability command):** 4 flags-off losses of the same class as
  SME_TOMB_HERO: 165724 (press 547 vs extracted 940), 170122 (2122 vs 2630), 175120 (2446 vs 2770), 024716 (2803 vs 3056).
  The hero Tombstone press has no cast state, so the extractor dates it at the next cast it sees, 253-508 ticks late;
  the diff names `Tombstone` at d = press + 2. `recon.hypotheses`: an ability command with run in (d, d + REDATE = 600] whose play's
  card is named by the diff is tried at R in [d - 4, d - 1]. Engine result: section 9.3.
### 9.3 Pooled exactness (RECON baseline; the comparison with the hand-rule gate is section 10)
- (a) RECON baseline (generator before v2, flags off, lib 5e8089a4, ASSIGN on, 151 scored strict-fresh matches):
  **123 / 151 pass apart from torn, 116 strict**; 3 records the flags-off extractor flags (155249, 000242 own_cycle_fail,
  031310 opp_no_fitting_deal) count as not passing. Rows `r2_recon_base_results.jsonl.gz`.
- Reference only, NOT a fair comparison: strict fresh 122 / 151 was scored on frozen inputs with the flags of its day and before
  SME_BANNER_GIVEN, so it is not the hand-rule pipeline of today (004719 exact in RECON is that gate fix, not RECON).
- (b) untested: the fair number = r2_gate (all 20 flags, same extractor + lib); v2 should recover 172955 + the TOMB_HERO class.
- ASSIGN off / guard: not run yet (r2_gate_a0, r2_recon_a0, r2v2_a0 queued; the guard needs cls_ticks, which recon results lack).


## 10. RECON-3: hand-rule gate vs RECON on the same inputs and lib (10-30, evidence `results/live/recon/r3/`; a unless marked)
Setup as section 9: the 151 scored strict-fresh FRESH2-8 matches, one lib (5e8089a4 tickprobe), one env (`recon/runR.sh`), ASSIGN on.
Gate = `sme_live.py all` on the flags-ON re-extraction (`data/r2/on_all.jsonl`, 20 fresh_prep flags); RECON = `recon_search.py` on the
flags-OFF re-extraction (v29 extractor only). v1 = r2_fail + r2_rest (generator before v2); v2 = r2v2_a (the 33 records v1 left not strictly
exact) + r2v2_b (the other 118; no exact match lost). Tool: `python3 recon/r3_report.py GATE V1a,V1b V2a,V2b [GATE_A0 RC_A0 V2_A0]`
(output `r3_report.txt`). Class as r2_tally: pass = strictly exact or exact apart from torn; a match the extractor flags counts as not passing.
### 10.1 Pooled (one-sided 95% Clopper-Pearson lower bounds)
| pipeline | pass apart from torn | strict |
|---|---:|---:|
| hand-rule gate (flags on) | **142 / 151 = 0.940 (low 0.898)** | 132 (0.874, low 0.821) |
| RECON v1 (flags off) | 123 (0.815, low 0.755) | 116 (0.768, low 0.705) |
| RECON v2 (flags off) | 126 (0.834, low 0.777) | 119 (0.788, low 0.726) |
| reference: strict fresh, frozen inputs of each scoring day | 122 (0.808, low 0.748) | 122 |
Unflagged only (3 records the flags-off extractor flags: 155249, 000242, 031310): v2 126 / 148 (0.851), strict 119 / 148 (0.804). Paired exact
sign tests (matches passing in only one pipeline): gate vs v2 **16 : 0** (p < 0.0001; strict 13 : 0, p = 0.0002), gate vs v1 19 : 0, v1 vs v2 0 : 3 (p = 0.25).
- (a) **The 142 / 151 is in-sample.** Every one of the 20 flags was written after tracing a failure on FRESH2-8 or dev, so 142 vs the
  reference 122 measures how many failures the rules were built to fix, not how well they generalise. The held-out figure for the
  hand-rule pipeline is still the frozen-day 122 / 151. FRESH9 (not frozen: it needs the Ranked battles after FRESH8's last log 082745
  on 10-29) is the only fair test of gate vs RECON. RECON is partly in-sample too (the 8 cases of section 8 shaped its operators), far less.
- (c) "RECON >= the hand rules on the same inputs" is contradicted: 126 vs 142 (16 : 0). Its gain over the 122 reference is 4 matches.
### 10.2 Recall, precision, ASSIGN guard, v2 vs v1
- Planted recall (section 9.1, unchanged): 22 / 25 visible plants restored inside the move set, inverse edit rank 1, 0 wrong fixes; 0 / 7 outside it (a dropped visible spell).
- Precision: v1 kept 5 adds on the failing records, ablation 5 / 5 needed (9.2). v2 keeps 7 adds on the 151 (Zap: 024716, 235834, 021310, 080149; IceWizard: 142334,
  155249, 000242) and 23 structural edits on 22 records. Ablation of the two new ones (`ice_ablate.jsonl`, this worker): IceWizard R5464 (155249) and R4996 (000242)
  **needed**; 024716's Zap R1397 needed (`v2a_ablate.jsonl`). **7 / 7 needed, 0 phantom adds.** No add or drop kept on a record the search did not fix.
- v2 vs v1: **+3, 0 lost** (172955 2630 / 2630, 023843 1765 / 1765, 044249 1766 / 1766: all from the opponent-spell +-500 grid = fitter parity). The repress
  edit fixed 0 of its 4 targets (10.3). No record gets worse from v1 to v2.
- ASSIGN guard, **gate, per frame (`f1fix/assign_guard.py`, the 5 reader-hidden records, SME_CLS_TICKS): PASS**: 0 OFF-exact frames lost, frame counts equal, no class worse.
  210016 improves 28 div + 16 torn_hidden -> 44 torn_hidden (class 0 -> 1); 083923, 173440, 042050, 062715 identical (`assign_guard_gate.txt`).
  RECON on the same 5: counts and class identical ASSIGN off vs on in v1 and v2 (210016 stays 44 div both ways: the flags-off input names the hidden body Golem,
  not Golemite, so ASSIGN has no window to use). A per-frame check on RECON was NOT done: recon results carry no cls_ticks (b: a small addition to recon_search).
### 10.3 Why the 16 gate-only matches fail in RECON v2 (a: flags-on vs flags-off input diff `recon/r3_onoff.py`, the v2 search logs)
| gap in the generator's hypothesis space | matches | what the hand rule did | why the search does not find it |
|---|---|---|---|
| hero Tombstone press | 100341, 145600, 165724, 170122, 175120, 024716 (6) | TOMB_HERO: ability dated to the swap, `unit_index` 2 | repress shifts the cast_seen ability but keeps its unit `cmdN_0` (the extractor writes no unit_index; the hand rule hard-codes TOMB_UNIT = 2, mech_rules.py:719): 165724 round 0 = 4 legal shifts, 0 better. **Diagnostic (a): the same flags-off records with only `unit_index` 2 added (`recon/r3_unit_test.py`): repress then makes 100341, 145600, 170122, 175120 and 024716 (with its Zap add) strictly exact (`unit2_results.jsonl`, ~5 min at 6 CPUs). 165724 reaches 1959 + 219 div, first 4079: its 3rd press (extracted 4481, true 4077) is bound to the later Tombstone play (4333), so the range R >= 4334 > d is empty; it needs a re-bind to the earlier play** |
| own point far from the tap | 141254 (3,162 units), 142926 (7,615) (+ 075729, a gate failure too, 11.6 tiles) | OWN_SPAWN / BODYPT: the first listed body | the own-point op looks for a body only within 3000 units (9.2) |
| phantom play the diff does not name | 130148 (2 opponent Zaps; the diff is a tower hp row), 031310 (a Zap at 3680 breaks the opponent cycle: opp_fitting_deals 0 -> 6144 without it) | ZAP_CHAIN1 / removal | drop is limited to plays implicated by the names in the diff; a tower row names no card; there is no cycle-repair edit |
| unseen press found from a victim | 091720 (Boss Bandit press, BB_RISE) | adds an ability from "rise without buff" | press needs the pressing card implicated by the diff; the diff names our Knight (the victim) |
| elixir-only diff / ability drop | 001856 (own press at 3157 never resolved), 230352 (two false gk_dash casts) | OWN_PENDCAST, GK_WALK drop them | an elixir-only diff implicates nothing; drop covers plays only |
| child of a living same-card body | 101018 (second Goblinstein) | NEAR_BIGGER2 | add (b) skips a card some near command already plays |
| reader-hidden annotation, not an input edit | 210016 (window named Golem, Golemite with HIDDEN_CHILD), 083923 | HIDDEN_CHILD | 210016: a comparator-side name for a body the reader dropped. 083923: reader_hidden and plays identical flags off vs on; 2 frames (935, 951) are div in RECON and torn_hidden in the gate after the same-looking round-2 shift (gate new_first 3131, RECON 935): a scoring-path difference, cause untested (b) |
(a) None of the 16 needs an engine change: with the hand rule's input the gate is strictly exact (or exact apart from torn) on all 16.
### 10.4 First divergence of every match not passing in v2 (23 failures + the 2 flagged-exact)
obs = our extraction / observation (a: an input change makes the gate exact, or SME.md traced it); eng? = engine or body position, untraced (b).
| match | gate | v2 (first div) | first diff row | class and trace |
|---|---|---|---|---|
| 083923 | pass 1814 + 41 torn | 1814 + 39 torn + 2 div (935) | MiniPekkaHero SIM-only in a hidden window | obs, scoring-path gap (b) |
| 091720 | strict | 2860 + 170 (3519) | our Knight_EV1 vs Knight hp | obs: unseen Boss Bandit press (a) |
| 100341, 145600, 165724, 170122, 175120 | strict | exact 1384 / 579 / 197 / 986 / 1147 (2930, 1308, 549, 2124, 2448) | Tombstone rows (the SIM keeps the passive monster) | obs: press dated late, no unit_index (a; diagnostic 10.3) |
| 024716 | strict | 1326 + 438 (2805) | Tombstone rows | obs: same class, press 3056 vs 2803 (a) |
| 101018 | strict | 2905 + 121 (5968) | Goblinstein reader-only | obs: child test dropped a real second play (a) |
| 123045 | fail 809 + 1726 (1768) | same | Witch skeletons / Golden Knight 2-60 units off | **eng? (b)**: Witch pushes on a dashing GK (SME.md), untraced |
| 130148 | strict | 1626 + 141 (3404) | tower hp 77 | obs: 2 phantom Zaps (a) |
| 141254 | pass (8 torn_late) | 1442 + 1586 (3044) | Hog / Firecracker / BarbLog reader-only | obs: own Knight tap 3 tiles off (a) |
| 142926 | fail 2038 + 8 div (581) | 56 + 1701 (254) | BlowdartGoblin 258, Knight 7,615 off | obs: own tap point (a); the gate's remainder = client lag, own Skeletons 10 ticks early (b) |
| 165155 | fail 2319 + 706 (4811) | 2309 + 719 (4791) | Hog Rider SIM-only | obs: reader double-labelled tick 4811 (a, lead: no scoring change) + the zone rule refuses the fitter's Hog move (20 ticks worse than the gate) |
| 210016 | pass 1953 + 44 torn_hidden | 1953 + 44 div (2068) | Golemite SIM-only | obs: the reader dropped a Golemite, window named Golem (a) |
| 230352 | fail 1429 + 710 (3002) | 379 + 1383 (914) | Golden Knight 118 / 124 off | obs: false dash cast (a); the gate's remainder = reader listing lag 7 ticks (a, owner: no comparator rule) |
| 001856 | strict | 1503 + 126 (3159) | own elixir only | obs: unresolved own press (a) |
| 031310 | strict (v2 flagged opp_no_fitting_deal) | 48 + 1716 (246) | Archer reader-only | obs: phantom Zap breaks the cycle (a) |
| 063025 | fail 188 + 1577 (153) | same | SuspiciousBush reader-only | obs: bush play missed, goblins taken for it (a; extractor fix owed, fails in both) |
| 071306 | fail 2799 + 233 (5473) | same | our Skeletons SIM-only, DarkMagicAOE, elixir | untraced (b) |
| 073232 | fail 2037 + 3 div (3312) | same | opponent Knight 33 / 49 units off | **eng? (b)**: body position, untraced |
| 074143 | fail 1680 + 83 (1572) | same | evolved Witch SIM-only at (9500, 31000) | **eng? (b)**: back-edge spawn, untraced |
| 075729 | fail 1460 + 251 (2917) | 1378 + 333 (2917) | Skeletons 10,700 units off | obs: own placement 11.6 tiles from the tap (a); BODYPT3 on the gate: 1556 + 155 (3272) |
| 155249, 000242 | strict | exact, flagged own_cycle_fail | - | not a divergence: RECON's `add IceWizard` restores the missed own play (ablation: needed); the extractor's flag stays. Un-flagging a record whose final plan passes the cycle rule is the lead's call (+2 pass if allowed) |
(a) 18 of the 23 sit in the observation layer with a gate fix or a traced cause, 1 (083923) is observation with an unexplained scoring path (b), and
**4 are untraced (b): 123045, 073232, 074143 are body-position / movement suspects (engine or reader), 071306 is untraced.** 3 to 4 of 23 matches the earlier ~1 in 25 engine count;
none of the 4 is among the 16 where RECON trails the gate.
### 10.5 Proposed next round (b until run; the lead decides; nothing started)
1. **Press unit and re-bind (generator only, ~1 h with planted checks, then a 6-match rerun of ~5 min at 6 CPUs).** Make the unit an edit dimension (try the unit indices
   the card has, instead of the extractor's 0 and the hand rule's hard-coded 2) and let repress re-bind the ability to an earlier play of the same card and side.
   Expected: +6 pass and +6 strict on the 6 Tombstone matches (5 measured with the patched input, a) -> v2 = 132 / 151 (low 0.821), strict 125 (low 0.769).
2. **Own point without the 3000-unit cap:** candidates = every body of the card first listed in the play's window, zone rule kept; 141254, 142926, 075729; expected +1 to +2 pass.
3. **Drop beyond the diff's names + cycle repair:** for a diff naming no card (tower hp row, elixir-only, a base plan that fails the cycle) propose dropping each opponent play
   / ability in [d - WIN, d], when the base cycle fails each play whose removal restores a fitting deal, and let drop cover ability casts: 130148, 031310, 001856 (+3);
   230352 moves its first div 914 -> 3002 but still fails.
4. **Press from the victim's attacker** (091720) and **add (b) next to a living same-card body** (101018): +2.
   Steps 1-4 together (b): about 139 / 151, within ~3 matches of the gate's 142; the rest is the reader-hidden annotation (210016, 083923), an observation record, not a search
   edit: keep HIDDEN_CHILD as an extractor annotation (lead call).
5. **The decisive measurement: FRESH9, held out.** Freeze the Ranked battles after 082745 on 10-29 (>= ~20 needed; live play is off, so the pool is what exists; count not checked), run the
   20-flag gate and RECON (steps 1-4 frozen BEFORE the run) on the same inputs, ASSIGN off and on + guard. Cost: laptop extraction (the 196-record regen took 27 min at 2 workers,
   so ~5-10 min for ~25) + ~10 min per pipeline on 12 CPUs. Without it every "RECON reaches parity" claim is in-sample, exactly like the hand rules' 142.
6. Smaller owed: `cls_ticks` in recon results (per-frame ASSIGN guard on RECON); the 083923 scoring-path gap (feed the gate's round-2 plan through RECON's scoring); re-date a
   first_seen play to a legal tap (165155).
Restart for this section: `python3 recon/r3_report.py` on the pod files (`/workspace/smeR/runs/{r2_gate,r2_fail,r2_rest,r2_gate_a0,r2_recon_a0}`, `/workspace/smeR2/runs/{r2v2_a,r2v2_b,r2v2_a0}`;
laptop copies `.foreman/scratch/recon3/in/`). Diagnostic: `recon/r3_unit_test.py` builds the patched inputs; run `R=/workspace/smeR2 CPUS=226-231 WORKERS=2 SME_THREADS=3 bash sme/recon/runR.sh
r3_unit2 recon <ABSOLUTE inputs path> /workspace/smeR/data/allframes` (runR cds, so a relative path fails).

## 11. RECON-4: FRESH9 held-out freeze, then generator v3 (10-30)
### 11.1 FRESH9 freeze (pre-registration: committed BEFORE any generator change and before any FRESH9 run)
- List `fresh/FRESH9.tsv` (sha256 88059ea537fbc7600bd5bd288bde53067e4b7570dd87c2446073e63dc8c779e8): 317 Ranked (pathOfLegend) battles of the main account,
  each paired with its live log by extract.batch's rule; cut = live log starts at or after 2026-10-29 08:28 EDT (FRESH8's last log is 082745); first log
  `live_play_20261029_083215`, last `live_play_20261030_103320` (battle 2026-10-30T14:36:43Z = 10:36 EDT, when live stopped). Build 160635001 for all 317.
  The hand-run logs of 10-30 10:43 / 10:56 are not in the list (no battle-log entry; not frozen). Created with `freeze.py 20261029_0828` at repo HEAD bf92222.
- Pipelines frozen against it: the 20-flag gate (fresh_prep.sh flags + SME_ZD_SINGLE) as of bf92222, and RECON v3 = generator v2 (bf92222) plus the operators
  of 11.2, whose code is committed before FRESH9 is run. No FRESH9 number may change a rule; a FRESH9 failure is reported, not fixed, in this round.
- Scored set = the RNG-free subset (as FRESH2-8); both re-extractions (flags on for the gate, flags off for RECON) from the same raw logs.
### 11.2 Generator v3 (code frozen at this commit, BEFORE any FRESH9 run; FRESH9 inputs extracted but not scored)
- FRESH9 extraction (laptop, 2 workers, `recon/r4_prep.sh`): 317 battles -> 179 RNG-free records (scored set), flags-on inputs sha256[:16] 0d0aeb6a03357912
  (`inputs_rngfree.jsonl`), flags-off inputs dcfe2ef45b32f144 (`inputs_all.jsonl` of the same 179), frames 177 files. Files in git-ignored `.foreman/scratch/recon4/f9/`.
- New operators in `recon.py` (all general, no per-match rule; planted checks `test_recon.py::t_r4`, `ok 56`): `repress` (re-date a late press, re-bind it to one of the
  latest 2 earlier plays of its card, unit index chosen from 0/1/2 by the engine); press add with the unit dimension, also for the other side's ability cards alive at d when
  the SIM landed a hit the game did not (`overhit`); own point from bodies NEW at the play's run (`born_points`, window -2..+24 ticks, formation clusters, no distance cap);
  drop of any opponent play or any ability press near d (names only rank), plus cycle repair (each opponent play whose removal restores a fitting deal); add (b) no longer
  blocked by a living same-card body (only a play running at the body's birth blocks it) and also anchored at the first-divergence row. `cls_ticks` is now in recon results.
- Dev check (in-sample, 16 gap matches, `v3_t16`/`v3_t3`): 13 of 16 reach the gate result (100341, 145600, 165724, 170122, 175120, 024716 Tombstone; 130148, 031310, 001856
  drops; 142926 = gate; 101018 add; 075729 1711/1711, better than the gate's 1460); still failing: 083923 (scoring path), 091720, 141254.
- Owner 10-30: the two flagged-exact records 155249, 000242 are COUNTED for RECON from now on; reports give both counts. The gate numbers are unchanged.
### 11.3 RECON-4 results and gaps (dev = in-sample; evidence `results/live/recon/r4/`)
- Dev 151, `dev_report_gate_v2_v3.txt`: gate 142 / 132; v2 126 / 119 (128 / 121 with the 2 counted); v3 136 / 129 (138 / 131 with the 2 counted; unflagged-only v3 = same 138 minus nothing).
  v3 gains over v2 (+10): the 6 Tombstone-hero matches, 130148, 001856, 101018, 075729 (1711 / 1711, the gate itself fails it), 142926 = gate, 031310 exact but still FLAGGED
  (opp_no_fitting_deal from the extractor; the drop repaired it) -- counted as not passing. Lost v2 -> v3: none; errors: none.
- Still failing on dev (v3): 083923 (2 frames scoring path, b), 091720 (overhit press added but no variant beats d; b: untested why), 141254 (the body is listed 13 ticks after the run:
  the Knight point edit is right but the search objective counts the torn_late frames as div, so no variant "beats d"; fix = score torn_late in the objective or accept a point edit on the
  full-run result), 210016 (HIDDEN_CHILD annotation, not an edit), 230352, 165155, 063025, 071306, 073232, 074143, 123045 (traced / untraced as section 10.4).
- FRESH9 gate (held out for the gate: its rules were frozen at bf92222): 122 / 177 pass, 117 strict, 35 flagged (27 opp_no_fitting_deal, 8 own_cycle_fail). The flagged 35 are
  exactly the class RECON's cycle repair / HIDDEN_GEN-type add targets; whether v3 passes them is the first thing to read when f9_v3 finishes.


## 12. RECON-5: counted flagged-exact records, then the opponent play sequence (10-30 / 10-31)
### 12.1 Step 1: ablation of every kept edit on the 8 flagged-but-exact FRESH9 records (a; `recon/ablate_edits.py`, 1 min on the pod)
Each kept edit of the v3 final plan (`runs/f9_v3/<m>/recon_plan.json`) is reverted ALONE (add -> removed, drop -> re-inserted, add + drop of one card within 60 ticks = one `replace`,
point / shift / repress -> the base value) and the whole match is re-scored by the unchanged comparator. needed = (exact frames, first div) gets worse.
| record | flag | kept structural edits | verdicts |
|---|---|---|---|
| 012313 | own_cycle_fail | add own Knight R3131 | needed |
| 014530 | own_cycle_fail | add own Tesla R4968 | needed |
| 024332 | opp_no_fitting_deal | add opp Zap R2902 (+ a drop / re-add of one Assassin at the same tick and point = a no-op on the commands, the deal is refitted) | needed (the no-op is not an edit) |
| 030902 | own_cycle_fail | add own IceWizard R4664 | needed |
| 040421 | opp_no_fitting_deal | add opp Zap R4176; replace Zap R3646 (2500,13500) -> R3644 (2000,13000) | both needed |
| 053225 | own_cycle_fail | add own IceWizard R2804; points of two opponent Zaps | all needed |
| 091421 | own_cycle_fail | add own Knight R5801 | needed |
| 102101 | own_cycle_fail | add own IceWizard R4526 | needed |
All the +-1 tick shifts of Log / BarbLog / Rocket (the extractor window, as in the gate) are needed too. 0 unneeded, 0 harmful, 0 errors. Counted (owner 10-30 rule):
FRESH9 v3 **128 pass / 125 strict of 177** (as extracted 120 / 117); `r4_report` output `results/live/recon/r5/f9_report_counted.txt`. Paired vs the gate (122 / 117, as extracted):
pass only-gate 3 / only-v3 9 (p .146), strict 1 / 9 (p .022) -- the gate is not credited with its own flagged-exact records, so this is the report format, not a like-for-like test.

### 12.2 Step 2 premise check: is the battle-log deck missing from the extractor? (c, contradicted)
- The ticket assumed the opponent's deck / levels / evo and hero forms from the official battle log were not yet used. They are: `extract.side_info` builds `sides[s]` from the paired battle-log entry
  (`deck` in API slot order, `api_ids`, `levels` = API level + 16 - maxLevel, `slot_flags` = API evolutionLevel 1 / 2, `word`), and `sme_live.plan_from` puts exactly that into `plan['decks']` / `slots` / `levels`. All 179 FRESH9 and all
  196 FRESH2-8 RNG-free records carry it (`derived` = the live-log-only deck is only the fallback when no battle-log entry exists). `recon_search`'s add (b) already draws unseen plays only from `plan['decks'][side]`.
- Replays (b of the ticket): `icebow/data/replay_rec/` holds two recordings only (`rec_20261008_210824`, `rec_20261026_130926`, the 10-26 device check); none is a FRESH9 / FRESH10 match. Harvesting one needs the MuMu device
  (`replay_rec/recorder.py --device`, Battle Log -> Watch), which live play occupies, so no deal-order data exists for any held-out match tonight. Not needed for the mechanism below: crforge's result does not depend on WHICH
  fitting deal the opponent has (a play is legal or refused), only on the play sequence fitting one.
### 12.3 What is actually wrong with the opponent_no_fitting_deal class (a; `.foreman/scratch/recon5/cyc*.py`, `recon/cyc.py`)
1. **Selection effect in the dev set.** FRESH2-8 hold 196 RNG-free records; the 151 "strict fresh" scored ones are the extractor-UNFLAGGED ones. 41 of the 196 (21%) have an opponent play sequence that fits no 4-card-cycle deal;
   only 1 of them (031310) is among the 151. FRESH9 keeps the flagged records (28 of 177 = 16% opponent no-fit by the cycle census, 27 flagged by the gate's extractor, plus 8 own), the gate passes 0 / 35 of them. So the dev 142 / 151 vs held-out 122 / 177 gap is mostly the excluded class.
2. **The identity deal.** For every non-fitting opponent `opp_deal_fit` is None and `recon.base_plan` / the gate hand crforge the deal [0..7]. crforge refuses the opponent's first play whose card is not in that hand: first divergence
   at tick 169-526 in 14 / 27 FRESH9 records although the cycle first fails at tick 1,000-5,900 (130404: first div 249, the cycle fails at play 53 of 56, tick 5,591). So most of the 1,100-2,800 diverging frames are an artefact of the deal.
3. **What fails the cycle.** 28 FRESH9 records (v3's flags-off extraction) have a non-fitting opponent sequence. Per record (`cyc.repairs`, any deck card, insertions only): 12 need ONE unseen play (4-13 optimal repairs each), 16 need 2-8 or
   no insertion-only repair (3 decks hold a Mirror, whose play reads as the mirrored card; repeated Heal / Elixir Collector readings). With insertions limited to spells, plus invented plays dropped, plus the Mirror reading, every one of the 28 has a repair
   (25 of cost <= 3, 16 of cost 1; `f9_cycle_census.json`, columns ins / spell / drop / ins+drop / spell+drop / spell+drop+mir).
### 12.4 Our own taps restore our missed plays (a; `recon/r5_taps.py`, real functions, 375 records FRESH2-9)
All 20 own_cycle_fail records have EXACTLY ONE own tap that no extracted own play explains (`recon.unmatched_taps`: same card within 120 ticks of tap + own_delay), and restoring it (point = the tap's point on 12,543 / 12,543 matched own plays,
run = tap + own_delay, window -2..+3) makes our known deal fit on 20 / 20. 355 cycle-clean records: 2 have an unmatched tap (142334: the engine accepted the add in RECON-2; 010059 untested). The missed cards are Skeletons / IceWizard / Knight / Tesla.
v3's add (b) restores it only where a body is listed (FRESH9: 6 of 11 own failures).
### 12.5 The mechanism and its planted checks (code `recon/cyc.py`, `recon.py` RECON-5 section, `recon_search.py` RECON_CYC=1; absent = v3 byte-identical)
- `cyc.solve / repairs`: the state after any play prefix is one of 70 x 24 = 1680 (hand set, queue order); shortest path with the observed plays (must be in hand), unseen plays of a hand card (cost 1),
  an observed play dropped (cost 1), an observed play read as the Mirror (cost 1). All optimal repairs are enumerated. `best_prefix_deal`: the deal that lets the most plays run (replaces the identity deal).
- `recon.cycle_repairs`: opponent side only, unseen plays restricted to SPELL cards (a reader can miss a spell; a troop leaves bodies), placed mid-gap at a grid point that touches nothing (>= radius + 1000 from every listed body / tower / projectile /
  area), elixir bank rule enforced, cycle re-checked, deck conflicts refused. `recon_search`: the base plan (best-prefix deal, own taps restored when they fit our cycle) plus up to 24 repairs are all scored by the engine; the top B start the unchanged beam search.
- Planted checks: `test_recon.py` ok 80 (24 new: best-prefix deal, planted deleted Zap restored in its gap, fits-after, ghost point clear, fitting side untouched, wrong deck refused, bank rule, own taps).
  `r5_planted.py` on real sequences (151 dev + 179 FRESH9, `results/live/recon/r5/planted_dev151_f9.txt`): 2,096 plants (each SPELL play of a fitting sequence deleted in turn); 696 (33%) invisible (still fits); of the 1,400 detected
  all 1,400 have the true (position, card) among the optimal repairs (completeness, by construction), median 3 optimal repairs, p90 7, max 12, unique 196 (14%): the cycle narrows an invisible spell to a handful, it does not identify it.
  Wrong deck: 0 / 330 real records have an observed play outside the battle-log deck; a deck with one played card swapped out is flagged on 330 / 330.
