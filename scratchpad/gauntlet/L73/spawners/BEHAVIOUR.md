# Spawner response: pros (icebow) vs live bot (L73, 2026-10-06)

Pros: 2,181 native re-drive replays (icebow side = the Xbow side, all >=7/8 core cards), 4,054 opponent spawner deploys, 132 games with a Witch.
Bot: 204 live logs 10-04..10-06 with a usable board (frames or decision audits), 277 deploys, 38 games with a Witch; 179 have a result.
Everything below is measured by `spawner_behaviour.py` + `bad_plays.py` (rows in `rows_*.jsonl`, all numbers in `results.json` / `behaviour_results.json`). Bot n is small for every family except Witch: the rare-family rows are indicative only.

**Method notes.** A "deploy" is one spawner *parent* body. Spawn children carry the parent's card id and name (a Witch skeleton is listed as `Witch`, max_hp 81 native / 119 live), so parents are told from children by max_hp (and, for huts, by never moving). Response = my plays in the 8 s after the deploy. Tower damage = my towers' hp lost in the next 15 s, as % of one princess tower. Bot plays are shifted +20 ticks (a bot play shows on the board 26 ticks after the decision; pros 0-10).

## Per-family table (pros / bot)

| family | who | n (games) | ignored % | 1st card % | 1st placement % | no same-lane play in 8 s % | life med s (>20 s %) | killed by Rocket / tower in range / Xbow in range % | my elixir at deploy | tower dmg 15 s |
|---|---|---|---|---|---|---|---|---|---|---|
| Witch | pros | 477 (132) | 10 | Rocket 18, Knight 16, IceWiz 15 | same-lane back 32, NEAR 18, opp-lane back 18 | 23 | 15.0 (32) | 29 / 19 / 24 | 6.7 | 5.9 |
| Witch | bot | 142 (38) | 11 | **Xbow 25**, Knight 17, IceWiz 16 | **opp-lane back 31**, same-lane back 26, bridge 18 | **40** | 18.4 (43) | **4** / 39 / 12 | **4.5** | **11.5** |
| NightWitch | pros | 306 (92) | 10 | Tesla 22, IceWiz 21, Skel 18 | same-lane back 44, opp back 19 | 25 | 19.0 (45) | 11 / 50 / 24 | 6.3 | 6.9 |
| NightWitch | bot | 24 (5) | 8 | Knight 41, Tesla 18 | same-lane bridge 36, NEAR 23 | 17 | 17.7 (46) | 0 / 45 / 14 | 3.4 | 11.2 |
| Furnace (walks in this build) | pros | 763 (124) | 8 | Tesla 18, IceWiz 17, Knight 14 | same-lane back 37, opp back 20 | 24 | 15.9 (31) | 11 / 15 / 22 | 6.1 | 5.1 |
| Furnace | bot | 34 (7) | 6 | **Xbow 28**, Tesla 28 | **opp-lane back 44**, same back 19 | **44** | 16.8 (38) | 3 / 31 / 16 | 3.5 | **14.4** |
| MotherWitch | pros / bot | 624 (166) / 5 (3) | 8 / 40 | Tesla 18, Knight 17 / Knight 67 | same back 37 / NEAR 67 | 22 / 40 | 12.2 / 6.3 | 8 / 0 | 6.1 / 5.2 | 8.0 / 0.4 |
| Tombstone | pros | 858 (165) | 16 | Log 20, Xbow 18, IceWiz 16 | same back 44, same bridge 24 | 32 | 15.4 (33) | tower n/a | 6.3 | 4.1 |
| Tombstone | bot | 33 (11) | 9 | Xbow 30, Tesla 17 | same bridge 37, same back 30 | 24 | 10.2 (15) | tower n/a | 3.8 | **10.9** |
| Graveyard | pros / bot | 657 (168) / 22 (8) | 3 / 0 | Knight 21, Tesla 18 / Log 32, IceWiz 18 | NEAR 29, bridge 25 / NEAR 41, ON 27 | 4 / 5 | 9.6 / 7.0 | n/a | 6.4 / 4.0 | 19.7 / 20.8 |

Goblin Hut (pros 361 / bot 8) and Barbarian Hut (8 / 9) behave like Tombstone; bot n is too small to say more. Graveyard is the same for both (Log, Knight, IceWizard on or next to it, tower takes ~20 % regardless).
Median first response: pros 2.6 s, bot 2.2 s. "ON" means <=3 tiles from the spawner, "NEAR" <=6 tiles.

## Differences, ranked by how much loss they explain

Result context: bot wins 17/60 (28 %) of games where the opponent played one of these spawners vs 68/119 (57 %) without; Witch games 8/36 (22 %). Pros: 37 % vs 46 %; Witch games 42 %. Extra tower damage in the 15 s after a deploy, bot minus pros, summed over families: 7.5 % of a princess tower per bot match (Witch 3.9, Furnace 1.6, Tombstone 1.1, Barb Hut 0.6, Night Witch 0.5). Spawner windows are not worse than the bot's baseline (12.0 vs 11.5 per 15 s) while pros are better than theirs (7.7 vs 8.9): the bot leaks, the pros contain.

