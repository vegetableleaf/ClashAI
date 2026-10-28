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

## D2c: several exit IPs under RoyaleAPI's written limits (built + tested OFFLINE 2026-10-27; NOT enabled)
No request to royaleapi.com was sent for D2c. Enabling it needs the lead's explicit go.

### Limits the code enforces (RoyaleAPI's conditions, accepted by the owner)
| condition | how |
|---|---|
| <= 2 req/s and <= 150k/day combined | ONE limiter in `state.db` for every lane and every restart: request starts `GLOBAL_GAP` = 0.63 s apart; a lane that wakes > `LATE` = 0.1 s after its slot takes a new one. Result: any 3 starts span >= 1.16 s (<= 2 per 1 s window), any 60 s window <= 96 (= 1.6/s). `DAILY_CAP` 140,000 per UTC day, counted per request in `state.db` (table `daily`); a followed redirect counts as one more. 1.6/s for 24 h is 138,240, so the cap is a backstop. |
| all instances / machines | `icebow/data/crawl_instance.lock` (sqlite exclusive lock, dropped by the OS on exit): a second real crawler process on the laptop refuses to start. Nothing else crawls RoyaleAPI. The D2b process started before this code does NOT take the lock: stop it before starting a D2c run. |
| IP rotation never to evade | each lane = one Chrome the owner logged in by hand; the code never logs in, never handles a check, never reads cookies; lanes on the same exit network (/24) are refused at start (`ips`). Global caps apply whatever the number of lanes. |
| honour Retry-After; 429 pauses that IP | `--auto-resume-rate`: that lane waits `max(Retry-After, 300 s doubling, max 3600 s)`, other lanes go on (`--rate-scope all` cools every lane). Without the flag a 429 pauses that lane until its RESUME (below), never before Retry-After. |
| challenges (RoyaleAPI reply 10-28: collection may continue through challenges; full stop only on a permanent ban) | challenge / login loss / first 401-403 / 3 failed network retries on a lane write `PAUSED_<port>.json` (with `trigger`: URL path without query, status, cf-mitigated, page title; also appended to `state.db` meta `blocks`) and post ONE alert naming the lane (port, exit IP). ONLY that lane waits, until the owner clears that Chrome by hand and runs `rc_crawl.py resume --lane <port>` (`RESUME_<port>`; a single-lane run also takes the plain `resume`). Other lanes keep collecting under the same global limits. The code never solves, scripts or navigates to a challenge and never reads cookies. |
| permanent ban: stop all | a lane still answered 401/403 (not a challenge) on its FIRST request after the owner's RESUME: `BANNED.json`, `STOP` file (every lane and every later start), one alert. |
| stop promptly | one `STOP` file stops every lane (checked before each request and every <= 5 s while waiting); an in-flight fetch finishes (<= 45 s timeout). |
| pause on request / on disruption | `stop`; 4 consecutive 5xx on a lane (3 retries, 30/60/120 s) write the global `PAUSED.json`: ALL lanes wait for the plain `RESUME`. A global `PAUSED.json` left by D2b also holds a restarted run until `resume`. |

Per lane (= per IP): `--min-gap` (default now 8 s, was 1 s) + 0..0.5 s jitter. Work queue and dedupe are D2b's `state.db`; claims are atomic under one lock, and the new run takes over D2b's `state.db` as is.

### Measured this session (a)
- Exit IPs (ssh + `curl api.ipify.org`, then the full path: `ssh -D` to 33308 -> headless Chrome `--proxy-server=socks5://...` -> `rc_crawl.py ips`): laptop 96.237.100.236; pods 32657, 33308 leave through a NAT POOL that picks 185.226.156.3 or 185.226.156.5 per connection (8 samples each, both addresses on both pods); 33920 gave 185.226.156.5 (1 sample). **So the 3 pods are ONE exit, not 3 (contradicts "each pod = one exit IP", (c))**, and a pod lane's address changes between connections.
- Tunnel down -> the proxied Chrome fails (no fallback to the laptop IP): `exit-IP check failed`.
- Live D2b crawl (progress.jsonl, read only): last segment at `--min-gap 8`: 71 requests in 658 s, 0 x 429; then a Cloudflare challenge at 23:29 UTC (and 00:00 UTC per the lead) on the in-page fetch while the tab looked normal. Earlier segments at shorter gaps had one 429 each.

