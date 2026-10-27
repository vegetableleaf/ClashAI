# RoyaleAPI replay crawl (ticket D2, plan1026 Pillar 4e) -- STATUS: BLOCKED, nothing crawled

Date 2026-10-27. Labels: (a) measured this session or read from a file, (b) plausible, untested, (c) contradicted.

## Why no crawler is running on the pod
- (a) Probe: ONE request, `curl https://royaleapi.com/` from pod 157.157.221.29 (port 30408), honest UA with contact address.
  Result: `HTTP/2 403`, `cf-mitigated: challenge`, body title "Just a moment..." (Cloudflare interactive challenge).
  Rule from the ticket: stop on any block page, never bypass Cloudflare. I stopped after that one request. No further request was sent.
- (a) The challenge is separate from rate limiting. RoyaleAPI said they cannot disable rate limiting; that does not clear this block.
  The approval email (as relayed to me) did not mention a Cloudflare allowlist for the pod IP.
- (a) `/data/replay` (the only endpoint that returns plays) is login-gated: it needs the owner's RoyaleAPI session cookie plus a
  `cf_clearance` cookie (scraper `royale/transport.py`, `royale/pipeline.py` `fetch_replay`). A session cookie is a credential;
  I may not read it out of a browser or type it anywhere, and I do not hold one.
- (a) The old crawlers only ever worked from a headful browser a human had cleared and logged into
  (`clash-replay-scraper/crawl_polite.py`, `royale/browser.py`: one visible Chrome, in-page `fetch()`, <= 1 req/s, pause on challenge/403/429).
  The pod has no display (`DISPLAY` unset on a RunPod container; that tooling raises "no display" on Linux). `cf_clearance` is
  bound to the IP and UA that solved the challenge (transport.py docstring), so a laptop-earned clearance cannot be moved to the pod
  without exactly the cookie copying the 10-08 rules forbid.
- (c) Contradicted: "a resumable crawler on one pod under nohup" is not buildable honestly today. Code written now could not be tested
  against the real endpoint, and its only working auth path would be a challenge bypass. I wrote none.

## What the old crawler measured (the only rate evidence we hold)
- (a) `clash-replay-scraper/crawl_run2.log` (10-05, curl + AIMD limiter, pool 4): "495 new replays in 50 min" = about 594 replays/hour.
  In that log: 32 `RateLimited` failures (each already after 6 backoffs), 10 "clearance expired" renewals. Individual 429 counts were
  not logged, so the per-request 429 rate is NOT measured. Do not quote one.
- (b) 750k at 594/h = 1,263 h = 52.6 days. At the polite 1 request/s ceiling (crawl_polite.py), replays cost about 1.1 requests each
  (1 request per replay + 1 history page per 10 battles), so about 3,300 replays/h, 79k/day, +750k in about 9.5 days. Untested: it
  needs the real 429 threshold, which moves (limiter.py docstring).
- (b) Storage per 100k replays: not measured by me. ILDATA.md: 252,238 replays + 17.8 M actions = 1.89 GB parquet, so about 750 MB per
  100k as parquet. Raw HTML payloads (crawl_polite keeps them) are larger; unmeasured.

## What would unblock it (owner / lead decision, not mine)
1. Ask RoyaleAPI to allowlist the pod IP in Cloudflare (or give a service token / bulk export). They control the Cloudflare rule;
   rate limiting is a different knob. An export dump would beat any crawl.
2. Or run the existing polite crawler on the LAPTOP in a real Chrome the owner clears and logs into (<= 1 req/s, pauses on
   challenge/429). The laptop is shared, so this needs the owner's go; expect re-clearance stops (cleared passes expired mid-crawl on
   10-05 and 10-08).
3. Either way, the crawler to build is: seed (leaderboard + deck ratings + clan players) -> battle history (`?before=` cursor) ->
   dedupe on replay tag -> `/data/replay` -> parse (`royale/parse.py`, `replay_ext`) -> IL_Replay-compatible parquet
   (`royaleapi-replay-parquet.v1`, columns in ILDATA.md source 1) with stop file + resume state. I can build and test it as soon as one of
   routes 1-2 gives it an endpoint it is allowed to call. Restart command: none yet (nothing running).

## State
- Pod /workspace/crawl: not created. No data anywhere. Probe temp files on the pod removed.
