"""rows.py TABLEDIR PREFIX -- every table row whose key starts with PREFIX (actions etc.)"""
import json, glob, sys, os
for f in sorted(glob.glob(os.path.join(sys.argv[1], '*.json'))):
    try: d = json.load(open(f))
    except Exception: continue
    if not isinstance(d, dict): continue
    for k, v in d.items():
        if isinstance(k, str) and k.startswith(sys.argv[2]):
            print(os.path.basename(f), k, json.dumps(v)[:int(os.environ.get('W', '900'))])