### Setup (the owner, after the lead's go)
`python -I scratchpad\gauntlet\L74\ildata\rc_crawl.py lanes` prints, from `lanes.json`, per lane: the `ssh -D` tunnel command, the Chrome line (own `--user-data-dir`, own port, `--proxy-server`), then the `ips` check and the crawl command. `lanes --start-tunnels` also starts the tunnels and prints their PIDs (stop by exact PID). Then: log in to RoyaleAPI in each Chrome by hand, run `ips` (opens and closes one tab per Chrome on api.ipify.org; must say OK), then `crawl ... --cdp URL1 --cdp URL2`. `status` shows today's count, the remaining budget, each lane's req/s, 429s and pauses, and the lane IPs.

### Concerns (read before go)
- (a) Only 2 distinct exits exist today (laptop + the pod pool). At 8 s per IP that is 0.25 req/s, not 1.6.
- (b) A pod lane's address alternates between .3 and .5. Cloudflare clearance is usually tied to the IP, so a pod lane may be challenged often; each challenge pauses that lane until the owner clears it by hand. Untested; the measurement below shows it.
- (b) The live laptop lane is already being challenged on the fetch path (2 times tonight). If the fetch is challenged right after each clearance, that lane alternates pause / RESUME / pause and the owner gets an alert each time; the code does nothing to avoid it (hard rule).
- (b) If the 429 is per ACCOUNT, cooling only the IP would keep sending for an account that was told to wait. Until (a) of the plan is known, use `--rate-scope all` (or one account per lane).
- The owner's own page loads in those Chromes (and Chrome's favicon fetch) also count against RoyaleAPI's 2/s; our 1.6/s cap leaves 0.4/s for them.
- "<= 1.6/s over any 1 s window" cannot hold literally for whole requests (it would mean <= 1 per second, a 1.0/s cap). Implemented: <= 2 per any 1 s window (RoyaleAPI's own limit) and <= 96 per any 60 s window (1.6/s).

### Measurement plan for the lead to approve (not run)
Goal: (a) is the 429 per IP or per account? (b) the safe per-IP gap. Both lanes logged in to the SAME RoyaleAPI account.
1. M1, 2 lanes (laptop + pod33308), same account, `--min-gap 8 --rate-scope ip --auto-resume-rate --max-replays 400`, about 50 min (0.25 req/s total, 1/8 of RoyaleAPI's limit). Read per lane from `status` / `progress.jsonl` / `blocks`: 429 times per lane.
   - per IP: 429s on one lane are not followed by 429s on the other within its next few requests, and the two lanes' 429 counts match single-IP history at 8 s (0 in 71 tonight).
   - per account: 429s arrive on both lanes together (within about 2 requests of each other), or the two-lane total behaves like ONE IP at half the gap (tonight's shorter-gap segments each had one 429; their exact gaps were not logged).
   - challenges per lane (count, time to the first, time between) tell whether a pod lane is usable at all; a ban stops M1 by rule.
2. M2 (only if M1 says per IP and no challenges): one lane at a time, 30 min each, gaps 6, 4, 3 s, stopping at the first 429; safe gap g = the smallest gap with 0 x 429 in 30 min, times 1.5 as margin.
3. If M1 says per account: per-IP lanes do not raise the limit; the rate is set by the account (one account per lane would be needed, and RoyaleAPI's combined caps still apply; ask the lead/owner before that).
IPs needed for 1.6 req/s = ceil(1.6 x g): g = 8 s -> 13 exits; g = 4 s -> 7; g = 2 s -> 4. Exits must differ by network (/24); RunPod pods on the 157.157.221.29 host count as one. Today's 2 exits give 2/g req/s (0.25 at 8 s).

## Earlier finding (pod route)
(D2c above routes a pod only as an exit for a Chrome the owner clears and logs into; the curl route stays dropped.)
A single request from pod 157.157.221.29 got `403 cf-mitigated: challenge`, and `/data/replay` needs the owner's login, so the pod route was dropped. Nothing was sent after that probe.
