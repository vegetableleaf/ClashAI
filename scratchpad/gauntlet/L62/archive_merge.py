"""Restore the pre-existing HANDOFF_ARCHIVE.md (2026-08-29 split, 2,740 lines) that today's split
overwrote, and append today's archived material after it. Lossless: old + new, in order."""
import pathlib

root = pathlib.Path(__file__).resolve().parents[3]
L62 = root / "scratchpad" / "gauntlet" / "L62"
old = (L62 / "_old_archive.md").read_text(encoding="utf-8").rstrip("\n").split("\n")
new = (L62 / "_new_archive_part.md").read_text(encoding="utf-8").rstrip("\n").split("\n")

sep = """

---
---

# SECOND SPLIT -- 2026-09-05 (§5cs.51)

Everything above this line is the FIRST archive split (2026-08-29): resolved `3x`/`4x` sections.
Everything below is the second: the old "what is running RIGHT NOW" block, the session narrative
§5a .. §5cs.42, and 270 lines of superseded HANDOFF header. Same rule as before -- **verbatim, and
nothing is deleted**; `HANDOFF.md` keeps the current state, §6 open work, §7 rules and §8 traps.
"""

merged = old + sep.split("\n") + new
(root / "HANDOFF_ARCHIVE.md").write_text("\n".join(merged) + "\n", encoding="utf-8")
print(f"restored {len(old)} + appended {len(new)} = {len(merged)} lines")
