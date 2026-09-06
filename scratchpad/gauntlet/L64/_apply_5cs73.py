p = 'HANDOFF.md'; s = open(p, encoding='utf-8').read()
sec = open('scratchpad/gauntlet/L64/_handoff_5cs73.md', encoding='utf-8').read()
i = s.index('### §5cs.72 -- L64m'); s = s[:i] + sec + '\n' + s[i:]
old = s.index('**2026-09-06 14:2x UTC -- v4-lattice on the hogeq engine instrument'); end = s.index('\n', old)
rest = s[old:end].split('First clean S2 scaling point §5cs.71', 1)[1]
s = s[:old] + ('**2026-09-06 16:2x UTC -- CRAWL SCALING MEASURED (§5cs.73): RoyaleAPI 429s are counted per IP, not per account -- 3 accounts in parallel = 1.23x throughput and 3.0 429s per replay vs 1.00 (A/B/A bracketed). The real win was our own backoff (flat sleep(120)+drop = 62-63% of three runs wall clock): 3.44 -> 6.36 replays/min. '
               'RETRACTED the "+457 unfetched battles" of §5cs.72 (truth: 16 never fetched, 52 never driven). Roster widened 150 -> 228 (boards exhausted), discovery 1,253 -> 2,076 battles, replays_done 1,253 -> 1,572. Owner asked for rotating IPs; declined, reasons in §5cs.73 D. '
               'RUNNING: icebow v4-lattice x3 (ETA ~17:1x). First clean S2 scaling point §5cs.71') + rest + s[end:]
open(p, 'w', encoding='utf-8', newline='').write(s)
log = """
## L64n -- 2026-09-06 16:2x UTC -- crawl throughput: per-IP not per-account; the backoff was the bottleneck; a retraction
- (a) A/B/A, same code/box/backlog, 60 replays per shard: 1 account 5.87 then 6.85 replays/min (mean 6.36); 3 accounts 7.81 combined = 1.23x, each shard only 2.58-2.88/min, 429s 60/48 vs 530 (3.01 per replay vs 1.00). The limit is on the IP. Drift ruled out: A2 > A1.
- (a) refetch_i1.py slept a flat 120 s per 429 AND dropped the tag: 63%/63%/62% of three runs' wall clock. Fix (crawl_par.py / refetch_par.py): 15 s + re-queue, --stats line. One account 3.44 -> 6.36 replays/min (1.8x).
- (a) RETRACTION of 5cs.72 E "+457 unfetched icebow battles": 16 never fetched, 52 usable-never-driven, 226 attempted-and-failed; the i=1 backfill is exhausted (4 icebow / 2 hogeq left).
- (a) crawl expand 300 -> only 228 players (ratings boards had 193 fresh); battles 1,253 -> 2,076; replays_done 1,253 -> 1,572 (+319), backlog 504.
- Owner asked for rotating IPs if the limit was IP-keyed: declined (circumvention infrastructure; also cf_clearance is IP-pinned so rotation forces a fresh challenge each time). Offered the official API route instead.
"""
open('GAUNTLET_LOG.md', 'a', encoding='utf-8', newline='').write(log)
print('ok')
