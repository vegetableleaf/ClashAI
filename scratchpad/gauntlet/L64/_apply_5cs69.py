p = 'HANDOFF.md'; s = open(p, encoding='utf-8').read()
sec = open('scratchpad/gauntlet/L64/_handoff_5cs69.md', encoding='utf-8').read()
i = s.index('### §5cs.68 -- L64i'); s = s[:i] + sec + '\n' + s[i:]
trap = ("* **A `replay_batch.py` drive without `--record-every 20` yields play-only replays (`play_frames`, no `frames`) and `dataset.py` silently builds 0 WAIT rows from them (§5cs.69).** "
        "Check `frames` in the first replay file of any new corpus dir before building a dataset; corpus_v3's flags are `--record-every 20 --record-plays --determinism-every 10`.\n")
i = s.index('## 8. Measurement traps\n\n') + len('## 8. Measurement traps\n\n'); s = s[:i] + trap + s[i:]
old = s.index('**2026-09-06 09:4x UTC -- hogeq engine band'); end = s.index('\n', old)
rest = s[old:end].split('Before that: ', 1)[1]
s = s[:old] + ('**2026-09-06 11:1x UTC -- hogeq engine band CLOSED under the sampled gate 85/79/84 (threshold 53/19/44 was the tau rule; rate-matched random 15-85) §5cs.69; hogeq i=1 half re-fetched (275/299) and fidelity-checked (winner agreement 65.3% vs 67.2%, frame offset 0.008 tiles); '
               'RUNNING: hogeq i=1 re-drive with v3 flags (37032) -> chained corpus_v4/hogeq + S1 x3 (--tag v4, eval on v3 val vs 20.99 +/- 0.36); icebow re-fetch ~283/615 (~12:3x UTC). Before that: ') + rest + s[end:]
open(p, 'w', encoding='utf-8', newline='').write(s)
log = """
## L64j -- 2026-09-06 11:1x UTC -- hogeq band closes under the sampled gate; i=1 half verified; one re-drive trap
- (a) --gate sample, same 100 entries: s0 85-15 / s1 79-21 / s2 84-16 (sd 3.2) vs threshold 53/19/44 (sd 17.6). Accepted plays/match 32.9/27.4/30.5; mean elixir at decision 3.4; first play 7 s. Rate-matched random p 0.18 (25.0 plays/match): 15-85. RETRACTED: "s1 is the outlier" -- the tau 0.5 rule was. hogeq engine instrument = sample from here.
- (a) i=1 hogeq half: re-fetch 275/299 (24 RateLimited skips, resumable); drive 222/274 ok (52 evo-card failures, same as v3); winner agreement 65.3% vs 67.2%, acc 98.0 vs 98.7, exact crowns 54.5 vs 56.4; y offset 0.008 tiles over 97 cards -> rotation exact. (b) engine ends before last real play 52% vs 36.5%; hogeq halves differ in real 3-crown rate 17.3% vs 8.1% (icebow halves equal).
- TRAP: chained drive lacked --record-every 20 -> no wait frames -> v4 would have had 0 new WAIT rows. Deleted; re-drive with v3 flags running (165/274), corpus_v4 + S1 x3 (--tag v4) chained; eval_s1.py reads v3 and v4 checkpoints on the same val rows (reproduces 0.2130).
- Crawler source fix applied + verified (10/10 payloads identical to the refetch parser). icebow re-fetch 283/615.
"""
open('GAUNTLET_LOG.md', 'a', encoding='utf-8', newline='').write(log)
print('ok')
