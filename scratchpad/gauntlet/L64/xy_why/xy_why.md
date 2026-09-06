# L64 xy_why -- why do ~50% of crawl2 replays carry no x/y?

Read-only. Inputs: `icebow/data/royaleapi/crawl2/`, `hogeq/data/royaleapi/crawl2/` (battles.csv,
plays_ext.csv, battles_raw.json, players_done.json, replays_done.json, probe_payload.html), the crawler
`C:\Users\benpe\clash-replay-scraper\crawl_icebow.py` / `crawl_deck.py`, crawl logs. Raw outputs in this
directory: `icebow_xy_why.txt`, `hogeq_xy_why.txt` (every cross-tab), `*_partials.txt`, `*_frac.json`;
scripts `xy_why.py`, `partials.py`.

## 1. Per-battle x/y flag (a, measured)

x/y is ALL-OR-NOTHING per battle. Histogram of the per-battle fraction of plays with x/y (hero-ability
rows `attr_ability=1 / _invalid` excluded -- they never carry coordinates, their marker has `data-x="None"`):

| fraction        | icebow (1,237 replays w/ plays) | hogeq (595) |
|-----------------|------:|------:|
| exactly 0       |   612 |   295 |
| (0, 0.2)        |     6 |     4 |
| [0.2, 0.8)      |     0 |     0 |
| [0.8, 1)        |     0 |     0 |
| exactly 1       |   619 |   296 |

icebow: 54,148 / 109,963 play rows have x/y; the 55,554 rows of the covered 619 replays lack x/y only on the
1,412 ability rows. hogeq: 24,672 / 52,973; covered-half misses = 1,147 ability rows only.
The 6 + 4 "partial" replays have exactly ONE x/y row each -- see section 3, they are the smoking gun.

## 2. Cross-tabs of has_xy (icebow; full tables in icebow_xy_why.txt) (a, measured)

NOTHING separates the halves. Every field sits at 50% +- sampling noise:

| field | levels (has_xy / n) |
|---|---|
| battle_type | pathOfLegend 605/1201 (50.4%); trail 6/15; friendly 1/10; clanMate 3/5; PvP 4/5; riverRaceDuelColosseum 0/1 |
| result | win 408/818 (49.9%); loss 211/419 (50.4%) |
| player is team[0] | always True: 619/1237 (the crawler always passes the crawled player as team) |
| crowns (team,opp) | (1,0) 392/779 50.3%; (0,1) 163/331 49.2%; (0,3) 36/66; (3,0) 12/31 |
| rating bucket | 2300: 169/345 49.0%; 2100: 152/302 50.3%; 2200: 80/172 46.5%; 2000: 62/128 48.4%; 2700: 28/41 68.3% (n small) |
| wins_7d bucket | 0-19: 293/591 49.6%; 20-39: 166/315 52.7%; 40-59: 88/190 46.3%; 60-79: 57/116 49.1% |
| deck | main variation 539/1074 50.2%; knight-hero variation 80/160 50.0% |
| player_tag | 99 players; every player with n>=20 sits between 38% and 69%; NO player is all-or-nothing |
| clan_tag | top 10 clans 38-61% |
| battle day (UTC) | 2026-08-29 62/129 48.1%; 08-30 141/283 49.8%; 08-31 46/90; 09-02 60/118 50.8%; 09-03 81/181 44.8%; 09-04 70/126 55.6%; 09-05 26/57 45.6%; old 2024-2025 battles 7/16 |
| battle hour (UTC) | 24 levels, 30-61%, no trend |
| age at crawl | battles sorted by timestamp, buckets of 100: 47,60,46,50,50,49,52,54,45,47,44,60,40% -- flat |
| within-player time split | 76 players have both halves; a clean time boundary (max uncovered ts < min covered ts) in only 8/76; covered-half median newer in 21/38 |
| fetch order (battles.csv row order, = crawl wave) | buckets of 100: 50,51,56,52,53,50,40,46,46,51,48,52,62% -- flat across waves 1-4 (Aug 30 -> Sep 5) |
| replay_tag format | all 12 chars, char0 always '0'; char1 (0/2/8/9) 46-57%; char3 Y 52.4% / P 45.3% / 9 34.4% (n=61) -- noise |
| plays per battle, elixir totals/leak | flat (46-53%) |
| battles_raw.json extra keys | NONE beyond battles.csv (same 18 keys); no replay/version/league/hasReplay field exists |
| crawl timestamp | not recorded per battle; players_done.json is a bare tag list |

