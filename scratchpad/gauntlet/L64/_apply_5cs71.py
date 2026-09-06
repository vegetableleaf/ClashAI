p = 'HANDOFF.md'; s = open(p, encoding='utf-8').read()
sec = open('scratchpad/gauntlet/L64/_handoff_5cs71.md', encoding='utf-8').read()
i = s.index('### §5cs.70 -- L64k'); s = s[:i] + sec + '\n' + s[i:]
old = s.index('**2026-09-06 12:0x UTC -- S1 LABEL TRAP FOUND'); end = s.index('\n', old)
rest = s[old:end].split('hogeq engine band CLOSED', 1)[1]
s = s[:old] + ('**2026-09-06 13:5x UTC -- FIRST CLEAN S2 SCALING POINT (§5cs.71): hogeq v4-lattice 22.56 +/- 0.58 vs v3-lattice 21.00 +/- 0.09 lattice-point top-1 on v3 val (3 seeds each), NLL 3.41 vs 3.61, within-1-tile 30.76 vs 28.30; convention +1.3 pp, data +2.5 pp. '
               'RUNNING: s1_hogeq_v4lat_s0 on the sample-gate engine instrument (27/100, `engine_hogeq/smp_v4lat0.txt`) vs 85/79/84; icebow i=1 drive 407/560 then fidelity/handedness -> corpus_v4/icebow -> lattice bands. '
               'Label trap §5cs.70 (floor grid on the pro lattice; `--grid lattice` shipped). hogeq engine band CLOSED') + rest + s[end:]
open(p, 'w', encoding='utf-8', newline='').write(s)
log = """
## L64l -- 2026-09-06 13:5x UTC -- first clean S2 scaling point: hogeq v4-lattice vs v3-lattice
- (a) v3 val 6,133 rows, 3 seeds each: v3 lattice 20.91/21.02/21.08 (21.00 +/- 0.09), NLL 3.611; v4 lattice 22.84/21.90/22.95 (22.56 +/- 0.58), NLL 3.407; card 57.8 vs 55.0, gate bal 66.6 vs 61.1, value 57.9 vs 55.1.
- (a) convention-free within-1-tile: v3 floor 26.99, v3 lattice 28.30, naive v4 floor 29.33, v4 lattice 30.76; mean miss 4.65 / 4.59 / 4.41 / 4.28 tiles. Convention +1.3 pp, data +2.5 pp, additive.
- (a) naive v4 record: floor tile 23.10 +/- 0.32 but cell 13.36 / NLL 4.18-4.24 -- the trap, not a scaling number. Trap: lattice cell_tile == cell_half; never in a column with floor tile.
- Running: smp_v4lat0 engine read (27/100) vs 85/79/84; icebow i=1 drive 407/560 -> fidelity/handedness -> corpus_v4/icebow -> lattice bands.
"""
open('GAUNTLET_LOG.md', 'a', encoding='utf-8', newline='').write(log)
print('ok')
