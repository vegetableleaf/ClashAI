
## Remaining failures of n9P (1 unflagged; 108 / 109, 278,863 exact frames; A2c-9N on bp9Y1)
n9P = bp9Y1's command (sme9 code, lib_f635c, SME_LATE9 + SME_MADE9, `bp9/run9.sh`) on inputs_v28 (`65b5e131` = v27o +
SME_IWPEND9: 10 opponent hero Ice Wizard presses in 7 matches get the run window back to their last valid-target frame).
0 regressions; 133 matches byte-identical to bp9Y1 (reproduced on pod 33920 as n9Y, sorted sha256 `5893ab91`). Fixed by it:
`171753` (press 3333 -> 3291), `014928` (5215 -> 5181); `211239` 1532 -> 4894 (1571 -> 1531) (SME.md A2c-9N).

| match | first div | class | mechanism (D1) | evidence |
|---|---:|---|---|---|
| `20261026_211239` | 4894 | body position | an opponent hero IW press held pending and never cast (the hero dies first); its re-search is the 5-unit turn | A2c-10 (ghost press, R = 4892 the only exact run in a 149-run sweep) |

## Remaining failures of bp9Y1 (3 unflagged; 106 / 109, 276,782 exact frames; A2c-9R on r93)
bp9Y1 = r93 (sme9 code, SME_LATE9 + SME_MADE9) on inputs_v27o (`ab3c7114`: same-tick plays of the two sides in the reader's
creation order, `bp9/order_inputs.py`); 0 regressions, 115 unchanged-input matches byte-identical to r93. Fixed by it:
`000233`, `164443`, `170912`, `180336`, `101112`, `172835`, `222712` (SME.md A2c-9R).

| match | first div | class | mechanism (D1) | evidence |
|---|---:|---|---|---|
| `20261026_171753` | 3293 | body position | opponent hero IW + cube 1 unit off in y (untraced, b) | A2c-9T 9.1 |
| `20261026_211239` | 1532 | body position | target death -> first move: the game's target-lost timer reaches attackFinishTime one tick before crforge's (b for the cause) | A2c-9R; BP4/BP5 death census 5 earlier / 2,052 |
| `20261027_014928` | 5183 | body position | a fresh route search adopted at 5182 with no crforge trigger (no goal, occluder or target change; b for the trigger) | A2c-9R; BP5 aim fit |

## Remaining failures of r87 (13 unflagged; 96 / 109, 264,960 exact frames; round 8)
First divergence from r87's results. Class from cls6 on r78 (`results/live/a2c8_cls_r78.tsv`; the sweep found no
single-command shift for any onset). Owners follow the ticket.

| match | first div | class | layer | owner | evidence |
|---|---:|---|---|---|---|
| `20261026_101112` | 5923 | body position | crforge goal flip vs the game's held route (route-kept class) | 9R | Fireball contradicted (lands ~5933, 6,000+ away); reference Skeleton enters a new cell row at 5923, crforge goal 855 -> 891, game keeps route (A2c-9T 9.3) |
| `20261026_164443` | 3213 | body position | crforge | BP | Ram landing push (BP3 item 2) |
| `20261026_170912` | 745 | body position | crforge | BP | near-node rebuild (BP3) |
| `20261026_171753` | 3293 (was 1789) | body position | unknown (b) | open | 1789 fixed by SME_LATE9 (birth-stamped R = 1768, frame 1770 torn_late; A2c-9T 9.1); next: opponent hero IW + cube 1 unit off in y, 30 at 3303 |
| `20261026_172835` | 2831 | body position | crforge goal flip vs the game's held route (route-kept class) | 9R | crforge re-plans 2830 (goal 1031 -> 1032 -> 1031 at 2832) as its reference WitchMother starts moving; game walks straight (A2c-9T 9.4) |
| `20261026_180336` | 2911 | body position | crforge | BP | Elite Archer hero stop (BP3) |
| `20261026_204518` | 723 | hp only | extractor | Zap (open) | unextracted Zap: X-Bow ZapFreeze made 722, 306 damage (A2c-M) |
| `20261026_211239` | 1532 | body position | crforge | BP | hero IW first move 1 tick early after target death (BP3) |
| `20261026_222712` | 4742 (was 4183) | body position | unknown (b; heading change, route-kept shape) | open | 4183 fixed by SME_MADE9 (Earthquake R 4182 -> 4183 from the area clock; frame 4183 torn_snap; deploy push contradicted; A2c-9T 9.2); next: our Skeleton step (-17, -96) vs (-43, -83) |
| `20261027_000233` | 4599 | body position | crforge | BP | skeleton 2 units off before a rebuild (BP3) |
| `20261027_001702` | 2492 | body in the sim, none near in the reader | extractor | A2c-M | inferred Zap point ~1000 off (A2c-M) |
| `20261027_010245` | 573 | hp only | extractor | Zap (open) | unextracted Zap: princess tower ZapFreeze, 77 damage (A2c-M) |
| `20261027_014928` | 5183 | body position | crforge / deploy-end (b) | BP | hero IW turns after a BarbLog Barbarian ends deploying (BP6 lead) |

