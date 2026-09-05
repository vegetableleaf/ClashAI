"""Replace the accreted 'Last updated' + ~20 stale 'Previous header' blocks with one compact
current-state header. The old stack is appended verbatim to HANDOFF_ARCHIVE.md. Lossless."""
import re, pathlib

root = pathlib.Path(__file__).resolve().parents[3]
src, arc = root / "HANDOFF.md", root / "HANDOFF_ARCHIVE.md"
lines = src.read_text(encoding="utf-8").split("\n")

i0 = next(i for i, l in enumerate(lines) if l.startswith("Last updated:"))
i1 = next(i for i, l in enumerate(lines) if l.strip() == "---" and i > i0)
old = lines[i0:i1]
assert len(old) > 100, len(old)

new = """Last updated: **2026-09-05 21:5x UTC**, branch `main`.

### Where the project stands (read this, then §6 / §7 / §8)

**The best policy we have is the imitation model**, `icebow/data/bc_pro/models/bc_bias_native_s0.pt`
(behaviour cloning on pro placements; **15.44 / 46.61** top-1/top-5 pro-cell agreement on v1 boards,
15.00 / 43.51 on v2). Nothing since has beaten it.

**Reinforcement learning on top of it has now failed twice on the real engine** (§5cs.44-51). Four
arms, ~1,500 engine matches: with a KL leash to the init the policy stays exactly where it started
(15.44 -> 16.33 -> 15.64 over 500 matches); without one it degenerates (-> 6.87, with 26% of its
placement logits railed). The unshaped engine reward has produced **no measured gain in pro
agreement, ever**. That is the central open problem, and it is a REWARD/DATA problem, not an
algorithm one -- see §5cs.51 D for what is closed and what is not.

**What was fixed today and matters going forward:**
* The **deploy rule** is now `sim.ppo_gate_rule: sample` (owner ruling) via one shared
  `clashrl/gate_rule.py` -- viewers and graders sample the gate instead of thresholding it at 0.25.
  A pro-calibrated gate (pro mean P(play) 0.111) essentially never crosses 0.25, so the old rule
  rendered every calibrated checkpoint catatonic (0.1-1.5 plays/match; 17.2-24.5 under sampling).
  `play.py` (live) and the sim trainer's greedy bench deliberately still use the threshold.
* The **gate prior** (Bernoulli CE toward the pro play-rate table, coef 2.0) prevents the gate
  collapse that killed the engA pair. Keep it in any future run.
* **Engine visualiser** published (`scratchpad/gauntlet/L62/live_view.py`, artifact
  https://claude.ai/code/artifact/3aca72fa-8f09-40e9-9d59-65c0dc2e03d2): the sim debugger's whole
  feature set -- radii, P1 band, term readout, gate probability -- on real engine frames.
* **Grid 432 is correct**; the owner's 576 proposal was measured and contradicted (§5cs.48).

**Never quote a pro-agreement number without a play rate beside it** (§5cs.46 retraction) and never
compare two instruments (§8). Older headers and the full narrative are in `HANDOFF_ARCHIVE.md`.
"""

lines[i0:i1] = new.split("\n")
src.write_text("\n".join(lines), encoding="utf-8")
with arc.open("a", encoding="utf-8") as f:
    f.write("\n\n## Archived: the stale HANDOFF header stack (superseded 'Previous header' blocks)\n\n")
    f.write("\n".join(old) + "\n")
print(f"header stack archived: {len(old)} lines -> {len(new.splitlines())}; "
      f"HANDOFF.md now {len(lines)} lines")