"5 strongest separators": there are none; the largest n>=50 deviation is battle day 2026-08-28 at
40/61 (65.6%) and rating 2700 at 28/41 (68.3%) -- both within binomial noise of 50% for their n.
The halves are a coin flip against every battle-level field. That rules out (i) mode and (ii) age.

## 3. How x/y is obtained, and where the half is lost (a, measured on the data; mechanism from code)

`crawl_icebow.py:257` fetches ONE endpoint for every battle, `/data/replay` (same params for all,
`royale/pipeline.py:148-154`); no per-battle HTTP status or "no replay" reason is recorded beyond the
`[crawl] refused` / `error` log lines (icebow wave 4 log: 0 refused, 371 AuthError, 101 RateLimited --
those are retried next run, they never reach battles.csv). Every battle in battles.csv got a
`success` payload whose timeline parsed (1,253/1,253 have plays > 0 except 16 with 0 timeline cards).

x/y comes from the payload's `.marker` elements (`crawl_icebow.py:89-92`, identical in
`crawl_deck.py:115-118`):

    key = (m.get("data-t"), m.get("data-c"), m.get("data-i", "0"))       # line 91
    ...
    mx = markers.get((t, card, str(occ))) or markers.get((t, card, "0"))  # line 101

`data-i` was ASSUMED to be a per-(tick,card) occurrence index ("Joined on (tick, card, occurrence-index)",
line 85). The evidence says it is not:

* In the probe payload (02GY9GQLLQ2Y, covered) all 109 markers carry `data-i="0"`, including markers
  whose (t, c) do not repeat -- consistent with any constant flag.
* In COVERED replays with a cross-side same-tick same-card pair (blue and red both play card C at
  tick t; 4 such pairs in icebow), BOTH rows got IDENTICAL x/y (4/4). So the second marker also has
  `data-i="0"` (the dict overwrote the first) and the red row fell through to the `"0"` fallback.
  `data-i` is NOT an occurrence index even in the covered half.
* In UNCOVERED replays with such a pair (6/6 in icebow, 4/4 in hogeq -- every uncovered replay that
  had one), exactly ONE row joined: the red row, occurrence 1, which looked up key `(t, card, "1")`.
  That key EXISTS in those payloads. Examples (icebow_partials.txt): 00YYPYJ2GPUU the-log t=4655
  -> (3.5, 17.5); 08GPVGVUL8YG the-log t=5893 -> (14.5, 17.5); 08RPVC8G8UL2 tornado t=5893 -> (13.5, 15.5).
  hogeq: 02GY9GCVRGLP the-log t=4501 -> (5.5, 14.5); 08JPVCYLYQVY mighty-miner t=511 -> (17.5, 30.5).

Conclusion: the "uncovered" payloads DO ship markers -- with `data-i="1"` -- and the join at line 101
drops all of them because it only ever looks up `"0"` or the occurrence index (which is 0 for every
play except the 10 same-tick pairs). 10/10 uncovered replays that could reveal an `i="1"` marker did;
0 payloads of an uncovered replay were kept on disk (only probe_payload.html), so this is inferred
from the join residue, not read from HTML.