Fixed in round 8 (from r78's 21):
- `165839`, `041602`: evolved Goblin Barrel point (8.1).
- `235355`: hero Balloon throw (8.1).
- `192935`: CROSS (8.3).
- `181217`: torn_hidden (8.4).
- `224856`: banner press (8.5).
- `001141`: GK8 (8.6).
- `225213`: drill point (8.1) + own charge drop (8.7).

## r78's 21 (round 8 item 1), for reference
`a2c8_cls_r78.tsv` lists the 20 first onsets plus `225213` (refused by crforge). Classes:
- body position 10;
- projectile only 3 (`165839`, `235355`, `041602`);
- hp only 3 (`192935`, `204518`, `010245`);
- body in the sim, none near 2 (`181217`, `001702`);
- Earthquake 1 (`222712`);
- body in the reader, none near 1 (`224856`).

## Every remaining failure of r6xc (29 unflagged + `225213` refused by crforge: GoblinDrill evolution after a refused play)
From `diag6.py` / `sweep6.py` / `cls6.py` on r6xc's plans (`results/live/r6xc_{diag6_x,sweep6_x}.jsonl`, `r6xc_cls6_x.tsv`). The class comes from cls6. Layer and evidence come from the dossiers of this round and the BP line; "unknown" means not traced. Closest sim tick is the sim tick nearest the onset frame.

| match | first div | class | layer | evidence |
|---|---:|---|---|---|
| `20261026_080929` | 2007 | body position | crforge / unknown | hero IW cube 60 units off; BP fresh worker. U_rec IceWizard (-1, 60); U_rec IceWizard (-1, 60); U_sim IceWizardHero (1, -60); closest sim tick t0+1 (2 diffs), el=t+1; 44 div frames |
| `20261026_094126` | 3485 | body position | crforge / unknown | hero IW cube; BP fresh worker. U_rec IceWizard (-25, 18); U_rec IceWizard (-25, 18); U_sim IceWizardHeroFloatingCube (25, -18); closest sim tick t0+0 (5 diffs); 872 div frames |
| `20261026_101112` | 660 | partial:ext:hero_cast:IceGolemite | extractor | hero Ice Golem cast; sweep +2 partial. U_rec Knight (0, 0); U_sim Knight (0, 0); A_sim IceGolemiteHero_Damage_AEO None; closest sim tick t0+0 (4 diffs); sweep: ability:cmd10_0 side0 dR+2 -> 662; 2677 div frames |
| `20261026_145247` | 3032 | body in the sim, none near in the reader | reader | step read (el=t+1), dead Skeleton 287 from its t point > STEP_MOVE 200; 1 div frame. U_rec Knight (5, -50); U_rec Skeletons (-16, 271); U_rec Xbow (0, 0); closest sim tick t0+1 (1 diffs), el=t+1; 1 div frames |
| `20261026_154319` | 5997 | body position | comparator | in-step read: exact in bpD (SnapRun2 on the clashbot-bp TickProbe build, not built here). U_rec Tesla (0, 0); U_rec Xbow (0, 0); U_rec GoblinHut (0, 0); closest sim tick t0+0 (8 diffs); 1 div frames |
| `20261026_164443` | 3213 | body position | crforge | Ram landing push order (BP, n=1). U_rec RamRider (-15, -2); U_rec RamRider (-16, -2); U_rec Skeletons (1, -9); closest sim tick t0+0 (6 diffs); 99 div frames |
| `20261026_165839` | 2539 | projectile only | crforge / unknown | evo Goblin Barrel decoy lateral offset (game +-258, sim smaller). P_rec GoblinBarrel (258, -68); P_rec GoblinBarrel (-258, -68); P_sim GoblinBarrelSpell_EV1_Decoy (-258, 68); closest sim tick t0+0 (4 diffs); 318 div frames |
| `20261026_170912` | 745 | body position | crforge | single replan (BP). U_rec Skeletons (-2, 19); U_sim Skeleton (2, -19); closest sim tick t0+0 (2 diffs); 4 div frames |
| `20261026_171753` | 1770 | partial:ext:own_play | extractor | own Knight tap-dated 2+ ticks early vs the elixir drop. U_sim Knight None; S0_elixir None 65060; closest sim tick t0+0 (2 diffs); sweep: Knight side0 dR+2 -> 1789; 1466 div frames |
| `20261026_172835` | 2831 | body position | unknown | Knight 30 units + WitchMother projectile 9 units. U_rec Knight (-30, -21); U_sim Knight (30, 21); P_rec WitchMother (-9, 1); closest sim tick t0+0 (4 diffs); 45 div frames |
| `20261026_180336` | 2911 | body position | crforge | single replan (BP). U_rec EliteArcher (9, 23); U_sim EliteArcherHero (-9, -23); closest sim tick t0+0 (2 diffs); 169 div frames |
| `20261026_181217` | 3041 | body in the sim, none near in the reader | extractor / unknown | sim-only hero Mini PEKKA body after its cast_seen ability. U_sim MiniPekkaHero None; closest sim tick t0+0 (1 diffs); 28 div frames |
| `20261026_183044` | 2978 | ext:hero_cast:Bowler | extractor | hero Bowler cast_seen 3 ticks late. P_rec Bowler None; closest sim tick t0+0 (1 diffs); sweep: ability:cmd32_0 side1 dR-3 -> clean +400; 87 div frames |
| `20261026_192935` | 382 | hp only: sim less/mixed damage at the same points | unknown | Knight 429 hp: X-Bow bolt landed in game, in flight in sim. U_rec Knight (0, 0); U_sim Knight (0, 0); P_sim xbow_projectile None; closest sim tick t0+0 (3 diffs); 1 div frames |
| `20261026_204518` | 723 | hp only: sim less/mixed damage at the same points | unknown | X-Bow 306 hp less in sim. U_rec Xbow (0, 0); U_sim Xbow (0, 0); closest sim tick t0+0 (2 diffs); 1479 div frames |
| `20261026_211239` | 1532 | body position | crforge | single retarget (BP). U_rec IceWizard (2, 60); U_rec IceWizard (2, 60); U_sim IceWizardHeroFloatingCube (-2, -60); closest sim tick t0+0 (4 diffs); 113 div frames |
| `20261026_222712` | 4183 | Earthquake pulse timing | unknown | Earthquake area, el=t+1, after a hero IW deploy. U_rec IceGolemite (-8, -34); U_rec BombTower (0, 0); U_rec IceWizard (139, -175); closest sim tick t0+1 (5 diffs), el=t+1; 160 div frames |
| `20261026_224856` | 493 | body in the reader, none near in the sim | extractor | hero Goblins bodies with no sim body (2nd wave after 6.9). U_rec Goblins None; closest sim tick t0+0 (1 diffs); 36 div frames |
| `20261026_233957` | 5461 | body in the reader, none near in the sim | comparator | in-step read: exact in bpD (SnapRun2, TickProbe build). U_rec ElectroDragon (1, -42); U_rec Knight (-28, 31); U_rec Tesla (-5933, -4992); closest sim tick t0+0 (6 diffs); 1 div frames |
| `20261026_235355` | 2681 | projectile only | comparator / crforge | Balloon death bomb: reader projectile, crforge no-hp character dropped by repr. P_rec Balloon None; closest sim tick t0+0 (1 diffs); 255 div frames |
| `20261026_235915` | 3048 | ext:hero_cast:Balloon | extractor | hero Balloon throw dated 1 tick early. P_sim BalloonHero_Skeletrooper_Projectile None; closest sim tick t0+0 (1 diffs); sweep: ability:cmd35_0 side1 dR+1 -> clean +400; 317 div frames |
| `20261027_000233` | 593 | projectile only | unknown | tower shot + Electro Spirit projectiles (BP fresh worker). P_rec tower_shot (-22, 599); P_rec ElectroSpirit (735, -102); P_sim TowerPrincessProjectile (22, -599); closest sim tick t0+0 (4 diffs); 48 div frames |
| `20261027_001141` | 5399 | body position | crforge | Golden Knight 1-4 units. U_rec GoldenKnight (-1, -4); U_sim GoldenKnight (1, 4); P_rec Xbow (-1, -1); closest sim tick t0+0 (4 diffs); 421 div frames |
| `20261027_001702` | 2492 | body in the sim, none near in the reader | unknown | evo Knight 60 units + sim-only Skeleton. U_rec Knight (-1, 60); U_sim Skeleton (1104, 1330); U_sim Knight_EV1 (1, -60); closest sim tick t0+0 (3 diffs); 84 div frames |
| `20261027_004031` | 2083 | ext:own_press | extractor | own IW press: drop pair holds our Skeletons, rule skips it; sweep -3 clean. S0_elixir None 30168; closest sim tick t0+0 (1 diffs); sweep: ability:cmd26_0 side0 dR-3 -> clean +400; 1 div frames |
| `20261027_010245` | 573 | hp only: sim less/mixed damage at the same points | unknown | princess tower 77 hp, closest sim t0-2. T_rec tower (0, 0); T_sim PrincessTower (0, 0); closest sim tick t0-2 (2 diffs); 1698 div frames |
| `20261027_010613` | 2187 | body in the reader, none near in the sim | extractor / crforge | Rascals boy 2,000 / girls 278 off. U_rec Rascals (0, -278); U_rec Rascals (0, -2000); U_rec Rascals (0, -278); closest sim tick t0-2 (6 diffs); 753 div frames |
| `20261027_014928` | 5183 | body position | crforge / unknown | hero IW 29 units (BP open). U_rec IceWizard (29, 13); U_rec IceWizard (29, 13); U_sim IceWizardHero (-29, -13); closest sim tick t0+0 (4 diffs); 478 div frames |
| `20261027_041602` | 2276 | projectile only | crforge / unknown | evo Goblin Barrel decoy lateral offset (game +-172). P_rec GoblinBarrel (172, 22); P_rec GoblinBarrel (-172, 22); P_sim GoblinBarrelSpell_EV1_Decoy (-172, -22); closest sim tick t0+0 (4 diffs); 1001 div frames |
