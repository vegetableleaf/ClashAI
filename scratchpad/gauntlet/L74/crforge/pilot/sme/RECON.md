# RECON: one general reconstruction instead of the SME_* hand rules (ENGINE-RECON, 2026-10-30)

Code: `sme/recon/` (`recon.py` rules + hypothesis generator, `test_recon.py` planted checks, `offline.py` the hand-rule
cases, `field_census.py` the rules on every frozen fresh input, `recon_search.py` the engine-scored search for a pod).
Evidence: `results/live/recon/`. Labels: (a) measured, (b) plausible but untested, (c) contradicted.

## STATUS (keep current)
- **RECON-8 (10-31 ~12:45 EDT, section 15) -- DONE, nothing of mine is running; NO engine change.** The ticket's premise (crforge's Golden Knight dash differs from the live game: length / target / speed) is CONTRADICTED (c). Every Golden Knight first divergence traced (FRESH9 174855 and 220240, FRESH10 134929, FRESH12 080315, dev 230352) is a wrong or missing PRESS in the plan, and in each the SIM reproduces every REC frame of the dash as soon as the press is right (a): 174855 = a Tornado pull (250 / tick) read as a dash (press dropped: whole record 1,742 / 1,742 frames exact); 230352 = a Rage-boosted walk (Manhattan 109 / tick) read as a dash (drop: 15 / 15 GK frames); 134929 = the live press was made while the GK was frozen (any press in 1664-1670 gives the same SIM; the extracted window 1671-1673 excludes it): whole record 1,887 / 1,887 exact with the press at 1668; 220240 and 080315 (FRESH12, clean held-out) = a REAL dash with NO press, hidden by `sme_live.gk_dashes`' one-cast-per-100-ticks gate after an earlier burst (press added: 35 / 35 and 31 / 31 GK frames exact; first divergence 3827 -> 4586 -> 4747 and 2854 -> 3595 -> 3927, the later ones being further presses one tick off inside their own extracted window, then a Log one step off). Scan of all 26 GK records I hold (99 presses; FRESH9-12, dev49, 8 of FRESH2-8): 18 of 26 records have no first divergence at all (every dash exact); 77 of 92 presses with frames exact as extracted, 5 fixed by a shift, 2 by a drop, 7 behind an earlier divergence, 1 open (confounded). Passing GK dashes: 398 / tick in REC and SIM; RECON-7's "REC 240-250 / tick" was 174855's Tornado pull. Size of the class: 4 failing GK records of the 406 FRESH9-12 + dev49 records; a perfect GK press fix makes 2 of them fully exact (174855, 134929): at most +0.5 pp. **FRESH13 frozen first (commit 76dbe5f: 43 Ranked battles after FRESH12, list sha 30f9a772) and NOT extracted or run** (no engine key to test; the pod disk is full, 204 MB free). Stop-and-report per the ticket: the next step (b) in 15.4 is generator / extractor work and needs the lead's decision. Tools `recon/r8_gk.py`, `r8_press.py`, `r8_scan.py`, `r8_scan_table.py`; evidence `results/live/recon/r8/`. Codex dispatches: none. **Pod 33903's disk (overlay 120 GB) is 100% full (not caused by RECON-8 alone; my SIM work dirs briefly took the last 200 MB until I moved them to /dev/shm), see 15.5.**
- **RECON-7 (10-31 ~11:15 EDT, section 14) -- DONE, nothing of mine is running.** (1) Position-only class (24 of 82 after RECON-5): NO spawn / first-listing offset (c: first diff 3-521 ticks after spawn, median 61, mixed sign); a mixture. Its largest homogeneous part, the 6 hero Barbarian Barrel records, is an unmodelled hero re-roll press the harness could not name + the generator's presser rule: `RECON_LATE=1` (SmeRun `late_unit` by object id) makes 5 of 6 dev records exact; `RECON_ROUNDS=80` fixes the 2 round-capped failures; absent keys = RECON-5 byte-identical (18 / 18). **FRESH12 (39 RNG-free, list sha 5edf783d frozen at c77355b before extraction, code 54c5ec6), counted pass / strict: gate 29 / 29, v3 28 / 28, RECON-5 33 / 32, RECON-7 34 / 33 (CP low .749 / .719); RECON-7 adds 044738 (hero BarbLog, 5 presses, ablation all needed); paired RECON-7 vs RECON-5 0 : 1; pooled clean FRESH11 + 12 (n 88) RECON-7 73 / 71 (.830 / .807, CP low .750 / .724).** (2) Pace (14.3): CLXIII's SIM ATTEMPTS match live (11.4 vs 11.2 / min); the SIM refused 19% (elixir hold 11.6%, tap loss 4%, game_over 3%); two real mechanisms (elixir hold, post-play decision 30 vs 26 ticks) fixed as opt-in `tap_hold` / `play_resume` (commit 00ca929, ok 11, absent key identical on 48 / 48 real games) but accepted plays / min did NOT move (9.45 -> 9.41 -> 9.37, paired CIs span 0): the gap is match-length composition (live 22% overtime vs SIM 10%: 0.64 of 1.46) + per-phase rates (0.82, ot3x -17%); owed: ghost-opponent D3 block. Pod tree `/workspace/smeR6` (smeR5 + this code; nothing running). Codex dispatches: none (ticket `a2/codex/RECON7_1.md` written, not used: the pod queue was short).
- **RECON-6 (10-31 ~05:45 EDT, section 13) -- DONE, nothing of mine is running.** The ticket's premise (hero / evolution FORM mismatches, 8 of 24) is CONTRADICTED (c): crforge derives every play's form from the cycle count, the form rule explains 2,641 / 2,648 form sequences on dev + FRESH9 + FRESH10 and 400 / 400 on FRESH11 (284 / 285 on its flags-off inputs, the residual a missed own Tesla whose tap is in the form gap), clearing the opponent's hero / evo flags makes 11 of 15 'form' failures worse and none better; the 'Hero / EV1' is the unit name in a first-diff row, not a form mismatch. Built `recon/forms.py` (form-count alignment, planted checks ok 73 + 24, `RECON_FORM=1` opt-in, absent = RECON-5 byte-identical, identical rows on 18 + 12 records): it changes 1 of 465 records (001538: the same exact plan as RECON-5's cycle repair, found independently). FRESH11 (69 battles, list sha fc9d6781 frozen at 3cb6a76 before extraction, code a2e03f5, 49 scored): counted pass / strict gate 37 / 34, v3 36 / 35, RECON-5 = RECON-5 + forms **39 / 38** (CP low .678 / .656; vs gate 2 : 4 p .69, strict 0 : 4 p .125; vs v3 0 : 3). Pooled clean FRESH10 + FRESH11 (137): gate 100 / 94, v3 97 / 94, RECON-5 **105 / 101** (CP low .699 / .668; vs v3 pass 0 : 8 p .0078, strict 0 : 7 p .016; vs gate pass 5 : 10 p .30, strict 2 : 9 p .065). ASSIGN guard PASS. Largest remaining failure class: position-only first-diff offsets, 24 of 82 (5 are exactly one tick of the unit's walk). Pod tree `/workspace/smeR5` (nothing running; smeR4 untouched). Evidence `results/live/recon/r6/`. Codex dispatches: 2 (`a2/codex/RECON6_1.md`, `RECON6_2.md`: shipping / launching FRESH11; both stopped at their first obstacle, an absent prep.log and a harmless tar ownership warning, so the shipping, launch and ablations were done by hand). Next: 13.4.
- **RECON-5 (10-31 ~05:45 EDT, section 12) -- DONE, nothing of mine is running.** Counted pass / strict (ablation-confirmed flagged-exact records counted): FRESH9 (177) gate 122 / 117, v3 128 / 125, v3 + RECON-5 **135 / 132** (CP low .704 / .686);
  FRESH10 (88, the clean held-out) gate 63 / 60, v3 61 / 59, v3 + RECON-5 **66 / 63** (.663 / .626; vs gate p .51, vs v3 p .06); dev49 (the 45 flagged records the old 151 excluded + 4) 6 / 11 / 18. Step 1: the 8 flagged-exact FRESH9 v3 records all ablation-confirmed (12.1).
  Code: `recon/cyc.py` + RECON-5 section of `recon.py` + `RECON_CYC=1` in `recon_search.py` (opt-in; absent = v3), frozen at fab0cad. Evidence `results/live/recon/r5/`. Reproduce: pod 33903 `/workspace/smeR4` (runs/, data/, drive_held.sh, drive_dev49.sh).
  Codex dispatches: none. Next: 12.9.
- (earlier RECON-5 line, superseded) **RECON-5 (10-31 ~03:00 EDT) -- held-out runs RUNNING.** Dev49 (a): raw exact gate 7, v3 14, v3 + RECON-5 25 of 49 (counted 6 / 10 / 17); code frozen at commit fab0cad (FRESH10_FREEZE.txt) BEFORE the held-out runs.
  Driver on 33903 `/workspace/smeR4/drive_held.sh` (PID 1054681; steps skip when `runs/<step>.log` says done; a half-done step: delete `runs/<step>` first; restart `cd /workspace/smeR4 && (nohup bash drive_held.sh > drive_held.out 2>&1 < /dev/null &)`;
  ends with HELD_DONE in `runs/held_drive.log`): f9_cyc_aff (40 affected FRESH9 records), f10_gate, f10_cyc_aff, f10_v3, ASSIGN-off guards. Then: pull `runs/<step>/recon_results.jsonl` (gate: results.jsonl), ablate the flagged-exact cyc records
  (`runR.sh RUN ablate2 INPUTS FRAMES` with RARGS="--runs RUNDIR --matches M1,M2"), `r5_confirm.py`, `r5_final.py --name FRESH9 ... --cyc-aff`. Codex dispatches: none.
- (earlier RECON-5 line) **RECON-5 (10-31 ~00:45 EDT, section 12) -- superseded by the line above.** Step 1 DONE (a): the 8 flagged-but-exact FRESH9 records (012313, 014530, 024332, 030902, 040421, 053225, 091421, 102101) ablated edit by edit
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
### 12.6 Dev result (a; 49 records = the 45 FRESH2-8 RNG-free records the old 151 excluded + the 4 flagged ones inside the 151; evidence `results/live/recon/r5/`, table `dev49_final.txt`)
Same engine / lib / env as every RECON run (`runR.sh`, lib 5e8089a4, ASSIGN on); gate = the 20-flag hand rules on the flags-on re-extraction, v3 = generator v3, cyc = v3 + RECON_CYC=1. raw = exact apart from torn with the extractor flag ignored;
counted = a flagged record counts when it is exact AND every kept structural edit is ablation-needed (`ablate_edits.py`, `r5_confirm.py`); as extracted = flagged never counts (all 49 are flagged).
| | gate | v3 | v3 + RECON-5 (v2) |
|---|---|---|---|
| raw pass / strict | 7 / 6 | 14 / 13 | **25 / 24** (CP low 0.385) |
| counted pass / strict | 6 / 5 | 11 / 10 | **18 / 17** (CP low 0.253 / 0.235) |
| as extracted | 6 / 5 | 1 / 1 | 1 / 1 |
Paired (raw): v3 vs cyc only-v3 0 / only-cyc 11 (p .001); gate vs cyc 0 / 18. Counted: v3 vs cyc 0 / 7 (p .016). cyc lost 0 records vs v3.
- Iterations on dev (disclosed): v1 (spell ghosts of any card, tap window -2..+3) = 23 raw; it LOST 155249, 000242, 060537 to v3 (their restored tap ran 8-20 ticks after tap + own_delay: window too narrow) and kept ghost spells that leave
  objects (RoyalDelivery, Log, Rage: 214831, 054032, 064121 got A_sim_only / extra units). v2: ghosts only for the card the reader cannot see (Zap, the RECON visibility rule), tap window -3..+25 -> 25 raw, 0 lost.
- v2 passes (25): 17 flagged records ablation-confirmed (own taps, Zap / BattleRam / MightyMiner / SuspiciousBush adds from v3's ops, 2 Mirror readings, drops of own ability presses), 6 with no structural edit (the best-prefix deal alone, or v3's swap on 031310),
  1 unconfirmable (001538: two dropped MegaKnight plays, the reverse run errors), 1 unflagged (142334). The 6 "deal only" records are exact although the cycle fails: the engine's refusal of a play no deal allows acts like dropping the invented / duplicated play.
- Still failing (24, v2): hero / evolution FORM mismatches (the SIM spawns BarbLogBarbarianHero / Knight_EV1 / Witch_EV1 where the reader lists the base card: 103056, 143825, 144727, 153413, 180849, 050136, 051010; the form is a function of how many
  times the card was cycled, so a missed play also shifts it: not modelled, (b)), unseen troop plays (171948 ZapMachine, 181209 MinionGiant, 213421 Xbow, 235316 IceSpirits, 054032 SuspiciousBush, 064121 LittlePrince area: cyc inserts spells only), and multi-play gaps.
### 12.7 FRESH9 held-out (a; frozen list of 10-30; code frozen at fab0cad before the cyc run; evidence `results/live/recon/r5/f9_*`)
The gate and v3 numbers are the held-out ones of RECON-4 (list and code frozen before any run). RECON-5 was DESIGNED after looking at FRESH9's failing records (the diagnosis of 12.3 came from them), so FRESH9 is held-out for its parameters
(nothing was tuned on it) but not for its idea; FRESH10 (12.8) is the clean test. RECON_CYC=1 was run on the 40 records it can change (opponent plays fit no deal, or an unmatched own tap); every other record takes no RECON_CYC path, so its row is the v3 row.
| 177 unique matches | gate | v3 | v3 + RECON-5 | best of v3 / RECON-5 (union) |
|---|---|---|---|---|
| as extracted, pass / strict | 122 / 117 | 120 / 117 | 121 / 118 | 121 / 118 |
| **counted** (ablation-confirmed), pass / strict | 122 / 117 (CP low .627 / .598) | 128 / 125 (.662 / .645) | **135 / 132 (.704 / .686)** | 136 / 133 (.710 / .692) |
| raw (flag ignored), pass / strict | 122 / 117 | 128 / 125 | 136 / 133 | 137 / 134 |
Paired, counted pass: gate vs cyc only-gate 3 / only-cyc 16 (p .004); v3 vs cyc 1 / 8 (p .039); gate vs v3 3 / 9 (p .146). RECON-5 gained 9 raw records over v3 (083215, 110215, 110854, 123731, 010059, 014211, 031423, 061817, 063534) and lost one
(040421: v3 solves it with drop + add + add through a non-fitting intermediate plan; the RECON_CYC run keeps the cycle rule on its repaired starts and its beam did not reach that route -> "union" = the better of the two runs by the comparator's own key; the
union is an analysis choice made after seeing this loss, (b)). 15 flagged-exact RECON-5 records ablated: 14 confirmed (own taps 9, Zap, IceWizard, Knight, SuspiciousBush adds), 1 not confirmable (061817, a Mirror reading whose reverse run errors).
Counted v3 (8 of 8 confirmed, 12.1) 128 / 125. Remaining 24 affected failures (cyc): unseen troop plays 8, hero / evolution form mismatches 8, areas 4, ghost-visible 4 (`fail_f9`-style census of the first diff rows).
### 12.8 FRESH10: the clean held-out test of RECON-5 (a; list `fresh/FRESH10.tsv` sha ae5d48da and the code (fab0cad) committed BEFORE the first run; evidence `results/live/recon/r5/f10_*`)
148 Ranked battles of 10-30 13:46 - 23:18 EDT after FRESH9 -> 90 RNG-free records, 88 unique matches (1 unplannable: no own deal in its record, every pipeline errors on it; the gate has one more error, 172612 "a kept variant failed"). 14 records
are affected (opponent no-fit, or an unmatched own tap); the gate and v3 ran on all 88.
| 88 unique matches | gate | v3 | v3 + RECON-5 |
|---|---|---|---|
| as extracted, pass / strict | 63 / 60 | 61 / 59 | 61 / 59 |
| **counted** (ablation-confirmed), pass / strict | 63 / 60 (CP low .626 / .591) | 61 / 59 (.603 / .579) | **66 / 63 (.663 / .626)** |
| raw (flag ignored), pass / strict | 64 / 61 | 65 / 63 | 69 / 66 (.699 / .663) |
Paired, counted pass: gate vs cyc only-gate 3 / only-cyc 6 (p .51); v3 vs cyc 0 / 5 (p .0625); gate vs v3 3 / 1 (p .63). RECON-5 gained 4 raw records over v3 (150042, 152453, 193232, 215458), lost 0. Flagged-exact RECON-5 records: 8 -> 5 confirmed
(2 Mirror readings, 3 adds), 1 deal-only (140450), 2 not confirmable (reverse run errors: 221240, 224356); v3's 4 flagged-exact: 0 confirmed (1 deal-only, 3 with a kept edit the ablation calls unneeded or errors).
What the gain is made of: FRESH9 14 confirmed = 11 own-tap restores + 3 v3-op adds; FRESH10 5 confirmed = 2 Mirror readings (cyc) + 3 v3-op adds reachable from the better start; dev 17 = 7 taps + 2 Mirror + 8 v3-op adds. The cycle-repair ghosts (Zap) restored
no record on its own in any set; the ghost-Zap and troop-insertion parts of the design are NOT shown to matter (b).
ASSIGN off / on guard, per frame (`r4_report.guard`, SME_CLS_TICKS): PASS for RECON-5 on FRESH9's 3 affected reader-hidden records and FRESH10's 1; gate and v3 on FRESH10's 3 reader-hidden records PASS (identical counts, no exact frame lost).
### 12.9 Verdict and next steps (labels as above)
- (a) The dev -> held-out gap is mostly a selection effect: the historic "strict fresh 151" excluded the 21% of RNG-free matches the extractor flags; those matches are 15-16% of FRESH9 / FRESH10 and the hand rules pass 0 / 35 of them in FRESH9.
- (a) The deck from the battle log was already in use; no replay data exists for any held-out match; neither can be the lever. The levers found: the opponent's deal (identity -> the deal that runs the most plays: exact frames 12% -> 40% on the 69 non-fitting
  records of FRESH2-9 before any search), our own action log (an unmatched tap = a missed own play, 20 / 20), and the Mirror reading (4 ablation-confirmed passing records over dev and FRESH10, plus FRESH9 061817 whose reverse run errors).
