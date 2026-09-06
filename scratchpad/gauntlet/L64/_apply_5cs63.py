p = 'HANDOFF.md'; s = open(p, encoding='utf-8').read()
sec = open('scratchpad/gauntlet/L64/_handoff_5cs63.md', encoding='utf-8').read()
i = s.index('### §5cs.62 -- L64c'); s = s[:i] + sec + '\n' + s[i:]
old = s.index('**2026-09-06 05:2x UTC -- S1 TRAINING RUNNING (L64c:'); end = s.index('\n', old)
rest = s[old:end].split('Before that: ', 1)[1]
s = s[:old] + ('**2026-09-06 05:5x UTC -- S1 TRAINING RUNNING (L64d: icebow s0 18.1 / s1 18.3 val tile, s2 then hogeq s0-2 running, ETA ~06:45 UTC, task b6vmgii7c; '
               'engine play harness for the new model built + smoked §5cs.63; §5cs.48 grid ruling RETRACTED §5cs.62); ENGINE UP, slots idle. Before that: ') + rest + s[end:]
open(p, 'w', encoding='utf-8', newline='').write(s)
log = """
## L64d -- 2026-09-06 05:5x UTC -- seed 1 agrees; engine play harness for the S1 model
- icebow s1 (a): val tile 18.34 / half 16.15 (s0: 18.12 / 15.36); old's 432 grid 13.28 vs old 13.70 (clean 14.29 vs 13.13). Band waits on s2.
- pipeline/engine_play.py (a): S1 model on the real engine vs L62 ghosts; 2-match smoke 1W-1L, 45/47 plays accepted, 8.8 plays/min (pool humans 10.9), deterministic. 3 offline tests OK.
- Traps: engine refuse code 13 = no elixir (engine_env retry keys on 1050 only); pool entry 02GY9R09LU8J 3-crowns us by t=70 s even with no plays -> 500-match run needs a no-plays control per tag.
"""
open('GAUNTLET_LOG.md', 'a', encoding='utf-8', newline='').write(log)
print('ok')
