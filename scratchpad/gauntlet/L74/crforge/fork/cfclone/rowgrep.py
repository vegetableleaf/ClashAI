# usage: rowgrep.py TABLESDIR FILE SUBSTR... -- print every row (name: columns) whose name contains a substring;
# FILE '*' = every table file
import json, os, sys
files = sorted(f for f in os.listdir(sys.argv[1]) if f.endswith(".json")) if sys.argv[2] == "*" else [sys.argv[2]]
for f in files:
    rows = json.load(open(os.path.join(sys.argv[1], f))).get("rows")
    if not isinstance(rows, dict):
        continue
    for n, r in rows.items():
        if any(s in n for s in sys.argv[3:]):
            print(f, n, json.dumps(r.get("columns", r), sort_keys=True))
