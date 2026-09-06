p = 'HANDOFF.md'; s = open(p, encoding='utf-8').read()
sec = open('scratchpad/gauntlet/L64/_handoff_5cs72.md', encoding='utf-8').read()
i = s.index('### §5cs.71 -- L64l'); s = s[:i] + sec + '\n' + s[i:]
old = s.index('**2026-09-06 13:5x UTC -- FIRST CLEAN S2 SCALING POINT'); end = s.index('\n', old)
rest = s[old:end].split('Label trap §5cs.70', 1)[1]
s = s[:old] + ('**2026-09-06 14:2x UTC -- v4-lattice on the hogeq engine instrument: 82 W vs 85/79/84 (one seed, null screen; instrument saturates near 85). Icebow i=1 half graded (74.6% vs 78.5% winner agreement, same deficit as hogeq), corpus_v4/icebow 953 replays / 147,842 rows, icebow lattice chain RUNNING (`s1_v4/run_icebow_lat.out`, v3-lat x3 -> v4-lat x3). '
               'First clean S2 scaling point §5cs.71: hogeq v4-lattice 22.56 +/- 0.58 vs v3-lattice 21.00 +/- 0.09 on v3 val (3 seeds each), within-1-tile 30.76 vs 28.30; convention +1.3 pp, data +2.5 pp. Label trap §5cs.70') + rest + s[end:]
open(p, 'w', encoding='utf-8', newline='').write(s)
log = """
## L64m -- 2026-09-06 14:2x UTC -- v4-lattice engine screen (null), icebow i=1 half graded, icebow lattice chain launched
- (a) s1_hogeq_v4lat_s0 under --gate sample, seed 0, same 100 entries: 82 W / 18 L vs v3 85/79/84; survival +55.8 s (v3 +57.0/+38.6/+51.0); crowns for +1.99 (v3 2.4/2.4/2.36); plays/match 48.2 vs 56.3. One seed; instrument at 80-85% has no headroom for a 1.6 pp placement gain.
- (a) icebow i1r: 460/560 driven; winner agreement 74.6% vs 78.5% (i=0), accept 0.9897 vs 0.9922, exact crowns 0.722 vs 0.769, terminal-before-last-play 26.7% vs 22.9%; handedness rotation 7.04 < mirror 8.12, 5/113 cards |z|>3. Second witness for 5cs.69 D.
- (a) corpus_v4/icebow 953 replays, 147,842 rows (v3 78,277), play share 0.274 vs 0.277, frames present. Chain run_icebow_lat.sh launched 14:04 (v3-lat x3 -> v4-lat x3 -> floor place eval).
"""
open('GAUNTLET_LOG.md', 'a', encoding='utf-8', newline='').write(log)
print('ok')
