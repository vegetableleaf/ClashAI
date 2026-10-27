## Fields (214 scenarios compared of 223; counts {"units_rs": 1209877, "units_cf": 1244456, "paired": 1170284, "shots_cf": 66583, "areas_cf": 44916, "samples": 142925, "shots_rs": 63982, "shots_paired": 55396, "press_same": 16838, "press_ok_rs": 1004, "press_ok_cf": 1043, "areas_rs": 31073, "areas_paired": 28291, "press_differs": 588})

| field | HEAD all | new all | new in-sync | new in-sync bodies | top mismatch (new) |
|---|---|---|---|---|---|
| area.frac | 89.70% (25203) | 89.76% (28291) | 89.23% (26900) | 89.23% (26900) | rs=0.81 cf=0.762 / Tornado x447; rs=0.571 cf=0.524 / Tornado x447 |
| area.motion | 57.98% (25203) | 64.73% (28291) | 64.05% (26900) | 64.05% (26900) | rs="Attached" cf="Area" / IceWizard x5598; rs="Attached" cf="Pulsing" / Firecracker x1236 |
| area.remaining_ms | 82.93% (25203) | 83.20% (28291) | 83.17% (26900) | 83.17% (26900) | rs=850 cf=800 / Tornado x447; rs=600 cf=550 / Tornado x447 |
| attack.frac | 96.44% (1057812) | 96.57% (1170284) | 97.04% (1152283) | 95.91% (348576) | rs=null cf=0.188 / PrincessTower x187; rs=null cf=0.062 / PrincessTower x177 |
| attack.has_target | 29.83% (1057812) | 98.72% (1170284) | 98.88% (1152283) | 98.46% (348576) | rs=true cf=false / PrincessTower x2485; rs=false cf=true / PrincessTower x2433 |
| attack.hit_speed_ms | 100.00% (1057812) | 100.00% (1170284) | 100.00% (1152283) | 100.00% (348576) |  |
| attack.load_ms | 97.92% (1057812) | 98.00% (1170284) | 98.54% (1152283) | 96.35% (348576) | rs=0 cf=100 / KingTower x215; rs=0 cf=350 / KingTower x213 |
| attack.phase | 98.34% (1057812) | 98.46% (1170284) | 98.74% (1152283) | 98.67% (348576) | rs="windup" cf="idle" / PrincessTower x2174; rs="idle" cf="windup" / PrincessTower x2123 |
| attack.progress_ms | 96.03% (1057812) | 96.19% (1170284) | 96.76% (1152283) | 95.25% (348576) | rs=50 cf=0 / PrincessTower x64; rs=0 cf=1250 / Fisherman x59 |
| attack.target | 28.10% (1057812) | 97.35% (1170284) | 97.67% (1152283) | 97.07% (348576) | rs="unpaired" cf=null / PrincessTower x2080; rs="unpaired" cf=null / KingTower x886 |
| bit.ability_active | 0.00% (5302) | 7.35% (6463) | 7.81% (5701) | 7.81% (5701) | rs=true cf=false / IceWizardHero x3919; rs=true cf=false / ValkyrieHero x934 |
| bit.ability_windup | 0.00% (1091) | 52.71% (1292) | 53.46% (1199) | 53.46% (1199) | rs=true cf=false / KnightHero x273; rs=true cf=false / MightyMiner x97 |
| bit.charged | 0.00% (623) | 90.25% (769) | 90.92% (716) | 90.92% (716) | rs=true cf=false / BattleRam x15; rs=true cf=false / DarkPrinceHero x15 |
| bit.clone | 0.00% (9) | 0.00% (9) | 0.00% (6) | 0.00% (6) | rs=true cf=false / Skeleton x9 |
| bit.evolved | 0.00% (31347) | 98.99% (34611) | 98.87% (30754) | 98.87% (30754) | rs=true cf=false / GoblinDummy x283; rs=true cf=false / RageBarbarianEvoGhost x66 |
| bit.hero | 0.00% (41452) | 92.23% (49239) | 91.99% (46202) | 91.99% (46202) | rs=false cf=true / TombstoneHero_Monster_Passive x1375; rs=true cf=false / TombstoneHero x1283 |
| bit.hidden | 87.71% (30721) | 95.52% (33460) | 95.54% (33451) | 95.54% (33451) | rs=true cf=false / Tesla x379; rs=false cf=true / Tesla x358 |
| bit.invisible | 69.78% (4514) | 65.29% (5065) | 63.16% (4395) | 63.16% (4395) | rs=true cf=false / TombstoneHero_Monster_Passive x1375; rs=true cf=false / GoblinHero_Flag_Building x167 |
| bit.underground | 71.85% (238) | 72.54% (244) | 72.34% (235) | 72.34% (235) | rs=false cf=true / GoblinDrill_EV1 x36; rs=false cf=true / MightyMiner x31 |
| buffs.ms | 97.77% (1057812) | 98.78% (1170284) | 98.98% (1152283) | 97.34% (348576) | rs=[] cf=[50] / Knight_EV1 x148; rs=[50] cf=[] / Knight_EV1 x147 |
| buffs.names | 98.11% (1057812) | 99.22% (1170284) | 99.35% (1152283) | 98.30% (348576) | rs=["Tombstone_hero_Ability wait"] cf=["Tombstone_hero_Monster_NoAttacksBuff"] / TombstoneHero_Monster_Passive x1223; rs=["IceWizardHeroSlow"] cf=[] / PrincessT |
| charge_frac | 0.00% (1057812) | 99.88% (1170284) | 99.89% (1152283) | 99.63% (348576) | rs=1.0 cf=0.0 / InfernoDragon x31; rs=1.0 cf=0.0 / MightyMiner x29 |
| charging | 99.99% (1057812) | 99.99% (1170284) | 99.99% (1152283) | 99.98% (348576) | rs=true cf=false / BattleRam x15; rs=true cf=false / DarkPrinceHero x15 |
| hide | 97.18% (1057812) | 99.92% (1170284) | 99.92% (1152283) | 99.74% (348576) | rs="hidden" cf="up" / Tesla x379; rs="up" cf="hidden" / Tesla x346 |
| name | 100.00% (1057812) | 100.00% (1170284) | 100.00% (1152283) | 100.00% (348576) |  |
| row.ability_ticks | 0.00% (1057812) | 99.99% (1170284) | 99.99% (1152283) | 99.97% (348576) | rs=69 cf=0 / ArcherQueen x9; rs=64 cf=0 / ArcherQueen x9 |
| row.attack_phase | 0.00% (1057812) | 98.52% (1170284) | 98.80% (1152283) | 98.55% (348576) | rs=0 cf=1 / PrincessTower x2421; rs=1 cf=0 / PrincessTower x2154 |
| row.charge | 0.00% (1057812) | 99.88% (1170284) | 99.89% (1152283) | 99.63% (348576) | rs=1000 cf=0 / InfernoDragon x31; rs=1000 cf=0 / MightyMiner x29 |
| row.deploy_ticks | 99.93% (1057812) | 99.93% (1170284) | 99.94% (1152283) | 99.80% (348576) | rs=21 cf=0 / Bat x63; rs=23 cf=0 / Bat x63 |
| row.dest_x | 99.98% (1057812) | 100.00% (1170284) | 100.00% (1152283) | 99.99% (348576) | rs=-1 cf=232164 / Skeleton x4; rs=-1 cf=67986 / MightyMiner x3 |
| row.dest_y | 99.98% (1057812) | 100.00% (1170284) | 100.00% (1152283) | 99.99% (348576) | rs=259632 cf=258552 / MightyMiner x12; rs=-1 cf=258210 / MightyMiner x5 |
| row.facing | 0.00% (1057812) | 26.82% (1170284) | 27.14% (1152283) | 89.70% (348576) | rs=[0, -256] cf=[0, 0] / KingTower x142791; rs=[0, -256] cf=[0, 0] / PrincessTower x111116 |
| row.flying | 99.97% (1057812) | 99.97% (1170284) | 99.98% (1152283) | 99.95% (348576) | rs=false cf=true / RoyalHog_EV1_Grounded x354 |
| row.footprint | 22.90% (1057812) | 75.55% (1170284) | 75.17% (1152283) | 99.90% (348576) | rs=[126000, 486000, 198000, 558000] cf=[144000, 504000, 180000, 540000] / KingTower x142925; rs=[126000, 18000, 198000, 90000] cf=[144000, 36000, 180000, 72000] |
| row.hp | 90.77% (1057812) | 91.15% (1170284) | 91.53% (1152283) | 96.13% (348576) | rs=4246 cf=4144 / PrincessTower x1250; rs=4230 cf=4802 / PrincessTower x1068 |
| row.knockback_ticks | 99.91% (1057812) | 99.98% (1170284) | 99.99% (1152283) | 99.95% (348576) | rs=6 cf=5 / Knight x17; rs=1 cf=0 / Knight x17 |
| row.level | 99.99% (1057812) | 100.00% (1170284) | 100.00% (1152283) | 100.00% (348576) | rs=16 cf=17 / MiniPekkaHero x14; rs=16 cf=18 / MiniPekkaHero x3 |
| row.max_hp | 99.99% (1057812) | 100.00% (1170284) | 100.00% (1152283) | 100.00% (348576) | rs=2220 cf=2443 / MiniPekkaHero x14; rs=1 cf=130 / Skeleton x4 |
| row.mount_uid | 99.95% (1057812) | 100.00% (1170284) | 100.00% (1152283) | 100.00% (348576) |  |
| row.radius | 100.00% (1057812) | 100.00% (1170284) | 100.00% (1152283) | 100.00% (348576) |  |
| row.shield | 99.96% (1057812) | 99.97% (1170284) | 99.99% (1152283) | 99.97% (348576) | rs=0 cf=250 / Recruit x47; rs=0 cf=384 / Recruit_EV1 x37 |
| row.status_flags | 92.58% (1057812) | 98.95% (1170284) | 99.02% (1152283) | 96.76% (348576) | rs=144 cf=16 / IceWizardHero x3919; rs=2 cf=16 / TombstoneHero_Monster_Passive x1375 |
| row.stun_ticks | 99.30% (1057812) | 99.69% (1170284) | 99.72% (1152283) | 99.23% (348576) | rs=5 cf=0 / PrincessTower x28; rs=0 cf=19995 / TombstoneHero_Monster_Passive x26 |
| shot.damage | 0.76% (48866) | 99.66% (55396) | 99.75% (51053) | 99.75% (51053) | rs=286 cf=0 / AxeMan_EV1_Projectile_Strong1 x119; rs=286 cf=0 / None x16 |
| shot.effect | 92.57% (48866) | 99.97% (55396) | 99.99% (51053) | 99.99% (51053) | rs=null cf={"buff": null, "ms": 2500} / TowerPrincessProjectile x8; rs={"buff": null, "ms": 2500} cf=null / IceWizardHeroProjectile x3 |
| shot.source | 1.72% (48866) | 99.04% (55396) | 99.35% (51053) | 99.35% (51053) | rs="unpaired" cf=5000037 / None x27; rs="unpaired" cf=5000021 / None x24 |
| shot.target | 89.33% (48866) | 89.05% (55396) | 90.34% (51053) | 90.34% (51053) | rs=5000007 cf=null / FirecrackerProjectile x510; rs=5000002 cf=null / HunterProjectile x258 |
| shot.type | 3.07% (48866) | 99.58% (55396) | 99.77% (51053) | 99.77% (51053) | rs=null cf="BowlerProjectile" / None x36; rs=null cf="IceWizardHeroProjectile" / None x24 |
| state | 98.51% (1057812) | 98.72% (1170284) | 98.97% (1152283) | 98.75% (348576) | rs="engaged" cf="idle" / PrincessTower x2484; rs="idle" cf="engaged" / PrincessTower x2434 |
| status.frozen | 99.85% (1057812) | 99.76% (1170284) | 99.79% (1152283) | 99.39% (348576) | rs=false cf=true / TombstoneHero_Monster_Passive x1330; rs=false cf=true / PrincessTower x152 |
| status.invisible | 99.87% (1057812) | 99.85% (1170284) | 99.86% (1152283) | 99.54% (348576) | rs=true cf=false / TombstoneHero_Monster_Passive x1375; rs=true cf=false / GoblinHero_Flag_Building x167 |
| status.raged | 99.84% (1057812) | 99.85% (1170284) | 99.90% (1152283) | 99.65% (348576) | rs=true cf=false / SkeletonArmy_EV1_Spectral x1402; rs=true cf=false / ValkyrieHero x144 |
| status.shielded | 99.90% (1057812) | 99.95% (1170284) | 99.98% (1152283) | 99.94% (348576) | rs=false cf=true / Knight_EV1 x168; rs=true cf=false / Knight_EV1 x168 |
| status.slow_frac | 99.38% (1057812) | 99.39% (1170284) | 99.48% (1152283) | 98.81% (348576) | rs=0.5 cf=0.625 / Knight_EV1 x73; rs=0.5 cf=null / Knight_EV1 x48 |
| status.slowed | 99.82% (1057812) | 99.83% (1170284) | 99.87% (1152283) | 99.81% (348576) | rs=true cf=false / PrincessTower x476; rs=false cf=true / PrincessTower x299 |
| status.stunned | 100.00% (1057812) | 100.00% (1170284) | 100.00% (1152283) | 99.99% (348576) | rs=false cf=true / IceWizardHero x24; rs=false cf=true / Knight x16 |
| status.taunted | 99.93% (1057812) | 99.93% (1170284) | 99.93% (1152283) | 99.87% (348576) | rs=false cf=true / PrincessTower x342; rs=false cf=true / IceWizardHero x311 |

