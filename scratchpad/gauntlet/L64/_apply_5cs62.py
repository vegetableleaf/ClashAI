import io
p = 'HANDOFF.md'; s = open(p, encoding='utf-8').read()
sec = open('scratchpad/gauntlet/L64/_handoff_5cs62.md', encoding='utf-8').read()
i = s.index('### §5cs.61 -- L64b'); s = s[:i] + sec + '\n' + s[i:]
h = s.index('### §5cs.48'); e = s.index('\n', h)
s = s[:e] + ' **[RETRACTED in §5cs.62 -- the probe read live-screen frame fractions as board tiles; on the trainer grid the 432 row pitch is 1.333 tiles and 576 has zero quantisation error.]**' + s[e:]
trap = ("* **`ActionSpace(cfg)` is the LIVE tap space; the trainer's grid is `sim/env.py::_board_action_space` (§5cs.62).** "
        "`cell_center` of the live space returns screen-frame fractions (arena box y 0.137..0.753), not board fractions; "
        "converting them with `*32` produced the phantom \"0.499-tile row pitch\" of §5cs.48. Any grid-geometry question about "
        "training goes through `_board_action_space`.\n")
i = s.index('## 8. Measurement traps\n\n') + len('## 8. Measurement traps\n\n'); s = s[:i] + trap + s[i:]
old = s.index('**2026-09-06 05:0x UTC -- S1 TRAINING RUNNING (L64b:'); end = s.index('\n', old)
rest = s[old:end].split('Before that: ', 1)[1]
s = s[:old] + ('**2026-09-06 05:2x UTC -- S1 TRAINING RUNNING (L64c: icebow s0 done, val tile 18.1%/half 15.4%, one seed §5cs.62; '
               's1-2 then hogeq s0-2 running, ETA ~06:45 UTC, task b6vmgii7c; §5cs.48 grid ruling RETRACTED §5cs.62); ENGINE IDLE. Before that: ') + rest + s[end:]
open(p, 'w', encoding='utf-8', newline='').write(s)
log = """
## L64c -- 2026-09-06 05:2x UTC -- RETRACTION of 5cs.48 (grid pitch), old init re-scored on S1 val, S1 seed 0
- RETRACTED (a): L62i measured the LIVE ActionSpace (frame fractions x32) -> phantom 0.499 pitch. Trainer grid (_board_action_space): 432 = 1.333 tiles/row (owner was right), 576 = 1.000 with ZERO snap error on 2,657 pro x-bows; 432 max backward snap 0.5 tiles, 0/242 in-reach x-bows lost at either grid (owner's "one tile back / out of reach" still contradicted in magnitude).
- Old init on the same 3,796 S1 val plays (a): 432 grid 13.70/41.73 (clean 2,072 rows 13.13/41.51; 37/85 val replays were in its train split); 1-tile bins 6.69%.
- S1 icebow s0 (a, one seed): val tile 18.1% / half 15.4% (baseline 8.9/8.5), card 59.2%, gate bal-acc 0.715 (leak gone), emb cos 0.20. Matched grid: 1-tile new 17.3 vs old 6.7; old's 432 grid new 12.5 vs old 13.7 (clean 13.6 vs 13.1); miss distance mean 4.07 vs 5.28 tiles.
- Monitor events also re-invoke the loop (a). Next: 3-seed bands per deck (~06:45 UTC).
"""
open('GAUNTLET_LOG.md', 'a', encoding='utf-8', newline='').write(log)
print('ok')
