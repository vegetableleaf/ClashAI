"""F1c-2: cue_ab.py results -> a Markdown agreement table (fields: per field, all pairs / in-sync pairs / in-sync
non-tower bodies, before (HEAD facade) and after; e1: per cue column and whole rows).

usage: python table.py fields_head.json fields_new.json e1_head.json e1_new.json > table.md
"""
import json
import sys


def load(p):
    return json.load(open(p, encoding="utf-8"))["result"]


def rate(r):
    return "-" if r["rate"] is None else f"{100 * r['rate']:.2f}% ({r['n']})"


def main():
    fh, fn, eh, en = (load(p) for p in sys.argv[1:5])
    head = {r["field"]: r for r in fh["fields"]}
    print(f"## Fields ({fn['compared']} scenarios compared of {fn['scenarios']}; counts {json.dumps(fn['counts'])})\n")
    print("| field | HEAD all | new all | new in-sync | new in-sync bodies | top mismatch (new) |")
    print("|---|---|---|---|---|---|")
    for r in fn["fields"]:
        h = head.get(r["field"])
        top = "; ".join(f"{m} x{c}" for m, c in r["top_mismatch"][:2]).replace("|", "/")
        print(f"| {r['field']} | {rate(h['all']) if h else '-'} | {rate(r['all'])} | {rate(r['sync'])} | "
              f"{rate(r['body_sync'])} | {top[:160]} |")
    print(f"\n## e1 cue tensors ({en['matches']} matched matches, {en['paired_tokens']} paired unit tokens)\n")
    print(f"Whole cue row equal: HEAD {rate(eh['row_agreement'])}, new {rate(en['row_agreement'])}\n")
    print("| cue column | HEAD | new | top mismatch (new) |")
    print("|---|---|---|---|")
    hc = {c["col"]: c for c in eh["columns"]}
    for c in en["columns"]:
        top = "; ".join(f"{m} x{k}" for m, k in c["top_mismatch"][:2]).replace("|", "/")
        print(f"| {c['col']} | {rate(hc[c['col']]) if c['col'] in hc else '-'} | {rate(c)} | {top[:140]} |")


if __name__ == "__main__":
    main()
