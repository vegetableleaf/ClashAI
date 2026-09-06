p = 'HANDOFF.md'; s = open(p, encoding='utf-8').read()
sec = open('scratchpad/gauntlet/L64/_handoff_5cs67.md', encoding='utf-8').read()
i = s.index('### §5cs.66 -- L64g'); s = s[:i] + sec + '\n' + s[i:]
trap = ("* **RoyaleAPI replay markers: `data-i` is a per-replay PERSPECTIVE flag, not an occurrence index (§5cs.67).** The crawler's join dropped every i=1 replay (half the crawl); "
        "the i=1 half is served in the other seat's frame (team at tile_y < 16) and must be rotated (18-x, 32-y) into the corpus frame. Keep raw payloads.\n")
i = s.index('## 8. Measurement traps\n\n') + len('## 8. Measurement traps\n\n'); s = s[:i] + trap + s[i:]
old = s.index('**2026-09-06 08:5x UTC -- S1 DONE'); end = s.index('\n', old)
rest = s[old:end].split('Before that: ', 1)[1]
s = s[:old] + ('**2026-09-06 08:3x UTC -- S2 UNBLOCKED: the x/y-less half of the crawl was a crawler join bug (§5cs.67); re-fetch of 615 icebow + 299 hogeq replays RUNNING (task bm34pp1cy, ~1-1.5 h) -> positioned corpus 2.0x; '
               'hogeq engine read running on both slots (thr_s0 / none_s0 done / rnd13_s0). S1 DONE (icebow tile 18.22 +/- 0.11, hogeq 20.99 +/- 0.36 §5cs.64-65); engine band closed for icebow §5cs.66. Before that: ') + rest + s[end:]
open(p, 'w', encoding='utf-8', newline='').write(s)
log = """
## L64h -- 2026-09-06 08:3x UTC -- the x/y-less half was a crawler join bug; re-fetch launched (2.0x positioned corpus)
- (a) x/y all-or-nothing per replay (icebow 619/612/6 partials, hogeq 296/295/4); no battle field separates the halves (mode, date, rating, player, wave all ~50%). Cause: `data-i` is a per-replay flag; crawl join keyed on it and only looked up "0". Fresh fetch of an uncovered tag: 109/109 markers, all i=1.
- (a) i=1 half is the other seat's frame (team median tile_y 13.5 vs 18.5) -> rotate (18-x, 32-y) at corpus build; handedness (b), check per-card x histograms after the re-fetch.
- Re-fetch running (refetch_i1.py, 615 + 299 tags, saved token accepted, raw payloads now kept). Expected: icebow 619 -> ~1,237 positioned replays, hogeq 296 -> 595. Next: hogeq engine read, then corpus v4 + S1 re-run as the data-scaling measurement.
"""
open('GAUNTLET_LOG.md', 'a', encoding='utf-8', newline='').write(log)
print('ok')
