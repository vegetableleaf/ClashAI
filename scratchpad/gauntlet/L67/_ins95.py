import pathlib
s = pathlib.Path("scratchpad/gauntlet/L67/_sec95.md").read_text(encoding="utf-8")
h = pathlib.Path("HANDOFF.md"); t = h.read_text(encoding="utf-8")
i = t.index("### §5cs.94 -- L66n"); t = t[:i] + s.rstrip() + "\n\n" + t[i:]
j = t.index("**2026-09-07 15:5x UTC -- THE ENGINE SEARCH TEACHER IS CLOSED (§5cs.94)")
status = ("**2026-09-07 18:xx UTC -- S4 OPENED (§5cs.95): live-shift cost measured on a degraded v3 VAL twin: v5lat 20.9 -> 16.8 exact cell "
          "(-4.2 pp), card 63.0 -> 50.6, +1.0 tile. Live-path guardrail REMOVED by owner ruling (gauntlet.md §6). Owner's FirstLight_CR "
          "pointer reviewed (scratchpad/gauntlet/L67/firstlight_review.md): offline-only, no learning curve, 'not plateaued' unsupported; "
          "its public 252k-replay HF dataset holds ~2,000 exact-icebow sides (est. from one shard) = one more corpus doubling. "
          "Gauntlet STOPPED for the owner's choice: (A) HF corpus doubling v6 vs (B) degradation-augmented v5 retrain. Box idle, VM off.**\n\n")
t = t[:j] + status + t[j:]
h.write_text(t, encoding="utf-8")
log = pathlib.Path("GAUNTLET_LOG.md")
log.write_text(log.read_text(encoding="utf-8").rstrip("\n") + """

## L67a+b (2026-09-07) -- S4 opened: live-shift cost measured; FirstLight_CR reviewed; stopped for owner ruling
- Live-path guardrail removed by owner ruling (gauntlet.md §6, quoted inline). Survey: play.py on old CNN/18x24/hardcoded tau 0.25; from_live has zero callers; all live inputs exist in scope.
- Measured (a): degraded twin of v3 VAL (obs_contract.degrade on every BoardState, same rows/targets). v5lat s0/s1/s2 exact cell 21.4/21.0/20.5 -> 16.7/16.6/17.1; card 63.2/63.2/62.7 -> 52.4/48.3/51.1; mean dist 3.54-3.61 -> 4.53-4.64 tiles; gate acc .82 -> .74-.76. The live shift costs more than a corpus doubling buys (+1.5 pp). §5cs.95 A.
- FirstLight_CR (owner pointer) read in full: offline-only (no capture/ADB), 252,238 RoyaleAPI replays public on HF, 12.7 M-param universal-card LSTM model, PPO at 1,528 concurrent matches / 8 GPUs. NO learning curve in the repo; results are argmax win rates vs frozen opponents; they hit our L62 passive-opponent trap (296/306 wins vs an IL that played <= 3 cards). "Not plateaued" = (b) unsupported. §5cs.95 B.
- Transferable + cheap: HF shard 0 has 41 exact-icebow sides / 10,000 -> ~2,070 over the dataset (est.) = one more corpus doubling (v6), S2 slope predicts +1.5 pp; skill tier unknown, must be A/B'd on the unchanged v3 VAL. §5cs.95 C.
- Stopped with --questions: next action (A) v6 corpus doubling from HF vs (B) degradation-augmented v5 retrain. Box idle, VM off.
""", encoding="utf-8")
print("ok")
