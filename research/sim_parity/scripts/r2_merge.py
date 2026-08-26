# -*- coding: utf-8 -*-
"""Merge the R2 claim files into one canonical stat_diffs.jsonl and emit the owner review table."""
import json, os, re, collections

LED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ledger")
LED = os.path.abspath(LED)

FILES = [
    ("troops_a",   "r2_troops_a.jsonl"),
    ("troops_b",   "r2_troops_b.jsonl"),
    ("troops_c",   "r2_troops_c.jsonl"),
    ("buildings",  "r2_buildings.jsonl"),
    ("spells",     "r2_spells.jsonl"),
    ("evos_a",     "r2_evos_a.jsonl"),
    ("evos_b",     "r2_evos_b.jsonl"),
    ("champions",  "r2_champions.jsonl"),
    ("xc_crown",   "r2_crosscheck_crown.jsonl"),
    ("xc_spawn_anchor", "r2_crosscheck_spawn_anchor.jsonl"),
    ("xc_ladder",  "r2_ladder_check.jsonl"),
]

from r2_overrides import PROP_OVERRIDE

def norm(v):
    """Normalise a claim value for equality comparison."""
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        f = float(v)
        return round(f, 6)
    if isinstance(v, str):
        s = v.strip()
        m = re.match(r'^[+]?(-?\d+(?:\.\d+)?)\s*(?:sec|secs|seconds|s|tiles|tile|%)?$', s, re.I)
        if m:
            try:
                return round(float(m.group(1)), 6)
            except ValueError:
                pass
        return s.lower()
    return json.dumps(v, sort_keys=True)

def fmt(v):
    if v is None:
        return "null"
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    if isinstance(v, (dict, list)):
        s = json.dumps(v, separators=(",", ":"))
        return s if len(s) <= 90 else s[:87] + "..."
    return str(v)

NULLISH = ("no column", "no entry", "none", "not published", "n/a", "absent",
           "no such column", "no history", "no vardefine")

