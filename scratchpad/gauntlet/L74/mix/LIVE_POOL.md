# Live-mirrored deck pool

Built by `live_pool.py` (112s). Library: 52566 distinct exact-form decks (504476 deck-sides); 52566 convert to 8 engine names. Loadability: checked in the Royale venv (forms_mode=deck, ICEBOW_ENGINE_DECK on the other side).

## Coverage

- live opponents: 1919; mapped exactly (deck contains every seen card): **829**; approximately (max overlap, or a seen card absent from the library): **1086**; not at all: **4** (|seen|=0 or no usable candidate in the first 20).
- opponents whose first-choice deck was skipped (unconvertible / unloadable) and fell to a later candidate: 0
- distinct decks in the pool: **895**; the top deck takes 1.7% of mapped opponents
- |seen| histogram: {0: 4, 2: 4, 4: 29, 5: 255, 6: 827, 7: 629, 8: 171}
- approx rows by (|seen|, overlap): {(4, 3): 6, (5, 3): 25, (5, 4): 100, (6, 3): 32, (6, 4): 204, (6, 5): 160, (7, 3): 14, (7, 4): 145, (7, 5): 183, (7, 6): 69, (8, 4): 30, (8, 5): 93, (8, 6): 24, (8, 7): 1}
- loadability: 10415 distinct candidate decks reset in RoyaleSim, 10415 loadable; blockers: none; pool decks with a refused-form fallback (loaded as base): 0

## Unmapped names

- live names never present in any library deck: none
- library card keys with no engine spelling (decks with them cannot convert): none

## Top 30 decks

