p = 'HANDOFF.md'; s = open(p, encoding='utf-8').read()
sec = open('scratchpad/gauntlet/L64/_handoff_5cs68.md', encoding='utf-8').read()
i = s.index('### §5cs.67 -- L64h'); s = s[:i] + sec + '\n' + s[i:]
trap = ("* **hogeq's gate tail is thin: p_gate p90 sits at 0.48-0.49 for all three S1 seeds, under tau 0.5 (§5cs.68).** A few hundredths of calibration moves the play rate by a third and the "
        "engine result by 25-35 wins/100; every hogeq engine number must be quoted with its accepted plays per match, and `threshold` reads on hogeq are seed-fragile.\n")
i = s.index('## 8. Measurement traps\n\n') + len('## 8. Measurement traps\n\n'); s = s[:i] + trap + s[i:]
old = s.index('**2026-09-06 08:3x UTC -- S2 UNBLOCKED'); end = s.index('\n', old)
rest = s[old:end].split('Before that: ', 1)[1]
s = s[:old] + ('**2026-09-06 09:4x UTC -- hogeq engine band 53/19/44 (threshold tau 0.5; random 18, no-plays 0; the outlier plays 17 cards/match vs 25-27 with the same p_gate median -- tau decides again §5cs.68); `smp_ck1` (s1 under --gate sample) RUNNING on 37031; '
               'hogeq re-fetch 260/299 (i=1 half rotated by (18-x, 32-y): winner agreement 64.1% vs v3 67.2%, tesla handedness confirms rotation not mirror); icebow re-fetch to RELAUNCH after hogeq; S2 UNBLOCKED (§5cs.67). Before that: ') + rest + s[end:]
open(p, 'w', encoding='utf-8', newline='').write(s)
log = """
## L64i -- 2026-09-06 09:4x UTC -- hogeq engine band 53/19/44; tau decides the outlier; rotated i=1 half passes first fidelity test
- (a) hogeq, 100 paired ghost entries seed 0, threshold tau 0.5: s0 53-47 / s1 19-1-80 / s2 44-56; random p0.13 18-82; no-plays 0-100. Survived longer 92/94/93; crowns against 1.40/2.06/1.46 (no-plays 2.87).
- (a) outlier s1: 17.4 accepted plays/match vs 26.8/24.9, p_gate median 0.361 vs 0.352/0.356, p90 0.484/0.493/0.491, frac>tau 0.059 vs 0.083/0.077; hog 174 vs 293/253, earthquake 52 vs 179/120, elixir at decision 8.73 vs 8.0/8.2. (b) tau decides -> smp_ck1 (same ckpt, --gate sample) running on 37031.
- (a) rotation of the re-fetched i=1 half (18000-x, 32000-y units), first 80 hogeq tags driven: 64 ok, winner agreement 41/64 = 64.1% (v3 67.2%), accept 97.6% (98.7%), exact crowns 43.8% vs 56.4% (b, n=64), terminal_vs_last_play median -101 vs +120 (b). Handedness: blue tesla left-fraction 0.224 vs 0.279 (mirror would give 0.776) -> rotation confirmed.
- Re-fetch hogeq 260/299; icebow attempt died on the Cloudflare check, connect() hardened, relaunch after hogeq. replay_drive.py: PLAYS_FILE/set_plays_file + rotation on load; replay_batch.py --plays-file.
"""
open('GAUNTLET_LOG.md', 'a', encoding='utf-8', newline='').write(log)
print('ok')