What `data-i` MEANS is (b) untested: a per-replay binary flag at 50% prevalence, independent of
mode/age/player/rating/side. The natural candidate is a perspective/inversion flag (the stored replay
is from the opponent's seat and the viewer mirrors the map) -- a coin flip by construction. It could
also be a payload-version flag with no geometric meaning. The 10 recovered rows cannot decide it: by
arena symmetry, "blue's log at (3.5,17.5) un-mirrored" and "red's log at (14.5,14.5) mirrored" are
the same raw numbers. The re-parse must therefore include the frame check that validated the covered
half (HANDOFF 5ag: blue tesla median tile_y = 20.0, 99-100% of blue defensive placements at y > 16);
if the `i=1` half comes out at tile_y ~ 12 / y < 16, apply x' = 18 - x, y' = 32 - y for that half.

## 4. hogeq (a, measured; hogeq_xy_why.txt)

Same pattern exactly: 296/595 (49.7%) covered, 295 exactly 0, 4 partials, each partial = one red
occurrence-1 row of a cross-side same-tick pair joined to a `data-i="1"` marker. pathOfLegend 295/593
(49.7%), win 163/326 (50.0%), loss 133/269 (49.4%), fetch-order buckets 47/48/46/52%, timestamp
buckets 56/46/56/41/52/47%, clean within-player time split 1/29. Single deck (no deck variation
effect). The crawler code is verbatim the same (`crawl_deck.py:108-140`).

## 5. Verdict and the ONE change

* (i) battle-mode property: (c) CONTRADICTED -- pathOfLegend 50.4% / 49.7%, every mode at ~50%.
* (ii) age/expiry property: (c) CONTRADICTED -- flat across battle date (2024 -> 2026-09-05), hour,
  crawl wave and within-player time order.
* (iii) crawler parsing gap: (a) MEASURED -- the markers are present with `data-i="1"` and the join
  key at `crawl_icebow.py:91/101` (`crawl_deck.py:117/127`) discards them. The 50/50 is a property of
  the `data-i` flag, which no battle-level field predicts, i.e. it is decided inside the replay
  payload, not by targeting.
* (iv) something else: only the open question of what `i=1` means geometrically (b).

ONE change: in `parse_replay_ext`, key markers on `(data-t, data-c)` plus side (`data-s` t->blue,
o->red, present on both element sets and currently ignored) and record `data-i` as a column
(`attr_i`), instead of keying on `data-i`. Then re-fetch the uncovered tags (list = replays in
plays_ext.csv with x/y fraction < 0.5: icebow 618, hogeq 299; the crawler skips anything in
replays_done.json, so the driver needs a re-fetch list rather than an edit of that file). Wave-4 rate
was ~2 replays/min -> ~5 h icebow, ~2.5 h hogeq. Crawler TARGETING needs no change -- there is nothing
to target on.

Expected yield (a, from the counts above, assuming `i=1` payloads carry a marker per non-ability play
as the covered half does -- 10/10 checks support it, a full-payload verification on the first re-fetch
is the gate):

| | now | after |
|---|---:|---:|
| icebow battles with x/y | 619 / 1,237 (50.0%) | 1,237 / 1,237 (~100%) |
| icebow play rows with x/y | 54,148 / 109,963 (49.2%) | ~107,146 / 109,963 (97.4%; the 2,817 ability rows never have x/y) |
| hogeq battles with x/y | 296 / 595 (49.7%) | 595 / 595 |
| hogeq play rows with x/y | 24,672 / 52,973 (46.6%) | ~50,578 / 52,973 (95.5%) |

That is a 2.0x gain in positioned replays from already-fetched battles, before any new crawling; the
457 battles in icebow battles_raw.json not yet fetched (1,710 raw vs 1,253 done) are a further ~457
positioned replays once fetched with the fixed parser. Side note (minor): the side-blind join also
gives both rows of a same-tick cross-side pair one marker (4 icebow pairs, one side's coordinates
wrong); the (t, c, side) key fixes that too.

STATUS: complete
