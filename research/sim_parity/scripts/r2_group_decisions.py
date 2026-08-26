# -*- coding: utf-8 -*-
"""Group the 316 R2 escalations by CAUSE so the owner makes ~a dozen decisions, not 316.

Clusters on the agents' own cause labels plus structural signals. Prints coverage so an
unclassified tail can never hide inside a 'misc' bucket.
"""
import json, collections, io, re

ROWS = [json.loads(l) for l in io.open("ledger/stat_diffs.jsonl", encoding="utf-8", errors="replace") if l.strip()]
ESC = [r for r in ROWS if r.get("verdict") == "escalate"]


def note(r):
    return (r.get("notes") or "").lower()


def paths_all_null(r):
    return all(r.get(k) in (None, "", []) for k in ("p1_vardefine", "p2_table", "p3_history"))


# Order matters: first match wins. Most specific first.
def classify(r):
    n = note(r)
    f = (r.get("field") or "").lower()
    if r.get("dup_disagreement"):
        return "DUP"
    if ("contamination" in n or "spawned unit" in n or "currently holds the" in n
            or ("parent" in n and "stat" in n)):
        return "PARENT"
    if "chain" in f or ("chain" in n and "tile" in n):
        return "GLOBAL"
    if r.get("family") in ("xc_ladder",) or "floor_indexed_model" in r or r.get("levels_py_as_implemented") is not None:
        return "LADDER"
    if "crown" in n and ("stale" in n or "1/6/2026" in n or "sweep" in n):
        return "CROWN"
    if "schema" in n or ("engine" in n and ("cannot" in n or "does not" in n or "reads" in n)):
        return "ENGINE"
    if r.get("current_db") in (None, ""):
        return "KBGAP"
    if paths_all_null(r):
        return "UNPUB"
    if "contradict" in n and ("itself" in n or "three" in n or "page" in n):
        return "PAGECONF"
    if "stale" in n or "superseded" in n or "balance update" in n or re.search(r"\d+/\d+/20\d\d", n):
        return "LAG"
    if "round()" in n or "floor(" in n:
        return "ROUNDING"
    if "naming collision" in n or "snapshot hygiene" in n:
        return "NAMING"
    if "verified" in n:
        return "VERIFIED"
    if r.get("vote") == "split":
        return "SPLIT"
    return "OTHER"


buckets = collections.defaultdict(list)
for r in ESC:
    buckets[classify(r)].append(r)

print("ESCALATIONS %d" % len(ESC))
for k, v in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
    print("  %-10s %3d" % (k, len(v)))
print("\nUNCLASSIFIED (OTHER) sample:")
for r in buckets["OTHER"][:10]:
    print("   %-20s %-24s vote=%-6s %s" % (r.get("key"), r.get("field"), r.get("vote"), note(r)[:80]))
json.dump({k: [{"key": r.get("key"), "field": r.get("field"), "current": r.get("current_db"),
                "p1": r.get("p1_vardefine"), "p2": r.get("p2_table"), "p3": r.get("p3_history"),
                "vote": r.get("vote"), "notes": r.get("notes"), "family": r.get("family"),
                "sources": r.get("sources", [])[:2]} for r in v]
           for k, v in buckets.items()},
          io.open("ledger/r2_buckets.json", "w", encoding="utf-8"), indent=1)