## e1 cue tensors (24 matched matches, 25508 paired unit tokens)

Whole cue row equal: HEAD 61.49% (25508), new 94.95% (25508)

| cue column | HEAD | new | top mismatch (new) |
|---|---|---|---|
| cue_known | 100.00% (25508) | 100.00% (25508) |  |
| state=idle | 99.87% (25508) | 99.90% (25508) | rs=1.000 cf=0.000 / Xbow x9; rs=0.000 cf=1.000 / Xbow x7 |
| state=moving | 99.55% (25508) | 99.55% (25508) | rs=1.000 cf=0.000 / Ram x28; rs=0.000 cf=1.000 / Ram x27 |
| state=engaged | 99.51% (25508) | 99.49% (25508) | rs=0.000 cf=1.000 / Ram x28; rs=1.000 cf=0.000 / Ram x27 |
| state=deploying | 99.95% (25508) | 99.95% (25508) | rs=1.000 cf=0.000 / GoblinHero x7; rs=1.000 cf=0.000 / Skeleton x2 |
| state=jumping | 99.95% (25508) | 100.00% (25508) |  |
| state=tunnelling | 100.00% (25508) | 100.00% (25508) |  |
| state=casting | 100.00% (25508) | 100.00% (25508) |  |
| charging | 99.99% (25508) | 99.99% (25508) | rs=1.000 cf=0.000 / BattleRam x1; rs=0.000 cf=1.000 / Prince x1 |
| tesla_hidden | 90.47% (25508) | 99.95% (25508) | rs=0.000 cf=1.000 / Tesla x5; rs=1.000 cf=0.000 / Tesla_EV1 x4 |
| has_target | 64.60% (25508) | 99.13% (25508) | rs=0.000 cf=1.000 / Skeleton x29; rs=0.000 cf=1.000 / Ram x28 |
| target_is_tower | 64.70% (25508) | 99.31% (25508) | rs=0.000 cf=1.000 / Ram x32; rs=1.000 cf=0.000 / Ram x31 |
| phase=idle | 99.51% (25508) | 99.51% (25508) | rs=1.000 cf=0.000 / Ram x28; rs=0.000 cf=1.000 / Ram x27 |
| phase=windup | 99.38% (25508) | 99.38% (25508) | rs=1.000 cf=0.000 / Ram x27; rs=0.000 cf=1.000 / Ram x27 |
| phase=hit | 99.79% (25508) | 99.79% (25508) | rs=1.000 cf=0.000 / Skeleton x11; rs=0.000 cf=1.000 / Xbow x9 |
| attack_frac | 97.71% (25508) | 97.71% (25508) | rs=0.417 cf=0.400 / Princess x9; rs=0.583 cf=0.567 / Princess x9 |
| status.frozen | 99.97% (25508) | 99.97% (25508) | rs=0.000 cf=1.000 / SkeletonWarrior x2; rs=0.000 cf=1.000 / Tesla x2 |
| status.slowed | 99.97% (25508) | 99.97% (25508) | rs=0.000 cf=1.000 / Tesla_EV1 x6; rs=1.000 cf=0.000 / BossBandit x1 |
| status.raged | 99.25% (25508) | 99.25% (25508) | rs=1.000 cf=0.000 / SkeletonArmy_EV1_Spectral x190; rs=0.000 cf=1.000 / AngryBarbarian_EV1 x1 |
| status.invisible | 98.71% (25508) | 98.71% (25508) | rs=1.000 cf=0.000 / TombstoneHero x224; rs=1.000 cf=0.000 / GoblinHero_Flag_Building x65 |
| status.shielded | 99.91% (25508) | 99.97% (25508) | rs=0.000 cf=1.000 / SkeletonWarrior x3; rs=1.000 cf=0.000 / Recruit_EV1 x3 |
| slow_frac | 99.59% (25508) | 99.59% (25508) | rs=0.000 cf=1.000 / Tesla_EV1 x6; rs=0.500 cf=0.625 / IceWizardHero x6 |