def as_num(v):
    """Return a float if v is a bare number (optionally with a unit), else None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.match(r'^[+~]?\s*(-?\d+(?:\.\d+)?)\s*(?:sec|secs|second|seconds|s|tiles?|t|%|x)?$',
                     v.strip(), re.I)
        if m:
            return float(m.group(1))
    return None

def dig_num(v):
    """Pull a number out of a short descriptive string like 'dmg_11 = 92' or 'Duration 4 sec'."""
    if not isinstance(v, str):
        return None
    s = v.strip()
    if len(s) > 70 or s.lower() in NULLISH:
        return None
    tail = re.split(r'[=:]', s)[-1] if re.search(r'[=:]', s) else s
    nums = re.findall(r'-?\d+(?:\.\d+)?', tail)
    if len(nums) == 1:
        return float(nums[0])
    return None

def is_nullish(v):
    return isinstance(v, str) and v.strip().lower() in NULLISH

def proposed_of(r):
    """Best-supported non-current value among the three paths (numbers preferred)."""
    cur = norm(r.get("current_db"))
    order = {"p2_table": 0, "p3_history": 1, "p1_vardefine": 2}
    cand = []
    for pk in ("p2_table", "p3_history", "p1_vardefine"):
        v = r.get(pk)
        if v is None or is_nullish(v):
            continue
        n = as_num(v)
        tier = 0 if n is not None else (1 if dig_num(v) is not None else 2)
        val = n if n is not None else (dig_num(v) if tier == 1 else v)
        cand.append((pk, val, norm(val), tier))
    if not cand:
        return None, 0
    counts = collections.Counter(n for _, _, n, _ in cand)
    ranked = sorted(cand, key=lambda t: (t[3], 0 if t[2] != cur else 1, -counts[t[2]], order[t[0]]))
    best = ranked[0]
    return best[1], counts[best[2]]

def one_liner(notes, limit=220):
    if not notes:
        return ""
    s = " ".join(str(notes).split())
    # first sentence, but keep it meaty
    parts = re.split(r'(?<=[.;])\s+', s)
    out = parts[0]
    i = 1
    while len(out) < 110 and i < len(parts):
        out = out + " " + parts[i]
        i += 1
    if len(out) > limit:
        out = out[:limit - 3].rstrip() + "..."
    return out.replace("|", chr(92)+"|")

# ---------------- load ----------------
rows = []
for fam, fn in FILES:
    path = os.path.join(LED, fn)
    with open(path, encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            r["_family"] = fam
            r["_file"] = fn
            r["_line"] = ln
            r["_nsrc"] = len(r.get("sources") or [])
            rows.append(r)

# ---------------- dedupe ----------------
groups = collections.OrderedDict()
for r in rows:
    groups.setdefault((r["key"], r["field"]), []).append(r)

canonical = []
dup_pairs = 0
dup_disagree = 0
escalated_by_dup = []
for (k, f), grp in groups.items():
    if len(grp) == 1:
        w = dict(grp[0])
        w["dup_verdicts"] = []
        canonical.append(w)
        continue
    dup_pairs += 1
    # keep the claim with more sources; tie -> earlier file in the canonical family order
    grp_sorted = sorted(grp, key=lambda r: (-r["_nsrc"], FILES.index((r["_family"], r["_file"]))))
    win = dict(grp_sorted[0])
    losers = grp_sorted[1:]

    def numof(r):
        p, _ = proposed_of(r)
        n = norm(p)
        return n if isinstance(n, float) else None

    wv, wn, wc = win.get("verdict"), numof(win), norm(win.get("current_db"))
    kinds = set()
    for l in losers:
        if l.get("verdict") != wv:
            kinds.add("verdict")
        ln = numof(l)
        if wn is not None and ln is not None and wn != ln:
            kinds.add("value")
        if norm(l.get("current_db")) != wc:
            kinds.add("current_db")
    disagree = bool(kinds)
    win["dup_verdicts"] = [{
        "from_file": l["_file"],
        "from_family": l["_family"],
        "line": l["_line"],
        "verdict": l.get("verdict"),
        "vote": l.get("vote"),
        "current_db": l.get("current_db"),
        "p1_vardefine": l.get("p1_vardefine"),
        "p2_table": l.get("p2_table"),
        "p3_history": l.get("p3_history"),
        "proposed": proposed_of(l)[0],
        "sources_count": l["_nsrc"],
        "cross_checks": l.get("cross_checks"),
        "notes": l.get("notes"),
    } for l in losers]
    win["dup_disagreement"] = bool(disagree)
    win["dup_disagreement_kind"] = sorted(kinds)
    if disagree:
        dup_disagree += 1
        if win.get("verdict") != "escalate":
            win["verdict_original"] = win.get("verdict")
            win["verdict"] = "escalate"
            escalated_by_dup.append((k, f, win["verdict_original"],
                                     [l.get("verdict") for l in losers], sorted(kinds)))
    canonical.append(win)

# ---------------- write canonical ledger ----------------
out_path = os.path.join(LED, "stat_diffs.jsonl")
with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
    for r in canonical:
        o = collections.OrderedDict()
        o["key"] = r["key"]
        o["field"] = r["field"]
        o["family"] = r["_family"]
        o["current_db"] = r.get("current_db")
        _ov = PROP_OVERRIDE.get((r["key"], r["field"]))
        o["proposed"] = (_ov if _ov is not None else proposed_of(r)[0]) if r.get("verdict") == "update" else None
        o["p1_vardefine"] = r.get("p1_vardefine")
        o["p2_table"] = r.get("p2_table")
        o["p3_history"] = r.get("p3_history")
        o["vote"] = r.get("vote")
        o["verdict"] = r["verdict"]
        if "verdict_original" in r:
            o["verdict_original"] = r["verdict_original"]
        o["cross_checks"] = r.get("cross_checks")
        o["sources"] = r.get("sources")
        o["notes"] = r.get("notes")
        o["dup_verdicts"] = r.get("dup_verdicts", [])
        if r.get("dup_verdicts"):
            o["dup_disagreement"] = bool(r.get("dup_disagreement"))
            o["dup_disagreement_kind"] = r.get("dup_disagreement_kind", [])
        o["provenance"] = {"file": r["_file"], "line": r["_line"], "sources_count": r["_nsrc"]}
        # ladder-only extra fields preserved
        for extra in ("card", "rarity", "floor_level", "effective_floor_for_this_stat", "cap_level",
                      "wiki_ladder", "wiki_formula", "wiki_formula_reproduces_rendered_table",
                      "levels_py_as_implemented", "floor_indexed_model",
                      "pre2025_rank_indexed_delta", "era", "wiki_v11_reachability", "game_dump"):
            if extra in r:
                o[extra] = r[extra]
        fh.write(json.dumps(o, ensure_ascii=False) + "\n")

# ---------------- stats ----------------
verd = collections.Counter(r["verdict"] for r in canonical)
print("rows_in", len(rows), "rows_out", len(canonical), "dup_pairs", dup_pairs, "dup_disagree", dup_disagree)
print("verdicts", dict(verd))
print("escalated_by_dup", len(escalated_by_dup))
for e in escalated_by_dup:
    print("  ", e)
json.dump({"rows_in": len(rows), "rows_out": len(canonical), "dup_pairs": dup_pairs,
           "dup_disagree": dup_disagree, "verdicts": dict(verd),
           "escalated_by_dup": escalated_by_dup},
          open(os.path.join(LED, "stat_diffs_merge_meta.json"), "w", encoding="utf-8"), indent=1)
