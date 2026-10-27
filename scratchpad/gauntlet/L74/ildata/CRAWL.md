# RoyaleAPI replay crawl (ticket D2 / D2b, plan1026 Pillar 4e)

Date 2026-10-27. Labels: (a) measured or read this session, (b) plausible, untested, (c) contradicted.

## Status
- **Crawler built and tested OFFLINE. It has sent zero requests to royaleapi.com.** HOLD until the owner says go.
- Owner decision 10-27: crawl on the LAPTOP at <= 1 request/s, in a Chrome the OWNER clears and logs into (RoyaleAPI approved crawling; no export).
- Code: `rc_parse.py` (parsers + IL_Replay schema), `rc_crawl.py` (transport, state machine, CLI), `test_rc.py` (13 offline tests).
  Output: `icebow/data/crawl/` (untracked): `replays/part-N.parquet`, `actions/part-N.parquet`, `raw/raw-N.jsonl.gz`, `state.db`, `progress.jsonl`.

## What the owner must do (once, then whenever an alert says so)
1. Start a SEPARATE Chrome with a debug port and its own profile (Chrome 136+ ignores the port on the default profile). PowerShell:
   `& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Users\benpe\chrome-royaleapi"`
2. In that window open https://royaleapi.com, complete the Cloudflare check by hand, **log in** (Battle Replay needs a login). Leave a royaleapi.com tab open.
   The port listens on 127.0.0.1 only. The crawler never opens, navigates or closes tabs and never reads cookies; it runs `fetch()` inside that tab.
3. Tell the lead "go". The lead (or owner) then creates the gate file: `New-Item icebow\data\crawl\OWNER_GO -Force` (no real request is possible without it).
4. Whenever Discord says "PAUSED": fix Chrome (clear the check / log in again / wait out a 429), then `python -I scratchpad\gauntlet\L74\ildata\rc_crawl.py resume`.

## Commands (from `C:\Users\benpe\ClashBot`)
| step | command |
|---|---|
| first contact, <= 5 requests, saves raw pages to `icebow/data/crawl/probe/` | `python -I scratchpad\gauntlet\L74\ildata\rc_crawl.py probe` |
| small first run, review the output | `python -I scratchpad\gauntlet\L74\ildata\rc_crawl.py crawl --max-replays 200` |
| **full run / restart (same command resumes from state.db)** | `python -I scratchpad\gauntlet\L74\ildata\rc_crawl.py crawl` |
| stop cleanly (flushes, exits) | `python -I scratchpad\gauntlet\L74\ildata\rc_crawl.py stop` then `del icebow\data\crawl\STOP` before restarting |
| status (counts, replays/h from progress.jsonl, 429s, pauses, MiB) | `python -I scratchpad\gauntlet\L74\ildata\rc_crawl.py status` |
| offline rehearsal, no browser, no network | `python -I scratchpad\gauntlet\L74\ildata\rc_crawl.py crawl --dry-run` |
| tests | `python -I scratchpad\gauntlet\L74\ildata\test_rc.py` |

Run it in a normal terminal window (it is a foreground loop; the laptop is shared, so no hidden service). Priority is set to below-normal.

## Behaviour (all tested offline, see below)
- Pace: request starts >= 1.0 s apart plus 0..0.5 s jitter (mean about 0.8 req/s). One request in flight. No ramping, no 429 probing.
- Challenge page / 429 / 403 / login loss: stops, flushes data, writes `PAUSED.json`, posts to Discord (`L69/discord/post.py`, reminder every 30 min),
  and sends NOTHING until the owner creates `RESUME`. A 429 also waits `max(Retry-After, 300 s)`, doubling per consecutive pause up to 3600 s.
  After RESUME the same request is tried once; if blocked again it pauses again.
- Network error or 5xx: 3 automatic retries (30 s, 60 s, 120 s), then a pause. A 404 on a player page skips that player.
- Login loss is detected by `/data/replay` not returning success, then confirmed with `/me` (302 = logged out). A refused replay while logged in is retried twice, then marked failed.
- Frontier: seeds = player tags in the old crawls' `battles.csv` + `--seed-url` pages (default `/players`, unverified) + `--seed-tags FILE`;
  then snowball from every opponent tag. Each player: up to `--max-pages` (3) history pages, stopping at `--floor` (2026-10-19, the balance patch).
  Kept battle types: `pathOfLegend`, `PvP`. Newest battles are fetched first. The same battle seen from both players' histories is fetched once (pair key).
