"""SME-F1FIX: torn_hidden frames and how many of them had their point checked (result.json torn_prov), per results file.
python3 hidden_pts.py RESULTS.jsonl ..."""
import json, sys
for p in sys.argv[1:]:
    n = chk = 0
    for r in map(json.loads, open(p)):
        for t, pv in (r.get('torn_prov') or {}).items():
            if isinstance(pv, dict) and pv.get('rule') == 'hidden':
                n += 1; chk += pv.get('point_checked', 0) > 0
    print(p, 'torn_hidden frames', n, 'point checked', chk)
