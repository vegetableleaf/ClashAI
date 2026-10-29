# P4 incentive audit by SIM forks (P3-FORK2, 2026-10-28)

Labels: (a) measured (number + source), (b) plausible, untested, (c) contradicted.
Source: run `cfaud3` (pod 32657, crforge fe364ceb, CLXIII-init policy FIXED, critic warm-up, `cf_diag`): 1,024 matches, updates 2-7 = 768 matches,
**1,926 fork samples**, K 2 CRN continuations, horizon 900 ticks (45 s) with Q also read at 150/300/450/600/750, 40% of samples run to the match end.
Full tables (all splits, 90% cluster-bootstrap CIs over matches): `P4_TABLES_cfaud3.md`; machine form `data/cfaud3_audit.json` (gitignored);
tools `p4_audit.py` (tables), `p4_persona.py`. Opponents = the pilot league (CLXIII copies with drawn `opp_style`, the human-timing exploiter w14opp_I, census decks).
Every number is a within-sample difference **alternative minus the policy's own action** in the K-mean return Q (+-1 = a win; win probability = dQ/2),
so "-0.24" = a 12-point lower win probability. Negative here does NOT mean the behaviour is bad for a human; it means the SIM, with this policy
continuing afterwards, pays less for it than for the policy's action.

## 0. Four findings that change the plan
1. (a) **Every Rocket-family alternative is priced clearly negative at 1x/2x and ~0 only in overtime**, and the terminal (match-end) audit agrees with the
   45-s Q: chip Rocket on the weakest princess dQ -0.24 [-0.30, -0.18] at 45 s vs **-0.22 [-0.36, -0.09] to the match end** (n 97 audited). So the
   verdict is NOT a short horizon and NOT critic bias in sign (see 3).
2. (a) **Raising cf_w now would train the policy AWAY from the required behaviours**: R_fork gives the Rocket / combo / king-pull alternatives negative
   advantage and the policy's own action positive. At the current 1x budget the share is small (design note, section 7), which is why it has not shown up.
   Until the causes below are fixed the Rocket-family triggers must stay (NO-DISCARD) but R_fork must not be weighted up for them.