| # | n_live | n_lost | engine |
|---|---|---|---|
| 1 | 32 | 19 | BarbLog, Fireball, Goblins@hero, Minions, Mortar@evolution, MovingCannon, Rascals, SkeletonBalloon@evolution |
| 2 | 31 | 8 | GoblinBarrel@evolution, GoblinGang, IceSpirits, InfernoTower, Knight@hero, Log, Princess@evolution, Rocket |
| 3 | 30 | 19 | BabyDragon@evolution, BattleHealer, Elixir Collector, Golem, MiniPekka@hero, MiniSparkys, Valkyrie@evolution, Vines |
| 4 | 29 | 10 | AxeMan@evolution, Bowler, Freeze, GoldenKnight, Graveyard, InfernoDragon@evolution, MiniSparkys, Tornado |
| 5 | 26 | 14 | Arrows, Clone, GiantSkeleton, GoblinBarrel, MinionHorde@evolution, SkeletonArmy@evolution, Tesla, ZapMachine |
| 6 | 26 | 3 | Archer@evolution, ElectroSpirit, Fireball, Knight@hero, Log, Skeletons, Tesla@evolution, Xbow |
| 7 | 26 | 3 | Bats@evolution, Berserker@hero, BombTower, EliteArcher, FireSpirits, Miner, RoyalDelivery, Wallbreakers@evolution |
| 8 | 24 | 11 | AngryBarbarians@evolution, DarkPrince@hero, ElectroWizard, GoblinGiant, Heal, Rage, Zap@evolution, ZapMachine |
| 9 | 24 | 4 | Balloon@hero, BarbLog, BombTower, IceGolemite, Miner, Musketeer@evolution, Skeletons, Snowball@evolution |
| 10 | 22 | 3 | ArcherQueen, Cannon@evolution, Earthquake, IceSpirits, Log, RoyalDelivery, RoyalHogs@evolution, Skeletons |
| 11 | 22 | 3 | ElectroSpirit, Fisherman, Hunter@evolution, Log, Monk, Rage, RoyalGiant@evolution, SkeletonWarriors |
| 12 | 20 | 16 | Assassin, BattleRam@evolution, ElectroWizard, EliteArcher@hero, Fireball, Ghost@evolution, Pekka, Zap |
| 13 | 18 | 7 | Bomber, ElectroWizard, GoblinCurse, GoblinGiant@evolution, GoblinMachine, Pekka@evolution, Rage, Vines |
| 14 | 16 | 11 | Arrows, Bowler, Giant@hero, Graveyard, Minions, SkeletonWarriors, Snowball@evolution, Witch@evolution |
| 15 | 16 | 8 | Arrows, BarbLog@hero, DartBarrell, ElectroSpirit, GoblinCage@evolution, MiniSparkys, RoyalHogs, RoyalRecruits@evolution |
| 16 | 16 | 3 | Cannon@evolution, Fireball, HogRider, IceGolemite, IceSpirits, Log, Musketeer@hero, Skeletons@evolution |
| 17 | 15 | 13 | DarkWitch, GoblinCurse, Golem, InfernoDragon@evolution, Miner, SkeletonArmy@evolution, SkeletonKing, Zap |
| 18 | 15 | 8 | Arrows, AxeMan@evolution, DarkMagic, DarkWitch, ElixirGolem, Rage, SkeletonArmy@evolution, SkeletonKing |
| 19 | 15 | 3 | BarbLog@hero, ElectroSpirit, Fireball, Fisherman, Ghost@evolution, Hunter, RoyalGiant@evolution, Skeletons |
| 20 | 14 | 4 | BattleHealer, ElectroDragon@evolution, Elixir Collector, ElixirGolem, Heal, Mirror, Skeletons@evolution, Tornado |
| 21 | 13 | 10 | Balloon, Barbarians@evolution, Fireball, LavaHound, MegaMinion@hero, SkeletonDragons, Tombstone, Zap@evolution |
| 22 | 12 | 7 | Arrows, GoblinGang, IceWizard, Mortar@evolution, MovingCannon, SkeletonBalloon@evolution, SkeletonKing, SpearGoblins |
| 23 | 12 | 1 | Archer@evolution, DarkWitch, Elixir Collector, Fireball, Golem, MegaMinion@hero, MiniPekka, Zap@evolution |
| 24 | 11 | 9 | Bats, GoblinGang, InfernoDragon@evolution, MegaKnight, Miner, SkeletonBalloon@evolution, SpearGoblins, Zap |
| 25 | 11 | 9 | BlowdartGoblin, FireSpirits, IceSpirits, SkeletonArmy@evolution, SkeletonBalloon@evolution, SkeletonKing, SuspiciousBush, Vines |
| 26 | 11 | 7 | Berserker@hero, BlowdartGoblin, HogRider, Knight@hero, MegaKnight@evolution, Prince, SkeletonArmy, Witch |
| 27 | 11 | 4 | BlowdartGoblin@evolution, BossBandit, FireSpirits, IceSpirits, Log, SpearGoblins, SuspiciousBush, Wallbreakers@evolution |
| 28 | 11 | 2 | Balloon@hero, BarbLog, Bowler, ElectroDragon@evolution, Freeze, InfernoDragon@evolution, RageBarbarian, Tornado |
| 29 | 11 | 1 | BarbLog, Berserker@hero, GoblinHut, Graveyard, IceWizard, Poison, Valkyrie@evolution, Witch@evolution |
| 30 | 11 | 0 | Berserker@hero, Bomber, Cannon@evolution, FireSpirits, GoblinDrill, Rocket, Skeletons, Snowball@evolution |

## Card shares: pool vs live

| card | live seen % | pool (n_live-weighted) % | old training pool (sides-weighted) % |
|---|---|---|---|
| megaknight | 16.2 | 19.9 | 1.8 |
| firecracker | 16.8 | 15.1 | 2.5 |
| minipekka | 17.8 | 18.1 | 6.7 |
| hogrider | 14.6 | 17.5 | 6.8 |
| elixirgolem | 8.0 | 6.3 | 1.9 |
| royalrecruits | 4.8 | 4.5 | 1.3 |
| skeletonballoon | 7.9 | 9.9 | 5.2 |
| golem | 5.7 | 5.6 | 21.7 |
| angrybarbarians | 8.9 | 11.6 | 24.9 |
| lavahound | 1.9 | 2.2 | 9.1 |
| xbow | 1.7 | 1.8 | 1.1 |
| mortar | 3.8 | 3.3 | 3.6 |

Live seen % is a LOWER bound on true presence (only cards we saw played); pool % counts the full completed deck.
