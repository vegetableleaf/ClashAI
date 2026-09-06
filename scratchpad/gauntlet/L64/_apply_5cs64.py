p = 'HANDOFF.md'; s = open(p, encoding='utf-8').read()
sec = open('scratchpad/gauntlet/L64/_handoff_5cs64.md', encoding='utf-8').read()
i = s.index('### §5cs.63 -- L64d'); s = s[:i] + sec + '\n' + s[i:]
h = s.index('**TRAPS (a):** (1) engine `result_code 13`'); h2 = s.index('(2) m1\'s 0-3 in 78 s is the ghost pool entry', h)
s = s[:h2] + '**[(2) WITHDRAWN in §5cs.64-C: a passive player loses to ANY entry in ~60-70 s; 02G is not pathological.]** ' + s[h2:]
old = s.index('**2026-09-06 05:5x UTC -- S1 TRAINING RUNNING (L64d:'); end = s.index('\n', old)
rest = s[old:end].split('Before that: ', 1)[1]
s = s[:old] + ('**2026-09-06 06:2x UTC -- S1 TRAINING RUNNING (L64e: icebow 3-seed band CLOSED val tile 18.22 +/- 0.11 §5cs.64; hogeq s0-2 running, ETA ~07:00 UTC, task b6vmgii7c; '
               'engine harness has a no-plays control, §5cs.63 trap (2) withdrawn); ENGINE UP, slots idle. Before that: ') + rest + s[end:]
open(p, 'w', encoding='utf-8', newline='').write(s)
log = """
## L64e -- 2026-09-06 06:2x UTC -- icebow band closed; no-plays control; L64d trap (2) withdrawn
- icebow 3 seeds (a): val tile 18.12/18.34/18.20 = 18.22 +/- 0.11 (baseline 8.90); half 15.99 +/- 0.57; card 59.26; gate bal-acc 0.70. Seed 2 best at epoch 20 (schedule maybe short, untested).
- Old init on its 432 grid (a): ahead of all 3 seeds on all rows (13.70 vs 12.54-13.28) but 37/85 val replays were in its train split; on the 2,072 clean rows all 3 seeds ahead (13.61-14.29 vs 13.13). Miss distance 4.07 vs 5.28 tiles every seed.
- `--gate none` control (a): passive icebow loses 0-3 at 61 s (099P9CL8L2QJ, the entry the model beat 2-1) and 70 s (02GY9R09LU8J). WITHDRAWN: L64d's "pathological entry" -- undefended = dead in a minute, any entry. Engine reads must be deltas vs the per-tag control. engine_env ghost retry now also keys on code 13.
- hogeq s0-2 running, ETA ~07:00 UTC.
"""
open('GAUNTLET_LOG.md', 'a', encoding='utf-8', newline='').write(log)
print('ok')