- (a) Held-out, counted pass: FRESH9 135 / 177 (CP low .704) vs gate 122 / 177 (.627), FRESH10 66 / 88 (.663) vs gate 63 / 88 (.626). The FRESH10 difference from the gate is NOT significant (3 : 6, p .51); against v3 it is 0 : 5 (p .06). Engine fidelity on a
  fresh held-out set is now ~0.75 counted (raw 0.77-0.78), against D1 0.90 / D2 0.98: still far, the remaining failures are form mismatches (hero / evolution activation by cycle count), unseen troop plays, area spells, and multi-play gaps.
- (b, next, in order of expected value) (1) hero / evolution FORM by cycle count (8 of the 24 remaining FRESH9 failures and 7 of the 24 dev ones: the SIM spawns the Hero / EV1 body the reader lists as the base card; the form of a play depends on the card's cycle count,
  which the repaired cycle now knows); (2) unseen troop plays with frame evidence (add (b) inside the repaired cycle, 8 FRESH9 failures); (3) own-tap ground truth for point and tick of EVERY own play (the tap's point is exact on 12,543 / 12,543) to drop the own-play shifts.
- Not done: the own side of the cycle repair beyond taps (own cycle failures without an unmatched tap: FRESH10 143358, 205343), troop-card ghosts, RECON_CYC on the 148 FRESH10 battles that are not RNG-free (the scored set excludes them as in FRESH2-9).

## 13. RECON-6: the hero / evolution form class (10-31)
Ticket: "8 of 24 affected FRESH9 failures (7 of 24 dev) are HERO / EVOLUTION FORM mismatches: the SIM spawns the Hero / EV1 body where the reader lists the base card; build ONE mechanism that gives every play's form from the cycle count + table rules".
Labels: (a) measured, (b) plausible untested, (c) contradicted. Code `recon/forms.py` (+ `test_forms.py`, `forms_census.py`, `forms_offline.py`, `form_diag.py`, `r6_*`), evidence `results/live/recon/r6/`. Pod tree `/workspace/smeR5` (smeR4 + this code; smeR4 untouched).
### 13.1 The premise is contradicted (c): the forms are already right; the "form" label is a naming artifact
- (a) crforge already derives every play's form from the cycle count: `MatchSide.item / count` (core ad8ef3a, tables 16.635.3). A card in the evolution slot (flag bit 0) counts its plays since its last evolved play; a play is evolved once the count reaches the evolved row's `DarkElixirCost`
  (Knight 2: plain, plain, evolved; Giant 1: alternate); a hero-slot card plays in its hero form whenever it is not evolved; a refused play counts too. The plan carries only the slot flags (battle-log API evolutionLevel 1 / 2) and the plays; the SIM spawns `Knight_EV1` / `IceWizardHero`
  from that rule. There is no form input that can be wrong except the flags and the play sequence.
- (a) The rule reproduces what the reader shows. `forms_census.py` on dev + FRESH9 + FRESH10 (465 records): 2,641 of 2,648 (side, card) form sequences (15,597 plays) are explained with no edit (99.74%); 15,191 of 15,191 planted flips of one observed form on those real sequences are detected.
  The 7 unexplained sequences are exactly 4 own sequences with a missed play (080427, 012313, 014530, 143358: each record's unmatched own tap, the bot's action log, lies in a gap the forms name, 4 / 4) and 3 opponent Mirror decks (001538, 192024, 200427).
  **FRESH11 (held out): 400 / 400 sequences explained on the flags-on extraction (69 records, 2,370 plays); 284 / 285 on the flags-off inputs the runs use (49 records): the one residual is our own Tesla in 035731, whose unmatched own tap (R4836) lies in the form gap R4448-5131: own-tap corroboration 5 / 5** (`forms_census_f11.txt`, `own_tap_form_gaps_f11.txt`).
- (a) The first-diff rows say "Hero / EV1" for another reason: the REC row carries the card's display name (`BarbLog`, `IceWizard`, `Knight`) whatever the form, the SIM row the crforge unit name (`BarbLogBarbarianHero`, `IceWizardHero`, `Knight_EV1`), and the comparator matches `(side, x, y, hp)`, never names.
  Opponent hero / evolution slot flags cleared on the 15 "form" records (RECON-5 final plans, `form_diag.py --noopp`, `r6_probe_run.sh`): first divergence EARLIER on 11, equal on 4, later on 0 (`probe_form_flags_off_15.txt`). Clearing only the BarbLog hero flag on 035831 turns the unit `BarbLogBarbarianHero` into `Barbarian`
  and leaves the first diff untouched (same point, same hp): that divergence is not the form.
- (a) What the first diffs really are (`r6_failclass.py`; all 82 failing records of FRESH9 + FRESH10 + dev49 after RECON-5): unit position-only offset 24, SIM-only body without a live twin 18, REC-only body without a SIM twin 17, area / projectile row first 10, hp-only difference at the same point 7,
  position + hp 4, tower row 2. Of the 15: 6 are hero Barbarian Barrel barbarians (live point 142 / 284 units behind the SIM's along the roll; hero BarbLog decks fail 7 of 14 records vs 19 of 98 with a plain BarbLog, Fisher p .018 over ~60 card / flag cells looked at, so b), 3 hero Ice Wizard cube /
  ability rows (105010, 130404, 153413), 2 hero Mini PEKKA bodies the reader does not list (101523, 022944: reader-hidden frames exist), correct-form Knight_EV1 / Witch_EV1 bodies with lower live hp (220240: our own Knight is evolved per our hand, SIM hp 1638 vs live 1103; 051010), 1 Ram (position, 28 units: 061408), 1 Knight (position, 39 units: 144727).
### 13.2 What was built (a: it works as specified; b: it fixes almost nothing on real records)
- `forms.rules` (tables) -> `predict` (the count rule) -> `align`: the cheapest explanation of an observed form sequence by the rule (DP over the count, <= 3 states: an observed play is kept (its form must agree), deleted (cost 1: an invented play, or a Mirror copy read as the copied card, which moves no count)
  or an unseen play is inserted (cost 1); all optimal alignments enumerated). `form_repairs` (opponent only, deletions only): each deleted play is dropped, or read as the Mirror when the side's previous play is the same card; kept when the sequence then fits a deal; the variants are extra starting members scored by the
  engine like RECON-5's cycle repairs. `RECON_FORM=1` in `recon_search.py` (opt-in; absent = RECON-5 / v3 byte-identical). `plan_cost` = the alignment cost of a final plan (0 = the rule explains every observed form of its plays).
- Planted checks: `forms.py` ok 73 (rule, clean sequences cost 0, flips, missing plays located, duplicates located), `test_forms.py` ok 24 (tables; a planted Mirror read breaks the cycle, is detected, gets a Mirror variant that fits a deal and has plan cost 0; no Mirror in the deck -> no Mirror reading;
  a clean record and the known-deal side get no repair; flips; the real-record census and the 15,191 planted flips). `test_recon.py` ok 81 and `test_search_dry.py` ok 12 unchanged.
- (a) Field effect: `forms_offline.py` on the 465 dev + FRESH9 + FRESH10 records: `form_repairs` yields a variant on ONE record, 001538 (`formdrop s0 MegaKnight R911,3097`); on FRESH11 on none. Forms ALONE (no cycle repair, pod `sm2_dev_form`, committed code) take 001538 from the gate's and v3's 56 of 1,765 exact frames (first div 263) to 1,777 / 1,777, the same plan RECON-5's cycle
  repair finds (two invented MegaKnight plays beside the Mirror plays): two independent routes agree. `plan_cost`: base {MegaKnight: 2} -> final {}: the edits are form-corroborated (extra evidence; the ablation, the owner's counting rule, still cannot run on that record; the other three records whose ablation cannot run, 061817 / 221240 /
  224356, are Mirror readings of cards without a form rule: no form signal, `planconf_unconfirmable.txt`). For 200427 the forms' optimal deletions (R2603 + R3922) are RECON-5's repair (mirror Pekka R2603, drop Pekka R3921); 192024 (5 Mirror reads, an Elixir Collector deck: the cycle repair costs 6) gets no variant.
- (a) Inertness: RECON_CYC=1 RECON_FORM=1 vs the stored RECON-5 rows: identical counts, first divergence and edits on 18 / 18 records (10 FRESH9 affected, 8 dev49; a tree one forms.py edit older, the edit only touches form_repairs) and on 12 / 12 FRESH11 affected records (committed code, below).
### 13.3 FRESH11: the second clean held-out test of RECON-5, and of the forms (a; list `fresh/FRESH11.tsv` sha fc9d6781 committed at 3cb6a76 BEFORE any extraction; code frozen at a2e03f5; evidence `r6/f11_*`)
69 Ranked battles of 10-30 23:21 - 10-31 04:07 EDT (after FRESH10; live ran CLXIII, then the CLXV trial from 02:26), 49 RNG-free records = 49 unique matches (scored set). 12 records affected by RECON_CYC (opponent plays fit no deal / an unmatched own tap), 0 with a form residual, 4 with reader-hidden bodies.
Gate / v3 / RECON-5 on the same raw logs and lib (5e8089a4), ASSIGN on; RECON-5 + forms = RECON_CYC=1 RECON_FORM=1 on the affected records (every other record takes no flagged path: its row is the v3 row).
| 49 unique matches | gate | v3 | v3 + RECON-5 | v3 + RECON-5 + forms |
|---|---|---|---|---|
| as extracted, pass / strict | 37 / 34 | 34 / 33 | 34 / 33 | 34 / 33 |
| **counted** (ablation-confirmed), pass / strict | 37 / 34 (CP low .634 / .568) | 36 / 35 (.612 / .590) | **39 / 38 (.678 / .656)** | 39 / 38 (identical rows) |
| raw (flag ignored), pass / strict | 37 / 34 | 36 / 35 | 39 / 38 | 39 / 38 |
Paired, counted: gate vs RECON-5 pass only-gate 2 / only-RECON-5 4 (p .69), strict 0 / 4 (p .125); v3 vs RECON-5 0 / 3 (p .25); RECON-5 vs forms 0 / 0 (identical on all 12 affected records). RECON-5 gained 3 raw records over v3 (234450, 023819, 034822) and lost none. Flagged-exact records: v3 2 (004941 Zap adds, 035731 Tesla add + 2 re-bound hero presses),
RECON-5 5 (those two + 234450 Skeletons add, 023819 Firecracker + Tesla adds, 034822 GoblinHut add): ablation of every kept structural edit, 0 unneeded, 0 harmful, all confirmed (`f11_abl_*.jsonl`); the gate's 8 flagged records are none exact. The gate fails 12: 7 are opponent-no-fitting-deal records (identity-deal artifact), RECON-5 turns 3 of v3's failures into exact records (234450, 023819, 034822).
ASSIGN off / on guard (per frame, `r4_report.guard`): PASS on all three: gate 4 reader-hidden records, v3 4, RECON-5 + forms 1: identical frame counts ASSIGN off vs on, no exact frame lost (`f11_assign_guard.txt`).
**Pooled clean held-out, FRESH10 + FRESH11 (n 137; both lists and the RECON-5 code frozen before any run on them; FRESH10 unplannable record counted as a fail in every column):** counted pass / strict gate 100 / 94 (.730 / .686, CP low .660 / .615), v3 97 / 94 (.708 / .686, .637 / .615), RECON-5 (= RECON-5 + forms) **105 / 101 (.766 / .737, CP low .699 / .668)**.
Paired: gate vs RECON-5 pass 5 / 10 (p .30), strict 2 / 9 (p .065); v3 vs RECON-5 pass 0 / 8 (p .0078), strict 0 / 7 (p .016); gate vs v3 pass 5 / 2 (p .45). (`pooled_final.txt`; FRESH9 135 / 177 (.763) is held-out for the parameters only.)
### 13.4 Verdict and next steps
- (c) The hero / evolution FORM mismatch class does not exist as an input problem: the forms the SIM spawns equal the forms the reader sees (99.74% of sequences on dev + FRESH9 + FRESH10, 100% / 99.65% on FRESH11 flags-on / off); the "8 of 24" / "7 of 24" came from the substring Hero / EV1 in a first-diff row's name. Flipping the opponent's forms makes failures worse, never better.
- (a) The mechanism the ticket asked for exists in crforge; what was added is a checkable instrument (the form alignment) that corroborates RECON's repairs (4 / 4 own gaps, 001538's two drops, 200427's Mirror reading) and found one repair on its own (001538). Expected effect on a held-out set: about 0 to 1 record in 465; measured on FRESH11: 0.
- (a) RECON-5 holds on the second clean set: counted 39 / 49 (.796) vs gate 37 (.755), v3 36 (.735); pooled over the two clean sets 105 / 137 (.766, CP low .699) vs gate 100 (.730): the gain over v3 is significant (8 : 0, p .0078), the gain over the hand-rule gate is not (10 : 5, p .30; strict 9 : 2, p .065).
  Engine fidelity on clean held-out matches is now ~0.77 counted, ~0.74 strict, against D1 0.90 / D2 0.98.
- (b, next, in order of expected value; the lead decides) (1) the position-only first-diff offsets, 24 of 82 failures after RECON-5 and the largest class: 5 of them are exactly one tick of the unit's walk (0.97-1.01 ticks: Knight x2, GoldenKnight, BowlerHero, a BarbLog-hero barbarian), 5 hero-barbarian ones are 2.37 ticks (142 units, x3) and 4.73 ticks (284, x2) (`position_offsets_in_ticks.txt`);
  measure the body's first-listing tick against crforge's spawn tick per unit type (a deploy / listing lag in crforge or the reader, not an input edit); (2) unseen troop plays with frame evidence (REC-only body without a SIM twin, 17: add (b) inside the repaired cycle); (3) SIM-only bodies without a twin (18): reader-hidden or extra bodies, check against `reader_hidden`;
  (4) the hero Barbarian Barrel lead (6 failing records, offsets 142 / 284; the live roll length is the same for hero and plain barrels, `barblog_roll_lengths.txt`, so look at the barbarian's spawn / first walk).
- Not done: forms for the own side beyond the taps check, insert-only explanations (an unseen troop play) as edits, Mirror of an evolved play (crforge: not held by a recorded battle).
## 14. RECON-7: the position-only class, and CLXIII's SIM pace (10-31)
Ticket: (1) "position-only first-diff offsets, 24 of 82 failures after RECON-5 (5 exactly one tick of the unit's walk, 5 hero-barbarian ones 2.37 / 4.73 ticks): measure the spawn / first-listing tick offset per unit type, decide crforge vs reader, ONE general rule";
(2) "CLXIII plays 11.2 cards / min live but 9.3 in SIM: find why and fix the SIM side". Labels: (a) measured, (b) plausible untested, (c) contradicted. Code `recon/r7_trace.py`, `recon/r7_press.py`, `SmeRun.java` (late_unit), `recon.py` (RECON_LATE), `recon_search.py` (RECON_ROUNDS); evidence `results/live/recon/r7/`; pod tree `/workspace/smeR6` (= smeR5 + this code).
### 14.1 Part 1: there is no spawn / first-listing offset (c); the class is a mixture, and its largest homogeneous part was a harness gap (a)
- (c) Spawn timing and listing delay are contradicted as the class's cause. For the 24 records (`r7_trace.py`: the unit's SIM and REC trajectory from its first listing to the first diff; `position_traces.txt`, `position_age_since_spawn.txt`): the first diff comes 3 - 521 ticks AFTER the unit's spawn (median 61; 6 of 22 traced within 40 ticks), the unit's first listing equals the SIM spawn row (+ the 2-tick frame grid) wherever it could be traced, and the sign is mixed: REC one tick ahead of the SIM (Knight 194827, BowlerHero 054304) and one tick behind (Knight 120902, BarbLog 143825). The "one tick of the walk" cases are 1 tick of a different thing each time: a Bowler boulder knock-back that ends one tick earlier in the game (194827), the Bowler stopping at range one tick later (054304), an Ice Wizard slow (180321), a Golden Knight dash (174855, 220240, 134929: REC 240 vs SIM ~290 units / tick), heading differences at a hit (144727, 060329, 013650). Exact records (the 77%) agree on spawn and walk start to the unit, so the engine's deploy / walk rule is right.
- (a) Round cap: 2 of the 82 failures stopped at search round 39 of 40 with a healing shift still ahead (dev 120902: its Knight start is a +1 run shift; FRESH9 132711); `RECON_ROUNDS=80` (opt-in, absent = 40) takes 120902 to 3,054 / 3,054 exact frames and 132711 to exact apart from one torn frame (`r7_rnd_*.jsonl`).
- (a) The six hero Barbarian Barrel records (FRESH9 035831, FRESH10 152809, dev 103056 / 143825 / 180849 / 050136; offsets 142 / 284 = 2 / 4 reader ticks of the roll) are an UNMODELLED ABILITY PRESS, not a spawn offset: the opponent's hero barbarian re-rolls (`BarbLogHeroAbility`, ManaCost 1, OnActivationAction `BarbLogHero_spawn_reroll`): the barbarian leaves, the barrel rolls back and the hero re-spawns. The reader lists the re-roll barrel as a SECOND BarbLog play (the cycle repair's `cyc drop s1 BarbLog` is exactly that phantom), and the press never entered the plan because (i) a `cmdN_u` ability names a unit the play made, and the barrel's barbarian is made later by the roll's end (`SmeRun: cmd7 names cmd5_0, which no play of side 0 made`: every press candidate was refused by the harness and dropped silently), (ii) the generator takes the side's latest play of the card of the WHOLE match as the presser (the phantom second BarbLog is later), and only plays within 120 ticks of d (143825: the barbarian walked 169 ticks first). Engine and reader agree once the press exists: a hand-added press at d - 2 takes FRESH9 035831 to 1,892 / 1,892 exact frames and FRESH10 152809 to 2,115 / 2,115 (`r7_press.py`).
### 14.2 The mechanism (RECON_LATE=1, opt-in; absent = RECON-5 byte-identical)
- `SmeRun.java`: an ability with `late_unit: NAME` (no unit binding) is queued in the tick loop like the Goblins' banner press: at the last tick before its run it names the side's newest live unit of that name BY OBJECT ID (as the game's command does); no unit alive then = no press. `recon.Tab.late_unit(card)` = the one character whose Ability row is the SPELL card's ability (BarbLog -> BarbLogBarbarianHero; none for any other card in the tables, checked on Knight / IceWizard / Tesla / Zap / Log / Pekka); the press hypothesis for such a card carries `late_unit` (and a `cmdN_0` bookkeeping reference for the elixir bank and the drop / remap rules) instead of the three (play, unit) guesses; the presser = the side's latest play of the card BEFORE d, at any age, when the diff names the card.
- Planted checks: `test_recon.py` ok 93 (was 81): late_unit table, `ability_cost` unchanged, RECON_LATE absent = the (play, unit) guesses and the old presser rule, a BarbLog play after d and one 280 ticks before d, the IceWizard presses unchanged, apply_edit / runnable carry the field.
- (a) Dev result (RECON_CYC=1 RECON_LATE=1, `r7_bl2_*`, `r7_bl3_dev`): FRESH9 035831 1,892 / 1,892 exact (first div was 3105), FRESH10 152809 2,115 / 2,115 (3754), dev 180849 1,765 / 1,765 (583), 050136 3,028 / 3,028 (3644), 143825 2,267 / 2,267 (1075; needs the press-at-any-age rule): 5 of 6; 103056 stays at 2846 (the elixir rule refuses its 4 press candidates: the flagged opponent's bank model is short). Each fix is a press + the cycle repair's `cyc drop BarbLog` (the re-roll barrel read as a second play).
- (a) Inertness (`inertness.txt`, `inert7.sh`): RECON-7 code with NO new key = the stored RECON-5 + forms rows on 10 FRESH9 + 8 dev records (counts, first divergence, edits) 18 / 18; the same 18 non-BarbLog records with RECON_LATE=1 RECON_ROUNDS=80 also 18 / 18.
### 14.3 Part 2: CLXIII's SIM pace (9.3 vs 11.2 plays / min): not the decision cadence, not the refusals (c); two real SIM-vs-live mechanisms fixed (opt-in); the gap is composition + per-phase rates (a)
Setup (a): live = the 856 CLXIII calibration-block matches (`live_table` cache); SIM = the D3 block (CLXIII live stack vs the ftR opponent, seed 741200, G2 on: tap loss + slow taps; rows `oplc_ftR_l0003_live_u0080`, 480 games, and 48-game paired probes on pod 33903, `rr_*` rows with every refusal reason: `rr_probe.py`, `rr_wrap.py`, `rr_run.sh`, `rr_an.py`, `rr_an2.py`, `phase_pace.py`, `dec_cadence.py`, `gapdist.py`).
- (a) The 11.2 vs 9.3 compares two different things. Live counts the PLAY events our bot issued (11.24 / min; 96.7% are confirmed, 10.82 / min); the SIM count was ACCEPTED plays (9.28). The SIM's own attempts are 11.44 / min raw, 11.36 real (64 of 1,935 attempts in 48 games, 3.3%, are made after the engine's match is over: `game_over`). So attempts match (+1%); the SIM refuses 19% of them (not_enough_elixir 11.6%, tap_lost 4.0% = the G2 model of the live 'unconfirmed' 3.3%, game_over 3.3%, match_over_before_landing 0.3%).
- (a) Mechanism 1, the elixir hold: the refused-by-elixir plays are the ones whose elixir at the decision exceeds the card cost by < 0.4 (refused 99.5% when elixir - cost < 0.375, 9 - 10% above; 480-game rows, `refused5.py`; probe median margin +0.23). The live game HOLDS a tap that cannot pay yet and runs it once it can, up to ~22 ticks after the tap's arrival (19,361 live plays, `latency/afford_arrival.txt`: refused only past 22); crforge's client gate refuses at once. Mechanism 2, the post-play decision: live decides again 26 ticks after a play decision in 50% of 894 post-play decisions (24-28 in 77%; 20 logs, `dec_cadence.py`), then every 10 ticks; the SIM waits for the next grid tick (30), so its minimum gap between plays is 1.5 s vs live 1.3 s (live: 17.8% of consecutive confirmed plays are < 1.5 s, the SIM 0.2%).
- Fix (opt-in, absent = byte-identical; `e1_eval` cfg `tap_hold` N and `play_resume: land`, `search_s0 --tap-hold 22 --play-resume land`; commit 00ca929, tests `test_tap_hold.py` ok 11, the existing tap_loss / action_delay / follow-up tests unchanged): a not-enough-elixir refusal at landing is retried each tick for N ticks (the ghost seats' `elixir_slack` rule), the attempt is tallied once, the next decision follows the held play's run; after a play the next decision is act + engine delay + 1. Absent key: 48 / 48 matches identical to the unpatched code on a real engine run (`rr_a` vs `rr_p1`).
- (c) Result of the fixes on 48 paired games (seeds 741200-741247, same decks): refusals not_enough_elixir 11.6% -> 1.3% (hold) -> 0.5% (hold + resume); minimum gap 1.5 -> 1.35 s (live 1.3); median gap between accepted plays 4.50 -> 4.32 s (live 3.80). **Accepted plays / min: 9.45 (A) -> 9.41 (hold, paired -0.04 [-0.36, +0.27]) -> 9.37 (hold + resume, paired -0.08 [-0.41, +0.25]).** The pace did not move: a refused play was simply re-decided 1.5 s later, and CLXIII is income-bound, not cadence-bound. The hypothesis that decide_every / refusal / tap timing makes CLXIII slow in SIM is contradicted.
- (a) What the gap is (live 11.13 vs SIM 9.67 plays / min pooled, `phase_pace.py`): the match-length mix. Live spends 22% of its time in overtime (ot2x 14%, ot3x 8%), the SIM 10% (ot2x 7%, ot3x 3%), and the overtime pace is 1.7-2.7x the single-elixir pace; with the live time shares the SIM would play 10.31: composition = 0.64 of the 1.46 gap (44%). The other 0.82 (56%) is the per-phase rate: live / SIM plays per min 1x 7.94 / 7.40, 2x 13.36 / 13.05, ot2x 13.88 / 12.64, ot3x 20.27 / 16.82; live spends 95-100% of its elixir income in every phase (23.5 of ~24 at 1x), the SIM 92-95% (79% in ot3x).
- (b, next) With the retries removed the SIM CLXIII DECIDES to play 9.8 / min (hold + resume) against live's 11.24 attempts: the residual is in the play decision itself, i.e. the state it sees (the ftR opponent plays 6.50 detected plays / min vs live humans 7.13, so the board is quieter) or the observation (live reader vs SIM), not the timing. Owed measurement: the same D3 block against a replayed-human (ghost) opponent seat (opponent plays fixed, only CLXIII's state-dependence left), and a per-phase paired comparison. Until then the opponent's human-likeness bar should be read per phase, not on the pooled pace.
### 14.4 FRESH12: the clean held-out test of RECON-5 and RECON-7 (a; list `fresh/FRESH12.tsv` sha 5edf783d committed at c77355b BEFORE any extraction; code frozen at 54c5ec6, identical on the pod by sha; evidence `r7/f12/`)
68 Ranked battles of 10-31 04:08 - 08:51 EDT (after FRESH11; live ran the CLXV trial / block), 39 RNG-free records = 39 unique matches (scored set; 9 records affected by RECON_CYC, 0 form residual, 1 reader-hidden, 9 with a BarbLog card in a deck).
Gate / v3 / RECON-5 / RECON-5 + forms / RECON-7 (`RECON_CYC=1 RECON_FORM=1 RECON_LATE=1 RECON_ROUNDS=80` on the 18 records it can change = the 9 affected + the 9 BarbLog-deck records; 0 had a round-39 v3 search; every other record keeps its v3 row, the RECON-5 argument 12.7) on the same raw logs and lib (5e8089a4), ASSIGN on (`r7_drive_f12.sh`, `r7_final.py`, `f12_final.txt`).
| 39 unique matches | gate | v3 | v3 + RECON-5 | + forms | RECON-7 |
|---|---|---|---|---|---|
| as extracted, pass / strict | 29 / 29 | 27 / 27 | 27 / 27 | 27 / 27 | 27 / 27 |
| **counted** (ablation-confirmed), pass / strict | 29 / 29 (CP low .604) | 28 / 28 (.577) | 33 / 32 (.719 / .689) | 33 / 32 (identical rows) | **34 / 33 (CP low .749 / .719)** |
| raw (flag ignored), pass / strict | 29 / 29 | 29 / 29 | 33 / 32 | 33 / 32 | 34 / 33 |
Paired, counted: RECON-7 vs RECON-5 pass only-RECON-5 0 / only-RECON-7 1 (p 1.0), strict 0 : 1; RECON-7 vs v3 pass 0 : 6 (p .031), strict 0 : 5 (p .0625); RECON-7 vs gate pass 1 : 6 (p .125), strict 1 : 5 (p .22); RECON-5 vs v3 pass 0 : 5 (p .0625). The one record RECON-7 adds: **044738 (opponent hero Barbarian Barrel: opp_no_fitting_deal, first divergence 332 under v3 / RECON-5) is exact (1,765 / 1,765) with FIVE hero re-roll presses (R 1706, 2588, 3086, 3978, 4387, one per BarbLog play); ablation: all 5 adds needed, 0 unneeded** (`f12_abl_r7.jsonl`: the 7 flagged-exact records, 13 structural edits, all needed; v3's 042803 too). RECON-7 lost no record; 8 of the 9 affected records give rows identical to RECON-5 (counts, first divergence, edits). Flagged-exact counted: RECON-5 6 (041418 Witch, 042803 Xbow, 052825 Zap, 061658 Skeletons tap, 075417 Knight tap + Goblinstein, 080850 2 Zaps), RECON-7 + 044738. ASSIGN off / on guard (`guard12.py`): PASS (1 reader-hidden record, failing in both, no exact frame lost; gate and v3).
FRESH11 (clean for the fix: frozen before any BarbLog work, run once): the RECON-7 set = 12 affected + 8 BarbLog-deck records (20); 19 rows identical to RECON-5 + forms; 1 differs, 012542 (opponent hero BarbLog: first divergence 539 -> 2,062 with `press s1 BarbLog (cmd4) R537`, still failing later, `f11_cmp.py`); no pass / strict count changes, no record lost.
**Pooled FRESH11 + FRESH12 (n 88, both clean for RECON-7), counted pass / strict:** gate 66 / 63 (.750 / .716, CP low .663 / .626), v3 64 / 63 (.727 / .716), RECON-5 72 / 70 (.818 / .795, CP low .737 / .712), **RECON-7 73 / 71 (.830 / .807, CP low .750 / .724)**. Paired: gate vs RECON-5 pass 3 : 9 (p .146), strict 1 : 8 (p .039); v3 vs RECON-5 pass 0 : 8 (p .0078); v3 vs RECON-7 0 : 9 (p .0039); RECON-5 vs RECON-7 0 : 1. FRESH10 is NOT clean for RECON-7 (its 152809 designed the fix); with it the engine fidelity on clean held-out records is ~0.77-0.83 counted, against D1 0.90 / D2 0.98.
### 14.5 Verdict and next steps
- (a) Part 1: no single offset. The one mechanism with a clean general rule is the hero press that the harness could not name (BarbLog); it is worth 6 of the 24 dev records (5 exact), 1 of 39 on FRESH12 (+1 pass, p 1.0 vs RECON-5: not significant on its own, a positive held-out confirmation of the mechanism), 0 pass changes on FRESH11 (1 record moved 539 -> 2,062). Expected effect on a held-out set: about 1 record in 40 (9 of the 39 FRESH12 records hold a BarbLog card; one fails for the missing press).
- (b, next, by expected value) (1) the remaining position-only mix, per mechanism: Golden Knight dash target / length (3 records: REC dash 240-250 / tick short vs the SIM's longer dash; passing GK records dash 398 / tick in both), Bowler boulder knock-back and stop-at-range one tick (194827, 054304), Ice Wizard slow on a Knight (180321), heading differences at a hit (144727, 060329, 013650); (2) 103056: the elixir rule refuses the 4 press candidates (the opponent bank model is 0.5 short on a flagged record); (3) the hero BarbLog failures that remain after the press (FRESH11 012542 at 2,062); (4) ownership of the phantom 'second BarbLog play' in the extractor (RECON drops it by the cycle repair; an extractor rule would save the search).
- Owed (pace): the ghost-opponent D3 block (14.3 b).
- Restart (pod 33903, CPUs 226-237, tree `/workspace/smeR6`; nothing running): FRESH12 driver `cd /workspace/smeR6 && (nohup bash sme/recon/r7_drive_f12.sh > drive_f12.out 2>&1 < /dev/null &)` (skips steps whose `runs/<step>.log` says done; delete a half-done `runs/<step>` first; data `data/f12/` = `.foreman/scratch/recon7/f12_data.tgz`, sets by `recon/r6_mk_sets.py /workspace/smeR6/data f12`); tables `python -I recon/r7_final.py ...` (usage in the file; ok lists = `r5_confirm.py` on the `recon/ablate_edits.py` rows). Pace probe: `CPUS=226-237 W=4 bash rr_run.sh OUTDIR NCHUNKS [--tap-hold 22 --play-resume land]` (12 games per chunk; `ov/` = the pod's eval code + commit 00ca929's e1_eval / search_s0), analysis scripts in `results/live/recon/r7/pace/`.
## 15. RECON-8: the Golden Knight dash (10-31, evidence `results/live/recon/r8/`)
Ticket: owner decision 10-31 "Yes, GK dash first" (an exception to the 10-29 no-one-by-one rule, because RECON-7 read the three failing GK records as real engine mechanics: "REC dash 240-250 / tick, short, vs the SIM's longer dash; passing GK records dash 398 in both"). Make crforge reproduce the dash as a game-wide rule (opt-in key, new build), never a per-record flag, never a looser comparator; if it is observation, say so and stop. Labels: (a) measured, (b) plausible untested, (c) contradicted. Tools (pod, `envR.sh` env, RAM-disk work dirs): `recon/r8_gk.py` (SIM Golden Knight every tick with buffs / targeting reference next to the REC rows), `recon/r8_press.py` (a press dropped / moved / added: GK exactness per REC frame + the whole-record comparator), `recon/r8_scan.py` + `r8_scan_table.py` (every GK press of 26 records: as extracted, dropped, moved to every tick of [lo - 14, hi + 2]).
### 15.1 FRESH13 frozen first (a)
`fresh/FRESH13.tsv`, sha256 30f9a772f4de5d0a4a9a32155e92df41c02698d9393ee0355b8686f2e3e12115, 43 Ranked battles of the main account (live logs 20261031_085656 .. 115235, battles 13:02Z .. 15:55Z; all 43 carry a live log; 0 overlap with FRESH9-12), freeze.py at repo HEAD c95368e, committed at 76dbe5f BEFORE any extraction, diagnosis or code change (`FRESH13_FREEZE.txt`). Not extracted and not run: there is no engine key to test, and the pod has no disk for another data set (15.5). It stays pre-registered for whatever the lead builds next.
### 15.2 The failing Golden Knight records are not an engine problem (a)
Method: take the record's final plan (RECON v3 / cyc plan, or the gate plan), change ONLY the Golden Knight press, run crforge, compare the GK's (x, y) with the REC GK on every REC frame of the window (`press_variants.txt`, `press_variants2.txt`; per-tick traces `trace_*.txt`).
| record | set | first div | the plan's press | what the live game did | test | result |
|---|---|---|---|---|---|---|
| 174855 | FRESH9 | 3039 | gk_dash 3037 | NO dash. The opponent's GK walks into OUR Tornado (at (6500, 21500), the REC `A` rows); the pull moves it 250 / tick, which `gk_dashes` (a body moving > 100 units / tick, Manhattan) reads as a dash | press dropped | GK 27 / 27 REC frames exact (3021-3073); whole record 1,742 / 1,742 exact (gate plan; was 1,696, first div 3039). The pull itself is exact: with the press at 3039 the SIM equals REC at 3039 to the unit |
| 230352 | dev (FRESH2-8) | 914 | gk_dash 912 | NO dash: the GK under the opponent's Rage walks 78 / tick = Manhattan 109 / tick > 100 | dropped | GK 15 / 15 frames exact (890-918); first div 914 -> 1752 |
| 134929 | FRESH10 | 1675 | gk_dash 1673, window 1671-1673 (dash onset - 2) | the live press came while the GK was FROZEN by the hero Ice Wizard (freeze until ~1669). The game (and crforge) hold the ability until the GK can dash, so any press in 1664-1670 gives the same SIM; the extractor's window starts later | press at 1664 .. 1670 (all identical) | GK 20 / 20 frames (1660-1700); WHOLE record 1,887 / 1,887 exact (was 1,857, first div 1675). Presses at 1671, 1672, 1674, 1675: not exact |
| 220240 | FRESH9 | 3827 | none | a REAL dash (Knight_EV1 hit for 535, then the X-Bow) at 3825-3827, never extracted: `gk_dashes` had fired on a burst at 3756-3758 (v 157; the GK matches REC there with no press at all, cause not traced; the final plan does not carry that cast) and its one-cast-per-100-ticks gate (`b - lastcast > 100`; 3827 - 3758 = 69) hid the real one | press ADDED at 3824 (3821-3826 tried) | GK 35 / 35 frames (3801-3869, incl. the odd 176 / 175 first step and the turn onto the X-Bow); first div 3827 -> 4586; the next GK chain's press (4582) at 4581 (inside its own extracted window 4581-4582) -> 20 / 20 frames, first div 4747 |
| 080315 | FRESH12 (clean) | 2854 | none | a real dash at 2855 (Knight hit for 535), same gate: burst at 2780-2782, 2856 - 2782 = 74 < 100 | press ADDED at 2853 | GK 31 / 31 frames; first div 2854 -> 3595; its next press at 3592 (inside the window 3592-3593) -> 22 / 22 frames, first div 3927 = a Log projectile one step off, not the GK |
(a) Every GK number the SIM produces in these records matches the live game as soon as the press is right: dash legs of 398 / tick, the odd first step, the chain's turn from target to target, the landing hold, the stop in range, the Tornado pull on a GK, the frozen start. (c) Contradicted: "crforge's dash is shorter / longer / aimed differently". The REC dashes of 134929, 220240 and 080315 are 398 / tick like the passing ones; the only REC "240-250 / tick" is 174855's Tornado pull, which was never a dash. RECON-7's 14.1 / 14.5 item "Golden Knight dash target / length (3 records)" is closed by this section.
### 15.3 Scan of every Golden Knight press I hold (a; `scan.jsonl`, `scan_table.txt`, `gk_records_first_div.txt`)
26 records with a GK press (FRESH9 8, FRESH10 4, FRESH11 1, FRESH12 3, dev49 2, 8 of FRESH2-8; the final RECON plan of each), 99 presses (80 gk_dash + 12 gk_buff with REC frames, 7 with no GK frame). Score of a press = REC frames in [tick - 4, tick + 60] whose GK the SIM reproduces to the unit.
- 18 of 26 records have NO first divergence (every REC frame exact, all their GK dashes included).
- 77 of 92 presses with frames are exact as extracted (66 / 80 gk_dash, 11 / 12 gk_buff). The other 15: 7 sit behind an earlier divergence (their GK frames are confounded: 143358 at 155, 220240 at 3827, 080315 at 2854, 123045 at 1768, 230352 at 914); 5 are fixed by a shift (134929 outside its window; 080315 1841, 220240 4581 and 5227, 123045 3741 at the edge of the extracted window: the repair loop only works at the first divergence, so these were not reached); 2 by a drop (174855, 230352); 1 open (123045 tick 1766, confounded with Witch / Skeleton diffs at 1768).
- Size of the class: 4 failing GK first divergences among the 406 FRESH9-12 + dev49 records (174855, 220240, 134929, 080315) plus 230352 and 123045 in FRESH2-8. A perfect GK press fix makes 2 of the 4 fully exact (174855, 134929); 220240, 080315 and 230352 move on to other classes (4747, 3927, 1752). That is at most +2 / 406 = 0.5 pp of engine fidelity.
### 15.4 Verdict and next steps (the lead decides; stop-and-report per the ticket)
- (a) No engine change is needed or built: no opt-in key, no new lib (lib `5e8089a4` and every running job untouched). The source of `5e8089a4` is NOT on any pod (30408 was wiped); it is reconstructable = upstream `e5462c82` (a clone is at `.foreman/scratch/recon8/crforge_src`, untracked) + the patches in `fork/f635/patches_up`, `fork/cfclone/patches`, `fork/f1fix`, `fork/f1fix3`, `fork/engfix` in the MAIN.md order; not needed now.
- The causes live in the extractor (`sme_live.gk_dashes`) and in the search: (1) a GK "burst" is any body motion > 100 units / tick (Manhattan, GK_STEP): a Tornado pull, a Rage walk and (b) a Log / Bowler push all pass; the dash itself is 400 / tick (the character row's JumpSpeed, measured 398-401), but a lone 250-unit hop (a close target) is not separable from a pull by speed alone (b); (2) `lastcast` is set by a burst that is not a dash and then hides the real dash for 100 ticks (220240 and the clean FRESH12 080315); (3) the press window is [dash onset - 2 ..], but a press during a freeze is held by the game, so the real press can be earlier than the window (134929); (4) the gate repair and RECON only act at the first divergence and only inside [lo, hi]; RECON's add / drop needs the first divergence to move by >= HEAL = 20 ticks, and on the v3 plan of 174855 the drop moves it only 3039 -> 3054 (+15; why 3054 diverges was not traced, b), so RECON never kept the drop.
- (b, in order, none run): (i) a general GK-press operator set in the RECON generator, engine-scored: drop / add (the side's latest GK play, any run tick in [d - 14, d]) / shift below [lo, hi] down to the last tick the GK could not dash, no HEAL minimum for it. Generator work, not an extractor patch per record and not engine work; expected gain on held-out sets 0 to 1 record in 100 (the class is 0.5 pp at most; FRESH12 080315 would still fail at 3927). (ii) or in the extractor: apply the 100-tick gate only after the false-burst filter and give `gk_dashes` a cause test (a Tornado area standing over the GK, a Rage buff); same gain. Neither is worth more than the Log / Bowler / IW-slow position classes of 14.5 (b), unless the lead wants the 0.5 pp.
- Next failing classes inside these records are not the Golden Knight: 080315 at 3927 (a Log projectile one step off), 220240 at 4747 and 230352 at 1752 (not traced), 123045 at 1768 (Witch / Skeletons).
### 15.5 Pod incident (a)
Pod 33903's disk (overlay 120 GB) was 100% full at 12:30 EDT (448 MB free at the start of this task, 180 KB at its worst, 204 MB after I cleaned): my SIM work dirs (`/tmp/r8_press_*`, `/tmp/r8_scan_*`, ~200-300 MB per 18-run batch) took the last space and one scan died on a truncated output (all its rows were discarded and the scan re-run from scratch on `/dev/shm`, 58 GB free; the tools now write `/dev/shm/r8_*` and delete it). Other workers' jobs may have hit write errors in that window (not checked). The space is held by other trees (`/workspace/smeR` and `smeR4`, 1.2 GB each, are RECON's own old trees and could go if the lead agrees). Nothing of mine is running; tree `/workspace/smeR6` (+ `r8/`, 268 KB: the plans and the scan list used here).
### 15.6 Restart
`cd /workspace/smeR6 && R=/workspace/smeR6 SME_TGT=1 SME_THREADS=4 CPUS=226-237 bash sme/recon/envR.sh python3 recon/r8_press.py PLAN FRAMES SIDE CMD RUN1,RUN2 T0 T1 [--add] [--full]` (RUN 0 = as is, -1 = drop; SIDE = the GK's side); trace `... recon/r8_gk.py PLAN FRAMES SIDE T0 T1 [--areas]`; scan `bash r8/scan.sh` (resumable; `r8/scan_list.txt` = match, plan, frames). Use absolute paths for PLAN / FRAMES (envR.sh changes directory).
