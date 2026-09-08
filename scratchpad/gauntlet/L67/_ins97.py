import pathlib

s = pathlib.Path("scratchpad/gauntlet/L67/_sec97.md").read_text(encoding="utf-8")
h = pathlib.Path("HANDOFF.md")
t = h.read_text(encoding="utf-8")
i = t.index("### §5cs.96 -- L67c")
t = t[:i] + s.rstrip() + "\n\n" + t[i:]
j = t.index("**2026-09-07 22:3x UTC -- OPTION A RUN, HEADLINE NULL (§5cs.96)")
status = ("**2026-09-08 02:3x UTC -- STUDENT WIRED TO THE LIVE PATH, OFF BY DEFAULT (§5cs.97): clashrl/student_live.py + 41 lines in "
          "play.py behind `play.student_ckpt` (unset = unchanged live behaviour; revert = unset the key or revert 597ddb7). First "
          "measurement off it CONTRADICTS an S4 premise: elixir-matched, the play gate on REAL detector frames tracks the ENGINE "
          "(frac p>0.5 24.8-32.5% over 3 seeds x 3 sessions vs engine 29.4-29.8%) while degrade() inflates it to 44.6-52.4% -- the "
          "modelled shift is not the real one on this axis and the degraded VAL is NOT a live proxy. Latency fine: student 28.7-37.6 ms, "
          "detector 45-80 ms vs act_period 1.5 s. Option B (degrade-augmented, 622,923 rows) training: seeds 0+1 in parallel, seed 2 after; "
          "2-seed read is a SCREEN, 3 seeds is the result.**\n\n")
t = t[:j] + status + t[j:]
h.write_text(t, encoding="utf-8")

log = pathlib.Path("GAUNTLET_LOG.md")
log.write_text(log.read_text(encoding="utf-8").rstrip("\n") + """

## L67d (2026-09-07/08) -- the student is wired to the live path; degrade() measured against REAL detector output
- NEW clashrl/student_live.py + play.py +41 lines behind `play.student_ckpt` (OFF by default -- unset key measured, added block skipped; revert = unset or git revert 597ddb7). LiveReads from play.py's own readers in the CONTRACT tower order, king hp None; from_live -> to_tokens -> S1Model encoded once; deck slot -> tray id on the base key (8 student slots vs 10 live identities); 36x64 lattice cell -> board -> actions.cell_at. Student decides (card, cell) ONLY: deploy_clamp, aim assists and affordability still run; unaffordable/unmappable = WAIT, never a silent fallback to the CNN.
- Dry run (a), student_dryrun.py, real sessions + real detector, no clicks: 5 runs / 3 sessions / 3 seeds, 223-400 frames each. Student 28.7-37.6 ms median (p95 61), detector 45-80 ms vs act_period 1.5 s -> latency is not a constraint. Play rate 12.6-19.5% at tau 0.5; 4-9 distinct cards, 8-19 distinct cells; no_mappable_card 5-9%. Spell tokens DO appear live (29-78/run) and training rows have zero.
- FINDING (a), elixir>=5 matched on both sides, gate_dist.py: frac p_play>0.5 = engine v3 VAL .294-.298, degrade() twin .446-.524, REAL LIVE .248-.325 (3 seeds x 3 sessions). Real live tracks the ENGINE; degrade() over-eggs the gate by 15-23 pp. The first, uncontrolled read (.247/.172/.373) was confounded by elixir mix and is SUPERSEDED.
- Consequence: the degraded VAL is not a proxy for live gating, and a B gain on it is not evidence of a live gain. Placement/card live remain unmeasured (b) -- next: re-point the L63 own-click harness (owner's recorded clicks = live-labelled placements) at the student.
- Own bugs (a): merge_aug indexed an NpzFile inside a loop (74 MB decompressed per row -> MemoryError); 3 parallel train_s1 = 160 MB free RAM (2.3 GB each, TWO fit on this box). Seeds killed at epoch 0, nothing lost.
""", encoding="utf-8")
print("ok")