- Dedupe + resume: `state.db` (sqlite) keys on replay tag and battle pair; a crash re-queues unflushed replays. A crash between the parquet write and the
  sqlite mark can duplicate one 500-replay buffer: dedupe on `replay_tag` when reading.
- Safety: STOP file, disk guard (stops below 10 GB free), `OWNER_GO` gate, no cookie access, no navigation, no CAPTCHA handling.
- Output schema: `royaleapi-replay-parquet.v1`, columns and types identical to the HF sample (replays: 11 columns, actions: 21). `payload_json`
  holds battle (type, mode, result, crowns, decks), events (tick, card, side, raw + native x/y, grid, arena label, seat flag, play number), aggregate elixir
  stats, card counts, and `source` with team/opponent tags and battle time (the HF set stripped these; ours keeps them).

## Offline evidence (a)
- `python -I test_rc.py`: ALL 13 TESTS PASSED (2026-10-27).
- Schema: our 2 schemas equal the sample parquet schemas (names + types). Events: 28,394 events from 400 sample replays rebuilt from their own source fields
  and compared with the sample's event JSON: 0 differences (this fixed the coordinate rule: seat 0 -> native (x, 32000-y), seat 1 -> (18000-x, y), and the
  champion list for ability candidates).
- Real payloads: 612 of the 614 payloads saved by the 10-05 crawl parse with play lists identical to its `plays_ext_i1.csv`; the other 2 are 265-byte empty stubs
  (0.3%), which `build_record` refuses and the crawler marks failed.
- State machine: pacing min gap 1.007 s over 97 requests; 429 / challenge / login loss each pause once, alert once, send nothing until RESUME, 429 waits >= 300 s;
  STOP honoured; stop + restart gives 72 unique replays, 0 duplicates; pair dedupe halves the work (72 vs 144 with `--no-pair-dedupe`); floor filter works.
- Full stack with a real Chrome (headless, throwaway profile) attached over CDP to a LOCAL stand-in server (BASE patched): 41 requests through in-page fetch,
  a 429 with Retry-After, pause, RESUME, 20 replays written, Chrome still open after detach, royaleapi.com never contacted.

## Rates and sizes
- (a) Old crawler 10-05 (curl + AIMD, pool 4): 495 replays in 50 min = 594/h; 32 `RateLimited` failures and 10 clearance renewals in that log. Individual 429s were not logged.
- (b) This crawler's ceiling: mean gap 1.25 s = about 2,900 requests/h. At about 1.15 requests per replay (1 replay + 1 history page per 10 battles, less pair dupes)
  that is about 2,500 replays/h = 60k/day, so +750k in about 12.5 days of uninterrupted running. Pauses, re-clearance and 429 cooldowns will stretch this; nothing
  here is measured against the real site. The measured number will come from `status` after the 200-replay run.
- (a, offline) Storage per 100k replays, measured on 611 real replays (87.3 actions each): replays parquet 467 MiB + actions parquet 534 MiB = about 1.0 GiB;
  raw HTML gz adds 418 MiB (`--no-raw` drops it). Plus about 1 to 2 KB per battle in `state.db`. +750k replays is about 7.5 GiB parquet + 3.1 GiB raw. The laptop C: drive has 61 GB free.
  (HF IL_Replay is 7.5 KB per replay; ours is 10.4 KB because `payload_json` embeds the event list that the actions table repeats.)

## Unknowns and risks (read before go)
- (b) The seed page `/players` is a guess from the old default; `probe` prints how many player links it finds. If 0, pass the right leaderboard path with `--seed-url`.
  Local tags from the old crawls (a few hundred) already seed the snowball, so a wrong seed URL costs one request.
- (a) The replay payload has NO card levels, tower hitpoints or game version (0 hits for "level" in the saved payloads). The decks in `payload_json` carry `level: null`.
  The history row HTML is stored (zlib, in `state.db`) so levels can be re-parsed if the row carries them; `probe` prints any attribute whose name contains "level".
  Patch timing is available only through `battle_timestamp`.
- (b) Pair dedupe assumes the two perspectives' replays are the same recording (not verified; `--no-pair-dedupe` turns it off).
- (b) Cloudflare may challenge an attached Chrome more often than a bare one; it cannot be known offline. The earlier crawls lost clearance mid-run on 10-05 and 10-08.
  The crawler's only response is to stop and ask. Do not add any workaround.
- `game_mode` for non-`pathOfLegend` types is the raw battle type string (the HF labels for them are unknown).

## Earlier finding (pod route)
A single request from pod 157.157.221.29 got `403 cf-mitigated: challenge`, and `/data/replay` needs the owner's login, so the pod route was dropped. Nothing was sent after that probe.
