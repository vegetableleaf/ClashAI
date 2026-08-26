# -*- coding: utf-8 -*-
"""Render the R2 owner batch review table from the canonical stat_diffs.jsonl."""
import json, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
LED = os.path.abspath(os.path.join(HERE, "..", "ledger"))

FAM_LABEL = collections.OrderedDict([
    ("troops_a", "Troops A"), ("troops_b", "Troops B"), ("troops_c", "Troops C"),
    ("buildings", "Buildings"), ("spells", "Spells"),
    ("evos_a", "Evolutions A"), ("evos_b", "Evolutions B"), ("champions", "Champions"),
    ("xc_crown", "Cross-check: crown-tower damage"),
    ("xc_spawn_anchor", "Cross-check: spawner / anchor sweep"),
    ("xc_ladder", "Cross-check: level ladder"),
])

# as reported by each sweep agent (their line-count fields reproduce exactly against the files)
AGENT = collections.OrderedDict([
    ("troops_a",        dict(keys=32, fields=426, matches=375, updates=23, pins=0,  esc=40)),
    ("troops_b",        dict(keys=32, fields=368, matches=323, updates=4,  pins=1,  esc=40)),
    ("troops_c",        dict(keys=31, fields=417, matches=385, updates=3,  pins=3,  esc=26)),
    ("buildings",       dict(keys=12, fields=202, matches=167, updates=9,  pins=2,  esc=24)),
    ("spells",          dict(keys=22, fields=230, matches=180, updates=15, pins=5,  esc=30)),
    ("evos_a",          dict(keys=21, fields=364, matches=301, updates=2,  pins=1,  esc=60)),
    ("evos_b",          dict(keys=21, fields=419, matches=352, updates=11, pins=3,  esc=53)),
    ("champions",       dict(keys=8,  fields=219, matches=139, updates=40, pins=7,  esc=33)),
    ("xc_crown",        dict(keys=24, fields=38,  matches=13,  updates=0,  pins=7,  esc=18)),
    ("xc_spawn_anchor", dict(keys=26, fields=585, matches=19,  updates=6,  pins=5,  esc=10)),
    ("xc_ladder",       dict(keys=20, fields=53,  matches=12,  updates=0,  pins=41, esc=0)),
])

from r2_overrides import PROP_OVERRIDE

EMDASH = "—"
ARROW = "→"
ELL = "…"


def cell(v, limit=150):
    if v is None:
        return "_null_"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (list, dict)):
        v = json.dumps(v, separators=(",", ":"), ensure_ascii=False)
    s = " ".join(str(v).split())
    if len(s) > limit:
        s = s[:limit - 1].rstrip() + ELL
    return s.replace("|", "\\|").replace("<", "&lt;")


def gist(notes, limit=230, row=None):
    if not notes:
        if row is not None:
            for src in (row.get("sources") or []):
                if src.get("raw"):
                    return "(no note recorded) source: " + cell(src["raw"], limit)
        return "_(no note recorded)_"
    s = " ".join(str(notes).split())
    parts = re.split(r'(?<=[.;])\s+', s)
    out, i = parts[0], 1
    while len(out) < 120 and i < len(parts):
        out += " " + parts[i]
        i += 1
    if len(out) > limit:
        out = out[:limit - 1].rstrip() + ELL
    return out.replace("|", "\\|").replace("<", "&lt;")


rows = [json.loads(l) for l in open(os.path.join(LED, "stat_diffs.jsonl"), encoding="utf-8")]


def prop(r):
    o = PROP_OVERRIDE.get((r["key"], r["field"]))
    return o if o is not None else r.get("proposed")


def curated(r):
    n = r.get("notes") or ""
    return bool(re.search(r'verified\s*[:=]\s*true', n, re.I)) or bool(re.search(r'\bcurat', n, re.I))


updates = [r for r in rows if r["verdict"] == "update"]
esc = [r for r in rows if r["verdict"] == "escalate"]
pins = [r for r in rows if r["verdict"] == "pin"]
matches = [r for r in rows if r["verdict"] == "match"]

b_dup, b_ver, b_split, b_other = [], [], [], []
for r in esc:
    if r.get("dup_disagreement"):
        b_dup.append(r)
    elif curated(r):
        b_ver.append(r)
    elif r.get("vote") == "split":
        b_split.append(r)
    else:
        b_other.append(r)

L = []
w = L.append

