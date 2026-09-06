p = 'HANDOFF.md'; s = open(p, encoding='utf-8').read()
sec = open('scratchpad/gauntlet/L64/_handoff_5cs65.md', encoding='utf-8').read()
i = s.index('### §5cs.64 -- L64e'); s = s[:i] + sec + '\n' + s[i:]
old = s.index('**2026-09-06 06:2x UTC -- S1 TRAINING RUNNING (L64e:'); end = s.index('\n', old)
rest = s[old:end].split('Before that: ', 1)[1]
s = s[:old] + ('**2026-09-06 07:5x UTC -- S1 DONE (6 checkpoints, icebow tile 18.22 +/- 0.11, hogeq 20.99 +/- 0.36 §5cs.64-65); ENGINE READ RUNNING (L64f: icebow s0 75-25 vs ghosts on 100 entries, no-plays 0-100, random 0-100 §5cs.65; '
               's1 checkpoint x100 in flight on port 37032); trainers 0. Before that: ') + rest + s[end:]
open(p, 'w', encoding='utf-8', newline='').write(s)
log = """
## L64f -- 2026-09-06 07:5x UTC -- hogeq band closed; first engine read with controls
- hogeq 3 seeds (a): val tile 21.30/20.58/21.08 = 20.99 +/- 0.36 (baseline 11.45), half 19.26, card 54.91 (42.32); value acc 53.7 (icebow 69.8; crowns mismatch suspected, untested). Best epochs 20/11/18.
- Engine, icebow s0 ckpt, 100 paired pool entries (a): threshold 75W-25L, sampled 68-32; no-plays control 0-100 (91 s), rate-matched random policy 0-100 (130 s). Model survives +115 +/- 5.5 s on 100/100 entries, crowns against 0.86 vs 3.00. Model win rate identical on entries the pro won (75%) and lost (76%); all 100 engine-terminated.
- Not established: reactive opponents; old init on this instrument; checkpoint variance (s1 ckpt in flight). Harness: --policy random added.
"""
open('GAUNTLET_LOG.md', 'a', encoding='utf-8', newline='').write(log)
print('ok')
