import pathlib
s = pathlib.Path("scratchpad/gauntlet/L67/_sec96.md").read_text(encoding="utf-8")
h = pathlib.Path("HANDOFF.md"); t = h.read_text(encoding="utf-8")
i = t.index("### §5cs.95 -- L67a+b")
t = t[:i] + s.rstrip() + "\n\n" + t[i:]
j = t.index("**2026-09-07 18:xx UTC -- S4 OPENED (§5cs.95)")
status = ("**2026-09-07 22:3x UTC -- OPTION A RUN, HEADLINE NULL (§5cs.96): 603 HF-mined replays (corpus v6 = 2,241, +0.45 doublings) moved "
          "exact cell 20.93 -> 21.04 (+0.11 pp vs a pre-registered +0.7) -- the S2 slope does NOT transfer to a foreign corpus. Card top-1 DID "
          "move 63.04 +- 0.28 -> 64.99 +- 0.57 (+1.96 pp, ~4 sd), NLL 3.224 -> 3.167, dist 3.571 -> 3.478: more data buys WHICH card, not WHERE. "
          "Degraded VAL unchanged (16.35 vs 16.76), so the -4.2 pp live shift survives the doubling. Dataset size retracted twice: ~2,070 -> ~625 "
          "-> 766 measured. DECISION (owner delegated): DO B -- degrade() as training augmentation on v6, 3 seeds, graded clean AND degraded.**\n\n")
t = t[:j] + status + t[j:]
h.write_text(t, encoding="utf-8")
log = pathlib.Path("GAUNTLET_LOG.md")
log.write_text(log.read_text(encoding="utf-8").rstrip("\n") + """

## L67c (2026-09-07) -- option A run: corpus v6 from FirstLight's HF dataset; headline NULL, card head +1.96 pp; B ruled ON
- RETRACTED twice: exact-icebow replays in VanguardX101/IL_Replay are 766 of 252,238 (0.30%), not the ~2,070 of §5cs.95 (one outlier shard) nor the ~625 of the 28-shard estimate. Also retracted: "new crowns mismatch 0" from the assembly script (bad key; real 473/603 = 78.4%).
- Pipeline (a): 52 parts downloaded (sha256 52/52), hf_to_crawl.py -> crawl2, 766 kept / 0 unpositioned / 0 duplicates of our 1,890-battle crawl; driven on both engine slots -> 603 usable, 163 failures ALL the known evo gap (card 26000043); accept 98.8-99.1%, 24.9 s/match, 2.05 h. corpus_v6 = 1,638 + 603 = 2,241; dataset 339,192 rows.
- Measured on the unchanged v3 VAL (3,796 plays, 3 seeds): exact cell 20.93 +- 0.49 -> 21.04 +- 0.22 (+0.11 pp vs pre-registered +0.7 = NULL); card 63.04 +- 0.28 -> 64.99 +- 0.57 (+1.96 pp, ~4 sd); NLL 3.224 -> 3.167; mean dist 3.571 -> 3.478 tiles. The S2 scaling line does not extend to this corpus; the split (card yes, cell no) is the finding.
- Degraded twin: 16.35 +- 0.56 vs v5's 16.76 +- 0.24 = no change. A clean-corpus doubling does nothing for the live shift.
- Untested (b) for the head split: tier (Ranked max-level vs our pro crawl), representation ceiling on placement, or drive label noise (78.4% crowns match). Cheapest discriminator named in §5cs.96 D: score val rows split by source.
- DECISION (owner delegated the B call): B ON -- obs_contract.degrade as training augmentation, base held at v6, 3 seeds, graded clean AND degraded, both reported whichever way they go.
""", encoding="utf-8")
print("ok")
