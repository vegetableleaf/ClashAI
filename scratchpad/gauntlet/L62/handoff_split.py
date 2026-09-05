"""Split HANDOFF.md into a lean working file + a verbatim archive. LOSSLESS: every original line
lands in exactly one of the two outputs (asserted). Run from the repo root."""
import re, sys, pathlib

root = pathlib.Path(__file__).resolve().parents[3]
src = root / "HANDOFF.md"
arc = root / "HANDOFF_ARCHIVE.md"
lines = src.read_text(encoding="utf-8").split("\n")
N = len(lines)


def find(pat, start=0):
    rx = re.compile(pat)
    for i in range(start, N):
        if rx.match(lines[i]):
            return i
    raise SystemExit(f"not found: {pat}")


i_s3 = find(r"^## 3\. What is running RIGHT NOW")
i_s4 = find(r"^## 4\. The central problem")
i_stream = find(r"^## §5a[ —-]")                      # first narrative section
i_keep = find(r"^### §5cs\.43 ")                      # today's engine-era sections stay
assert i_s3 < i_s4 < i_stream < i_keep, (i_s3, i_s4, i_stream, i_keep)

head = lines[:i_s3]                 # header + §1 + §2
old_s3 = lines[i_s3:i_s4]           # archived: dead run state
mid = lines[i_s4:i_stream]          # §4..§11 -- ledger, open work, rules, traps, inventory
stream = lines[i_stream:i_keep]     # archived: the §5a..§5cs.42 narrative
recent = lines[i_keep:]             # kept: today

# index of everything archived, for grepping the archive
idx = []
for block, tag in ((old_s3, "3"), (stream, "5x")):
    for ln in block:
        if not ln.startswith("## ") or ln.startswith("### "):
            continue                              # top-level sections only -- subsections bloat it
        m = re.match(r"^## *(§?[0-9A-Za-z.]+)[ .—-]+(.*)$", ln)
        if m:
            title = re.sub(r"[*`]", "", m.group(2)).strip()
            idx.append(f"- `{m.group(1)}` {title[:110]}")

new_s3 = """## 3. What is running RIGHT NOW

**2026-09-05 21:5x UTC -- NOTHING IS TRAINING.** The engB engine-PPO pair was killed at m=602/609
(§5cs.51, owner ruling); engA before it (§5cs.46). Box state verified at the kill: python processes
7 -> 3, free RAM 5.0 GB.

* **Alive and NOT to be touched:** the replay crawler (PIDs 29444 + 53824, `crawl_icebow.py expand 150`),
  the owner's Nucleo uvicorn (PID 63608, port 8765). The sandbox VM `qemu-system-x86_64-headless`
  (PID 54304, 413 MB) is UP with both engine slots now FREE (ports 38031/38032, 37031/37032).
* **Checkpoints that matter.** IL init `icebow/data/bc_pro/models/bc_bias_native_s0.pt`
  (sha a1273d5d, 15.44/46.61 v1, 15.00/43.51 v2) -- the best policy we have, and the thing every
  engine-PPO arm failed to beat. Evidence-only: `data/bench/engB_{ctrl,kl}_{m0,m250,m500|m502,latest}.pt`
  and the engA set. `data/bench/` is gitignored.
* **Instruments** (never mix two of them in one comparison): `scratchpad/gauntlet/L61/read_ckpt.py`
  (pro cell agreement, deterministic, CONDITIONAL ON A PLAY -- always quote a play rate beside it);
  `clashrl.cli policy-stats` and `L62/gate_probe.py` (sim, now honouring `sim.ppo_gate_rule`);
  the engine train logs' own GATE readout. Gate health = `p_gate` within ~0.7-1.3x of `gp_target`
  AND p50/p90/max not coincident (§5cs.49).
* **Open lines with the box now free:** bridge v2 dynamic verification (`L62/re_verify_bridge.py
  deploy --bridge v2`, port 37041); the live-socket run of the engine visualiser (`L62/live_view.md` §6);
  the distillation teacher (§6-PRIORITY-B). Full list in §6.
* History of what USED to run here (the cuda run, the gate-prior sweeps, floor7/aggro/gatec2/c2r,
  engA) is in `HANDOFF_ARCHIVE.md`.
"""

new_recent_head = """## 5x. Session narrative -- RECENT ONLY

Everything before §5cs.43 (2026-09-05 17:1x UTC) lives verbatim in **`HANDOFF_ARCHIVE.md`**, with a
section index at the end of this file. Grep the archive by section id (`§5bw`, `§5cj`, ...). The
sections kept below are the engine era: the real-engine environment, the two PPO pairs, the gate
work, the visualiser, and the verdict.
"""

arc_head = f"""# HANDOFF ARCHIVE

Verbatim history split out of `HANDOFF.md` on 2026-09-05 (§5cs.51) so a new session does not spend
its context on dead runs. **Nothing here was edited or summarised** -- it is the original text,
in order: the old "what is running right now" block (every run in it is stopped), then the session
narrative §5a .. §5cs.42.

Current state, standing rules (§7), measurement traps (§8) and open work (§6) stay in `HANDOFF.md`.
Grep here by section id when a number's provenance is needed.

"""

out = head + new_s3.split("\n") + mid + new_recent_head.split("\n") + recent + [
    "", "---", "", "## Archive index (`HANDOFF_ARCHIVE.md`)", ""] + idx + [""]
archive = arc_head.split("\n") + old_s3 + stream

src.write_text("\n".join(out), encoding="utf-8")
arc.write_text("\n".join(archive), encoding="utf-8")

# lossless check: every original line is in exactly one output
kept = len(head) + len(mid) + len(recent)
archived = len(old_s3) + len(stream)
assert kept + archived == N, (kept, archived, N)
print(f"original {N} lines -> HANDOFF.md {len(out)} (kept {kept} + new prose) "
      f"+ HANDOFF_ARCHIVE.md {len(archive)} (archived {archived}); index {len(idx)} entries")
