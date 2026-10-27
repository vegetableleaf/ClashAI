"""row.py FILE NAME [KEYS..] -- one row's columns of a crforge table json"""
import json, sys
r = json.load(open(sys.argv[1]))["rows"][sys.argv[2]]["columns"]
ks = sys.argv[3:]
print({k: v for k, v in r.items() if (not ks and not k.endswith("ExportName") and "Effect" not in k) or k in ks})