1. **The bot meets spawners with too little elixir (measured; direction of cause untested).** Median elixir when a troop spawner lands: bot 4.3, pros 6.3; below 4 in 44 % vs 22 % of cases, 6+ in 31 % vs 54 %. Tower damage after a deploy at <4.5 elixir: 23.4 % of a princess (n=89) vs 0.7 % at >=4.5 (n=95); pros 8.7 vs 5.5. Caveat: low elixir may mean the bot was already defending. Concrete: `live_play_20261005_093839` t0=3121, two Witches (one already at the left tower, 4 children each), bot at 3.4 elixir spends 10 on Tesla/IceWizard/Knight, all on the right lane, tower loses 53 %.
2. **Rocket is dead weight (measured).** Rocket is in the bot's hand in 93 % of 59,232 decisions, with 6+ elixir in 22 % of them, and is played 0.37 times a game against 2.37 for pros. It is the pros' top first answer to a Witch (18 %; Rocket kills 29 % of pro-killed Witches) and the bot's 4 % (kills 4 %). Against troop spawners the bot's Witch lives >20 s 42 % vs 28 %, and 38 % of its spawner kills happen with the spawner in range of its own tower (pros 22 %). Rocket was affordable in 47 % of the 180 bot deploys with decision data and played in 4 %; the model's chosen-card p_play for Rocket was 0 at those moments in most cases (`rocket_hold.json`, `bad_plays.json`). Example `live_play_20261006_160823` t0=3205 Witch, Rocket in hand and affordable, never played, 167 % of a princess lost.
3. **First response is the wrong card or lane (measured).** Xbow first: bot 23 % vs pros 11 % of troop-spawner responses, at 4.3 elixir for a 6-elixir card, and 93 % of the bot's Xbow responses land >11.5 tiles from the spawner (pros 77 %), i.e. cycle plays at (2.5/15.5, 19.5). No play at all in the spawner's lane within 8 s: Witch 40 % vs 23 %, Furnace 44 % vs 24 %. Opposite-lane first response 37 % vs 28 % (x<9 split, so centre plays near x=9 are ambiguous). Examples: `live_play_20261006_140737` t0=2972 Witch, 1.9 elixir, Xbow after 7.2 s at (15.5,19.5); `live_play_20261005_074842` t0=2943 Furnace, Xbow first at (2.5,19.5), Furnace lives 26 s.
4. **Tornado wasted (small n).** While a spawner is alive 21 % of bot Tornados hit nothing (15/73) vs 7 % pros (51/754); children-only 8 % vs 1 %. Examples `live_play_20261004_094328` ticks 2861, 4627; `live_play_20261005_064528` t3216 (8.5,24.5), Witch 3.7 tiles away.
5. **Not a difference, or contradicted by the data.** Ignoring: only 11 % unanswered (pros 10 %); first response time is the same. Log wasted on Bats: contradicted, 5 of 1,230 bot Logs hit only Bats (0.4 %; pros 0.1 %); Log hits the spawner 58 % of the time with one alive (pros 48 %). Spells on children instead of the spawner: Log 8/158 (5 %) vs 3 %; Rocket 2/12 (e.g. `live_play_20261004_021126` t4590 at (13.5,5.5), 10 tiles from the Witch). Over-commit: elixir spent in the 8 s is the same (5.4 vs 5.4 for Witch); the bot just starts lower and ends at 3.9 vs 5.8 median.
6. Context, not a bot play: opponents land spawners deeper against the bot (Witch 9.5 tiles behind the river vs 6.5; Furnace 15.2 vs 6.5), out of reach of Xbow and often Rocket.

## Suspicious board identity (for the parallel audit)

- Several "Witch" bodies at once is the engine labelling, not a reader slip: bot games show up to 22 Witch-id bodies, native pros up to 22; real Witches are never more than 2. Bot ratio is 1,636 child tracks to 142 parents (pros 4,615 to 477). Example `live_play_20261005_093839` tick 3126: 6 Witch bodies, 2 with max_hp 1220, 4 with max_hp 119.
- 12 % of bot troop-spawner deploys (25 of 205; pros 0.4 %) are first listed already inside the bot's own half, 15 of them living <3 s: the parent drops out of the audit and re-enters. Examples: `live_play_20261005_091743` Night Witch "deployed" at ticks 1610, 3521, 3619, 3713, all at y 16-21; `live_play_20261005_100121` Furnace at 651, 1886, 3674, 0.2 s each. This inflates bot n and misdates t0 for those rows.
- Hero Tombstone: 155 pro near-duplicate pairs (two 529-hp bodies per play); Tombstone hp can read -1.

## Files and command

`scratchpad/gauntlet/L73/spawners/`: `spawner_behaviour.py` (extract + summarise), `bad_plays.py`, `rocket_hold.py`, `make_tables.py`, `results.json` (shared with the identity audit; mine are keys `pros`, `bot`, `excess_tower_damage`, `bad_plays`, `rocket_hold`; a private copy is `behaviour_results.json`), `rows_pros.jsonl`, `rows_bot.jsonl`, `spells_*.jsonl`, `tables.md`.
Run from the repo root: `icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L73/spawners/spawner_behaviour.py && ...bad_plays.py` (about 40 s, 3 CPU processes).

**Limits.** Bot rare-family cells have n<35. Pro opponents are a different population than ladder opponents. Tower damage in the window includes every source, not only the spawner; windows from overlapping deploys double count. Kill cause is inferred from what was in range at the last sighting, not from damage logs. Bot 10-04 logs have frames only for 60 games; the other 144 use decision audits (about 13 ticks apart).