3. (a) The SIM prices the Rocket's cost in the learner's OWN defence and tempo, not in the opponent's punishment: after a Rocket the learner loses
   +0.20 [+0.16, +0.23] more princess HP (sum of fractions) and lands 0.35 fewer plays in 45 s, while the opponent lands 0.19 fewer plays; the Rocket's own chip
   (+0.10 of a princess) is outweighed (foe princess HP lost -0.08 net vs the policy's action).
4. (a) The price falls monotonically with the match clock: chip Rocket -0.33 (1x) / -0.14 (2x) / +0.01 [-0.07, +0.10] (OT, n 29). Humans' Rocket lift lives in
   2x/OT (macros: Rocket cycling after failed X-Bows in 2x/OT **+0.082 [+0.030, +0.143]**, pros 25.1% vs CLXIII 2.1%). Direction agrees, level does not.

## 1. Verdict per behaviour (P4 expected signs; main horizon dQ vs the policy's action, 90% CI, n samples)
| behaviour (PLAN P4 expected sign) | SIM (a) | human / live evidence | verdict |
|---|---|---|---|
| Rocket on Ram Rider / Balloon / Royal Hogs with Tesla out of cycle: **+** | wincon `rocket_on`: hoglike -0.18 [-0.27, -0.09] (n 38); Tesla not in hand -0.25 [-0.36, -0.15] (n 47); in hand -0.11 | none on the exact cell (pros chip share 0.38 of investment plays; heavy-push Rocket in the answer pros 7.6% vs CLXIII 1.9%) | **WRONG SIGN**; static aim explained 0.08 of the -0.19 (section 6); still negative with drift (-0.10) |
| Rocket on a lone Golem: **-** | heavy -0.25 [-0.41, -0.12] (n 29) | -- | sign agrees, but so does every other target (no discrimination) |
| troop in front of a locked Mortar / X-Bow: **+** | siege `front` vs chosen -0.02 [-0.06, +0.03] (n 192); vs `troop_on` +0.02; terminal -0.04 [-0.18, +0.08] | macros: `sneaky_lock` win +0.007 [-0.042, +0.055] (not positive either) | **zero, unresolved** (power: +-0.05) |
| chip Rocket in a close overtime: **+** | OT +0.009 [-0.07, +0.10] (n 29); close-OT subset too small (<20) | pros chip 2.79 per Rocket-opportunity-minute in OT even vs CLXIII 0.44 live | **~0, not positive**; mismatch with pros is of LEVEL |
| X-Bow after failures vs a denier: **-** | `xbow_reach` vs chosen -0.03 [-0.13, 0.02] overall; vs denier decks -0.05 [-0.12, +0.03], vs others -0.02 | macros `def_xbow_hard` win +0.162 but 30 s margin -0.067 | sign agrees weakly, unresolved |
| Rocket cycling (`rocket`, `xbow_after_fail`->`rocket_princess`) | -0.24 / -0.26 (45 s); -0.22 / -0.25 terminal | pros +0.062 [-0.015, +0.148] win, 30 s margin +0.079 [+0.050, +0.117]; after2 +0.066 | **MISMATCH** (sign at 1x/2x, level in OT) |
| Rocket + Tornado combo vs the lone Rocket | combo - rocket_clump **-0.055 [-0.09, -0.02]** (n 299, the combo is WORSE); it does add foe princess damage (+0.041 [+0.02, +0.06]) and foe-king-side effects (own plays +0.11) but costs 3 more elixir (dPhi -0.033 [-0.05, -0.01]) | macros `rocket_tornado_clump` win -0.020 [-0.133, +0.094] (no lift) | combo is NOT better than the lone blast in the SIM, and humans show no lift either; both well below "wait" (-0.37) |
| Tornado toward our king | tornado_king vs chosen -0.16 (n 252); **vs tornado_on (no pull) -0.048 [-0.08, -0.02]**, own princess HP lost +0.013 [-0.01, +0.03] (no saving), terminal -0.10 [-0.25, +0.05] | macros `king_redirect` pro -0.085 [-0.147, -0.016], HF +0.024 | SIM and pros agree in sign (negative, an association); **no princess-HP benefit from the pull in the SIM** -> fidelity item for ENG-SME (3.F) |

## 2. Situation splits that matter (dQ vs the policy's action, 90% CI; full list in P4_TABLES_cfaud3.md)
- chip Rocket (`rocket_princess`): 1x -0.33 [-0.38, -0.28] (n 160) / 2x -0.14 [-0.23, -0.05] (67) / OT +0.01 [-0.07, +0.10] (29); ahead -0.16, even -0.34, behind -0.12;
  safe & idle (no foe body on our half, policy waited) -0.26 [-0.32, -0.21] (n 159); foe on our half -0.14; X-Bow in hand -0.26 vs none -0.20; Tesla in hand -0.28 vs not -0.22;
  elixir >= 8 -0.38 vs < 8 -0.21. (The "displaces the policy's X-Bow" explanation predicts a bigger gap for X-Bow in hand: 0.06 only -> not the main cause.)
- combo by value: 6-8 elixir -0.29, 8+ -0.36 (the bigger clumps are not better); clump of the lone Rocket < 4: -0.49.
- xbow_after_fail: `rocket_princess` 1x -0.30 / 2x -0.19 / OT -0.05 [-0.15, +0.06]; `xbow_reach` 1x -0.06, 2x -0.06, OT +0.03 [-0.06, +0.13].
- tornado_king: ahead -0.13, even -0.15, behind -0.21; heavy -0.16, hog-like -0.17, other -0.16 (no unit-class discrimination: the owner's "works for some units" is not visible);
  distance < 6 tiles -0.20 vs 6+ -0.14.

## 3. Mismatch diagnosis by measurement (the five candidate causes of the PLAN)
A. **Horizon too short: contradicted for the Rocket (c).** dQ by horizon (same samples, audited, n 97): 150 -0.11, 450 -0.17, 750 -0.24, match end -0.22 [-0.36, -0.09].
   The cost GROWS with the horizon and stays at the match end; no later payoff appears. For `rocket_clump` the terminal is -0.11 [-0.26, +0.03] (n 56): weaker but not positive.
   The macros' own finding that defensive X-Bow pays late (30 s margin -0.067, win +0.162) is a horizon case (b) not yet tested here: `xbow_defensive` is -0.13 at 45 s and
   -0.05 [-0.17, +0.09] at the end (n 101): the gap closes toward the end but the SIM never shows the +0.16. Needs the macro prefix with horizon 'end' (next item).
B. **Critic bias: partly, in magnitude not sign (a).** Within-sample slope of the terminal diff on the horizon diff (audited samples): rocket 0.56 +- 0.14 (n 121), rocket_tornado 0.52 +- 0.13 (191),
   siege 0.48 +- 0.15, xbow 0.72 +- 0.14, tornado_redirect 0.89 +- 0.17, wincon 1.01 +- 0.20, ALL **0.64 +- 0.05 (n 1,181)** - below the PLAN band [0.7, 1.3]. Calibrated, the chip Rocket is
   ~ -0.24 x 0.56 = -0.13 at the horizon (consistent with the terminal -0.22 [-0.36, -0.09]); still negative. The Phi part alone (tower P_hat, no critic) is also negative:
   dPhi -0.127 [-0.15, -0.11]; critic part -0.192. `cf_adv_scale` (landed) applies the calibration; the pooled slope is the number to use (0.64), per-trigger slopes are noisy.
C. **Opponent behaviour: contradicted as the primary cause for this effect (a); relevant for the missing human payoff (b).** SIM opponents DO punish the elixir spend in tower HP
   (own princess +0.20) but through OUR weaker defence/tempo (own plays -0.35, foe plays -0.19), not by attacking more. What the SIM may lack is what makes the chip pay for a human: an opponent
   that answers the Rocket-and-cycle plan badly or an overtime tiebreak that is decided by tower HP at the clock. Opponent realism is the P2-OPP / P2-SCORE business (SIM opponents convert
   mistakes 0.7% vs 6-7% live, REPORT_history). No SIM-opponent-only test can separate this without the human-like opponents (planned).
D. **Badly specified alternative: likely for the wincon `rocket_on` (b -> A/B running).** The alternative aims at the unit's present position; a Hog/Ram walks ~2-3 tiles during the
   Rocket's flight, and the measured static-aim coverage is 38% of a blast's value vs 46% with drift (oracle 79%, decision_options.py lines 1395-1398). `cf_rocket_lead=drift` (landed) aims
   `rocket_clump` and `rocket_on` where the bodies will be. Result of the A/B (`cfaud4`): section 6 (the aim explains 0.08-0.12 of the deficit; not the sign).
E. **Engine fidelity (Rocket damage): consistent with the tables (a).** SIM Rocket on a full-HP princess: +0.10..0.11 of a princess (sample: 0.112 of 4,858); tables: RocketSpell Damage 580,
   CrownTowerDamagePercent -77. The real-game number at level 16 is not measured here (b -> ENG-SME): a Rocket worth 11% of a princess for 4 elixir is the quantity the whole sign depends on.
F. **Engine fidelity (Tornado pull to the king): not observable as a benefit (a); mechanism unknown (b).** `tornado_king` vs `tornado_on` (same cast, no net pull): own princess HP lost +0.013 [-0.01, +0.03], own king HP lost +0.001,
   and dQ is -0.048 [-0.08, -0.02] (worse, because the pull costs the foe-princess chip: -0.004). If the pull worked as the owner describes the difference should be clearly negative in princess HP lost. Needs a scripted scenario (L74/fastplays harness: Hog
   at the bridge, Tornado centre toward the king, both princesses up) on crforge fe364ceb: does the Hog retarget to the king? -> ENG-SME.
G. **Tiebreak rule / OT: untested here (b).** OT dQ ~0 could still hide a missing tiebreak value of chip damage; 29 OT samples cannot resolve it. A direct test: forks rooted in OT at even crowns with the
   horizon running to the end (needs a scenario start with OT, `ot_start_share`) - proposed below.

## 4. Persona fork test (HUMANLIKE.md 10.2 (c)), trigger `xbow_after_fail`, 207 samples / 168 matches (`p4_persona.py`, `data/cfaud3_persona.md`)
Contrasts: X-Bow again (`xbow_reach`) - wait; chip Rocket - wait; Rocket - again. Personas = opponent type, the drawn opp_style dims (halves at the range middle), opponent deck archetype.
- (a) **No sign change of any contrast in any persona at the power available** (again - wait: every level between -0.12 and +0.11, almost all CIs include 0).
- (a) Opponent archetype is the one dimension that moves again - wait: royal_giant +0.106 [-0.07, +0.32] (n 19), other -0.002, weak_other -0.024, hyperbait **-0.120 [-0.20, -0.03]** (n 23);
  hyperbait - royal_giant -0.227 [-0.45, -0.03]. Sign pattern is the doctrine's (X-Bow again is good vs Royal Giant, bad vs bait); each cell is n 19-49 so this is (b)-grade until the pooled run is bigger.
- (a) Style dims (bank, aggression, lane bias, temperature, spell delay): no difference resolved for again - wait (half-vs-half diffs -0.07..+0.04, CIs +-0.09);
  the Rocket cost is smaller vs high spell-delay opponents (-0.09 vs -0.22, diff -0.13 [-0.24, -0.03]) and temperature >= 1 (-0.09 vs -0.20): same sign everywhere, size changes.
- Reading for P2-OPP: the SIM opponents' DECKS (archetypes) carry the persona dependence the memory needs; the drawn style knobs and the opponent model type carry none (power +-0.09). Memory has little to
  learn from the current SIM opponents beyond the deck matchup it already sees; a human-like opponent whose X-Bow answers differ is needed before adaptation can be audited.
- Power: ~40-100 samples per level; detectable half-vs-half difference ~0.12. A larger persona run (forced persona dims, xbow_after_fail p 0.1) would take ~3 h on the 26-actor budget.

## 5. Human evidence used (macros/LIBRARY, sha 828cedf7..., MACROS.md; associations in matched cells, never causal)
rocket_cycle (pro) win +0.062 [-0.015, +0.148], 30 s margin +0.079 [+0.050, +0.117], horizon 600; after failed X-Bows in 2x/OT +0.082 [+0.030, +0.143]; rocket_tornado_clump no lift; rocket_tornado_tower win -0.025;
king_redirect pro -0.085 [-0.147, -0.016] / HF +0.024; def_xbow_hard win +0.162 [+0.080, +0.238] (30 s margin -0.067, horizon 1200); sneaky_lock +0.007. Pro chip relationship in the PLAN
(0 chips 0.392 -> 2+ 0.564) is an association with the confounder "pros chip when safe"; the SIM's 0.696 vs 0.582 is also an association. The fork numbers above are CAUSAL within the SIM, so the correct
comparison is fork-vs-macro-lift on the same situation cell (done in the table of section 1), not fork-vs-win-rate-by-chip-count.

## 6. cfaud4: A/B of the drift-aimed Rocket alternatives (cf_rocket_lead = drift; triggers rocket / wincon / siege / rocket_tornado; updates 1-4 = 512 matches)
One change vs cfaud3 (same code otherwise, same pool; independent samples; table `P4_TABLES_cfaud4.md`). dQ vs the policy's action, static aim (cfaud3, updates >= 1) -> drift aim (cfaud4):
| alternative | static | drift | reading |
|---|---|---|---|
| wincon `rocket_on` | -0.185 [-0.26, -0.12] (n 85) | **-0.103 [-0.17, -0.04]** (n 77) | aim explains ~0.08; 2x -0.070, OT -0.084 now include 0; still negative (a) |
| rocket_tornado `rocket_clump` (the lone blast next to the combo) | -0.277 [-0.32, -0.24] | **-0.152 [-0.19, -0.11]** (n 245) | aim explains ~0.12 (a) |
| rocket `rocket_clump` | -0.205 [-0.26, -0.15] | -0.166 [-0.23, -0.10] (n 100) | small; 2x -0.06, OT -0.08 now include 0 |
| rocket `rocket_princess` (control, no lead) | -0.236 | -0.230 | unchanged, as it must be (b: the A/B has no hidden drift) |
| rocket_tornado `combo` (already drift-aimed) | -0.321 | -0.325 | unchanged (control) |
| siege `rocket_on` | -0.214 (n 87) | -0.259 (n 36) | not improved (n small; siege targets are buildings: no walk) |
Verdict (a): the static aim was a real specification defect worth 0.08-0.12 on the Rocket-at-a-body alternatives; with it fixed the Rocket on a Hog-like/heavy wincon is -0.10 (was -0.19) and
the wincon `rocket_on` is no longer resolved negative in 2x / OT - but nothing turns positive. Remaining gap (open): the wincon expected sign is still wrong at 1x (-0.15 [-0.27, -0.04]); the chip cost (section 0.3) is untouched by
the aim. Next causes in order of cost: (1) the policy-continuation after a Rocket (a Rocket-aware continuation, i.e. the macro prefix with the learned policy masked for the window), (2) the wincon alternative lands in a state where the policy would have
used Tesla/Knight: the audit compares to the policy's own action, so a good habit is the baseline (this is correct, not a defect), (3) engine fidelity (3.E, 3.F). `cf_rocket_lead` stays opt-in OFF in code; the lead should switch it on for
production runs (drift is what the live decoder's `rocket_value_lead` uses): that is a one-key decision, hash-neutral until set.
The run then died at update 5: an ENGINE exception in a fork actor (crforge fe364ceb): `UnsupportedOperationException: Deflect_3000014 deflects proj_4000359 from the king tower KingTower_0_0 without a target, which is not modelled`
(CfCore.step; seen twice, actor 24; no such crash in cfaud3's 1,024 matches; the drift-aimed Rocket lands elsewhere). For ENG-SME: a projectile deflected by the king tower with no target is unmodelled; `data/cfaud4.log.txt` lines 74-100.

## 7. Design note: raising fork credit's share of the gradient (for the lead / owner; no code)
Numbers (a, cfaud3 / pilot4): real rows ~325 per match (41.6k per 128-match update); sd of real GAE advantage 0.174; cf rows (after shrink) |A| 0.36-0.54; cost ~12-14 s of actor wall per
1x of fork ticks per match (match wall ~106 s unforked); alt rows per match ~1.4 per 1x (5.7 at 4x); K 2, horizon 300-900. The learner-bound fast loop (PRO 6000 box, ~2,048 matches/update)
makes the rollout wall largely free until rollouts become the bottleneck (b: LOOP-INT must give the actual split).
- Gradient energy share, crude (sum of A^2 over rows): 0.71x budget (the pilot4 defaults) -> ~1.3%; 4x -> ~7%; proportional to cf_w^2 (cf_w 2 -> 4x those). The earlier "0.1-0.2%" counted rows, not energy.
- Information, not energy, is the point: a cf row has SNR ~1 (reliability-shrunk) vs ~0.2 for a win-only row (PLAN), i.e. ~25x the information per row on those decisions. At 2,048 matches/update the 0.71x budget
  gives ~2,900 samples per update (about 8 per trigger-class per 100 matches) - enough for the trigger decisions, not for the rest of the policy.
- Knobs, ranked by cost per unit of credit: (1) cf_w 2-3 at the same budget (free in compute; keep cf_clip 3; noise is controlled by shrink; (b) stable up to w ~ 3-5); (2) cf_adv_scale 0.64 (the measured slope) first,
  so the unit is calibrated before weighting (net effect w x 0.64); (3) budget x2-4 only for the triggers with the largest SNR x |dQ| (rocket_tornado, tornado_redirect, xbow: SNR 1.2-2); (4) drop cf_audit_p to 0.05 in
  production (the audit runs 5-10x cheaper than the terminal forks it needs; keep 0.3 only in gate runs); (5) K 3 only for idle_full / log_bait.
- **Blocking condition (a):** do (1)-(3) only after the Rocket-family prices are fixed or gated (section 0.2). Gate option that keeps the triggers: weight R_fork per trigger (cf_w_by trigger, not built), start Rocket-family
  triggers at weight 0 (they still log and are audited each update) and raise them as the audit signs turn right.

## 8. Routing (for the lead)
- ENG-SME: (0) crforge fe364ceb raises UnsupportedOperationException `Deflect_3000014 deflects proj_4000359 from KingTower_0_0 without a target` in CfCore.step (cfaud4, section 6); (i) Rocket tower damage and level-16 scaling vs the real game (SIM 11% of a princess for 4 elixir); (ii) Tornado pull to the king: scripted Hog-at-bridge scenario, does the unit retarget the king / lose princess HP; (iii) OT tiebreak rule value of tower HP.
- P2-OPP: SIM opponents do not reproduce the human response to elixir-spending plans (conversion 0.7% vs 6-7%); persona dependence exists only through the deck archetype; a persona-forced run needs opponents that
  differ in X-Bow answers.
- P6-MACRO / P3-FORK (next): prefix alternatives for rocket_cycle after failed X-Bow in 2x/OT (horizon 600, 'after2') and def_xbow_hard (horizon 1200 / end, K 2); credit on every prefix action; the OT / 2x state roots (`ot_start_share`)
  are the cheapest place to test whether the SIM pays the humans' Rocket lift.

## 9. P3-FORK3 (2026-10-29): why the SIM prices the Rocket family negative -- artifact checks (owner 10-29)
Job: find the cause; remove it if it is a SIM / opponent / measurement artifact; never tune numbers. Runs on pod 32657, crforge
**5e8089a4** (facade c003fc74 -> build_5e, tables 16.402.22), tree cfh9 = commit 8743a53 (minus the opt-in redirect key), CLXIII
init fixed (critic warm-up only), K 2, horizon 900 + sweep 150..1200, audit 30% to the end, cf_diag + plays, rocket_empty, macros on.
Arms: **base** f3base2 = the cfaud3 pilot league (5 x 128 matches, updates 1-4 used = 512 matches, 1,820 samples; CLXIII wins 68%
of the real matches); **ftR** f3ftR3 + f3ftR4 = every matchup vs ftR (opp_ft_s0_R_sim.pt 28ef721b, T 1, live training census);
**oplcB** f3oplcB3 = vs arm B u0120 (7aefe312); f3redir = base + cf_redirect_king_tiles 9 (tornado_redirect only). Tables: `P4_TABLES_f3base2.md` (p4_audit), `P4_F3_ARMS.md` (fork3_tables.py, all updates).
Numbers: dQ in the return (+-1 = a win: win probability = dQ / 2), alternative minus the policy's own action unless named,
90% match-cluster bootstrap CI; "terminal" = the audited match-end return; HP in princess units (sum of the two princesses).

### 9.1 Decomposition: the chip is priced POSITIVE; spending the Rocket is what costs (a, base)
| contrast | 45 s | terminal |
|---|---|---|
| rocket_princess - chosen (chip Rocket) | -0.230 [-0.264, -0.196] (n 349); 1x -0.298, 2x -0.129, OT -0.071 | -0.087 [-0.236, +0.055] (n 112) |
| rocket_empty - chosen (Rocket into nothing: 4 elixir + the card) | -0.321 [-0.363, -0.280] (n 317); 1x -0.401, 2x -0.219, OT -0.087 | -0.243 [-0.387, -0.097] (n 103) |
| rocket_princess - rocket_empty (the chip itself) | **+0.089 [+0.064, +0.113]** (1x +0.106) | **+0.181 [+0.070, +0.293]** |
At idle, safe moments (the policy waited, no enemy body on our half, 1x) the empty Rocket costs -0.378 [-0.453, -0.307] and +0.229
own princess HP over 45 s; the cost grows steadily (own princess +0.014 / +0.044 / +0.107 / +0.170 / +0.205 at 150 / 300 / 450 /
600 / 750 ticks) while the policy's own line out-damages the foe by 0.125 more. So the SIM pays for the chip (+0.18 at the end);
the negative total is the price of 4 elixir + the Rocket card spent at a moment the policy did not choose.

### 9.2 Estimand: on the SAME estimand the SIM reproduces the human / live numbers (a)
The human lifts are associations at moments people CHOSE; the fork prices a Rocket FORCED at a random affordable decision. The
association computed inside the SIM (`sim_assoc.py`: CLXIII's own chip Rockets, rocket_played samples aimed within 3 tiles of a
princess, vs "Rocket affordable, not played" moments; own princess HP lost over the next 45 s of the policy's own continuation):
| own princess HP lost, chip Rocket - control, 1x | value |
|---|---|
| SIM base (5e8089a4) | -0.033 [-0.077, +0.013] (46 vs 283) |
| SIM cfaud3 (fe364ceb) | +0.008 [-0.042, +0.061] (69 vs 221) |
| live CLXIII vs humans (opp_response.py, 858 matches) | +0.004 [-0.043, +0.056] (29 vs 50,361) |
| pros vs humans (1,606 matches) | -0.005 [-0.023, +0.016] (327 vs 91,572) |
All four agree: no defence cost at chosen moments. The forced Rocket: +0.192 [+0.160, +0.223] (base). The policy's own Rockets vs
waiting: cfaud3 -0.035 [-0.072, +0.001], base +0.040 [-0.029, +0.110] (wait - chosen; both include 0). Reading: the "SIM negative /
humans positive" contrast compared two estimands; the SIM is not shown to misprice the moments humans use. No human data price a
Rocket at a random moment, so the forced price can be neither confirmed nor refuted by them.

### 9.3 Opponent (ticket item 1)
Arms on 5e8089a4, ALL updates pooled (u0 included: the Q columns carry the un-adapted critic for ftR / oplcB; the HP columns are raw
tower HP and critic-free). base 640 matches, ftR 384 (f3ftR3 2 updates + f3ftR4 1, seeds 101 / 202), oplcB 128 (u0 only: the
arms were stopped at the lead's 10-29 wrap-up). CLXIII wins 66% / 87% / 72% of the real matches.
| forced chip Rocket (rocket - chosen) | base | ftR | oplcB |
|---|---|---|---|
| dQ 45 s | -0.227 [-0.258, -0.195] | -0.235 [-0.277, -0.196] | -0.208 [-0.283, -0.128] |
| dQ terminal (audited) | -0.089 [-0.214, +0.044] (146) | -0.468 [-0.673, -0.261] (66) | -0.126 [-0.445, +0.205] (23) |
| Rocket into nothing dQ 45 s | -0.315 [-0.351, -0.278] | -0.302 [-0.344, -0.260] | -0.337 [-0.416, -0.265] |
| chip itself (princess - empty) | +0.086 [+0.065, +0.108] | +0.069 [+0.041, +0.096] | +0.141 [+0.086, +0.208] |
| OWN princess lost 45 s (their punishment) | +0.171 [+0.146, +0.197] | **+0.115 [+0.090, +0.142]** | +0.110 [+0.051, +0.169] |
| FOE princess lost 45 s (our displaced line) | -0.048 [-0.069, -0.029] | **-0.117 [-0.149, -0.084]** | -0.157 [-0.227, -0.089] |
| foe plays landed | -0.112 | -0.142 | -0.217 |
| rocket_cycle (after2) to the end | -0.051 [-0.090, -0.014] (775) | -0.049 [-0.130, +0.023] (178) | +0.017 [-0.076, +0.106] (73) |
| def_xbow def - bridge 1200 ticks | -0.081 [-0.138, -0.025] | -0.101 [-0.171, -0.032] | -0.076 [-0.175, -0.005] |
Reading (a): with the human-imitation opponents the opponent's punishment of the spend is ~1/3 smaller (own princess +0.115 vs
+0.171), but CLXIII's own displaced line is worth 2-3x more against them (they let X-Bows lock: lock .73-.78 vs live .47), so
the total price does not move (-0.235 / -0.208 vs -0.227) and no contrast changes sign. The opponent model is relevant in BOTH
directions and neither available model is calibrated on X-Bow defence (P2-OPP / OPP-SIEGE2 business); with a human-calibrated
lock rate (.47) the displaced-line term would shrink (b, untested). Comparison with humans: section 9.2 (association, which the
SIM matches).

### 9.4 Horizon / value (item 2)
(a) The terminal agrees in sign with the 45-s read for the spend (-0.243 vs -0.321) and the chip's value is larger at the end
(+0.181 vs +0.089); the net chip Rocket is -0.087 [-0.236, +0.055] at the end (cfaud3: -0.22 [-0.36, -0.09]): smaller than at 45 s
(the horizon Q exaggerates, slope ~0.6 as in section 3.B) but not positive. The macros below run to the end.

### 9.5 Macros vs CLXIII's own continuation (item 4; library 828cedf7)
| | SIM base | human (MACROS.md) |
|---|---|---|
| rocket_cycle.after2: Rocket the lower princess now - policy (2x / OT, >= 2 failed X-Bows; the policy itself Rockets within 600 ticks in 1% of continuations) | end -0.062 [-0.103, -0.021] (n 619: OT 489 -0.057, 2x 130 -0.079); 600 ticks -0.066 [-0.096, -0.036]; 30-s margin -0.041 [-0.065, -0.018] | win +0.091 [+0.033, +0.153]; 30-s margin +0.082 [+0.058, +0.108] |
| def_xbow_hard: defensive X-Bow (+ counter-lock, fired in 77% of continuations) - bridge X-Bow (vs EQ / HOG / BEATDOWN, answer ready / short) | 1200 ticks -0.066 [-0.121, -0.010] (n 126); 600 -0.130 [-0.171, -0.090]; 30-s margin -0.147 [-0.187, -0.107]; end +0.044 [-0.174, +0.258] (n 35) | win +0.117 [+0.070, +0.166]; 30-s margin -0.058 [-0.081, -0.034] |
| def_xbow: wait - the policy's X-Bow (hostile matchups) | 1200 ticks +0.042 [-0.009, +0.094] | -- |
Reading: rocket_cycle: a MISMATCH remains (SIM -0.03 win prob vs human +0.09), smaller than for the generic chip Rocket (-0.12);
association vs causal applies (humans pick the moment inside the 30-s window; the fork picks a random affordable one). def_xbow:
the SIM shows the human time profile (it gives up chip early: 30-s margin negative in both) and is ~0 at the end (n 35, CI +-0.2):
not resolved; no contradiction.

### 9.6 Engine on the Rocket path (item 3; SME.md, ENG's measurements, not re-run here)
(a) Elixir regen exact (178 / 357 per tick, both sides to 1e-4); Rocket crown-tower damage 546 = live 7/7; overtime tiebreak = the
game (15 FRESH2/3 OT matches exact to the end); strict fresh battles exact 109/132 (CP lower 0.762): given the same plays, fights
and tower HP match live, so the forced-Rocket defence cost comes from the two policies' choices, not the engine (b: the inexact
battles are not split by play phase). (a) Tornado to our king: crforge DOES activate our king when the pull brings the unit near
it (cfaud3 tornado_king - tornado_on, units < 9 tiles from our king: king activated +0.061 [+0.019, +0.122] at 150 ticks, own
princess lost -0.038 [-0.086, +0.007], dQ +0.020 [-0.038, +0.080] (n 53)); the negative average came from far units (9-12 tiles:
-0.109 [-0.169, -0.052], n 103): a badly specified alternative (the trigger accepts units within 12 tiles of our PRINCESS). Fix
built opt-in: `cf_redirect_king_tiles` (null = off). Base arm: tornado_king - tornado_on -0.013 [-0.048, +0.020] at 45 s, terminal
+0.104 [-0.093, +0.314] (n 54).

### 9.7 Verdict per candidate cause (graded)
| cause (PLAN P4) | grade | evidence |
|---|---|---|
| engine fidelity (Rocket damage, elixir, tiebreak) | (c) not the cause | ENG SME: 546 = live, regen exact, OT tiebreak exact (9.6) |
| engine fidelity (Tornado to king) | (c) not an engine gap | king activates +0.061..+0.069 when the unit is near; spec fix below |
| badly specified alternative: tornado_redirect target | (a) artifact, FIXED opt-in | cf_redirect_king_tiles 9 (f3redir, 256 matches): tornado_king - tornado_on +0.003 [-0.026, +0.031] (n 234; was -0.013 base / -0.048 cfaud3), our king activated +0.069 [+0.042, +0.098] at 7.5 s, own princess lost +0.015 [-0.007, +0.036] (no princess saved), terminal -0.081 [-0.257, +0.088]: the negative price was the far units; the pull itself is ~0, not positive |
| badly specified alternative: static Rocket aim | (a) partial artifact (P3-FORK2, cfaud4) | drift aim recovers 0.08-0.12 on rocket_on / rocket_clump |
| measurement / estimand (forced vs chosen moments) | (a) explains the SIM-vs-human contrast | 9.2: same estimand -> SIM = live = pros (no defence cost at chosen moments) |
| opponent punishment | (a) moves the parts, not the total | 9.3 |
| horizon too short | (c) for the price; partly for the size | terminal -0.087 base (smaller than 45 s, not positive); rocket_cycle to the end -0.05 |
| critic bias | (a) magnitude only | slope ~0.6 (section 3.B); terminal signs agree |
**Verdict for the owner: (a) the negative price of a chip Rocket FORCED at a random affordable moment is real in this SIM after every
artifact check above** (engine exact, opponent model swapped twice, horizon to the end, spec defects fixed): it is the price of
4 elixir + the card at a moment the policy did not choose (-0.30 at 45 s, -0.24 at the end), while the chip itself is paid +0.09 /
+0.18. It does NOT contradict the human data: on the human estimand (chosen moments) the SIM gives the human answer (9.2). What the
SIM does not show anywhere is a state class where a forced Rocket is positive: OT -0.07..-0.11, rocket_cycle after2 -0.05 (humans'
association +0.09). Open (b): (i) a human-calibrated X-Bow defence in the opponent (lock .47) would cut the displaced-line part;
(ii) "chosen-like" moments: a Rocket alternative restricted to states where the policy's own Rocket probability is high (the
estimand humans and CLXIII's own Rockets share) is the next measurement; (iii) the Rocket weight-0 decision stays with the owner.
