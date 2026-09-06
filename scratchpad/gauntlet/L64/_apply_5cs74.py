p = 'HANDOFF.md'; s = open(p, encoding='utf-8').read()
sec = open('scratchpad/gauntlet/L64/_handoff_5cs74.md', encoding='utf-8').read()
i = s.index('### §5cs.73 -- L64n'); s = s[:i] + sec + '\n' + s[i:]
old = s.index('**2026-09-06 16:2x UTC -- CRAWL SCALING MEASURED'); end = s.index('\n', old)
rest = s[old:end].split('RUNNING: icebow v4-lattice x3 (ETA ~17:1x). ', 1)[1]
s = s[:old] + ('**2026-09-06 17:4x UTC -- S2 SCALING REPLICATES ON THE SECOND DECK (§5cs.74): icebow v4-lattice 19.84 +/- 0.19 vs v3-lattice 18.17 +/- 0.15 = +1.67 pp per corpus doubling, against hogeq +1.56 pp; NLL 3.33 vs 3.50, card 62.1 vs 59.2, gate 74.5 vs 70.2, value 72.2 vs 69.9. Convention-free within-1-tile: icebow 25.76 floor -> 28.03 lattice -> 29.95 v4. '
               'RUNNING: icebow backlog drain 410/504 (one account, per-IP §5cs.73). NEXT: corpus_v5 = +52 never-driven +~500 new replays -> the THIRD scaling point; then hogeq roster past its PLAYERS_CAP 50 (expand ported to crawl_deck.py). ') + rest + s[end:]
open(p, 'w', encoding='utf-8', newline='').write(s)
log = """
## L64o -- 2026-09-06 17:4x UTC -- the S2 scaling result replicates on icebow
- (a) icebow, same v3 val (6,133 rows), 3 seeds per arm: v3 lattice 18.02/18.18/18.31 = 18.17 +/- 0.15; v4 lattice 19.84/20.02/19.65 = 19.84 +/- 0.19. +1.67 pp per doubling vs hogeq's +1.56. NLL 3.326 vs 3.495, card 62.1 vs 59.2, gate bal 74.5 vs 70.2, value 72.2 vs 69.9. No seed overlap.
- (a) within-1-tile, both decks: hogeq 26.99 floor -> 28.30 lattice -> 30.76 v4 (convention +1.31, data +2.46); icebow 25.76 -> 28.03 -> 29.95 (convention +2.27, data +1.92). The split is deck-dependent -- icebow's floor labels were the more damaged, so it gained more from the fix. Mean miss 4.65->4.28 and 4.07->3.76 tiles.
- (b) Two points per deck is not a curve. Next: corpus_v5 (+52 never-driven, +~500 fetched today) for the third point; then the hogeq roster past PLAYERS_CAP=50 (expand ported to crawl_deck.py, backup in scratchpad).
"""
open('GAUNTLET_LOG.md', 'a', encoding='utf-8', newline='').write(log)
print('ok')
