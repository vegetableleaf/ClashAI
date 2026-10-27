# IL data beyond 252k replays (plan1026 Pillar 4e)

Date 2026-10-27. Labels: (a) measured/read from a source this session, (b) plausible, untested, (c) contradicted by evidence.
The search was shallow (about 8 web queries plus page fetches). "Nothing found" means not found by these queries, not proven absent.

## Verdict
- (a) No public dataset I found has more than the 252,238 replays we already hold. The only other replay-level set is tiny.
- (a) The IL_Replay schema string is `royaleapi-replay-parquet.v1`, so it was built from RoyaleAPI replay pages. It has no licence and no provenance; its manifest says source IDs, dates and tags were stripped.
- (a) Counting both sides, the 252k replays already give 504,476 deck-sides (AUDIT_opponents.md s3). If "1 M" means 1 M sides of play, the gap is about +250k replays. If it means 1 M replays (~70 M actions at 70.7 actions per replay = 17.8 M / 252k), the gap is +750k.
- (a) No route that respects the RoyaleAPI staff stance reaches 1 M replays within the plan's 6 to 8 weeks. The only fast route is a mass crawl, which is the owner's decision (below). Nothing was crawled.

## Sources
| # | Source | URL | Size | Fields | Licence / terms | Freshness | Cost to ingest |
|---|---|---|---|---|---|---|---|
| 1 | HF IL_Replay (held) | https://huggingface.co/datasets/VanguardX101/IL_Replay | (a) 252,238 replays, 17,836,160 actions, 1.89 GB, 52+52 parquet files, 1,315 downloads last month | replays: battle_type, game_mode, result, crowns, payload_json (decks with levels: Ranked sample level 16, friendly sample level 11). actions: event_index, kind, side, card_key, card_play_number, replay_tick_20hz, time_seconds, form_at_play, native_x/y, grid_x/y, arena_column/row | (a) none stated (cardData has no license field, README silent). Origin is RoyaleAPI replays (schema name), so third-party terms may apply (b) | (a) created 2026-09-06, no change since; battle dates stripped, so pre/post 10-19 patch is unknown (b: likely pre-patch) | Done. Free ask: the owner VanguardX101 via the HF discussion for more shards / licence |
| 2 | Our pro corpus | local gen_v32 | (a) 14,661 replays, 3.5 M rows | both sides, level 11 | own RoyaleAPI crawl | ended 09-06 | done |
| 3 | PRO2 | local | (a) 1,069 battles | crawl2 format | own crawl | 10-08 | done |
| 4 | RoyaleAPI replay crawl | royaleapi.com replay pages | see sizing below | full replays, levels, both sides | (a) staff reply (discuss.royaleapi.com/t/royaleapi-scrape/50033, read via search snippet; the page itself gave me 403): "please don't scrape our website, it doesn't matter the reason or the volume", pointing to the official API. ToS (royaleapi.com/tos, 2024-10-11): I saw only IP-ownership text, could not read an automation clause | live, current patch | would give the whole 1 M, if allowed; Cloudflare-blocked since 10-08 |
| 5 | TV Royale harvest (device) | in-game, L74/replay_rec | (b) planned ~800/day, untested at that rate | both sides from the game's own viewer; 99.7-99.8% position accuracy on 60 live matches (commit 112ec3f) | owner-approved; game ToS is the owner's call | current patch, top-ladder bias | emulator time; already built |
| 6 | Own battle log + live replays | api.clashroyale.com + in-game | (a) poller log 10-27 07:02-08:02: +4,+5,+4,+3 new per 15 min = ~16/h, ~100-130/day (plan says ~130) | official API: deck, result, crowns only; plays only via the device recorder | official API terms, own tag | current | running |
| 7 | Official API, other players | https://api.clashroyale.com | (a) last 25 battles per player (Towards AI write-up) | decks, results, no plays | key bound to IP; rate limit not measured by me | current | meta census only, not imitation (RoyaleAPI forum confirms no timing endpoint) |
| 8 | Grandediw/clash-royale-battle | https://huggingface.co/datasets/Grandediw/clash-royale-battle | (a) 2.82 M rows CSV | battleTime, arena.id, gameMode.id (other columns not visible to me) | (a) MIT | dates unknown | battle-level, no plays: census at most |
| 9 | wty-yy/Clash-Royale-Replay-Dataset (KataCR) | https://github.com/wty-yy/Clash-Royale-Replay-Dataset | (a) two folders (fast_hog_2.6, golem_ai), counts not stated; built from battle videos by OCR + detection | offline-RL replays, format undocumented | repo licence not shown (code repo KataCR is MIT) | 2025 (arXiv 2504.04783), 8 commits | tiny, video-derived: cross-check only |
| 10 | Godul/dm1 | https://github.com/Godul/dm1 | Jan 2019 RoyaleAPI games | time, arena, result, player, deck | unknown | (a) 2019, obsolete | no |
| 11 | Kaggle / papers | searched | (b) nothing found | | | | arXiv 2012.12186 (oracle planner) and KataCR use simulator or video, not a public replay set |

## RoyaleAPI crawl, sized honestly (owner decides; nothing was crawled)
- (a) Stopped 10-08 by Cloudflare. On 10-05 the owner cleared a human check by hand and the clearance expired mid-crawl before (memory ice-wizard-crawl-unblocked).
- (a) Staff stance is against any scraping at any volume (snippet above). A crawl breaks that request, and getting past Cloudflare is access-control evasion. I recommend against it without permission.
- (b) Arithmetic if permitted: +750k replay pages. One page every 2 s sequentially is 17 days; every 5 s is 43 days; plus player-listing calls and re-clearance stops. I found no measured sustained rate of our old crawler in the repo, so these are untested.
- (b) A permission/bulk-export request to RoyaleAPI is cheap and the only legitimate path. No evidence either way on the answer.

## Contribution per day
| Stream | Replays/day | Days to +250k | Days to +750k |
|---|---|---|---|
| TV Royale | ~800 (b) | 313 | 938 |
| Own live + battle-log replays | ~130 (a, plan figure) | 1,923 | 5,769 |
| Both | ~930 | 269 | 806 |
| RoyaleAPI crawl, if allowed | ~17k-43k (b) | 6-15 | 17-43 |

## Recommended route
1. (a) Define the target in sides. 504k sides exist; 1 M sides = +250k replays. Do not wait on 1 M replays to train.
2. Ask VanguardX101 on the HF discussion page (free): provenance, licence, patch date, more shards? Only cheap lead for a large jump. ETA unknown (b).
3. Owner asks RoyaleAPI for written permission or a bulk export. If granted, 1 M replays in about 3 to 6 weeks (b). If refused, drop the route.
4. Run TV Royale (approved): ~290k a year, the fresh-patch stratum for fine-tuning and evaluation, not the bulk.
5. With no outside help: 252k + 15.7k + ~930/day = ~270k at day 20 and ~500k in about 9 months. 1 M replays is not reachable this way inside the plan.
6. (b, untested) Before paying for more data, read Pillar 4d's scaling curve: if loss is flat past 252k replays, more data does not buy a bigger model.

## Sample
Two small parquet files (6.3 MB total, replays + actions part-000051) are in `icebow/data/ildata_samples/hf_il_replay/` (not committed), read with `python -I` via `peek.py` here. The schema above comes from them.