w("# R2 Owner Batch Review " + EMDASH + " sim-parity sweep, 2026-08-26")
w("")
w("One merged view of eleven independent R2 claim files (8 family sweeps + 3 cross-checks), "
  "deduped by `(key, field)`. Canonical ledger: `research/sim_parity/ledger/stat_diffs.jsonl` "
  "(**%d** rows). Nothing in `icebow/config/cards.yaml` or `cards_stats.json` was modified " % len(rows)
  + EMDASH + " this is a proposal sheet.")
w("")
w("**Dedupe rule applied.** Where two sweeps claimed the same `(key, field)`, the claim with more "
  "sources was kept and the loser is preserved verbatim under `dup_verdicts` in the canonical row. "
  "Where duplicates disagreed " + EMDASH + " different verdict, different proposed value, or a "
  "different reading of `current_db` " + EMDASH + " the merged verdict was forced to `escalate` "
  "(section 2a). **39** pairs were duplicated: **26** agreed, **13** did not.")
w("")
w("**How to read a verdict.** `update` = two or more paths agree the KB is wrong and no curated "
  "`verified: true` value is being overturned. `escalate` = a human must decide. `pin` = the KB is "
  "right and the wiki is wrong, recorded so a later scrape does not \"fix\" it. `match` = recorded "
  "agreement, kept because it corrects an earlier claim.")
w("")
w("| Section | Contents | Rows |")
w("| --- | --- | ---: |")
w("| 1. Updates | agreed corrections, grouped by family | %d |" % len(updates))
w("| 2. Escalations | owner decisions, with all raw values | %d |" % len(esc))
w("| 3. Pins | KB confirmed right against the wiki | %d |" % len(pins))
w("| 4. Statistics | coverage and match rate | " + EMDASH + " |")
w("")
w("---")
w("")

# ---------------- 1. UPDATES ----------------
w("## 1. UPDATES " + EMDASH + " agreed corrections")
w("")
w("%d fields where the sources agree the KB is wrong and no curated `verified: true` value is at "
  "stake. `Vote` is the agreement level across the three paths (P1 `#vardefine` / P2 attributes "
  "table / P3 dated History): `3of3` and `2of3` are the ordinary case; `2of2`, `1of1` and "
  "`offline` mean fewer paths publish the field at all." % len(updates))
w("")
by_fam = collections.OrderedDict((f, []) for f in FAM_LABEL)
for r in updates:
    by_fam[r["family"]].append(r)
n = 0
for fam, grp in by_fam.items():
    if not grp:
        continue
    n += 1
    w("### 1.%d %s " % (n, FAM_LABEL[fam]) + EMDASH + " %d" % len(grp))
    w("")
    w("| Key | Field | Current " + ARROW + " Proposed | Vote | Evidence |")
    w("| --- | --- | --- | --- | --- |")
    for r in sorted(grp, key=lambda x: (x["key"], x["field"])):
        w("| `%s` | `%s` | %s %s **%s** | %s | %s |" % (
            r["key"], cell(r["field"], 60), cell(r["current_db"], 60), ARROW, cell(prop(r), 70),
            r.get("vote") or EMDASH, gist(r["notes"], row=r)))
    w("")

w("---")
w("")

# ---------------- 2. ESCALATIONS ----------------
w("## 2. ESCALATIONS " + EMDASH + " needs a human")
w("")
w("%d rows. Raw values are given on all three paths so no decision requires reopening the source. "
  "P1 = `#vardefine` on the card page, P2 = rendered attributes table, P3 = dated History entry. "
  "Untruncated text for every row is in `stat_diffs.jsonl`." % len(esc))
w("")
w("| Bucket | Why it is here | Rows |")
w("| --- | --- | ---: |")
w("| 2a | two sweeps claimed the same field and disagreed | %d |" % len(b_dup))
w("| 2b | a curated `verified: true` value is contradicted by the sources | %d |" % len(b_ver))
w("| 2c | split vote " + EMDASH + " no two paths agree | %d |" % len(b_split))
w("| 2d | sources agree; the fix is a schema or engine decision, not a field write | %d |" % len(b_other))
w("| 2e | edit-war quarantine | 0 |")
w("")


