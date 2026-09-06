p = 'HANDOFF.md'; s = open(p, encoding='utf-8').read()
sec = open('scratchpad/gauntlet/L64/_handoff_5cs70.md', encoding='utf-8').read()
i = s.index('### §5cs.69 -- L64j'); s = s[:i] + sec + '\n' + s[i:]
trap = ("* **S1 placement labels: the crawl lattice (500-unit half-tiles) sits ON the floor-grid cell boundaries, and the crawl spells the same point as 500k or 500k-1 at random (§5cs.70).** "
        "`floor` flips 72% of hogeq labels by jitter and the i=1 rotation flips them the other way; train with `--grid lattice` (round), never mix conventions in one comparison, and read a checkpoint's `grid` before placing with it.\n")
i = s.index('## 8. Measurement traps\n\n') + len('## 8. Measurement traps\n\n'); s = s[:i] + trap + s[i:]
old = s.index('**2026-09-06 11:1x UTC -- hogeq engine band CLOSED'); end = s.index('\n', old)
rest = s[old:end].split('Before that: ', 1)[1]
s = s[:old] + ('**2026-09-06 12:0x UTC -- S1 LABEL TRAP FOUND (§5cs.70): floor-quantised placement labels on a grid whose boundaries are the pro lattice; 126/455 hogeq lattice points carried two labels, the i=1 rotation flips the jitter side, naive v4 s0 read tile 0.2328 but cell 0.1365 (v3: 0.2130 / 0.2003). '
               'Fix `--grid lattice` shipped (floor default untouched, v3 checkpoints read identically). RUNNING: naive v4 x3 (record), then chained hogeq v3-lattice x3 -> v4-lattice x3 (ETA ~14:00 UTC, `s1_v4/run_hogeq_lat.out`); icebow i=1 chain armed on its re-fetch (403/615). '
               'hogeq engine band CLOSED under the sampled gate 85/79/84 §5cs.69. Before that: ') + rest + s[end:]
open(p, 'w', encoding='utf-8', newline='').write(s)
log = """
## L64k -- 2026-09-06 12:0x UTC -- S1 label trap: floor grid on the pro lattice; naive v4 mixes conventions; `--grid lattice` shipped
- (a) crawl x/y are 500k or 500k-1 at random for the same point; floor(x*36) puts the lattice ON cell boundaries -> 126/455 hogeq lattice points carry two labels, 71.8% of rows jittered; rotation of the i=1 half flips the side. Naive v4 s0 on v3 val: tile 0.2328 (v3 0.2130) but cell_half 0.1365 (0.2003), NLL 4.18 (3.90). Engine inverse was 250 units off the lattice.
- (a) fix: model_v3 cell_label/tile_of_cell/cell_xy, train_s1 --grid lattice (stored in ckpt args), eval_s1/engine_play honour it; floor path byte-identical (s1_hogeq_s0 0.2130/0.2003/3.899 reproduced); lattice round-trip 0.000 units; 0 points with two labels.
- Running: naive v4 x3 to completion (record), chained v3-lattice x3 -> v4-lattice x3 (ETA ~14:00 UTC); icebow i=1 chain armed. Next: lattice bands, then a lattice checkpoint on the sample-gate engine instrument vs 85/79/84.
"""
open('GAUNTLET_LOG.md', 'a', encoding='utf-8', newline='').write(log)
print('ok')
