p = 'HANDOFF.md'; s = open(p, encoding='utf-8').read()
sec = open('scratchpad/gauntlet/L64/_handoff_5cs66.md', encoding='utf-8').read()
i = s.index('### §5cs.65 -- L64f'); s = s[:i] + sec + '\n' + s[i:]
trap = ("* **Two engine slots, not four (§5cs.66).** 37031/37032 are the adb-forward doors and 38031/38032 the DIRECT doors of the same two guest engines; "
        "a client on 38031 while 37031 is busy hangs on `eng.reset` until the 120-s client timeout. Check `netstat -an | grep 3703` for ESTABLISHED before launching.\n")
i = s.index('## 8. Measurement traps\n\n') + len('## 8. Measurement traps\n\n'); s = s[:i] + trap + s[i:]
old = s.index('**2026-09-06 07:5x UTC -- S1 DONE'); end = s.index('\n', old)
rest = s[old:end].split('Before that: ', 1)[1]
s = s[:old] + ('**2026-09-06 08:5x UTC -- S1 DONE (6 checkpoints, icebow tile 18.22 +/- 0.11, hogeq 20.99 +/- 0.36 §5cs.64-65); ENGINE BAND CLOSED for icebow (L64g: 3 ckpts 75/71/71 wins of 100 vs ghosts, no-plays 0, random 0-3 §5cs.65-66); '
               'hogeq ghost pool subagent in flight; both engine slots free when it finishes; trainers 0. Before that: ') + rest + s[end:]
open(p, 'w', encoding='utf-8', newline='').write(s)
log = """
## L64g -- 2026-09-06 08:5x UTC -- engine checkpoint band closed; rate-matched random buried
- 3 icebow ckpts x 100 paired entries (a): 75-25 / 71-29 / 71-29, survival +115/+112/+112 s over no-plays (SE ~5.3), crowns against 0.86/0.93/0.86. Val-tile order does not predict engine order; indistinguishable at this n.
- Random p 0.13 (a): 15.2 plays/min, 7.7 accepted/min, 3W-97L, +44 s. Survival per accepted play ~5.7 s random vs ~11.8 s model.
- TRAP (a, subagent): 38031/38032 are the direct doors of the SAME two engines as 37031/37032 -- two slots, not four.
- Next: hogeq on the engine (pool subagent in flight), then S2/S3 per Square One.
"""
open('GAUNTLET_LOG.md', 'a', encoding='utf-8', newline='').write(log)
print('ok')
