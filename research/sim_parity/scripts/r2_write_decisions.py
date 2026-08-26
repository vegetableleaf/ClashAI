# -*- coding: utf-8 -*-
"""Render ledger/r2_buckets.json into ONE owner-facing decision document.
One DECISION per cause; the affected rows sit under it as evidence, not as separate choices."""
import json, io, collections

B = json.load(io.open("ledger/r2_buckets.json", encoding="utf-8"))

META = {
 "KBGAP": ("Fields the wiki publishes that the sim leaves EMPTY",
   "Apply all as additions.",
   "These are gaps, not conflicts: the sim has no value at all, so nothing owner-verified is being "
   "overwritten. Filling them can only move the sim toward the real game. A few are big "
   "(three_musketeers has no damage; inferno_tower has no `attacks`)."),
 "LAG": ("The wiki's stat block LAGS the wiki's own balance history",
   "Apply all; they are what the third extraction path exists to catch.",
   "The card's #vardefine still holds a pre-balance number while the page's own dated History says "
   "it changed. This is the known failure mode that made a naive re-import dangerous. Each row "
   "carries the dated entry that supersedes it. Bulk of these are the 4/8/2026 update."),
 "SPLIT": ("Sources genuinely disagree and no 2-of-3 majority formed",
   "Review individually — these are the only ones that truly need your judgement.",
   "No automated rule can settle these. Each row shows all three readings."),
 "UNPUB": ("No source publishes the value ANYWHERE",
   "Keep the sim's current value, mark it `unsourced: true`, and measure in-game when convenient.",
   "The sweep looked on all three paths and found nothing. Mighty Miner's bomb radius (2.5) is the "
   "flagship case. Leaving them flagged is honest; silently keeping them is what produced the "
   "'not published in the KB' comments that turned out to be false."),
 "VERIFIED": ("Rows YOU marked verified:true that the sources contradict",
   "Read each one — your ruling outranks the wiki, but these look like real errors.",
   "Per your standing rule these are never auto-overwritten. Several are severe (zap_evo's removed "
   "3rd pulse, dark_prince's doubled splash)."),
 "CROWN": ("Crown-tower damage still stale after the 1/6/2026 sweep",
   "Apply all, AND fix the audit tool's regex.",
   "The sweep looked complete because `crown_damage_audit.py` FALSE-PASSES: its regex demands "
   "'of the full damage' while the 2026 line reads 'of ITS full damage'. It matched a 2020 line "
   "and printed ok. Every pin also landed on a parent card and missed its evolution."),
 "DUP": ("Two sweep agents claimed the same field and disagreed",
   "Apply the merge's pick (more sources wins); listed here for transparency.",
   "Not a data problem — a process one. Shown so a disagreement can't hide."),
 "ROUNDING": ("floor() vs round() convention on derived DPS",
   "One ruling covers all of them: adopt the wiki's floor().",
   "e.g. goblins 125/1.1 -> floor 113 (what the wiki renders) vs the sim's 114. Each is off by one "
   "and harmless alone, but the convention should match the game's."),
 "PARENT": ("The sim holds the PARENT's or SPAWNED unit's stat instead of the card's own",
   "Apply all — these are unambiguous mix-ups.",
   "The exact failure class that once gave 4 buildings their spawned unit's stats. Tell-tale: the "
   "stored number is EXACTLY another vardefine on the same page."),
 "ENGINE": ("The data is agreed; the decision is a SCHEMA or ENGINE change",
   "Defer to Phase I implementation — no data decision needed now.",
   "The sim's schema cannot hold the real shape (e.g. three_musketeers' second melee attack mode; "
   "electro_dragon_evo's 'full damage for 3, reduced for the rest')."),
 "PAGECONF": ("The wiki page contradicts ITSELF",
   "Review — or settle by checking in-game.",
   "Prose, table and history give different answers on one page. Fisherman's slow is the worst: "
   "prose says 35%, one history entry says -30%, another removes it entirely."),
 "GLOBAL": ("One shared constant, not a per-card field",
   "One ruling sets it for every chain card.",
   "The sim hardcodes _CHAIN_TILES = 3.0; THREE independent pages publish 4 tiles; cards.yaml's "
   "own comment says 3.5. All three disagree. This is the Electro Dragon chain issue you raised."),
 "NAMING": ("Field-name collisions / snapshot hygiene",
   "Cosmetic; apply with the rest.", "No gameplay effect."),
 "OTHER": ("Uncategorised leftovers",
   "Review individually.", "Only the rows no rule matched."),
}
ORDER = ["KBGAP","LAG","CROWN","PARENT","VERIFIED","GLOBAL","ROUNDING","ENGINE","PAGECONF","SPLIT","UNPUB","DUP","NAMING","OTHER"]

out = []
w = out.append
tot = sum(len(B.get(k, [])) for k in B)
w("# R2 — Owner Decision Sheet")
w("")
w("**%d escalations from the sim-parity stat sweep, grouped into %d decisions.**" % (tot, len([k for k in ORDER if B.get(k)])))
w("Generated 2026-08-26 from `ledger/stat_diffs.jsonl` (179 keys, 3,321 fields checked, 2,838 matched).")
w("")
w("Nothing has been changed in the sim. Tick a decision and I apply that whole group in Phase I.")
w("")
w("---")
w("")
w("## Decision summary")
w("")
w("| # | Decision | Rows | My recommendation |")
w("|---|---|---|---|")
for i, k in enumerate([k for k in ORDER if B.get(k)], 1):
    t, rec, _ = META[k]
    w("| %d | %s | %d | %s |" % (i, t, len(B[k]), rec))
w("")
w("Decisions 1-4, 7, 8 and 13 are bulk 'yes/no'. Decisions 5, 10, 11 and 14 need row-by-row reading;")
w("that is **%d rows total**, not 316." % sum(len(B.get(k, [])) for k in ("VERIFIED","SPLIT","PAGECONF","OTHER")))
w("")
w("---")
w("")
for i, k in enumerate([k for k in ORDER if B.get(k)], 1):
    t, rec, why = META[k]
    rows = B[k]
    w("## %d. %s" % (i, t))
    w("")
    w("**Rows:** %d  |  **Recommendation:** %s" % (len(rows), rec))
    w("")
    w("%s" % why)
    w("")
    w("- [ ] Accept recommendation for all %d" % len(rows))
    w("- [ ] I want to go row by row")
    w("")
    fams = collections.Counter(r.get("family") for r in rows)
    w("<sub>families: %s</sub>" % ", ".join("%s %d" % (a, b) for a, b in fams.most_common()))
    w("")
    w("| card | field | sim has | wiki says | why |")
    w("|---|---|---|---|---|")
    for r in sorted(rows, key=lambda x: (x.get("family") or "", x.get("key") or "")):
        prop = next((v for v in (r.get("p3"), r.get("p1"), r.get("p2")) if v not in (None, "", [])), "-")
        n = (r.get("notes") or "").replace("|", "/").replace("\n", " ")
        n = (n[:150] + "...") if len(n) > 150 else n
        w("| `%s` | %s | %s | %s | %s |" % (r.get("key"), r.get("field"), r.get("current"), prop, n))
    w("")
    w("---")
    w("")
io.open("R2_DECISIONS.md", "w", encoding="utf-8").write("\n".join(out))
print("wrote R2_DECISIONS.md  (%d decisions, %d rows)" % (len([k for k in ORDER if B.get(k)]), tot))