def esc_table(grp, show_dup=False):
    out = ["| Key | Field | current_db | P1 vardefine | P2 table | P3 history | Vote | Why it needs a human |",
           "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in sorted(grp, key=lambda x: (x["family"], x["key"], x["field"])):
        why = gist(r["notes"], 260, row=r)
        if show_dup:
            parts = []
            for d in r.get("dup_verdicts", []):
                pv = d.get("proposed")
                extra = ""
                if isinstance(pv, (int, float)) or (isinstance(pv, str) and len(pv) <= 30):
                    extra = " (proposed %s)" % cell(pv, 30)
                parts.append("%s claimed `%s`%s" % (d["from_family"], d["verdict"], extra))
            nsrc = r["provenance"]["sources_count"]
            why = "**Kept `%s` from %s (%d source%s); %s.** %s" % (
                r.get("verdict_original", r["verdict"]), r["family"],
                nsrc, "" if nsrc == 1 else "s", "; ".join(parts), why)
        out.append("| `%s` | `%s` | %s | %s | %s | %s | %s | %s |" % (
            r["key"], cell(r["field"], 60), cell(r["current_db"], 70),
            cell(r.get("p1_vardefine"), 110), cell(r.get("p2_table"), 130),
            cell(r.get("p3_history"), 150), r.get("vote") or EMDASH, why))
    return out


w("### 2a. Duplicate-claim disagreements " + EMDASH + " %d" % len(b_dup))
w("")
w("Two independent sweeps landed on the same `(key, field)` and did not agree. The kept claim is "
  "the one with more sources; the losing claim is quoted in the last column and preserved in full "
  "under `dup_verdicts`. Three were forced from `update`/`pin` to `escalate` purely by the merge: "
  "`elixir_collector.lifetime`, `tombstone.spawns.interval`, `goblin_curse.damage`.")
w("")
L.extend(esc_table(b_dup, show_dup=True))
w("")

w("### 2b. Curated verified:true contradicted " + EMDASH + " %d" % len(b_ver))
w("")
w("Owner-overturn requests: a value someone curated deliberately and marked trusted, which the "
  "current sources contradict. None was auto-written.")
w("")
L.extend(esc_table(b_ver))
w("")

w("### 2c. Split votes " + EMDASH + " %d" % len(b_split))
w("")
w("No two independent paths agree, so there is no majority to act on. Several are wiki "
  "self-contradictions (a page disagreeing with its own History, or with its own second table); "
  "the rest are fields only one path publishes at all.")
w("")
L.extend(esc_table(b_split))
w("")

w("### 2d. Data agreed, decision is schema or engine " + EMDASH + " %d" % len(b_other))
w("")
w("The sources are not in dispute here. These escalate because acting on them means adding a "
  "field, changing a shared constant, or reconciling two code paths " + EMDASH + " not editing one "
  "number.")
w("")
L.extend(esc_table(b_other))
w("")

w("### 2e. Edit-war quarantines " + EMDASH + " 0")
w("")
w("**None.** All 595 incoming claims carry `cross_checks.edit_war = \"pass\"`. Every sweep "
  "re-fetched its pages live on 2026-08-26 and compared revids " + EMDASH + " in most groups the "
  "full body, byte for byte " + EMDASH + " against its own archived copy. No page changed under a "
  "sweep while it ran, so no row is quarantined. Two sweeps raised false CHANGED flags and cleared "
  "them: the ladder sweep traced Archers / Bomber / Baby Dragon to a `<!-- revid:... -->` "
  "provenance line an earlier fetch script had prepended to the archive (every stat line identical "
  "at a one-line offset), and the evolutions-A sweep confirmed its 25 parent pages differed from "
  "the archived timepoint only by that same stamp.")
w("")
w("---")
w("")

# ---------------- 3. PINS ----------------
w("## 3. PINS CONFIRMED")
w("")
w("%d fields where the KB is right and the published wiki value is wrong or stale. They are "
  "recorded so a future scrape does not \"correct\" a correct value back to the artifact." % len(pins))
w("")
lad = [r for r in pins if r["family"] == "xc_ladder"]
oth = [r for r in pins if r["family"] != "xc_ladder"]
w("### 3.1 Card-level pins " + EMDASH + " %d" % len(oth))
w("")
w("| Key | Field | Pinned value | Sweep | Why the KB wins |")
w("| --- | --- | --- | --- | --- |")
for r in sorted(oth, key=lambda x: (x["family"], x["key"], x["field"])):
    w("| `%s` | `%s` | %s | %s | %s |" % (r["key"], cell(r["field"], 60), cell(r["current_db"], 70),
                                          FAM_LABEL[r["family"]], gist(r["notes"], 260, row=r)))
w("")
w("### 3.2 Level-ladder pins " + EMDASH + " %d" % len(lad))
w("")
w("One finding, %d fields. The wiki's per-level table is not transcribed game data: each card page "
  "carries only the level-11 `#vardefine` and MediaWiki renders every other row as "
  "`round(v11 * 1.1^(L-11))`. That formula reproduced the rendered table exactly on 53/53 fields, "
  "so the wiki cannot adjudicate a scaling model " % len(lad) + EMDASH + " it *is* a model, and the "
  "wrong one. `levels.py` is correct for the current game: the 31/3/2025 patch note (\"All troop "
  "stats have now been defined with Common Rarity as the base\") is exactly the absolute-level rule "
  "it implements, and all 45 non-Common level-11 values in use today are reachable under it "
  "(probability by chance 4.3e-19). Worst per-card deviation from the wiki artifact is 66 points "
  "(Golem hitpoints at L16, -0.80%).")
w("")
w("| Card | Field | Rarity | Worst deviation vs wiki | Verdict |")
w("| --- | --- | --- | --- | --- |")
for r in sorted(lad, key=lambda x: (x.get("rarity") or "", x["key"], x["field"])):
    dev = ""
    lp = r.get("levels_py_as_implemented") or {}
    d = lp.get("dev_vs_wiki_by_level") or {}
    if isinstance(d, dict) and d:
        try:
            worst = max(d.items(), key=lambda kv: abs(float(kv[1])))
            dev = "%s pts @ L%s" % (cell(worst[1], 20), worst[0])
        except Exception:
            dev = ""
    w("| %s | `%s` | %s | %s | pin |" % (r.get("card") or r["key"], cell(r["field"], 40),
                                         r.get("rarity") or EMDASH, dev or EMDASH))
w("")
w("---")
w("")

# ---------------- 4. STATISTICS ----------------
flagged = len(updates) + len(pins) + len(esc)
tot_fields = sum(a["fields"] for a in AGENT.values())
tot_match = sum(a["matches"] for a in AGENT.values())
tot_keys = sum(a["keys"] for a in AGENT.values())
raw_lines = sum(a["updates"] + a["pins"] + a["esc"] for a in AGENT.values())
groups = json.load(open(os.path.join(LED, "r2_groups.json"), encoding="utf-8"))
distinct_keys = set()
for v in groups.values():
    distinct_keys |= set(v)
line_keys = set(r["key"] for r in rows) - {"<anchor sweep>", "<levels.py>", "party_hut"}
clean_keys = len(distinct_keys - line_keys)

w("## 4. STATISTICS")
w("")
w("### 4.1 Coverage")
w("")
w("| Measure | Value |")
w("| --- | ---: |")
w("| Claim files merged | 11 (8 family sweeps + 3 cross-checks) |")
w("| Distinct card keys swept | **%d** |" % len(distinct_keys))
w("| Key-visits re-covered by a cross-check | 70 (crown 24, spawner/anchor 26, ladder 20) |")
w("| Keys that came back fully clean (no line at all) | %d |" % clean_keys)
w("| Fields checked | **%d** |" % tot_fields)
w("| Claim lines in | 595 |")
w("| Canonical rows out | **%d** |" % len(rows))
w("| Duplicate `(key, field)` pairs collapsed | 39 (26 agreed, 13 disagreed) |")
w("| Edit-war quarantines | 0 |")
w("")
w("### 4.2 Match rate")
w("")
w("| Measure | Count | Rate |")
w("| --- | ---: | ---: |")
w("| Field-checks performed (a field re-checked by a cross-check counts again) | %d | 100%% |" % tot_fields)
w("| Field-checks that produced **no** claim line | %d | **%.1f%%** |"
  % (tot_fields - raw_lines, 100.0 * (tot_fields - raw_lines) / tot_fields))
w("| Field-checks that produced a claim line | %d | %.1f%% |"
  % (raw_lines, 100.0 * raw_lines / tot_fields))
w("")
w("After dedupe those claim lines collapse to **%d** distinct `(key, field)` pairs: %d flagged "
  "(`update` + `pin` + `escalate`) and %d recorded as `match`."
  % (len(rows), flagged, len(matches)))
w("")
w("Two numbers are in play and they are not the same measure. **%d** (%.1f%%) is the sum of the "
  "`matches` each sweep reported " % (tot_match, 100.0 * tot_match / tot_fields) + EMDASH +
  " fields it explicitly wrote down as agreeing. **%d** (%.1f%%) is field-checks minus every claim "
  "line. The %d-field gap is almost entirely the spawner/anchor cross-check, which checked 585 "
  "fields (155 curated level-scaled values inverted through `levels.base_for` across both decks, "
  "plus spawner wiring) but emitted only its 19 explicit match lines. The no-line rate is the "
  "honest denominator; the %.0f%% figure understates agreement."
  % (tot_fields - raw_lines, 100.0 * (tot_fields - raw_lines) / tot_fields,
     (tot_fields - raw_lines) - tot_match, 100.0 * tot_match / tot_fields))
w("")
w("### 4.3 Verdicts, canonical ledger")
w("")
w("| Verdict | Rows | Share |")
w("| --- | ---: | ---: |")
for v, cnt in [("escalate", len(esc)), ("update", len(updates)), ("match", len(matches)), ("pin", len(pins))]:
    w("| `%s` | %d | %.1f%% |" % (v, cnt, 100.0 * cnt / len(rows)))
w("| **total** | **%d** | |" % len(rows))
w("")
w("Pre-dedupe the eleven files carried 113 `update`, 334 `escalate`, 75 `pin`, 73 `match` "
  "(595 lines). The merge dropped 39 duplicate rows and moved 3 into `escalate` by forced verdict "
  "on a disagreeing duplicate.")
w("")
w("### 4.4 Per sweep")
w("")
w("| Sweep | Keys | Fields | Matches reported | Updates | Pins | Escalations | No-line rate |")
w("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
for fam, a in AGENT.items():
    fl = a["updates"] + a["pins"] + a["esc"]
    w("| %s | %d | %d | %d | %d | %d | %d | %.1f%% |" % (
        FAM_LABEL[fam], a["keys"], a["fields"], a["matches"], a["updates"], a["pins"], a["esc"],
        100.0 * (a["fields"] - fl) / a["fields"]))
w("| **total** | **%d** | **%d** | **%d** | **%d** | **%d** | **%d** | **%.1f%%** |" % (
    tot_keys, tot_fields, tot_match,
    sum(a["updates"] for a in AGENT.values()), sum(a["pins"] for a in AGENT.values()),
    sum(a["esc"] for a in AGENT.values()),
    100.0 * (tot_fields - raw_lines) / tot_fields))
w("")
w("The Keys column sums to %d because the three cross-checks re-covered keys the family sweeps "
  "already owned; %d distinct card keys were swept in total. Read the no-line rate as breadth, not "
  "as health: the two low outliers are the targeted cross-checks, which only ever looked at fields "
  "already suspected of a specific defect. The ladder sweep's 22.6%% is the extreme case "
  % (tot_keys, len(distinct_keys)) + EMDASH + " all 41 of its lines are `pin`, meaning `levels.py` "
  "was right and the wiki was wrong on every one of them." )
w("")
w("### 4.5 Reconciliation — the one-line partition")
w("")
w("Reported as the merged headline: **%d** keys, **%d** field-checks partitioned into "
  "**%d** agreeing, **%d** `update`, **%d** `pin`, **%d** `escalate` "
  % (len(distinct_keys), tot_fields, tot_fields - flagged, len(updates), len(pins), len(esc)) +
  EMDASH + " canonical, i.e. after the 39 duplicate pairs were collapsed. The pre-dedupe partition "
  "of the same 3,321 field-checks is 2,799 / 113 / 75 / 334, which is what the eleven sweep "
  "summaries sum to.")
w("")
w("---")
w("")
w("*Generated from `research/sim_parity/ledger/stat_diffs.jsonl` by "
  "`research/sim_parity/scripts/r2_merge.py` and `r2_review_md.py`. Run summary appended to "
  "`research/sim_parity/conflicts.md` under `## R2 sweep 2026-08-26`.*")

out = os.path.join(LED, "R2_REVIEW.md")
open(out, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
print("wrote", out, len(L), "lines")
print("updates", len(updates), "esc", len(esc), "(dup", len(b_dup), "ver", len(b_ver),
      "split", len(b_split), "other", len(b_other), ") pins", len(pins), "match", len(matches))
print("fields", tot_fields, "flagged", flagged, "clean", tot_fields - flagged,
      "keys", len(distinct_keys), "clean_keys", clean_keys)
